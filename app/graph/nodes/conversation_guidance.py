"""对话引导节点"""
import logging
from typing import Dict, Any
from app.graph.state import AgentState
from langchain_core.messages import HumanMessage
from app.domain.services.conversation_guidance_service import ConversationGuidanceService

logger = logging.getLogger(__name__)

# 创建服务实例
_guidance_service = ConversationGuidanceService()


def conversation_guidance_node(state: AgentState) -> dict:
    """对话引导节点：通过多轮问答确认用户需求"""
    logger.info("执行对话引导节点")
    
    result = {}
    
    try:
        # 获取当前状态
        current_city = state.get("city_name")
        current_day_count = state.get("day_count")
        
        # 获取用户输入和对话历史
        user_input = ""
        conversation_history = []
        if state.get("messages"):
            for msg in state["messages"]:
                conversation_history.append(msg)
                if isinstance(msg, HumanMessage):
                    user_input = msg.content if hasattr(msg, 'content') else str(msg)
        
        # 调用对话引导服务
        guidance_result = _guidance_service.guide_conversation(
            user_input=user_input,
            conversation_history=conversation_history,
            current_city=current_city,
            current_day_count=current_day_count
        )
        
        # 更新状态
        result["in_guidance_mode"] = True
        
        # 如果提取到新信息，更新状态
        if guidance_result.get("city_name"):
            result["city_name"] = guidance_result["city_name"]
        if guidance_result.get("day_count"):
            result["day_count"] = guidance_result["day_count"]
        
        # 添加 AI 回复消息
        if guidance_result.get("messages"):
            result["messages"] = guidance_result["messages"]
        
        logger.info(f"对话引导完成: city={result.get('city_name')}, days={result.get('day_count')}")
        
    except Exception as e:
        logger.error(f"对话引导节点异常: {e}", exc_info=True)
        result["error"] = f"对话引导失败: {str(e)}"
    
    return result


