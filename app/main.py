"""FastAPI 应用入口"""
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
from app.api.routes import router
from app.config import settings
from app.graph.workflow import init_agent_graph
from app.infrastructure.checkpoint.saver import aclose_checkpointer
from app.infrastructure.logging import setup_logging
from app.infrastructure.llm.langsmith_setup import setup_langsmith_environment

# 创建 FastAPI 应用
app = FastAPI(
    title="AI-Tourism Agent Service",
    description="基于 LangGraph 的智能旅游规划 Agent 服务",
    version="1.0.0"
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件，记录所有 HTTP 请求"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 记录请求信息
        logger.info(
            f"[REQUEST] {request.method} {request.url.path} | "
            f"Client: {request.client.host if request.client else 'unknown'} | "
            f"Query: {dict(request.query_params)}"
        )
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # 记录响应信息
            logger.info(
                f"[RESPONSE] {request.method} {request.url.path} | "
                f"Status: {response.status_code} | "
                f"Time: {process_time:.3f}s"
            )
            
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.exception(
                f"[ERROR] {request.method} {request.url.path} | "
                f"Exception: {str(e)} | "
                f"Time: {process_time:.3f}s"
            )
            raise


# 添加请求日志中间件（在 CORS 之前）
app.add_middleware(RequestLoggingMiddleware)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


@app.on_event("startup")
async def startup():
    """应用启动事件"""
    # 初始化日志系统（必须在最前面）
    setup_logging()
    
    logger.info("AI-Tourism Agent Service 启动中...")
    logger.info(f"Checkpoint 类型: {settings.checkpoint_type}")
    logger.info(f"OpenAI 模型: {settings.openai_model_name}")
    logger.info(f"OpenAI max_output_tokens: {settings.openai_max_output_tokens}")
    
    # 初始化 LangSmith（通过环境变量方式）
    setup_langsmith_environment()
    
    # 预初始化图与 checkpointer，避免首次请求时在运行中的 event loop 里做同步初始化导致报错
    await init_agent_graph()
    logger.info("服务启动完成")


@app.on_event("shutdown")
async def shutdown():
    """应用关闭事件"""
    logger.info("AI-Tourism Agent Service 关闭中...")
    await aclose_checkpointer()


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "AI-Tourism Agent Service",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.agent_host,
        port=settings.agent_port,
        reload=True
    )

