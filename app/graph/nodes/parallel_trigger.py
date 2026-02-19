"""并行触发节点（用于触发并行执行）"""
import logging
from typing import Dict, Any
from app.graph.state import AgentState

logger = logging.getLogger(__name__)


def parallel_trigger_node(state: AgentState) -> dict:
    """
    并行触发节点：不做任何操作，仅用于触发并行执行
    这个节点用于确保 fetch_weather 和 fetch_poi 能够并行执行
    """
    logger.info("执行并行触发节点")
    # 不更新任何状态，仅作为路由节点
    return {}


