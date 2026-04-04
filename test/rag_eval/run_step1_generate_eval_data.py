from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from openai import OpenAI
from loguru import logger

from test.rag_eval.config import RagEvalConfig


# 给 LLM 的每个 context 做一定截断，避免 prompt 过长导致超限
CONTEXT_CHAR_LIMIT = 2500


def _read_prompt_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_eval_cases(path: Path) -> List[Dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("test cases file must be a JSON array")
    required_keys = {"id", "city_name", "day_count"}
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"test case #{idx} is not an object")
        missing = required_keys - set(row.keys())
        if missing:
            raise ValueError(f"test case #{idx} missing required keys: {sorted(missing)}")
        if "ground_truth_answer" in row and row["ground_truth_answer"] is not None:
            if not isinstance(row["ground_truth_answer"], str):
                raise ValueError(f"test case #{idx} ground_truth_answer must be string or null")
    return rows


def format_contexts_for_prompt(contexts: List[str]) -> str:
    # 让 LLM 能区分不同片段
    lines: List[str] = []
    for i, ctx in enumerate(contexts, start=1):
        # 再次截断（双保险）
        c = (ctx or "")[:CONTEXT_CHAR_LIMIT]
        c = c.strip()
        lines.append(f"[{i}] {c}")
    return "\n\n".join(lines)


def generate_answer_non_streaming(
    *,
    client: OpenAI,
    model: str,
    temperature: float,
    max_tokens: int,
    system_prompt_or_user_prompt: str,
) -> str:
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": system_prompt_or_user_prompt}],
    )
    content = resp.choices[0].message.content if resp.choices else None
    return content or ""


def _sample_corpus_chunks_for_travel_plan_gt(
    docs: List[Any],
    *,
    max_chunks: int,
    chars_per_chunk: int,
    total_char_budget: int,
) -> List[str]:
    """从整库/子库语料中均匀抽样若干 chunk，控制总字符量，便于行程类 GT 覆盖多段攻略。"""
    if not docs:
        return []
    n = max(1, min(max_chunks, len(docs)))
    if len(docs) <= n:
        chosen_indices = list(range(len(docs)))
    else:
        step = max(1, len(docs) // n)
        chosen_indices = list(range(0, len(docs), step))[:n]

    texts: List[str] = []
    used = 0
    overhead_per_chunk = 32
    for i in chosen_indices:
        t = (getattr(docs[i], "page_content", "") or "").strip()
        if not t:
            continue
        piece = t[: max(1, chars_per_chunk)]
        need = len(piece) + overhead_per_chunk
        if used + need > total_char_budget and texts:
            break
        texts.append(piece)
        used += need
    return texts


def _generate_gt_travel_plan_answer(
    *,
    client: OpenAI,
    model: str,
    prompt_template: str,
    city_name: str,
    day_count: Any,
    customization_requirements: Optional[str],
    question: str,
    corpus_docs: List[Any],
    config: RagEvalConfig,
) -> Optional[str]:
    """
    基于语料生成「多日行程形态」的中文参考答案，用于 RAG 评测；
    与 RAGAS TestsetGenerator 的合成 QA 不同，输出对齐真实规划结构。
    """
    chunks = _sample_corpus_chunks_for_travel_plan_gt(
        corpus_docs,
        max_chunks=config.gt_plan_max_chunks,
        chars_per_chunk=config.gt_plan_chars_per_chunk,
        total_char_budget=config.gt_plan_context_char_budget,
    )
    if not chunks:
        return None

    corpus_context = format_contexts_for_prompt(chunks)
    try:
        days = int(day_count)  # type: ignore[arg-type]
        day_label = f"{days}"
    except (TypeError, ValueError):
        day_label = str(day_count) if day_count is not None else "未指定"

    cust = (customization_requirements or "").strip() or "无"

    user_prompt = prompt_template.format(
        city_name=city_name or "未指定",
        day_count=day_label,
        customization_requirements=cust,
        question=question,
        corpus_context=corpus_context,
    )

    max_out = max(512, min(int(config.gt_plan_max_tokens), 8192))
    resp = client.chat.completions.create(
        model=model,
        temperature=0.15,
        max_tokens=max_out,
        messages=[{"role": "user", "content": user_prompt}],
    )
    content = resp.choices[0].message.content if resp.choices else None
    text = (content or "").strip()
    return text or None


def _generate_gt_answer_with_llm_fallback(
    *,
    client: OpenAI,
    model: str,
    question: str,
    docs: List[Any],
    max_tokens: int,
) -> Optional[str]:
    """
    当 TestsetGenerator 失败时的兜底方案：
    直接基于整库/子库 docs 与 question 生成参考答案，避免 ground_truth_answer 为空。
    """
    if not docs:
        return None

    sampled = docs[: min(12, len(docs))]
    contexts: List[str] = []
    for d in sampled:
        text = (getattr(d, "page_content", "") or "").strip()
        if text:
            contexts.append(text[:1200])
    if not contexts:
        return None

    context_block = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(contexts, start=1))
    prompt = (
        "你是一名旅游评测标注员。请根据给定问题和资料，生成一段可用于评测的参考答案。"
        "要求：仅基于资料，不要编造；若资料不足要明确说明。只输出参考答案正文。\n\n"
        f"问题：{question}\n\n资料：\n{context_block}\n\n参考答案："
    )

    resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        max_tokens=max(256, min(max_tokens, 900)),
        messages=[{"role": "user", "content": prompt}],
    )
    content = resp.choices[0].message.content if resp.choices else None
    text = (content or "").strip()
    return text or None


