"""路由决策函数"""
from loguru import logger
from app.graph.state import AgentState


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
    in_guidance_mode = state.get("in_guidance_mode", False)
    
    logger.info(f"检查意图识别结果: intent_type={intent_type}, city={city_name}, days={day_count}, in_guidance_mode={in_guidance_mode}")
    
    # 如果处于引导模式，或者已经有城市信息，说明正在进行旅游规划对话
    # 即使意图识别为 non_tourism，也应该继续引导流程（可能是用户在回答引导问题）
    if in_guidance_mode or city_name:
        # 检查是否已获取完整信息
        if city_name and day_count:
            return "tourism"  # 信息完整，进入主流程
        else:
            return "tourism_need_guidance"  # 继续引导
    
    # 如果明确是非旅游意图且不在引导模式，走通用回复
    if intent_type == "non_tourism":
        return "non_tourism"
    
    # 如果意图识别为旅游意图，检查是否提取到完整信息
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


