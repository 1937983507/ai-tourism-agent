"""配置管理模块"""
import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
except ImportError:
    # 兼容旧版本 pydantic
    from pydantic import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    
    # OpenAI 配置
    openai_api_key: str
    openai_base_url: str = "https://api.chatanywhere.org"
    openai_model_name: str = "gpt-4o-mini"
    openai_max_output_tokens: int = 4000
    
    # Checkpoint 配置
    # memory: 仅内存，重启后丢失；sqlite: 持久化到本地文件，重启后可恢复
    checkpoint_type: str = "sqlite"  # memory, sqlite 或 postgres
    sqlite_db_path: str = "./checkpoints.db"
    postgres_conn_string: Optional[str] = None
    
    # Java 服务配置
    java_service_url: str = "http://localhost:8290"
    java_service_internal_token: Optional[str] = None
    
    # 服务配置
    agent_port: int = 8291
    agent_host: str = "0.0.0.0"
    log_level: str = "INFO"
    
    # 日志配置
    log_dir: str = "./logs"  # 日志目录
    log_retention_days: int = 7  # 日志保留天数
    log_rotation: str = "00:00"  # 日志轮转时间（每天午夜轮转，确保一天一个文件）
    log_encoding: str = "utf-8"  # 日志文件编码
    
    # 天气 API 配置
    openweather_api_key: Optional[str] = None
    
    # LangSmith 配置
    langsmith_enabled: bool = True  # 是否启用 LangSmith 追踪
    langsmith_api_key: Optional[str] = None  # LangSmith API Key
    langsmith_project: Optional[str] = "ai-tourism-agent"  # 项目名称
    langsmith_endpoint: Optional[str] = None  # LangSmith API 端点（可选，默认使用官方端点）
    langsmith_workspace_id: Optional[str] = None  # Workspace ID（可选）
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例）"""
    return Settings()


# 全局配置实例
settings = get_settings()