def _load_chroma_corpus_documents_for_gt(
    *,
    config: RagEvalConfig,
    city_name: str,
) -> tuple[List[Any], int]:
    """
    从 Chroma 拉取用于 TestsetGenerator 的整库（或按城市子集）文档，而非 top-k 检索结果。
    返回 (LangChain Document 列表, 实际加载条数)。
    """
    from langchain_core.documents import Document

    from app.domain.services.rag_retrieval_service import _get_vectorstore  # noqa: E402

    vs = _get_vectorstore()
    if vs is None:
        return [], 0

    coll = getattr(vs, "_collection", None)
    if coll is None:
        return [], 0

    where: Optional[Dict[str, str]] = None
    if config.gt_corpus_scope == "city":
        city = (city_name or "").strip()
        if not city:
            return [], 0
        where = {config.city_metadata_key: city}

    max_total = max(1, int(config.gt_max_corpus_docs))
    out: List[Document] = []

    # 单次拉取最多 max_total 条 chunk（整库或按城市过滤后的子集）
    result = coll.get(
        where=where,
        limit=max_total,
        include=["documents", "metadatas"],
    )
    ids = result.get("ids") or []
    docs_batch = result.get("documents") or []
    metas = result.get("metadatas") or []
    for i, _doc_id in enumerate(ids):
        text = docs_batch[i] if i < len(docs_batch) else ""
        md = metas[i] if i < len(metas) else {}
        out.append(Document(page_content=text or "", metadata=dict(md or {})))

    return out, len(out)


