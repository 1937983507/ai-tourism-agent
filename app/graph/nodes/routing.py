"""路由决策函数"""
import logging
from app.graph.state import AgentState

logger = logging.getLogger(__name__)


def check_intent_result(state: AgentState) -> str:
    """
    检查意图识别结果，决定下一步
    
    Returns:
        "tourism": 旅游意图且已提取到完整信息，继续业务逻辑
        "tourism_need_guidance": 旅游意图但信息不完整，需要引导
        "non_tourism": 非旅游意图，直接回复
    """
    intent_type = state.get("intent_type")
    city_name = state.get("city_name")
    day_count = state.get("day_count")
    
    logger.info(f"检查意图识别结果: intent_type={intent_type}, city={city_name}, days={day_count}")
    
    if intent_type == "non_tourism":
        return "non_tourism"
    
    if intent_type == "tourism":
        # 检查是否提取到完整信息
        if city_name and day_count:
            return "tourism"
        else:
            # 信息不完整，需要引导
            return "tourism_need_guidance"
    
    # 默认需要引导
    return "tourism_need_guidance"


def check_guidance_complete(state: AgentState) -> str:
    """
    检查对话引导是否完成（是否已获取到完整信息）
    
    Returns:
        "complete": 已获取完整信息，继续业务逻辑
        "continue_guidance": 仍需继续引导
    """
    city_name = state.get("city_name")
    day_count = state.get("day_count")
    
    logger.info(f"检查引导完成状态: city={city_name}, days={day_count}")
    
    if city_name and day_count:
        # 已获取完整信息
        return "complete"
    else:
        # 仍需继续引导
        return "continue_guidance"


