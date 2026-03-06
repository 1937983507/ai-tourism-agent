"""日志配置设置模块"""
import os
import sys
from pathlib import Path
from loguru import logger
from app.config import settings


def setup_logging():
    """
    配置 loguru 日志系统
    
    功能：
    - 按天轮转日志文件（每天午夜）
    - 自动删除超过保留天数的日志
    - 同时输出到控制台和文件
    - 包含详细的日志格式（时间、级别、模块、行号、消息）
    """
    # 移除默认的控制台处理器
    logger.remove()
    
    # 确保日志目录存在
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 日志文件路径格式：logs/app-2024-01-01.log
    log_file = log_dir / "app-{time:YYYY-MM-DD}.log"
    
    # 日志格式
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # 控制台输出（带颜色）
    logger.add(
        sys.stderr,
        format=log_format,
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )
    
    # 文件输出（按天轮转，自动删除过期日志）
    logger.add(
        str(log_file),
        format=log_format,
        level=settings.log_level,
        rotation=settings.log_rotation,  # 每天午夜轮转
        retention=f"{settings.log_retention_days} days",  # 保留7天
        compression=None,  # 不压缩（可选：zip, tar.gz 等）
        encoding=settings.log_encoding,
        backtrace=True,
        diagnose=True,
        enqueue=True,  # 异步写入，提高性能
    )
    
    # 错误日志单独文件（ERROR 及以上级别）
    error_log_file = log_dir / "error-{time:YYYY-MM-DD}.log"
    logger.add(
        str(error_log_file),
        format=log_format,
        level="ERROR",
        rotation=settings.log_rotation,
        retention=f"{settings.log_retention_days} days",
        encoding=settings.log_encoding,
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )
    
    # logger.info(f"日志系统已初始化 | 日志目录: {log_dir.absolute()} | 保留天数: {settings.log_retention_days} 天")
    
    return logger

