"""意图识别评估入口：评估 LLM 原始输出 vs 规则校验后输出。"""
from __future__ import annotations

import json
import os
import sys

import json5
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage

# 允许从 tools/intent_eval 直接运行脚本
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.services.llm_intent_service import LLMIntentService  # noqa: E402


# ====== 可修改参数（评估入口）======
MODELS = [
    "gpt-4o-mini",  # gpt-4o-mini、gpt-4.1-nano
]
TEST_CASES_FILE = Path(__file__).resolve().parent / "test_cases.json"
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
RUN_NAME_PREFIX = "intent_eval"
# ==================================


@dataclass
class StageMetrics:
    total: int = 0
    intent_correct: int = 0
    city_correct: int = 0
    day_correct: int = 0
    guidance_reason_correct: int = 0
    all_correct: int = 0

    def to_dict(self) -> Dict[str, Any]:
        def safe_div(x: int, y: int) -> float:
            return round((x / y) if y else 0.0, 4)

        return {
            "total": self.total,
            "intent_accuracy": safe_div(self.intent_correct, self.total),
            "city_accuracy": safe_div(self.city_correct, self.total),
            "day_accuracy": safe_div(self.day_correct, self.total),
            "guidance_reason_accuracy": safe_div(self.guidance_reason_correct, self.total),
            "all_fields_accuracy": safe_div(self.all_correct, self.total),
        }


def load_test_cases(path: Path) -> List[Dict[str, Any]]:
    """
    使用 JSON5 解析，支持 //、/* */ 注释与尾逗号；纯 JSON 亦为合法 JSON5。
    这样可在 test_cases.json 中写分类说明，而无需在每条用例里加 category 字段。
    """
    text = path.read_text(encoding="utf-8")
    cases = json5.loads(text)
    if not isinstance(cases, list):
        raise ValueError("测试用例文件根节点必须是数组")
    return cases


def normalize_value(v: Any) -> Any:
    if v == "null":
        return None
    return v


def normalize_pred(pred: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intent_type": pred.get("intent_type"),
        "city_name": normalize_value(pred.get("city_name")),
        "day_count": normalize_value(pred.get("day_count")),
        "guidance_reason": normalize_value(pred.get("guidance_reason")),
    }


def update_metrics(metrics: StageMetrics, pred: Dict[str, Any], expected: Dict[str, Any]) -> None:
    p = normalize_pred(pred)
    e = normalize_pred(expected)

    metrics.total += 1
    intent_ok = p["intent_type"] == e["intent_type"]
    city_ok = p["city_name"] == e["city_name"]
    day_ok = p["day_count"] == e["day_count"]
    guidance_ok = p["guidance_reason"] == e.get("guidance_reason")

    metrics.intent_correct += int(intent_ok)
    metrics.city_correct += int(city_ok)
    metrics.day_correct += int(day_ok)
    metrics.guidance_reason_correct += int(guidance_ok)
    metrics.all_correct += int(intent_ok and city_ok and day_ok and guidance_ok)


def eval_one_case(
    service: LLMIntentService, model_name: str, case: Dict[str, Any]
) -> Dict[str, Any]:
    user_query = case["query"]
    state: Dict[str, Any] = {
        "messages": [HumanMessage(content=user_query)],
        "city_name": None,
        "day_count": None,
        "in_guidance_mode": False,
    }
    stage_result: Dict[str, Any] = {
        "llm_raw": None,
        "after_rules": None,
        "error": None,
    }

    # 重点：这里一次调用拿到两个阶段的结果，确保评估链路一致。
    try:
        pair = service.recognize_intent_with_stages(state, model_name=model_name)
        stage_result["llm_raw"] = pair["llm_raw"]
        stage_result["after_rules"] = pair["after_rules"]
    except Exception as exc:
        stage_result["error"] = str(exc)

    return {
        "id": case.get("id"),
        "query": user_query,
        "expected": deepcopy(case.get("expected", {})),
        "llm_raw": stage_result["llm_raw"],
        "after_rules": stage_result["after_rules"],
        "error": stage_result["error"],
    }


def _extract_stage_for_compare(stage_name: str, row: Dict[str, Any]) -> Dict[str, Any]:
    if stage_name == "llm_raw":
        raw = deepcopy(row.get("llm_raw") or {})
        # llm_raw 阶段的 guidance 字段名是 llm_guidance_reason，统一映射为 guidance_reason 参与对比
        raw["guidance_reason"] = raw.get("llm_guidance_reason")
        return raw
    return deepcopy(row.get("after_rules") or {})


