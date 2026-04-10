"""RAG 检索节点：旅游主链路与天气、景点并行，按城市过滤向量检索。"""
from typing import Dict, Any

from loguru import logger

from app.graph.state import AgentState
from app.domain.services.rag_retrieval_service import RagRetrievalService

_service = RagRetrievalService()


def rag_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """
    从 Chroma 向量库检索与当前城市相关的文档片段，写入 state.rag_context。
    仅更新 rag_context，避免与并行节点（天气/POI）产生写冲突。
    """
    logger.info("执行 RAG 检索节点")
    city_name = state.get("city_name")
    day_count = state.get("day_count")
    customization = state.get("customization_requirements")

    ctx = _service.retrieve_to_prompt_text(
        city_name=city_name or "",
        day_count=day_count,
        customization_requirements=customization,
    )
    return {"rag_context": ctx}
