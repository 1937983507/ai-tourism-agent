"""Agent 服务封装"""
from typing import AsyncIterator, Dict, Any
from langchain_core.messages import HumanMessage
from loguru import logger
from app.graph.workflow import get_agent_graph


class AgentService:
    """Agent 服务类"""
    
    def __init__(self):
        self.graph = get_agent_graph()
    
    async def chat_stream(
        self,
        session_id: str,
        user_id: str,
        message: str
    ) -> AsyncIterator[str]:
        """流式对话"""
        config = {"configurable": {"thread_id": session_id}}
        initial_state: Dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "messages": [HumanMessage(content=message)]
        }

        logger.info(f"调用 graph.astream_events，thread_id: {session_id}, 新消息: {message[:50]}...")

        # 需要捕获 AI 回复的节点名称集合（非流式，直接取节点输出的 messages）
        GUIDANCE_NODES = {"conversation_guidance", "general_response", "general_response"}
        # plan_route 节点走流式 token，单独处理
        in_plan_route = False
        plan_route_streamed = ""

        try:
            from langchain_core.messages import AIMessage

            async for event in self.graph.astream_events(
                initial_state, config=config, version="v2"
            ):
                event_type = event.get("event")
                event_name = event.get("name", "")

                # ---- plan_route: 流式捕获 LLM token ----
                if event_type == "on_chain_start" and event_name == "plan_route":
                    in_plan_route = True
                    plan_route_streamed = ""

                if event_type == "on_chat_model_stream" and in_plan_route:
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield chunk.content
                        plan_route_streamed += chunk.content

                if event_type == "on_chain_end" and event_name == "plan_route":
                    in_plan_route = False
                    # 用节点完整输出补全流式可能截断的部分
                    output = event.get("data", {}).get("output") or {}
                    route_plan = output.get("route_plan", "")
                    if isinstance(route_plan, str) and len(route_plan) > len(plan_route_streamed):
                        yield route_plan[len(plan_route_streamed):]

                # ---- 引导 / 通用回复节点：直接取节点 return 的新 AIMessage ----
                if event_type == "on_chain_end" and event_name in GUIDANCE_NODES:
                    output = event.get("data", {}).get("output") or {}
                    if output.get("error"):
                        yield f"\n错误: {output['error']}"
                        return
                    # output["messages"] 是节点 return dict 里的列表，只含本节点新增的消息
                    for msg in output.get("messages", []):
                        if isinstance(msg, AIMessage) and msg.content:
                            yield msg.content

                # ---- 图执行结束 ----
                if event_type == "on_chain_end" and event_name == "__end__":
                    return

        except Exception as e:
            logger.exception(f"流式对话异常: {e}")
            yield "\n错误: 服务暂时不可用，请稍后重试"
    

    async def chat(
        self,
        session_id: str,
        user_id: str,
        message: str
    ) -> Dict[str, Any]:
        """非流式对话（用于测试）"""
        config = {"configurable": {"thread_id": session_id}}
        initial_state: Dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "messages": [HumanMessage(content=message)]
        }
        
        try:
            result = await self.graph.ainvoke(initial_state, config=config)
            return {
                "response": result.get("messages", [])[-1].content if result.get("messages") else "",
                "error": result.get("error")
            }
        except Exception as e:
            logger.exception(f"对话异常: {e}")
            return {
                "response": "",
                "error": str(e)
            }


# 全局服务实例
_agent_service = None


def get_agent_service() -> AgentService:
    """获取 Agent 服务实例（单例）"""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service

