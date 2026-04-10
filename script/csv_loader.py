from __future__ import annotations

import csv
import inspect
from pathlib import Path
from typing import Dict, Iterable, Iterator, List

import pandas as pd
from pandas.errors import ParserError
from langchain_core.documents import Document

_READ_CSV_SUPPORTS_ENCODING_ERRORS = "encoding_errors" in inspect.signature(
    pd.read_csv
).parameters


def detect_encoding_by_header(csv_path: Path) -> str:
    """
    只读第一行猜测编码，适配你 Windows 上 CSV 常见的 `utf-8-sig / gb18030 / utf-16`。

    为什么只读第一行：
    - 速度快
    - 避免一次性读取大文件
    - 大多数 CSV 的表头编码规律一致
    """

    encodings = ("utf-8-sig", "gb18030", "utf-16")
    with csv_path.open("rb") as f:
        b = f.readline()
    if not b:
        return "utf-8-sig"
    for enc in encodings:
        try:
            b.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8-sig"


def iter_documents_from_csv(
    *,
    csv_path: Path,
    content_col: str,
    meta_cols: List[str],
    max_rows: int,
    start_row: int = 0,
) -> Iterator[Document]:
    """
    把一行 CSV -> 一个原始 Document：
    - `page_content` = content_col（用于切块/embedding）
    - `metadata` = meta_cols（用于检索时精准过滤）

    约定：
    - metadata 的所有值都会被转成 `str`，避免 Chroma/LangChain 在过滤时遇到类型不一致问题。
    - 空值会用 pandas.fillna("") 统一补成空字符串。
    """

    # 先用“表头探测编码”作为优先候选，再做多编码回退，避免大文件中段出现解码错误时直接失败。
    first_guess = detect_encoding_by_header(csv_path)
    strict_order = [first_guess, "utf-8-sig", "gb18030", "utf-16"]
    # 宽松解码时优先 gb18030：表头常为 ASCII 会被误判为 UTF-8，正文实为 GB 系；若再先用 UTF-8+replace 会大面积乱码。
    replace_order = ["gb18030", "utf-8-sig", "utf-16"]

    def _read(enc: str, *, encoding_errors: str | None) -> pd.DataFrame:
        kw: dict = {"encoding": enc, "dtype": str}
        if encoding_errors is not None and _READ_CSV_SUPPORTS_ENCODING_ERRORS:
            kw["encoding_errors"] = encoding_errors
        return pd.read_csv(csv_path, **kw).fillna("")

    strict_tried: List[str] = []
    df = None
    for enc in strict_order:
        if enc in strict_tried:
            continue
        strict_tried.append(enc)
        try:
            df = _read(enc, encoding_errors=None)
            break
        except (UnicodeDecodeError, ParserError):
            continue

    replace_tried: List[str] = []
    if df is None and _READ_CSV_SUPPORTS_ENCODING_ERRORS:
        for enc in replace_order:
            if enc in replace_tried:
                continue
            replace_tried.append(enc)
            try:
                df = _read(enc, encoding_errors="replace")
                break
            except (UnicodeDecodeError, ParserError):
                continue

    if df is None:
        detail = f"strict={strict_tried}"
        if replace_tried:
            detail += f", replace={replace_tried}"
        raise RuntimeError(f"无法解码或解析 CSV（{detail}）：{csv_path}")

    # 显式校验正文列，避免列名写错时静默跳过全部数据，导致“看起来成功、实际 0 入库”。
    if content_col not in df.columns:
        raise RuntimeError(
            f"DATA_CONTENT_COL 不存在: {content_col}。可选列: {list(df.columns)}"
        )

    # 二次保护：即使上游误传，也不把正文列重复写入 metadata。
    effective_meta_cols = [col for col in meta_cols if col != content_col]

    # meta 列同样做显式校验，便于尽早发现配置问题。
    missing_meta_cols = [col for col in effective_meta_cols if col not in df.columns]
    if missing_meta_cols:
        raise RuntimeError(
            f"DATA_META_COLS 包含不存在的列: {missing_meta_cols}。可选列: {list(df.columns)}"
        )

    if max_rows and max_rows > 0:
        df = df.head(max_rows)

    # 逐行迭代生成 Document：保持流式处理，避免大 CSV 带来额外峰值内存。
    for row_idx, row in df.iterrows():
        if row_idx < start_row:
            continue
        content = str(row.get(content_col, "")).strip()
        if not content:
            continue
        metadata: Dict[str, str] = {}
        for col in effective_meta_cols:
            metadata[col] = str(row.get(col, "")).strip()
        # 内部断点字段：标记“这是 CSV 第几行（0-based）”。
        metadata["__row_index"] = str(row_idx)
        yield Document(page_content=content, metadata=metadata)

