from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv


def _env_bool(v: Optional[str], *, default: bool = False) -> bool:
    """把环境变量字符串解析成 bool。

    支持形式：
    - True: `1/true/yes/y/on`
    - False: `0/false/no/n/off`
    - 其他/空：返回 default
    """
    s = (v or "").strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default


def _env_int(v: Optional[str], *, default: int) -> int:
    try:
        return int((v or "").strip() or default)
    except Exception:
        return default


def _env_float(v: Optional[str], *, default: float) -> float:
    try:
        return float((v or "").strip() or default)
    except Exception:
        return default


def _parse_meta_cols(v: str, all_cols: List[str]) -> List[str]:
    """解析 `DATA_META_COLS`。

    - `*`：使用全列（data.csv 的所有字段）
    - `colA,colB`：只取指定列
    """
    s = (v or "").strip()
    if s == "*" or s == "":
        return list(all_cols)
    cols = [x.strip() for x in s.split(",") if x.strip()]
    missing = [c for c in cols if c not in all_cols]
    if missing:
        raise RuntimeError(f"DATA_META_COLS 指定了不存在的列: {missing}")
    return cols


@dataclass(frozen=True)
class IngestConfig:
    # Input
    data_csv: Path
    data_content_col: str
    data_meta_cols: List[str]
    max_rows: int

    # Chunking
    chunk_strategy: str  # semantic|recursive
    chunk_mode: str  # iter|bulk

    # SemanticChunker params
    chunker_backend: str  # ollama|openai
    ollama_base_url: str
    ollama_model_name: str
    semantic_breakpoint_amount: float
    semantic_add_start_index: bool
    semantic_min_chunk_size: int

    # RecursiveCharacterTextSplitter params
    recursive_chunk_size: int
    recursive_chunk_overlap: int

    # Vector store (Chroma)
    chroma_dir: Path
    chroma_collection: str
    chroma_reset: bool
    chroma_batch_add: int
    chroma_flush_mode: str  # batch|per_doc

    # Embeddings for vectorization (OpenAI)
    openai_base_url: str
    openai_api_key: str
    embedding_model: str
    embedding_request_timeout: float
    embedding_show_progress: bool

    # Resume / progress
    checkpoint_file: Path
    progress_log_every_docs: int


