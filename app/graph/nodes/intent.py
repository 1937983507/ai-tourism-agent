"""意图理解节点"""
import logging
from typing import Dict, Any
from app.graph.state import AgentState
from app.domain.services.intent_service import IntentService

logger = logging.getLogger(__name__)

# 创建服务实例
_intent_service = IntentService()


def intent_understanding_node(state: AgentState) -> dict:
    """意图理解节点：解析用户需求（城市、天数、偏好等）"""
    logger.info("执行意图理解节点")
    
    # 只返回需要更新的字段
    result = {}
    
    # 从最后一条用户消息中提取信息
    if state.get("messages"):
        last_message = state["messages"][-1]
        user_input = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # 调用意图理解服务
        intent_result = _intent_service.extract_intent(user_input)
        result.update(intent_result)
    
    return result

