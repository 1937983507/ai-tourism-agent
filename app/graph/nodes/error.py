"""错误处理节点"""
from typing import Dict, Any
from loguru import logger
from app.graph.state import AgentState


def handle_error_node(state: AgentState) -> dict:
    """错误处理节点"""
    error_msg = state.get('error', '未知错误')
    logger.error(f"处理错误: {error_msg}")
    
    # 只返回需要更新的字段
    # 可以在这里添加错误恢复逻辑
    return {}  # 错误信息已经在 state 中，不需要再次返回

