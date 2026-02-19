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
        logger.info(f"开始流式对话，session_id: {session_id}, user_id: {user_id}")
        
        # 构建配置（thread_id 对应 session_id）
        config = {
            "configurable": {
                "thread_id": session_id
            }
        }
        
        # 构建初始状态
        initial_state: Dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "messages": [
                HumanMessage(content=message)
            ]
        }
        
        try:
            last_message_count = 0
            accumulated_content = ""
            
            # 流式调用图
            async for event in self.graph.astream(initial_state, config=config):
                # 处理事件流
                # event 是一个字典，键是节点名，值可能是状态字典或 None
                if not isinstance(event, dict):
                    continue
                    
                for node_name, node_state in event.items():
                    logger.debug(f"处理节点事件: {node_name}, node_state类型: {type(node_state)}")
                    
                    # 检查 node_state 是否为 None
                    if node_state is None:
                        logger.debug(f"节点 {node_name} 的状态为 None，跳过")
                        continue
                    
                    # 确保 node_state 是字典类型
                    if not isinstance(node_state, dict):
                        logger.warning(f"节点 {node_name} 的状态不是字典类型: {type(node_state)}")
                        continue
                    
                    # 检查是否有错误
                    if node_state.get("error"):
                        error_msg = node_state.get("error", "处理过程中出现错误")
                        yield f"\n错误: {error_msg}"
                        return
                    
                    # 获取消息列表
                    messages = node_state.get("messages", [])
                    if messages and len(messages) > last_message_count:
                        # 获取新增的消息
                        new_messages = messages[last_message_count:]
                        last_message_count = len(messages)
                        
                        # 处理新增消息
                        for msg in new_messages:
                            # 只处理 AI 消息
                            from langchain_core.messages import AIMessage
                            if isinstance(msg, AIMessage) and hasattr(msg, 'content'):
                                content = msg.content
                                if isinstance(content, str) and content:
                                    # 计算新增内容（增量输出）
                                    if len(content) > len(accumulated_content):
                                        new_content = content[len(accumulated_content):]
                                        accumulated_content = content
                                        # 流式返回新增内容
                                        for char in new_content:
                                            yield char
                    
                    # 如果到达结束节点或格式化输出节点，确保输出完整内容
                    if node_name == "format_output" or node_name == "__end__":
                        # 确保所有内容都已输出
                        route_plan = node_state.get("route_plan")
                        if route_plan and len(route_plan) > len(accumulated_content):
                            remaining = route_plan[len(accumulated_content):]
                            for char in remaining:
                                yield char
                            accumulated_content = route_plan
                        if node_name == "__end__":
                            return
        except Exception as e:
            logger.error(f"流式对话异常: {e}", exc_info=True)
            yield f"\n错误: 服务暂时不可用，请稍后重试"
    
    async def chat(
        self,
        session_id: str,
        user_id: str,
        message: str
    ) -> Dict[str, Any]:
        """非流式对话（用于测试）"""
        logger.info(f"开始对话，session_id: {session_id}, user_id: {user_id}")
        
        config = {
            "configurable": {
                "thread_id": session_id
            }
        }
        
        initial_state: Dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "messages": [
                HumanMessage(content=message)
            ]
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

