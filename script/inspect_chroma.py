from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

import chromadb
from dotenv import dotenv_values

try:
    import tiktoken
except Exception:  # noqa: BLE001 - 无 tiktoken 时降级为字符统计
    tiktoken = None


def _build_token_counter() -> tuple[str, Any]:
    """
    构建 token 计数器。
    - 优先使用 tiktoken 的 cl100k_base（与 OpenAI 常见 embedding/chat 模型接近）
    - 若环境缺少 tiktoken，则降级为字符长度计数并明确标识
    """
    if tiktoken is None:
        return "char_fallback", None
    try:
        return "cl100k_base", tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001
        return "char_fallback", None


def _token_len(text: Any, encoder: Any) -> int:
    if not isinstance(text, str) or not text:
        return 0
    if encoder is None:
        return len(text)
    return len(encoder.encode(text))


def _load_chroma_settings(project_dir: Path) -> tuple[Path, str]:
    """
    从项目根目录的 .env 读取 Chroma 配置。
    这里不依赖 env_config.py，避免检查脚本被 OPENAI_API_KEY 等无关配置阻塞。
    """
    env_path = project_dir / ".env"
    env_map = dotenv_values(env_path) if env_path.exists() else {}

    chroma_dir_raw = str(env_map.get("CHROMA_DIR") or "./chroma_db")
    collection = str(env_map.get("CHROMA_COLLECTION") or "travel_docs")

    chroma_dir = Path(chroma_dir_raw)
    if not chroma_dir.is_absolute():
        chroma_dir = (project_dir / chroma_dir).resolve()
    return chroma_dir, collection


def _safe_len(v: Any) -> int:
    return len(v) if isinstance(v, str) else 0


def _percentile(sorted_values: list[int], p: float) -> int:
    if not sorted_values:
        return 0
    idx = int((len(sorted_values) - 1) * p)
    return sorted_values[idx]


def inspect_collection(
    *,
    persist_dir: Path,
    collection_name: str,
    sample_size: int = 20,
    batch_size: int = 500,
    preview_text_chars: int = 600,
) -> None:
    # 连接本地持久化 Chroma 数据库
    client = chromadb.PersistentClient(path=str(persist_dir))
    col = client.get_collection(collection_name)

    total = col.count()
    print(f"[概览] persist_dir={persist_dir}")
    print(f"[概览] collection={collection_name}")
    print(f"[概览] chunk_total={total}")

    if total == 0:
        print("[提示] 当前 collection 为空。")
        return

    # 1) 全量巡检统计（分页，避免一次性读取过多内存）
    token_backend, encoder = _build_token_counter()
    token_lengths: list[int] = []
    char_lengths: list[int] = []
    key_presence_counter: Counter[str] = Counter()
    empty_content_count = 0
    tiny_chunk_threshold = 20
    tiny_chunk_count = 0

    offset = 0
    while offset < total:
        page = col.get(
            limit=batch_size,
            offset=offset,
            include=["documents", "metadatas"],
        )
        docs = page.get("documents") or []
        metas = page.get("metadatas") or []

        for i, doc in enumerate(docs):
            char_len = _safe_len(doc)
            token_len = _token_len(doc, encoder)
            char_lengths.append(char_len)
            token_lengths.append(token_len)
            if char_len == 0:
                empty_content_count += 1
            if 0 < token_len < tiny_chunk_threshold:
                tiny_chunk_count += 1

            md = metas[i] if i < len(metas) else None
            if isinstance(md, dict):
                for k, v in md.items():
                    # 仅统计“有值”的键覆盖率，便于看哪些字段真正可用于过滤。
                    if str(v).strip():
                        key_presence_counter[k] += 1

        offset += batch_size

    token_sorted = sorted(token_lengths)
    char_sorted = sorted(char_lengths)
    avg_tokens = int(sum(token_lengths) / len(token_lengths)) if token_lengths else 0
    avg_chars = int(sum(char_lengths) / len(char_lengths)) if char_lengths else 0
    print(f"[长度口径] token_backend={token_backend}")
    print(
        "[长度分布(token)] "
        f"min={token_sorted[0]} "
        f"p50={_percentile(token_sorted, 0.50)} "
        f"p90={_percentile(token_sorted, 0.90)} "
        f"p99={_percentile(token_sorted, 0.99)} "
        f"max={token_sorted[-1]} "
        f"avg={avg_tokens}"
    )
    print(
        "[长度分布(char)] "
        f"min={char_sorted[0]} "
        f"p50={_percentile(char_sorted, 0.50)} "
        f"p90={_percentile(char_sorted, 0.90)} "
        f"p99={_percentile(char_sorted, 0.99)} "
        f"max={char_sorted[-1]} "
        f"avg={avg_chars}"
    )
    print(f"[质量] empty_content_count={empty_content_count}")
    print(
        f"[质量] tiny_chunk_lt_{tiny_chunk_threshold}_tokens="
        f"{tiny_chunk_count} ({(tiny_chunk_count / total):.2%})"
    )

    # 2) metadata 完整性（按“有值覆盖率”排序）
    print("[元数据覆盖率Top10] key -> non_empty_ratio (non_empty_count/total)")
    for k, cnt in key_presence_counter.most_common(10):
        ratio = cnt / total
        print(f"- {k}: {ratio:.2%} ({cnt}/{total})")

    # 3) 随机抽样查看内容与 metadata
    # 这里用随机 offset 抽样，直观查看是否存在乱码、无效文、重复文等问题。
    actual_sample = min(sample_size, total)
    sampled_offsets = sorted(random.sample(range(total), actual_sample))
    print(f"[随机抽样] sample_size={actual_sample}")
    for idx, off in enumerate(sampled_offsets, start=1):
        row = col.get(limit=1, offset=off, include=["documents", "metadatas"])
        doc = (row.get("documents") or [""])[0] or ""
        md = (row.get("metadatas") or [{}])[0] or {}
        preview = doc.replace("\n", " ")[:preview_text_chars]
        print(
            f"{idx:02d}. offset={off} "
            f"tokens={_token_len(doc, encoder)} "
            f"chars={len(doc)}"
        )
        # 显示完整原属性（metadata），便于核对字段是否完整/正确。
        print(f"    metadata={json.dumps(md, ensure_ascii=False, sort_keys=True)}")
        print(f"    text_preview={preview}")
        if len(doc) > preview_text_chars:
            print(f"    text_preview_truncated=true (showing first {preview_text_chars} chars)")


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    chroma_dir, collection = _load_chroma_settings(project_dir)
    inspect_collection(
        persist_dir=chroma_dir,
        collection_name=collection,
        sample_size=20,
        batch_size=500,
        preview_text_chars=600,
    )


if __name__ == "__main__":
    main()