def load_config() -> IngestConfig:
    """
    从项目根目录 `.env` 读取配置，并用合理默认值补齐。

    关键点：
    - 入口脚本不直接接触 `.env` 的字符串，而是只依赖这个函数产出的强类型 `IngestConfig`。
    - 这样后续模块（切块器/入库器）都可以只用 cfg.xxx，不关心 env 的细节。
    - 读取 metadata 列时，需要先读 data.csv 的表头；因此这里会额外做一次“读表头”操作。
    """

    here = Path(__file__).resolve().parent
    env_path = here / ".env"
    load_dotenv(dotenv_path=str(env_path), override=False)

    data_csv = Path(os.environ.get("DATA_CSV", str(here / "data.csv"))).resolve()
    if not data_csv.exists():
        raise FileNotFoundError(f"DATA_CSV not found: {data_csv}")

    data_content_col = os.environ.get("DATA_CONTENT_COL", "text")
    max_rows = _env_int(os.environ.get("MAX_ROWS"), default=0)

    # 先读一次表头拿到 meta cols 的可选列名（兼容 Windows 常见编码）
    import pandas as pd

    # 用 dtype=str 避免 pandas 把数字列转成 float/NaN，导致 metadata 键值变成非字符串
    # 编码探测可能会因为“表头少量字节”误判，所以这里做逐编码尝试。
    encodings = ("utf-8-sig", "gb18030", "utf-16")
    sample_df = None
    for enc in encodings:
        try:
            sample_df = pd.read_csv(
                data_csv, nrows=1, encoding=enc, dtype=str
            ).fillna("")
            break
        except UnicodeDecodeError:
            continue
    if sample_df is None:
        raise RuntimeError(f"无法解码 DATA_CSV（已尝试 {encodings}）：{data_csv}")

    all_cols = list(sample_df.columns)
    data_meta_cols = _parse_meta_cols(os.environ.get("DATA_META_COLS", "*"), all_cols)
    # 约束：正文列不进入 metadata，避免在向量库中重复存储大文本。
    # page_content 已经承载正文；metadata 保留结构化过滤字段即可。
    data_meta_cols = [c for c in data_meta_cols if c != data_content_col]

    chunk_strategy = os.environ.get("CHUNK_STRATEGY", "semantic").strip().lower()
    chunk_mode = os.environ.get("CHUNK_MODE", "iter").strip().lower()

    chunker_backend = os.environ.get("CHUNKER_BACKEND", "ollama").strip().lower()
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    ollama_model_name = os.environ.get("OLLAMA_MODEL", "bge-small-zh-v1.5").strip()
    semantic_breakpoint_amount = _env_float(os.environ.get("SEMANTIC_BREAKPOINT_AMOUNT"), default=90.0)
    semantic_add_start_index = _env_bool(os.environ.get("SEMANTIC_ADD_START_INDEX"), default=False)
    semantic_min_chunk_size = _env_int(os.environ.get("SEMANTIC_MIN_CHUNK_SIZE"), default=0)

    recursive_chunk_size = _env_int(os.environ.get("RECURSIVE_CHUNK_SIZE"), default=512)
    recursive_chunk_overlap = _env_int(os.environ.get("RECURSIVE_CHUNK_OVERLAP"), default=64)

    chroma_dir = Path(os.environ.get("CHROMA_DIR", str(here / "chroma_db"))).resolve()
    chroma_collection = os.environ.get("CHROMA_COLLECTION", "travel_docs")
    chroma_reset = _env_bool(os.environ.get("CHROMA_RESET"), default=False)
    chroma_batch_add = _env_int(os.environ.get("CHROMA_BATCH_ADD"), default=64)

    openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    embedding_model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_request_timeout = _env_float(os.environ.get("EMBEDDING_REQUEST_TIMEOUT"), default=60.0)
    embedding_show_progress = _env_bool(os.environ.get("EMBEDDING_SHOW_PROGRESS"), default=False)

    checkpoint_file = Path(
        os.environ.get("CHECKPOINT_FILE", str(here / "ingest_checkpoint.json"))
    ).resolve()
    progress_log_every_docs = _env_int(os.environ.get("PROGRESS_LOG_EVERY_DOCS"), default=20)

    if not openai_api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY：请在 getTravelData/.env 配置")

    if chunk_strategy not in ("semantic", "recursive"):
        raise RuntimeError(f"未知 CHUNK_STRATEGY={chunk_strategy}（semantic|recursive）")
    if chunk_mode not in ("iter", "bulk"):
        raise RuntimeError(f"未知 CHUNK_MODE={chunk_mode}（iter|bulk）")

    if chunker_backend not in ("ollama", "openai"):
        raise RuntimeError(f"未知 CHUNKER_BACKEND={chunker_backend}（ollama|openai）")

    # 语义切块的断点阈值建议在 0~100（percentile），超过范围通常是误配置。
    if not (0 < semantic_breakpoint_amount <= 100):
        raise RuntimeError(
            "SEMANTIC_BREAKPOINT_AMOUNT 必须在 (0, 100] 区间（percentile）"
        )

    # Recursive splitter 的 overlap 必须小于 chunk_size，否则切块行为会退化。
    if recursive_chunk_size <= 0:
        raise RuntimeError("RECURSIVE_CHUNK_SIZE 必须是正整数")
    if recursive_chunk_overlap < 0:
        raise RuntimeError("RECURSIVE_CHUNK_OVERLAP 不能为负数")
    if recursive_chunk_overlap >= recursive_chunk_size:
        raise RuntimeError("RECURSIVE_CHUNK_OVERLAP 必须小于 RECURSIVE_CHUNK_SIZE")

    # Chroma 批量入库批次也做范围校验，避免后续写入阶段才报错。
    if chroma_batch_add <= 0:
        raise RuntimeError("CHROMA_BATCH_ADD 必须是正整数")
    chroma_flush_mode = os.environ.get("CHROMA_FLUSH_MODE", "batch").strip().lower()
    if chroma_flush_mode not in ("batch", "per_doc"):
        raise RuntimeError("CHROMA_FLUSH_MODE 必须是 batch|per_doc")
    if progress_log_every_docs <= 0:
        raise RuntimeError("PROGRESS_LOG_EVERY_DOCS 必须是正整数")

    return IngestConfig(
        data_csv=data_csv,
        data_content_col=data_content_col,
        data_meta_cols=data_meta_cols,
        max_rows=max_rows,
        chunk_strategy=chunk_strategy,
        chunk_mode=chunk_mode,
        chunker_backend=chunker_backend,
        ollama_base_url=ollama_base_url,
        ollama_model_name=ollama_model_name,
        semantic_breakpoint_amount=semantic_breakpoint_amount,
        semantic_add_start_index=semantic_add_start_index,
        semantic_min_chunk_size=semantic_min_chunk_size,
        recursive_chunk_size=recursive_chunk_size,
        recursive_chunk_overlap=recursive_chunk_overlap,
        chroma_dir=chroma_dir,
        chroma_collection=chroma_collection,
        chroma_reset=chroma_reset,
        chroma_batch_add=chroma_batch_add,
        chroma_flush_mode=chroma_flush_mode,
        openai_base_url=openai_base_url,
        openai_api_key=openai_api_key,
        embedding_model=embedding_model,
        embedding_request_timeout=embedding_request_timeout,
        embedding_show_progress=embedding_show_progress,
        checkpoint_file=checkpoint_file,
        progress_log_every_docs=progress_log_every_docs,
    )