def _collect_failure_detail(stage_name: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    expected = normalize_pred(row.get("expected", {}))
    pred = normalize_pred(_extract_stage_for_compare(stage_name, row))
    mismatches: List[str] = []
    for key in ("intent_type", "city_name", "day_count", "guidance_reason"):
        if pred.get(key) != expected.get(key):
            mismatches.append(key)
    if not mismatches:
        return None
    return {
        "id": row.get("id"),
        "query": row.get("query"),
        "mismatched_fields": mismatches,
        "expected": expected,
        "predicted": pred,
        "error": row.get("error"),
    }


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _format_one_line_result(result: Dict[str, Any]) -> str:
    p = normalize_pred(result or {})
    return (
        f"intent_type={p.get('intent_type')}, "
        f"city_name={p.get('city_name')}, "
        f"day_count={p.get('day_count')}, "
        f"guidance_reason={p.get('guidance_reason')}"
    )


def _build_failed_cases_compare_lines(rows: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    idx = 1
    for row in rows:
        expected = normalize_pred(row.get("expected", {}))
        llm_raw = _extract_stage_for_compare("llm_raw", row)
        after_rules = _extract_stage_for_compare("after_rules", row)

        expected_n = normalize_pred(expected)
        llm_n = normalize_pred(llm_raw)
        rules_n = normalize_pred(after_rules)
        is_pass = (expected_n == llm_n) and (expected_n == rules_n)
        if is_pass:
            continue

        lines.append(f"[Case {idx}]")
        lines.append(f"Q: {row.get('query')}")
        lines.append(f"Expected: {_format_one_line_result(expected_n)}")
        lines.append(f"LLM Raw: {_format_one_line_result(llm_n)}")
        lines.append(f"After Rules: {_format_one_line_result(rules_n)}")
        lines.append("")
        idx += 1

    if idx == 1:
        lines.append("No failed cases.")
    return lines


def save_text(path: Path, lines: List[str]) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_for_model(model_name: str, cases: List[Dict[str, Any]], run_dir: Path) -> Dict[str, Any]:
    service = LLMIntentService()
    llm_metrics = StageMetrics()
    rule_metrics = StageMetrics()
    rows: List[Dict[str, Any]] = []

    for case in cases:
        row = eval_one_case(service, model_name, case)
        rows.append(row)

        expected = row["expected"]
        llm_pred = row["llm_raw"] or {}
        rule_pred = row["after_rules"] or {}
        update_metrics(llm_metrics, llm_pred, expected)
        update_metrics(rule_metrics, rule_pred, expected)

    model_result = {
        "model": model_name,
        "case_count": len(cases),
        "metrics": {
            "llm_raw": llm_metrics.to_dict(),
            "after_rules": rule_metrics.to_dict(),
            "improvement": {
                "intent_accuracy_delta": round(
                    rule_metrics.to_dict()["intent_accuracy"] - llm_metrics.to_dict()["intent_accuracy"], 4
                ),
                "city_accuracy_delta": round(
                    rule_metrics.to_dict()["city_accuracy"] - llm_metrics.to_dict()["city_accuracy"], 4
                ),
                "day_accuracy_delta": round(
                    rule_metrics.to_dict()["day_accuracy"] - llm_metrics.to_dict()["day_accuracy"], 4
                ),
                "guidance_reason_accuracy_delta": round(
                    rule_metrics.to_dict()["guidance_reason_accuracy"]
                    - llm_metrics.to_dict()["guidance_reason_accuracy"], 4
                ),
                "all_fields_accuracy_delta": round(
                    rule_metrics.to_dict()["all_fields_accuracy"] - llm_metrics.to_dict()["all_fields_accuracy"], 4
                ),
            },
        },
        # 仅输出失败用例，便于快速定位问题
        "failed_cases": {
            "llm_raw": [x for x in (_collect_failure_detail("llm_raw", row) for row in rows) if x],
            "after_rules": [x for x in (_collect_failure_detail("after_rules", row) for row in rows) if x],
        },
    }
    save_json(run_dir / f"{model_name.replace('/', '_')}.json", model_result)

    # 失败用例对比文本：每个样本 4 行，便于人工快速比较
    compare_lines = _build_failed_cases_compare_lines(rows)
    save_text(run_dir / f"{model_name.replace('/', '_')}_failed_cases.txt", compare_lines)
    return model_result


def main() -> None:
    ensure_output_dir(OUTPUT_DIR)
    run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"{RUN_NAME_PREFIX}_{run_tag}"
    ensure_output_dir(run_dir)

    cases = load_test_cases(TEST_CASES_FILE)
    all_models: List[Dict[str, Any]] = []
    for model in MODELS:
        all_models.append(run_for_model(model, cases, run_dir))

    summary = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "cases_file": str(TEST_CASES_FILE),
        "models": MODELS,
        "results_dir": str(run_dir),
        "model_summaries": [
            {
                "model": x["model"],
                "case_count": x["case_count"],
                "metrics": x["metrics"],
            }
            for x in all_models
        ],
    }
    save_json(run_dir / "summary.json", summary)
    print(f"[intent-eval] done. results saved to: {run_dir}")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    main()