def _generate_gt_answer_with_testset_generator(
    *,
    docs: List[Any],
    config: RagEvalConfig,
) -> Optional[str]:
    """
    使用 RAGAS TestsetGenerator 自动生成 ground_truth_answer（取生成样本的 reference 字段）。
    docs 应为整库/子库语料（LangChain Document），非单次 similarity_search 的 top-k。
    若失败或无结果，返回 None（调用方自行降级）。
    """
    if not docs:
        return None

    from openai import AsyncOpenAI
    from ragas.embeddings.base import embedding_factory
    from ragas.llms import llm_factory
    from ragas.testset import TestsetGenerator
    from ragas.testset.transforms import default_transforms_for_prechunked

    ragas_model = config.ragas_llm_model_name or config.llm_model_name

    try:
        async_client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )
        ragas_llm = llm_factory(ragas_model, client=async_client)
        ragas_embeddings = embedding_factory(
            "openai",
            model=config.embedding_model_name,
            client=async_client,
        )
        generator = TestsetGenerator(llm=ragas_llm, embedding_model=ragas_embeddings)
        transforms = default_transforms_for_prechunked(
            llm=ragas_llm,
            embedding_model=ragas_embeddings,
        )
        # docs 本身就是预切分 chunk，使用 prechunked transforms，
        # 避免 default_transforms 中 HeadlineSplitter 对 `headlines` 属性的依赖报错。
        testset = generator.generate_with_chunks(
            chunks=docs,
            testset_size=max(1, int(config.ragas_gt_testset_size)),
            transforms=transforms,
            raise_exceptions=False,
        )
    except Exception as e:
        logger.warning(f"Auto GT generation failed in TestsetGenerator: {e}")
        return None

    try:
        rows = testset.to_list()
    except Exception as e:
        logger.warning(f"Auto GT conversion failed in testset.to_list(): {e}")
        return None

    if not rows:
        logger.warning("Auto GT generation returned empty testset rows")
        return None

    for row in rows:
        ref = (row.get("reference") or "").strip()
        if ref:
            return ref

    # 兜底：部分合成器可能只给 response
    for row in rows:
        resp = (row.get("response") or "").strip()
        if resp:
            return resp

    return None


