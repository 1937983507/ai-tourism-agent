from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import dotenv_values


def _require(d: Dict[str, Any], key: str) -> str:
    v = d.get(key)
    if v is None or str(v).strip() == "":
        raise ValueError(f"Missing required config key: {key}")
    return str(v).strip()


def _normalize_gt_scope(v: Any) -> str:
    s = str(v or "full").strip().lower() or "full"
    if s not in {"full", "city"}:
        raise ValueError("RAG_EVAL_GT_CORPUS_SCOPE must be 'full' or 'city'")
    return s


def _normalize_gt_source(v: Any) -> str:
    s = str(v or "travel_plan").strip().lower() or "travel_plan"
    if s not in {"travel_plan", "ragas_testset"}:
        raise ValueError(
            "RAG_EVAL_GT_SOURCE must be 'travel_plan' (默认，多日行程形态) "
            "or 'ragas_testset' (RAGAS 合成 QA，非行程)"
        )
    return s


@dataclass(frozen=True)
class RagEvalConfig:
    # OpenAI for answer generation + RAGAS judge
    openai_api_key: str
    openai_base_url: str
    llm_model_name: str
    embedding_model_name: str
    answer_temperature: float = 0.2

    # Chroma retrieval
    chroma_dir: str = "./chroma_db"
    collection_name: str = "travel_docs"
    top_k: int = 5
    city_metadata_key: str = "source_city"

    # Files/outputs
    output_dir: str = "./test/rag_eval/outputs"
    run_name_prefix: str = "rag_eval"

    # RAGAS metrics model settings (optional)
    ragas_llm_model_name: Optional[str] = None
    # Step2：RAGAS 结构化输出默认 max_tokens=1024，长行程答案在 Faithfulness NLI 阶段易截断报错，需调大
    ragas_llm_max_tokens: int = 16384
    # 仅用于 Faithfulness：限制参与「拆句+NLI」的答案长度（字符）。0=不截断（需足够 ragas_llm_max_tokens）
    ragas_faithfulness_answer_max_chars: int = 12000
    # ContextRecall / ContextPrecisionWithReference 的 reference（即用 ground_truth_answer）过长时易超 token，0=不截断
    ragas_reference_max_chars: int = 12000

    # Generation token controls (optional, but helpful)
    max_tokens: int = 600
    # Step1: auto-generate ground_truth_answer
    auto_generate_ground_truth_answer: bool = True
    # travel_plan = 专用中文多日行程参考答案（推荐）；ragas_testset = RAGAS 合成 QA
    gt_source: str = "travel_plan"
    ragas_gt_testset_size: int = 1
    # 整库 GT：从 Chroma 拉取文档（非 top-k 检索片段）
    # full = 当前 collection 最多 N 条 chunk；city = 仅当前样例城市 metadata
    gt_corpus_scope: str = "full"
    gt_max_corpus_docs: int = 3000
    # 行程形态 GT：抽样 chunk 数与上下文总长度上限
    gt_plan_max_chunks: int = 32
    gt_plan_chars_per_chunk: int = 1000
    gt_plan_context_char_budget: int = 16000
    gt_plan_max_tokens: int = 2500

    @staticmethod
    def from_env_file(env_path: Path) -> "RagEvalConfig":
        raw = dotenv_values(str(env_path))
        if not raw:
            raise ValueError(f"Empty or missing env file: {env_path}")

        openai_api_key = _require(raw, "RAG_EVAL_OPENAI_API_KEY")
        openai_base_url = _require(raw, "RAG_EVAL_OPENAI_BASE_URL")
        llm_model_name = _require(raw, "RAG_EVAL_LLM_MODEL_NAME")
        embedding_model_name = _require(raw, "RAG_EVAL_EMBEDDING_MODEL_NAME")

        def _get_float(k: str, default: float) -> float:
            v = raw.get(k, None)
            if v is None or str(v).strip() == "":
                return default
            return float(v)

        def _get_int(k: str, default: int) -> int:
            v = raw.get(k, None)
            if v is None or str(v).strip() == "":
                return default
            return int(v)

        def _get_bool(k: str, default: bool) -> bool:
            v = raw.get(k, None)
            if v is None or str(v).strip() == "":
                return default
            return str(v).strip().lower() in {"1", "true", "yes", "on"}

        return RagEvalConfig(
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            llm_model_name=llm_model_name,
            embedding_model_name=embedding_model_name,
            answer_temperature=_get_float("RAG_EVAL_ANSWER_TEMPERATURE", 0.2),
            chroma_dir=str(raw.get("RAG_EVAL_CHROMA_DIR", "./chroma_db")).strip() or "./chroma_db",
            collection_name=str(raw.get("RAG_EVAL_COLLECTION_NAME", "travel_docs")).strip() or "travel_docs",
            top_k=_get_int("RAG_EVAL_TOP_K", 5),
            city_metadata_key=str(raw.get("RAG_EVAL_CITY_METADATA_KEY", "source_city")).strip()
            or "source_city",
            output_dir=str(raw.get("RAG_EVAL_OUTPUT_DIR", "./test/rag_eval/outputs")).strip()
            or "./test/rag_eval/outputs",
            run_name_prefix=str(raw.get("RAG_EVAL_RUN_NAME_PREFIX", "rag_eval")).strip() or "rag_eval",
            ragas_llm_model_name=str(raw.get("RAGAS_LLM_MODEL_NAME", "")).strip() or None,
            ragas_llm_max_tokens=_get_int("RAG_EVAL_RAGAS_LLM_MAX_TOKENS", 16384),
            ragas_faithfulness_answer_max_chars=_get_int(
                "RAG_EVAL_RAGAS_FAITHFULNESS_ANSWER_MAX_CHARS", 12000
            ),
            ragas_reference_max_chars=_get_int("RAG_EVAL_RAGAS_REFERENCE_MAX_CHARS", 12000),
            max_tokens=_get_int("RAG_EVAL_MAX_TOKENS", 600),
            auto_generate_ground_truth_answer=_get_bool(
                "RAG_EVAL_AUTO_GENERATE_GT_ANSWER", True
            ),
            gt_source=_normalize_gt_source(raw.get("RAG_EVAL_GT_SOURCE", "travel_plan")),
            ragas_gt_testset_size=_get_int("RAG_EVAL_GT_TESTSET_SIZE", 1),
            gt_corpus_scope=_normalize_gt_scope(raw.get("RAG_EVAL_GT_CORPUS_SCOPE", "full")),
            gt_max_corpus_docs=_get_int("RAG_EVAL_GT_MAX_CORPUS_DOCS", 3000),
            gt_plan_max_chunks=_get_int("RAG_EVAL_GT_PLAN_MAX_CHUNKS", 32),
            gt_plan_chars_per_chunk=_get_int("RAG_EVAL_GT_PLAN_CHARS_PER_CHUNK", 1000),
            gt_plan_context_char_budget=_get_int(
                "RAG_EVAL_GT_PLAN_CONTEXT_CHAR_BUDGET", 16000
            ),
            gt_plan_max_tokens=_get_int("RAG_EVAL_GT_PLAN_MAX_TOKENS", 2500),
        )

    def apply_to_app_env_for_rag_import(self) -> Dict[str, str]:
        """
        兼容主项目 `app.config` 的 env 命名。
        评测用 .env 的 key 是 RAG_EVAL_*，这里会映射为主项目期望的 env 名称，
        以便复用 `RagRetrievalService` 的 build_query / 检索实现。
        """
        mapped: Dict[str, str] = {
            # OpenAI
            "OPENAI_API_KEY": self.openai_api_key,
            "OPENAI_BASE_URL": self.openai_base_url,
            "OPENAI_MODEL_NAME": self.llm_model_name,
            "OPENAI_EMBEDDING_MODEL_NAME": self.embedding_model_name,
            "OPENAI_MAX_OUTPUT_TOKENS": "4000",
            # RAG settings
            "RAG_ENABLED": "true",
            "RAG_CHROMA_DIR": self.chroma_dir,
            "RAG_COLLECTION_NAME": self.collection_name,
            "RAG_TOP_K": str(self.top_k),
            "RAG_CITY_METADATA_KEY": self.city_metadata_key,
        }
        for k, v in mapped.items():
            os.environ[k] = v
        return mapped

    def config_snapshot(self) -> Dict[str, Any]:
        # 避免在结果文件中直接写入 key；base_url 可以保留。
        redacted_key = self.openai_api_key[:2] + "****" + self.openai_api_key[-4:]
        return {
            "openai_base_url": self.openai_base_url,
            "openai_api_key_redacted": redacted_key,
            "llm_model_name": self.llm_model_name,
            "embedding_model_name": self.embedding_model_name,
            "answer_temperature": self.answer_temperature,
            "chroma_dir": self.chroma_dir,
            "collection_name": self.collection_name,
            "top_k": self.top_k,
            "city_metadata_key": self.city_metadata_key,
            "ragas_llm_model_name": self.ragas_llm_model_name,
            "ragas_llm_max_tokens": self.ragas_llm_max_tokens,
            "ragas_faithfulness_answer_max_chars": self.ragas_faithfulness_answer_max_chars,
            "ragas_reference_max_chars": self.ragas_reference_max_chars,
            "max_tokens": self.max_tokens,
            "auto_generate_ground_truth_answer": self.auto_generate_ground_truth_answer,
            "gt_source": self.gt_source,
            "ragas_gt_testset_size": self.ragas_gt_testset_size,
            "gt_corpus_scope": self.gt_corpus_scope,
            "gt_max_corpus_docs": self.gt_max_corpus_docs,
            "gt_plan_max_chunks": self.gt_plan_max_chunks,
            "gt_plan_chars_per_chunk": self.gt_plan_chars_per_chunk,
            "gt_plan_context_char_budget": self.gt_plan_context_char_budget,
            "gt_plan_max_tokens": self.gt_plan_max_tokens,
            "output_dir": self.output_dir,
            "run_name_prefix": self.run_name_prefix,
        }

