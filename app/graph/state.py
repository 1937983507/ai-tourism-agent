"""Agent 状态定义"""
from typing import TypedDict, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Agent 工作流状态（继承 MessagesState）"""
    session_id: str
    user_id: str
    city_name: Optional[str] = None
    day_count: Optional[int] = None
    weather_data: Optional[str] = None
    poi_data: Optional[str] = None
    route_plan: Optional[str] = None
    structured_output: Optional[dict] = None
    error: Optional[str] = None
    # 意图识别相关字段
    intent_type: Optional[str] = None  # "tourism" | "non_tourism" | "tourism_need_guidance"
    in_guidance_mode: Optional[bool] = False  # 是否处于对话引导模式
    # messages 字段由 MessagesState 自动管理

