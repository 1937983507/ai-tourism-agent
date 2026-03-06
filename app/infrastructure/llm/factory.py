"""LLM 工厂类 - 统一管理 LLM 实例创建"""
from typing import Optional, List
from loguru import logger
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from app.config import settings


class LLMFactory:
    """LLM 工厂类，负责创建和管理 LLM 实例"""
    
    @staticmethod
    def create_streaming_llm(
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatOpenAI:
        """
        创建流式 LLM 实例
        
        Args:
            temperature: 温度参数
            max_tokens: 最大输出 token 数，默认使用配置值
            **kwargs: 其他参数
            
        Returns:
            ChatOpenAI 实例
        """
        
        llm_params = {
            "api_key": settings.openai_api_key,
            "base_url": settings.openai_base_url,
            "model_name": settings.openai_model_name,
            "max_tokens": max_tokens or settings.openai_max_output_tokens,
            "temperature": temperature,
            "streaming": True,
        }
        
        # 合并其他参数
        llm_params.update(kwargs)
        
        return ChatOpenAI(**llm_params)
    
    @staticmethod
    def create_llm(
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: Optional[dict] = None,
        **kwargs
    ) -> ChatOpenAI:
        """
        创建普通 LLM 实例
        
        Args:
            temperature: 温度参数
            max_tokens: 最大输出 token 数
            response_format: 响应格式（如 JSON），需要通过 model_kwargs 传递
            **kwargs: 其他参数
            
        Returns:
            ChatOpenAI 实例
        """
        # 基础参数
        llm_params = {
            "api_key": settings.openai_api_key,
            "base_url": settings.openai_base_url,
            "model_name": settings.openai_model_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # 如果指定了 response_format，需要通过 model_kwargs 传递
        if response_format:
            # response_format 需要通过 model_kwargs 传递
            model_kwargs = kwargs.get("model_kwargs", {})
            model_kwargs["response_format"] = response_format
            llm_params["model_kwargs"] = model_kwargs
            # 移除 kwargs 中的 model_kwargs，避免重复
            kwargs = {k: v for k, v in kwargs.items() if k != "model_kwargs"}
        
        # 合并其他参数
        llm_params.update(kwargs)
        
        return ChatOpenAI(**llm_params)