def main() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    prompt_path = Path(__file__).resolve().parent / "prompt" / "rag_eval_answer_prompt.txt"
    gt_plan_prompt_path = (
        Path(__file__).resolve().parent / "prompt" / "rag_eval_gt_travel_plan.txt"
    )
    cases_path = Path(__file__).resolve().parent / "test_cases.json"

    if not env_path.exists():
        raise FileNotFoundError(
            f"Missing evaluation env file: {env_path}. Please copy from .env.example."
        )
    if not prompt_path.exists():
        raise FileNotFoundError(f"Missing prompt template: {prompt_path}")
    if not gt_plan_prompt_path.exists():
        raise FileNotFoundError(f"Missing GT travel plan prompt: {gt_plan_prompt_path}")
    if not cases_path.exists():
        raise FileNotFoundError(f"Missing test cases file: {cases_path}")

    config = RagEvalConfig.from_env_file(env_path)

    # 1) 创建运行目录
    run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(config.output_dir) / f"{config.run_name_prefix}_{run_tag}"
    output_dir.mkdir(parents=True, exist_ok=True)

    eval_data_path = output_dir / "eval_data.jsonl"
    step1_meta_path = output_dir / "step1_meta.json"

    # 2) 映射 env 以复用主项目 RagRetrievalService 的实现
    config.apply_to_app_env_for_rag_import()

    # 3) 延迟导入：确保 app.config settings 能读到映射后的 env
    from app.domain.services.rag_retrieval_service import RagRetrievalService  # noqa: E402

    retrieval_service = RagRetrievalService()

    # 4) LLM 客户端（非流式）
    client = OpenAI(api_key=config.openai_api_key, base_url=config.openai_base_url)
    prompt_template = _read_prompt_template(prompt_path)
    gt_travel_plan_template = _read_prompt_template(gt_plan_prompt_path)

    cases = load_eval_cases(cases_path)

    with eval_data_path.open("w", encoding="utf-8") as f:
        for case in cases:
            case_id = case["id"]
            city_name: str = case["city_name"]
            day_count: Optional[int] = case["day_count"]
            customization_requirements: Optional[str] = case.get(
                "customization_requirements"
            )
            ground_truth_answer: Optional[str] = case.get("ground_truth_answer")
            ground_truth_generator: Optional[str] = None

            # 5) 问题：当前直接使用 build_query 产出的自然语言 query 作为评测问题
            question = retrieval_service.build_query(
                city_name=city_name,
                day_count=day_count,
                customization_requirements=customization_requirements,
            )

            docs = retrieval_service.retrieve_docs_for_rag_eval(
                city_name=city_name,
                day_count=day_count,
                customization_requirements=customization_requirements,
            )
            contexts = [(d.page_content or "")[:CONTEXT_CHAR_LIMIT].strip() for d in docs]

            gt_corpus_doc_count = 0
            if (
                config.auto_generate_ground_truth_answer
                and (ground_truth_answer is None or not str(ground_truth_answer).strip())
            ):
                corpus_docs, gt_corpus_doc_count = _load_chroma_corpus_documents_for_gt(
                    config=config,
                    city_name=city_name,
                )
                doc_pool = corpus_docs if corpus_docs else docs

                if config.gt_source == "ragas_testset":
                    auto_gt = _generate_gt_answer_with_testset_generator(
                        docs=corpus_docs,
                        config=config,
                    )
                    if auto_gt and auto_gt.strip():
                        ground_truth_answer = auto_gt.strip()
                        ground_truth_generator = "ragas_testset"

                if config.gt_source == "travel_plan" or not (
                    ground_truth_answer and str(ground_truth_answer).strip()
                ):
                    plan_gt = _generate_gt_travel_plan_answer(
                        client=client,
                        model=config.llm_model_name,
                        prompt_template=gt_travel_plan_template,
                        city_name=city_name,
                        day_count=day_count,
                        customization_requirements=customization_requirements,
                        question=question,
                        corpus_docs=doc_pool,
                        config=config,
                    )
                    if plan_gt and plan_gt.strip():
                        ground_truth_answer = plan_gt.strip()
                        ground_truth_generator = "travel_plan_llm"

                if not (ground_truth_answer and str(ground_truth_answer).strip()):
                    fallback_gt = _generate_gt_answer_with_llm_fallback(
                        client=client,
                        model=config.llm_model_name,
                        question=question,
                        docs=doc_pool,
                        max_tokens=config.max_tokens,
                    )
                    if fallback_gt and fallback_gt.strip():
                        ground_truth_answer = fallback_gt.strip()
                        ground_truth_generator = "llm_qa_fallback"

            # RAG评估时要用和生成时一致的 contexts
            contexts_for_prompt = format_contexts_for_prompt(contexts)

            prompt = prompt_template.format(
                question=question,
                contexts=contexts_for_prompt,
            )

            answer = generate_answer_non_streaming(
                client=client,
                model=config.llm_model_name,
                temperature=config.answer_temperature,
                max_tokens=config.max_tokens,
                system_prompt_or_user_prompt=prompt,
            )

            # 元数据（用于排查检索是否真的命中到了当前城市）
            retrieved_docs_metadata: List[Dict[str, Any]] = []
            for d in docs:
                md = getattr(d, "metadata", None) or {}
                retrieved_docs_metadata.append(
                    {
                        "title": md.get("title"),
                        "time": md.get("time"),
                        "url": md.get("url"),
                        "source_city": md.get("source_city"),
                    }
                )

            record = {
                "id": case_id,
                "question": question,
                "contexts": contexts,
                "answer": answer,
                "city_name": city_name,
                "day_count": day_count,
                "customization_requirements": customization_requirements,
                "ground_truth_answer": ground_truth_answer,
                "ground_truth_generator": ground_truth_generator,
                "ground_truth_corpus_scope": config.gt_corpus_scope,
                "ground_truth_corpus_doc_count": gt_corpus_doc_count,
                "retrieved_docs_metadata": retrieved_docs_metadata,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    step1_meta_path.write_text(
        json.dumps(
            {
                "run_at": datetime.now().isoformat(timespec="seconds"),
                "cases_count": len(cases),
                "test_cases_path": str(cases_path),
                "eval_data_path": str(eval_data_path),
                "config": config.config_snapshot(),
                "output_dir": str(output_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[rag-eval] step1 done. eval data saved to: {eval_data_path}")


if __name__ == "__main__":
    main()

