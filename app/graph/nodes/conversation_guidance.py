"""对话引导节点"""
from typing import Dict, Any
from loguru import logger
from app.graph.state import AgentState
from app.domain.services.conversation_guidance_service import ConversationGuidanceService

# 创建服务实例
_guidance_service = ConversationGuidanceService()


def conversation_guidance_node(state: AgentState) -> dict:
    """对话引导节点：通过多轮问答确认用户需求"""
    logger.info("执行对话引导节点")
    
    result = {}
    
    try:
        # 对话引导
        guidance_result = _guidance_service.guide_conversation(state)
        
        # 更新状态
        result["in_guidance_mode"] = True
        
        # 如果提取到新信息，更新状态
        if guidance_result.get("city_name"):
            result["city_name"] = guidance_result["city_name"]
        elif state.get("city_name"):
            result["city_name"] = state.get("city_name")
            
        if guidance_result.get("day_count"):
            result["day_count"] = guidance_result["day_count"]
        elif state.get("day_count"):
            result["day_count"] = state.get("day_count")
        
        # 添加 AI 回复消息
        if guidance_result.get("messages"):
            result["messages"] = guidance_result["messages"]
        
        logger.info(f"对话引导完成: city={result.get('city_name')}, days={result.get('day_count')}")
        
    except Exception as e:
        logger.error(f"对话引导节点异常: {e}", exc_info=True)
        result["error"] = f"对话引导失败: {str(e)}"
    
    return result


