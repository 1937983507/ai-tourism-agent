"""通用回复节点"""
import logging
from typing import Dict, Any
from app.graph.state import AgentState
from langchain_core.messages import HumanMessage
from app.domain.services.general_response_service import GeneralResponseService

logger = logging.getLogger(__name__)

# 创建服务实例
_general_response_service = GeneralResponseService()


def general_response_node(state: AgentState) -> dict:
    """通用回复节点：处理非旅游意图，直接调用 LLM 进行回复"""
    logger.info("执行通用回复节点")
    
    result = {}
    
    try:
        # 获取用户输入和对话历史
        user_input = ""
        conversation_history = []
        if state.get("messages"):
            for msg in state["messages"]:
                conversation_history.append(msg)
                if isinstance(msg, HumanMessage):
                    user_input = msg.content if hasattr(msg, 'content') else str(msg)
        
        # 调用通用回复服务
        response_result = _general_response_service.generate_response(
            user_input=user_input,
            conversation_history=conversation_history
        )
        
        # 添加 AI 回复消息
        if response_result.get("messages"):
            result["messages"] = response_result["messages"]
        
        logger.info("通用回复生成完成")
        
    except Exception as e:
        logger.error(f"通用回复节点异常: {e}", exc_info=True)
        result["error"] = f"通用回复失败: {str(e)}"
    
    return result


