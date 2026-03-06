"""LangSmith 配置和初始化模块"""
from typing import Optional, List
from loguru import logger
from langsmith import Client
from langchain_core.tracers import LangChainTracer
from langchain_core.callbacks import BaseCallbackHandler
from app.config import settings


def setup_langsmith_environment():
    """
    通过环境变量方式设置 LangSmith
    这种方式可以让 LangChain 自动识别并启用 LangSmith
    """
    if not settings.langsmith_enabled or not settings.langsmith_api_key:
        return
    
    import os
    
    # 设置环境变量（LangChain 会自动识别）
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    
    if settings.langsmith_project:
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    
    if settings.langsmith_endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
    
    logger.info("已通过环境变量方式配置 LangSmith")

