"""API 路由定义"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from loguru import logger
from app.api.models import ChatRequest, HealthResponse, ToolInfo
from app.application.agent_service import get_agent_service
from app.domain.tools.manager import get_tools
from app.config import settings

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查接口"""
    tools = get_tools()
    tools_dict = {tool.name: "available" for tool in tools}
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        checkpoint_backend=settings.checkpoint_type,
        tools=tools_dict
    )


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools():
    """获取工具列表"""
    tools = get_tools()
    return [
        ToolInfo(
            name=tool.name,
            description=tool.description,
            available=True
        )
        for tool in tools
    ]


@router.post("/chat-stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口（SSE）"""
    logger.info(f"[CHAT-STREAM] 收到流式对话请求，session_id: {request.session_id}, user_id: {request.user_id}, message: {request.message[:100]}")
    
    agent_service = get_agent_service()
    model_name = settings.openai_model_name
    
    async def event_generator():
        """SSE 事件生成器（兼容 Java 服务格式）"""
        try:
            async for token in agent_service.chat_stream(
                session_id=request.session_id,
                user_id=request.user_id,
                message=request.message
            ):
                # 转义特殊字符
                escaped_token = token.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                
                # 格式化 SSE 事件（兼容 Java 服务格式）
                sse_data = f'{{"choices":[{{"index":0,"text":"{escaped_token}","finish_reason":"stop","model":"{model_name}"}}]}}'
                yield f"data: {sse_data}\n\n"
            
            # 发送结束事件
            end_data = '{"choices":[{"finish_reason":"stop"}]}'
            yield f"data: {end_data}\n\n"
        
        except Exception as e:
            logger.exception(f"[SSE] 流式对话异常: {e}")
            error_msg = f"抱歉，我暂时无法回复您的消息。错误: {str(e)[:100]}"
            error_data = f'{{"choices":[{{"index":0,"text":"{error_msg}","finish_reason":"stop","model":"{model_name}"}}]}}'
            yield f"data: {error_data}\n\n"
    
    return EventSourceResponse(event_generator())


@router.post("/chat")
async def chat(request: ChatRequest):
    """非流式对话接口（用于测试）"""
    logger.info(f"[CHAT] 收到对话请求，session_id: {request.session_id}, user_id: {request.user_id}, message: {request.message[:100]}")
    
    agent_service = get_agent_service()
    result = await agent_service.chat(
        session_id=request.session_id,
        user_id=request.user_id,
        message=request.message
    )
    
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    
    return {
        "response": result["response"],
        "session_id": request.session_id
    }

