"""请求/响应模型"""
from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """对话请求模型"""
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    message: str = Field(..., description="用户消息")


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
    version: str = Field(default="1.0.0", description="版本号")
    checkpoint_backend: str = Field(..., description="Checkpoint 后端类型")
    tools: dict = Field(..., description="可用工具列表")


class ToolInfo(BaseModel):
    """工具信息模型"""
    name: str
    description: str
    available: bool = True







