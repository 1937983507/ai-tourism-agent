"""FastAPI 应用入口"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.config import settings
from app.graph.workflow import init_agent_graph
from app.infrastructure.checkpoint.saver import aclose_checkpointer

# 配置日志（包含文件名、函数名、行号）
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d:%(funcName)s] - %(message)s"
)

logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="AI-Tourism Agent Service",
    description="基于 LangGraph 的智能旅游规划 Agent 服务",
    version="1.0.0"
)

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
    logger.info("AI-Tourism Agent Service 启动中...")
    logger.info(f"Checkpoint 类型: {settings.checkpoint_type}")
    logger.info(f"OpenAI 模型: {settings.openai_model_name}")
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

