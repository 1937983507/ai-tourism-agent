from __future__ import annotations

from typing import Iterable, Iterator

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def _build_recursive_splitter(*, chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    """
    递归切块（经典中文优先参数）。
    你给的经典参数我原样采用，只把 splitter 初始化封装起来。

    separators 层级从“段落/行程块”到“句子标点”，确保中文语义优先切割：
    - "\n\n" / "\n"：按段落、按换行
    - "。！？"：句号/感叹号/问号
    - "，"：最后兜底按逗号切，避免过长
    """

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\n",
            "\n",
            "。",
            "！",
            "？",
            "，",
        ],
        length_function=len,
    )


def iter_recursive_chunks(
    *,
    documents: Iterable[Document],
    chunk_mode: str,  # iter|bulk
    chunk_size: int,
    chunk_overlap: int,
) -> Iterator[Document]:
    """
    RecursiveCharacterTextSplitter 切块，提供 iter/bulk 两种生成模式。

    这里的 chunk 是纯规则/长度驱动（不像 SemanticChunker 依赖语义断点），
    适合作为“并列切块策略”的候选。
    """

    text_splitter = _build_recursive_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    mode = chunk_mode.lower().strip()
    if mode == "bulk":
        docs = list(documents)
        print(f"[chunk][recursive] bulk original_docs={len(docs)}")
        for cd in text_splitter.split_documents(docs):
            yield cd
        return

    if mode != "iter":
        raise RuntimeError(f"未知 CHUNK_MODE={chunk_mode}（iter|bulk）")

    chunk_total = 0
    for doc_idx, doc in enumerate(documents):
        split_docs = text_splitter.split_documents([doc])
        if doc_idx < 2:
            print(f"[chunk][recursive][debug] doc_idx={doc_idx} chunk_count={len(split_docs)}")
            if split_docs:
                print(f"[chunk][recursive][debug] chunk_preview={split_docs[0].page_content[:120]}")
        for cd in split_docs:
            chunk_total += 1
            yield cd
    print(f"[chunk][recursive] iter done. chunk_total={chunk_total}")

