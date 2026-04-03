"""并行触发节点（用于触发并行执行）"""
from typing import Dict, Any
from loguru import logger
from app.graph.state import AgentState


def parallel_trigger_node(state: AgentState) -> dict:
    """
    并行触发节点：不做任何操作，仅用于触发并行执行
    这个节点用于确保 fetch_weather、fetch_poi、rag_retrieve 能够并行执行
    """
    logger.info("执行并行触发节点")
    # 不更新任何状态，仅作为路由节点
    return {}


