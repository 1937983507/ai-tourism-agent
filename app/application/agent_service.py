"""Agent 服务封装"""
import logging
from typing import AsyncIterator, Dict, Any
from langchain_core.messages import HumanMessage
from app.graph.workflow import get_agent_graph

logger = logging.getLogger(__name__)


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
        
        try:
            from langchain_core.messages import AIMessage
            accumulated_content = ""
            last_message_count = 0
            in_plan_route = False
            plan_route_accumulated = ""

            async for event in self.graph.astream_events(
                initial_state, config=config, version="v2"
            ):
                event_type = event.get("event")
                event_name = event.get("name", "")
                # logger.info(f"event_type: {event_type}, event_name: {event_name}")

                # 标记进入 plan_route 节点，后续只捕获该节点的 LLM 流式输出
                if event_type == "on_chain_start" and event_name == "plan_route":
                    in_plan_route = True
                    plan_route_accumulated = ""

                # 节点结束：退出 plan_route 标记，或图结束时提前返回
                if event_type == "on_chain_end":
                    if event_name == "plan_route":
                        in_plan_route = False
                    elif event_name == "__end__":
                        return

                # 实时捕获 plan_route 节点内 LLM 的流式 token，逐块 yield 给前端
                if event_type == "on_chat_model_stream" and in_plan_route:
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        yield content
                        plan_route_accumulated += content
                        accumulated_content += content

                # 节点结束时处理输出：错误、plan_route 补全、其他节点的 AI 消息
                if event_type == "on_chain_end":
                    output = event.get("data", {}).get("output")
                    if output and isinstance(output, dict):
                        if output.get("error"):
                            yield f"\n错误: {output.get('error', '处理过程中出现错误')}"
                            return

                        # plan_route 流式可能不完整，用完整 route_plan 补全未输出的部分
                        if event_name == "plan_route":
                            route_plan = output.get("route_plan")
                            if route_plan and isinstance(route_plan, str):
                                accumulated_length = len(plan_route_accumulated)
                                if len(route_plan) > accumulated_length:
                                    for char in route_plan[accumulated_length:]:
                                        yield char
                                    plan_route_accumulated = route_plan
                                    accumulated_content = route_plan

                        # 非 plan_route 节点（如 conversation_guidance 等）的 AI 回复，增量 yield
                        messages = output.get("messages", [])
                        if messages and len(messages) > last_message_count:
                            new_messages = messages[last_message_count:]
                            last_message_count = len(messages)
                            if event_name != "plan_route":
                                for msg in new_messages:
                                    if isinstance(msg, AIMessage) and hasattr(msg, "content"):
                                        content = msg.content
                                        if isinstance(content, str) and content and content not in accumulated_content:
                                            if len(content) > len(accumulated_content):
                                                new_content = content[len(accumulated_content):]
                                                accumulated_content = content
                                                for char in new_content:
                                                    yield char

        except Exception as e:
            logger.error(f"流式对话异常: {e}", exc_info=True)
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
            logger.error(f"对话异常: {e}", exc_info=True)
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

