"""Agent 状态定义"""
from typing import Optional
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Agent 工作流状态（继承 MessagesState）"""
    session_id: str
    user_id: str
    # 城市
    city_name: Optional[str] = None
    # 天数
    day_count: Optional[int] = None
    # 定制化需求：用于记录用户偏好（除城市/天数外）
    # 例如：家庭/情侣/单人出游、不吃辣/爱吃辣、有老人/有小孩、人文景观/自然景观等
    customization_requirements: Optional[str] = None
    # 天气信息
    weather_data: Optional[str] = None
    # 景点信息
    poi_data: Optional[str] = None
    # RAG：按城市过滤检索到的游记/知识片段摘要，供路线规划使用
    rag_context: Optional[str] = None
    # 路线规划
    route_plan: Optional[str] = None
    # 结构化输出
    structured_output: Optional[dict] = None
    # 错误信息
    error: Optional[str] = None
    # 意图类型
    intent_type: Optional[str] = None  # "tourism" | "non_tourism" | "tourism_need_guidance"
    # 是否处于对话引导模式
    in_guidance_mode: Optional[bool] = False
    # 引导原因，用于生成上下文感知的引导回复
    # 可选值：missing_city / ambiguous_city / multi_city / foreign_city
    #         missing_day / invalid_day_zero / invalid_day_overflow / ambiguous_day / missing_both
    guidance_reason: Optional[str] = None
    # messages 字段由 MessagesState 自动管理
