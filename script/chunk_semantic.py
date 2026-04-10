from __future__ import annotations

from typing import Iterable, Iterator, Optional

from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import OllamaEmbeddings


def _build_chunk_embeddings(
    *,
    backend: str,
    ollama_base_url: str,
    ollama_model_name: str,
    openai_base_url: str,
    openai_api_key: str,
    openai_embedding_model: str,
):
    """为 SemanticChunker 构建“切块用”的 embeddings。

    注意：SemanticChunker 本质上需要一个 embedding 模型来判断语义断点。

    - backend=ollama：使用本地 Ollama embedding（bge 模型）
    - backend=openai：使用远程 OpenAI embedding（需要 OPENAI_API_KEY）
    """
    backend = backend.lower().strip()
    if backend == "openai":
        # 用远程 embedding 作为切块 embedding
        return OpenAIEmbeddings(
            openai_api_base=openai_base_url,
            openai_api_key=openai_api_key,
            model=openai_embedding_model,
        )

    if backend == "ollama":
        return OllamaEmbeddings(
            base_url=ollama_base_url,
            model=ollama_model_name,
        )

    raise RuntimeError(f"未知 chunker_backend={backend}（ollama|openai）")


def iter_semantic_chunks(
    *,
    documents: Iterable[Document],
    chunk_mode: str,  # iter|bulk
    chunker_backend: str,  # ollama|openai
    ollama_base_url: str,
    ollama_model_name: str,
    semantic_breakpoint_amount: float,
    semantic_add_start_index: bool,
    semantic_min_chunk_size: int,
    openai_base_url: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    openai_embedding_model: str = "text-embedding-3-small",
) -> Iterator[Document]:
    """
    语义切块：
    - 使用 LangChain 的 SemanticChunker（现成接口）
    - 输出 chunk Document，metadata 会保留原始 Document metadata

    这就是你要的“语义切块 + 保留元数据”核心步骤。

    iter/bulk：
    - iter：逐条原始 doc split（省内存，便于你跑大数据）
    - bulk：一次性对一组 doc split（更快，但会占用更多内存）
    """

    if chunker_backend.lower() == "openai":
        if not openai_base_url or not openai_api_key:
            raise RuntimeError("chunker_backend=openai 需要 openai_base_url/openai_api_key")
    else:
        # 非 openai 后端（当前是 ollama）时，不强制要求 openai_* 参数。
        openai_base_url = openai_base_url or ""
        openai_api_key = openai_api_key or ""

    embeddings = _build_chunk_embeddings(
        backend=chunker_backend,
        ollama_base_url=ollama_base_url,
        ollama_model_name=ollama_model_name,
        openai_base_url=openai_base_url,
        openai_api_key=openai_api_key,
        openai_embedding_model=openai_embedding_model,
    )

    text_splitter = SemanticChunker(
        embeddings,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=semantic_breakpoint_amount,
        # 强制替换默认英文分句规则，兼容中文/英文标点，并把换行也视为候选边界。
        # 说明：有些游记是“无句号但有换行”结构（标题、清单、行程），
        # 仅靠标点会漏分，这里额外按 \n{1,} 切分。
        sentence_split_regex=r"(?<=[。！？.!?])\s+|\n{1,}",
        add_start_index=semantic_add_start_index,
        min_chunk_size=semantic_min_chunk_size if semantic_min_chunk_size > 0 else None,
    )

    mode = chunk_mode.lower().strip()
    if mode == "bulk":
        # bulk 模式：先把 documents 全部物化成 list，然后 split_documents
        # 这会增加内存占用，但切块速度可能更快。
        docs = list(documents)
        print(f"[chunk][semantic] bulk original_docs={len(docs)}")
        for cd in text_splitter.split_documents(docs):
            yield cd
        return

    if mode != "iter":
        raise RuntimeError(f"未知 CHUNK_MODE={chunk_mode}（iter|bulk）")

    chunk_total = 0
    for doc_idx, doc in enumerate(documents):
        # iter 模式：每次只对一个原始 Document split，
        # 避免一次性把所有文档读入内存。
        split_docs = text_splitter.split_documents([doc])
        if doc_idx < 2:
            # 重点调试信息：前几条 doc 的 chunk 情况
            print(f"[chunk][semantic][debug] doc_idx={doc_idx} chunk_count={len(split_docs)}")
            if split_docs:
                print(f"[chunk][semantic][debug] chunk_preview={split_docs[0].page_content[:120]}")
        for cd in split_docs:
            chunk_total += 1
            yield cd
    print(f"[chunk][semantic] iter done. chunk_total={chunk_total}")

