from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from openai import AsyncOpenAI, OpenAI

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from test.rag_eval.config import RagEvalConfig  # noqa: E402


def _latest_run_dir(output_dir: Path, run_name_prefix: str) -> Path:
    candidates = [
        p
        for p in output_dir.iterdir()
        if p.is_dir() and p.name.startswith(run_name_prefix + "_")
    ]
    if not candidates:
        raise FileNotFoundError(f"No run dir found under: {output_dir}")
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _load_eval_data(eval_data_path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with eval_data_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _safe_mean(xs: List[float]) -> float:
    return float(statistics.mean(xs)) if xs else 0.0


def _safe_median(xs: List[float]) -> float:
    return float(statistics.median(xs)) if xs else 0.0


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _truncate_text(text: str, max_chars: int) -> str:
    """RAGAS 若干指标对长文本会爆输出 token；max_chars<=0 表示不截断。"""
    t = (text or "").strip()
    if max_chars <= 0 or len(t) <= max_chars:
        return t
    return t[:max_chars]


def _preview_text(text: str, max_len: int = 96) -> str:
    t = (text or "").replace("\n", " ").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _format_metric(v: Any) -> str:
    if v is None:
        return "n/a"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "n/a"
    if isinstance(x, float) and math.isnan(x):
        return "n/a"
    return f"{x:.4f}"


def _context_chunk_stats(contexts: List[Any]) -> tuple[int, int]:
    """(chunk 条数, 总字符数)"""
    cs = contexts or []
    return len(cs), sum(len(str(c or "")) for c in cs)


def _configure_step2_logging(*, verbose: bool) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if verbose else "INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )


def _metric_float_or_none(v: Any) -> Optional[float]:
    """RAGAS 可能返回 nan；写入 JSON 时转为 null 更稳妥。"""
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    return x


def _gt_answer_embedding_similarity(
    client: OpenAI,
    embedding_model: str,
    answer: str,
    ground_truth_answer: str,
) -> Optional[float]:
    answer_text = (answer or "").strip()
    gt_text = (ground_truth_answer or "").strip()
    if not answer_text or not gt_text:
        return None

    emb_resp = client.embeddings.create(
        model=embedding_model,
        input=[answer_text, gt_text],
    )
    if not emb_resp.data or len(emb_resp.data) < 2:
        return None

    emb_a = emb_resp.data[0].embedding
    emb_b = emb_resp.data[1].embedding
    return _cosine_similarity(emb_a, emb_b)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-dir",
        type=str,
        default="",
        help="Step1 output run dir (contains eval_data.jsonl). If empty, use latest.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="DEBUG：打印每个 RAGAS 子步骤",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="不打印每条用例的详情与指标行（仍打印启动/收尾汇总）",
    )
    args = parser.parse_args()

    _configure_step2_logging(verbose=args.verbose)

    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"Missing env file: {env_path}")

    config = RagEvalConfig.from_env_file(env_path)

    output_root = Path(config.output_dir)
    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        run_dir = _latest_run_dir(output_root, config.run_name_prefix)

    eval_data_path = run_dir / "eval_data.jsonl"
    if not eval_data_path.exists():
        raise FileNotFoundError(f"Missing eval data: {eval_data_path}")

    rows = _load_eval_data(eval_data_path)
    if not rows:
        raise ValueError(f"No rows in eval data: {eval_data_path}")

    gt_answer_count = sum(
        1 for r in rows if isinstance(r.get("ground_truth_answer"), str) and r.get("ground_truth_answer", "").strip()
    )

    logger.info("======== rag-eval step2 ========")
    logger.info("run_dir: {}", run_dir.resolve())
    logger.info("eval_data: {} ({} rows)", eval_data_path.resolve(), len(rows))
    logger.info(
        "ground_truth_answer: {} / {} rows",
        gt_answer_count,
        len(rows),
    )

    # 延迟导入 ragas：确保依赖已安装
    from ragas.llms import llm_factory
    from ragas.embeddings.base import embedding_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecisionWithReference,
        ContextRecall,
        ContextRelevance,
        Faithfulness,
    )

    ragas_model = config.ragas_llm_model_name or config.llm_model_name

    logger.info("RAGAS LLM model: {}", ragas_model)
    logger.info("embedding model: {}", config.embedding_model_name)
    logger.info(
        "RAGAS llm max_tokens={} | faithfulness answer cap={} chars | reference cap={} chars",
        config.ragas_llm_max_tokens,
        config.ragas_faithfulness_answer_max_chars,
        config.ragas_reference_max_chars,
    )

    client = AsyncOpenAI(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
    )
    sync_client = OpenAI(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
    )

    llm = llm_factory(
        ragas_model,
        client=client,
        max_tokens=max(1024, int(config.ragas_llm_max_tokens)),
    )
    embeddings = embedding_factory(
        "openai",
        model=config.embedding_model_name,
        client=client,
    )

    faithfulness = Faithfulness(llm=llm)
    context_relevance = ContextRelevance(llm=llm)
    answer_relevancy = AnswerRelevancy(llm=llm, embeddings=embeddings)
    context_recall = ContextRecall(llm=llm)
    context_precision_w_ref = ContextPrecisionWithReference(llm=llm)

    ragas_results_path = run_dir / "ragas_results.jsonl"

    metric_names = [
        "faithfulness",
        "context_recall",
        "context_precision_with_reference",
        "context_relevance",
        "answer_relevancy",
        "gt_answer_embedding_similarity",
    ]
    logger.info("metrics: {}", ", ".join(metric_names))

    faithfulness_failures = 0
    context_recall_failures = 0
    context_precision_failures = 0

    with ragas_results_path.open("w", encoding="utf-8") as f:
        for idx, r in enumerate(rows, start=1):
            t_row0 = time.perf_counter()
            case_id = r.get("id")
            q = r["question"]
            answer = r["answer"]
            contexts = r["contexts"]
            ground_truth_answer = r.get("ground_truth_answer")

            n_chunks, ctx_chars = _context_chunk_stats(contexts)
            has_gt = bool(
                isinstance(ground_truth_answer, str) and ground_truth_answer.strip()
            )

            if not args.quiet:
                logger.info(
                    "---- case {}/{} id={} ----",
                    idx,
                    len(rows),
                    case_id,
                )
                logger.info("question: {!r}", _preview_text(q, 160))
                logger.info(
                    "sizes: contexts={} chunks, {} chars | answer={} chars | has_gt={}",
                    n_chunks,
                    ctx_chars,
                    len(answer or ""),
                    has_gt,
                )

            answer_for_faith = _truncate_text(
                answer, config.ragas_faithfulness_answer_max_chars
            )
            gt_ref = _truncate_text(
                ground_truth_answer or "", config.ragas_reference_max_chars
            )
            if args.verbose and not args.quiet:
                logger.debug(
                    "faithfulness input: response_len={} (after cap {})",
                    len(answer_for_faith),
                    config.ragas_faithfulness_answer_max_chars,
                )
            try:
                faith_score = faithfulness.score(
                    user_input=q,
                    response=answer_for_faith,
                    retrieved_contexts=contexts,
                ).value
            except Exception as e:
                faithfulness_failures += 1
                logger.warning(
                    "Faithfulness metric failed for id={}: {}",
                    case_id,
                    e,
                )
                faith_score = None

            if args.verbose and not args.quiet:
                logger.debug("context_relevance …")
            ctx_rel_score = context_relevance.score(
                user_input=q, retrieved_contexts=contexts
            ).value
            if args.verbose and not args.quiet:
                logger.debug("answer_relevancy …")
            ans_rel_score = answer_relevancy.score(
                user_input=q, response=answer
            ).value

            context_recall_score: Optional[float] = None
            context_precision_score: Optional[float] = None
            if gt_ref:
                if args.verbose and not args.quiet:
                    logger.debug(
                        "context_recall (reference_len={}) …",
                        len(gt_ref),
                    )
                try:
                    context_recall_score = _metric_float_or_none(
                        context_recall.score(
                            user_input=q,
                            retrieved_contexts=contexts,
                            reference=gt_ref,
                        ).value
                    )
                except Exception as e:
                    context_recall_failures += 1
                    logger.warning(
                        "ContextRecall failed for id={}: {}",
                        case_id,
                        e,
                    )
                if args.verbose and not args.quiet:
                    logger.debug("context_precision_with_reference …")
                try:
                    context_precision_score = _metric_float_or_none(
                        context_precision_w_ref.score(
                            user_input=q,
                            reference=gt_ref,
                            retrieved_contexts=contexts,
                        ).value
                    )
                except Exception as e:
                    context_precision_failures += 1
                    logger.warning(
                        "ContextPrecisionWithReference failed for id={}: {}",
                        case_id,
                        e,
                    )
            elif args.verbose and not args.quiet:
                logger.debug("skip context_recall / context_precision (no gt reference)")

            if args.verbose and not args.quiet:
                logger.debug("gt_answer_embedding_similarity …")
            gt_answer_sim_score = _gt_answer_embedding_similarity(
                client=sync_client,
                embedding_model=config.embedding_model_name,
                answer=answer,
                ground_truth_answer=ground_truth_answer or "",
            )

            if not args.quiet:
                logger.info(
                    "metrics: faith={} | ctx_recall={} | ctx_prec={} | ctx_rel={} | ans_rel={} | gt_emb={}",
                    _format_metric(faith_score),
                    _format_metric(context_recall_score),
                    _format_metric(context_precision_score),
                    _format_metric(ctx_rel_score),
                    _format_metric(ans_rel_score),
                    _format_metric(gt_answer_sim_score),
                )
                logger.info(
                    "case {} done in {:.1f}s",
                    case_id,
                    time.perf_counter() - t_row0,
                )

            out = {
                "id": r.get("id"),
                "question": q,
                "metrics": {
                    "faithfulness": faith_score,
                    "context_recall": context_recall_score,
                    "context_precision_with_reference": context_precision_score,
                    "context_relevance": _metric_float_or_none(ctx_rel_score),
                    "answer_relevancy": _metric_float_or_none(ans_rel_score),
                    "gt_answer_embedding_similarity": gt_answer_sim_score,
                },
            }
            f.write(json.dumps(out, ensure_ascii=False) + "\n")

    # 汇总统计
    faith_scores: List[float] = []
    context_recall_scores: List[float] = []
    context_precision_scores: List[float] = []
    ctx_rel_scores: List[float] = []
    ans_rel_scores: List[float] = []
    gt_answer_sim_scores: List[float] = []

    results_rows = _load_eval_data(ragas_results_path)
    for r in results_rows:
        m = r["metrics"]
        fv = m.get("faithfulness")
        if fv is not None:
            faith_scores.append(float(fv))
        cr = m.get("context_recall")
        if cr is not None:
            context_recall_scores.append(float(cr))
        cp = m.get("context_precision_with_reference")
        if cp is not None:
            context_precision_scores.append(float(cp))
        cv = m.get("context_relevance")
        if cv is not None:
            ctx_rel_scores.append(float(cv))
        av = m.get("answer_relevancy")
        if av is not None:
            ans_rel_scores.append(float(av))
        gt_sim = m.get("gt_answer_embedding_similarity")
        if gt_sim is not None:
            gt_answer_sim_scores.append(float(gt_sim))

    summary = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "eval_data_path": str(eval_data_path),
        "run_dir": str(run_dir),
        "case_count": len(rows),
        "ground_truth_coverage": {
            "ground_truth_answer_count": gt_answer_count,
            "ground_truth_answer_ratio": round(gt_answer_count / len(rows), 4),
        },
        "metrics": {
            "faithfulness": {
                "mean": _safe_mean(faith_scores),
                "median": _safe_median(faith_scores),
                "scored_count": len(faith_scores),
                "failed_count": faithfulness_failures,
            },
            "context_recall": {
                "mean": _safe_mean(context_recall_scores),
                "median": _safe_median(context_recall_scores),
                "scored_count": len(context_recall_scores),
                "failed_count": context_recall_failures,
            },
            "context_precision_with_reference": {
                "mean": _safe_mean(context_precision_scores),
                "median": _safe_median(context_precision_scores),
                "scored_count": len(context_precision_scores),
                "failed_count": context_precision_failures,
            },
            "context_relevance": {
                "mean": _safe_mean(ctx_rel_scores),
                "median": _safe_median(ctx_rel_scores),
            },
            "answer_relevancy": {
                "mean": _safe_mean(ans_rel_scores),
                "median": _safe_median(ans_rel_scores),
            },
            "gt_answer_embedding_similarity": {
                "mean": _safe_mean(gt_answer_sim_scores),
                "median": _safe_median(gt_answer_sim_scores),
                "scored_count": len(gt_answer_sim_scores),
            },
        },
        "config": config.config_snapshot(),
        "metric_names": metric_names,
    }

    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    msum = summary["metrics"]
    logger.info("======== step2 summary ========")
    logger.info("per-row results: {}", ragas_results_path.resolve())
    logger.info("aggregate file: {}", summary_path.resolve())
    logger.info(
        "means: faith={:.4f} (fail {}) | ctx_recall={:.4f} (fail {}) | "
        "ctx_prec={:.4f} (fail {}) | ctx_rel={:.4f} | ans_rel={:.4f} | gt_emb={:.4f}",
        msum["faithfulness"]["mean"],
        msum["faithfulness"]["failed_count"],
        msum["context_recall"]["mean"],
        msum["context_recall"]["failed_count"],
        msum["context_precision_with_reference"]["mean"],
        msum["context_precision_with_reference"]["failed_count"],
        msum["context_relevance"]["mean"],
        msum["answer_relevancy"]["mean"],
        msum["gt_answer_embedding_similarity"]["mean"],
    )
    print(f"[rag-eval] step2 done. results saved to: {run_dir}")


if __name__ == "__main__":
    main()

