"""RAG 检索：本地 Chroma + OpenAI 兼容 Embeddings。"""
from __future__ import annotations

import threading
from typing import Any, List, Optional, TYPE_CHECKING

from loguru import logger

from app.config import settings

if TYPE_CHECKING:
    from langchain_community.vectorstores import Chroma as LCChroma
    from langchain_core.documents import Document

_store_lock = threading.Lock()
_embeddings: Any = None
_vectorstore: Optional["LCChroma"] = None


def _build_embeddings():
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        openai_api_base=settings.openai_base_url,
        openai_api_key=settings.openai_api_key,
        model=settings.openai_embedding_model_name,
    )


def _get_vectorstore():
    """懒加载 Chroma（只读检索），避免每次请求重复连接。"""
    global _embeddings, _vectorstore

    if not settings.rag_chroma_dir or not str(settings.rag_chroma_dir).strip():
        return None

    with _store_lock:
        if _vectorstore is None:
            from pathlib import Path

            from langchain_community.vectorstores import Chroma as LCChroma

            persist = Path(settings.rag_chroma_dir).expanduser().resolve()
            if not persist.is_dir():
                logger.warning(f"RAG Chroma 目录不存在，跳过检索: {persist}")
                return None

            _embeddings = _build_embeddings()
            _vectorstore = LCChroma(
                collection_name=settings.rag_collection_name,
                embedding_function=_embeddings,
                persist_directory=str(persist),
            )
            logger.info(
                f"RAG Chroma 已连接: dir={persist}, collection={settings.rag_collection_name}"
            )
        return _vectorstore


def invalidate_rag_client_cache() -> None:
    """测试或配置热更新时可调用，释放全局缓存。"""
    global _embeddings, _vectorstore
    with _store_lock:
        _embeddings = None
        _vectorstore = None


class RagRetrievalService:
    """面向 Agent 节点的检索封装：按 metadata 城市过滤 + 相似度检索。"""

    def _build_customization_phrases(
        self, customization_requirements: Optional[str]
    ) -> List[str]:
        """
        将类似：
          companions=家庭;elderly=有老人;kids=有小孩;pace=慢节奏;diet=不吃辣
        解析为自然语言短语：
          家庭出游， 有老人， 有小孩， 行程慢节奏， 不吃辣
        """

        if not customization_requirements:
            return []

        text = str(customization_requirements).strip()
        if not text:
            return []

        # 允许传入自由文案（无 key=value），则直接当作一个短语。
        if "=" not in text:
            return [text]

        parts = [p.strip() for p in text.split(";") if p.strip()]
        out: List[str] = []

        mapping = {
            "companions": {
                "家庭": "家庭出游",
                "情侣": "情侣出行",
                "单人": "单人出游",
                "朋友": "朋友结伴",
                "团体": "团体出游",
            },
            "elderly": {
                "有老人": "有老人",
                "没有老人": "没有老人同行",
            },
            "kids": {
                "有小孩": "有小孩",
                "没有小孩": "没有小孩同行",
            },
            "pace": {
                "慢节奏": "行程慢节奏",
                "中等": "行程节奏中等",
                "高强度": "行程节奏高强度",
            },
            "diet": {
                "爱吃辣": "爱吃辣",
                "不吃辣": "不吃辣",
            },
            "accessibility": {
                "需要轻松": "需要轻松行程",
                "走路少": "希望少走路",
            },
            "budget": {
                "经济": "预算经济",
                "中等": "预算中等",
                "高端": "预算高端",
            },
        }

        for item in parts:
            if "=" not in item:
                cleaned = item.strip()
                if cleaned and cleaned not in out:
                    out.append(cleaned)
                continue

            key, raw_val = item.split("=", 1)
            key = key.strip()
            val = raw_val.strip()
            if not key or not val:
                continue

            if key in mapping and val in mapping[key]:
                phrase = mapping[key][val]
            elif key == "interests":
                interests = [x.strip() for x in val.split(",") if x.strip()]
                if interests:
                    phrase = "偏好" + "、".join(interests)
                else:
                    continue
            elif key in mapping and val not in mapping[key]:
                phrase = val
            else:
                phrase = val

            phrase = str(phrase).strip()
            if phrase and phrase not in out:
                out.append(phrase)

        return out

    def build_query(
        self,
        city_name: str,
        day_count: Optional[int],
        customization_requirements: Optional[str],
    ) -> str:
        city = (city_name or "").strip()
        if not city:
            return "旅游攻略"

        if day_count is not None:
            base = f"{city}{int(day_count)}天旅游攻略"
        else:
            base = f"{city}旅游攻略"

        phrases = self._build_customization_phrases(customization_requirements)
        if not phrases:
            return f"{base}。"

        # 使用中文句式组织：{base}，{p1}，{p2}。
        tail = "，".join(phrases)
        return f"{base}，{tail}。"

    def retrieve_docs_for_rag_eval(
        self,
        city_name: str,
        day_count: Optional[int] = None,
        customization_requirements: Optional[str] = None,
    ) -> List["Document"]:
        """
        返回命中的片段列表（不拼接成大段上下文）。
        失败/未启用：返回空列表。
        """
        if not settings.rag_enabled:
            return []

        city = (city_name or "").strip()
        if not city:
            return []

        vs = _get_vectorstore()
        if vs is None:
            return []

        logger.info(
            "RAG 检索开始",
            city=city,
            day_count=day_count,
            customization_requirements=customization_requirements,
        )

        query = self.build_query(city, day_count, customization_requirements)
        logger.info(f"RAG 检索查询语句：{query}")

        meta_key = settings.rag_city_metadata_key or "source_city"
        flt = {meta_key: city}

        try:
            docs = vs.similarity_search(
                query=query,
                k=max(1, int(settings.rag_top_k)),
                filter=flt,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"RAG 检索失败（已降级为空上下文）: {e}")
            return []

        if not docs:
            logger.info(f"RAG 检索无命中: city={city}, query={query[:80]}...")
            return []

        logger.info(f"RAG 检索完成: city={city}, hits={len(docs)}")
        return docs

    def docs_to_prompt_text(self, docs: List["Document"]) -> str:
        """
        主流程用：把命中的片段列表拼接成给规划 LLM 阅读的文本（带引用 metadata）。
        """
        if not docs:
            return ""

        lines: List[str] = []
        for i, doc in enumerate(docs, start=1):
            md = getattr(doc, "metadata", None) or {}
            title = str(md.get("title", "")).strip()
            time = str(md.get("time", "")).strip()
            content = getattr(doc, "page_content", None) or ""
            preview = content.replace("\n", " ").strip()
            if len(preview) > 700:
                preview = preview[:700] + "…"
            lines.append(f"[{i}] title={title} time={time} \n    {preview}")

        return "\n\n".join(lines)

    def retrieve_to_prompt_text(
        self,
        city_name: str,
        day_count: Optional[int] = None,
        customization_requirements: Optional[str] = None,
    ) -> str:
        """
        返回可直接给规划 LLM 阅读的纯文本（带引用 metadata）。
        失败或未启用时返回空字符串。
        """

        # RAG 检索文档片段
        docs = self.retrieve_docs_for_rag_eval(
            city_name=city_name,
            day_count=day_count,
            customization_requirements=customization_requirements,
        )
        # 拼接成给规划 LLM 阅读的文本（带引用 metadata）
        return self.docs_to_prompt_text(docs)
