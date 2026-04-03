"""Agent 状态定义"""
from typing import Optional
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Agent 工作流状态（继承 MessagesState）"""
    session_id: str
    user_id: str
    city_name: Optional[str] = None
    day_count: Optional[int] = None
    # 定制化需求：用于记录用户偏好（除城市/天数外）
    # 例如：家庭/情侣/单人出游、不吃辣/爱吃辣、有老人/有小孩、人文景观/自然景观等
    customization_requirements: Optional[str] = None
    weather_data: Optional[str] = None
    poi_data: Optional[str] = None
    route_plan: Optional[str] = None
    structured_output: Optional[dict] = None
    error: Optional[str] = None
    # 意图识别相关字段
    intent_type: Optional[str] = None  # "tourism" | "non_tourism" | "tourism_need_guidance"
    in_guidance_mode: Optional[bool] = False  # 是否处于对话引导模式
    # 引导原因，用于生成上下文感知的引导回复
    # 可选值：missing_city / ambiguous_city / multi_city / foreign_city
    #         missing_day / invalid_day_zero / invalid_day_overflow / ambiguous_day / missing_both
    guidance_reason: Optional[str] = None
    # messages 字段由 MessagesState 自动管理
