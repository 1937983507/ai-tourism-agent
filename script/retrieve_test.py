from __future__ import annotations

"""
最小检索测试脚本：
- 从现有 Chroma 向量库做相似检索
- 打印 top-k 命中结果（摘要 + metadata）

用法示例：
1) 使用默认查询（不传参数）
   python retrieve_test.py

2) 指定查询与返回条数
   python retrieve_test.py "北京亲子游行程建议" 5

3) 指定查询、返回条数、城市过滤
   python retrieve_test.py "北京亲子游行程建议" 5 北京
"""

import sys

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma as LCChroma

from env_config import load_config


def main() -> None:
    cfg = load_config()

    # 1) 读取查询参数
    query = sys.argv[1] if len(sys.argv) > 1 else "北京亲子游怎么玩"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    city = sys.argv[3] if len(sys.argv) > 3 else "北京"
    if k <= 0:
        raise ValueError("k 必须是正整数")

    # 2) 构建与入库一致的 embedding 配置
    embeddings = OpenAIEmbeddings(
        openai_api_base=cfg.openai_base_url,
        openai_api_key=cfg.openai_api_key,
        model=cfg.embedding_model,
        request_timeout=cfg.embedding_request_timeout,
        show_progress_bar=cfg.embedding_show_progress,
    )

    # 3) 连接本地持久化 Chroma
    vectorstore = LCChroma(
        collection_name=cfg.chroma_collection,
        embedding_function=embeddings,
        persist_directory=str(cfg.chroma_dir),
    )

    # 4) 执行相似检索
    # 过滤条件：仅返回指定城市的 chunk（metadata["source_city"]）
    docs = vectorstore.similarity_search(
        query=query,
        k=k,
        filter={"source_city": city},
    )
    print(f"[query] {query}")
    print(f"[city_filter] {city}")
    print(f"[hits] {len(docs)}")

    # 5) 打印结果摘要，便于人工快速验证检索质量
    for i, doc in enumerate(docs, start=1):
        md = doc.metadata or {}
        preview = doc.page_content.replace("\n", " ")[:220]
        print(f"\n--- hit #{i} ---")
        print(f"title={md.get('title', '')}")
        print(f"url={md.get('url', '')}")
        print(f"source_city={md.get('source_city', '')}")
        print(f"preview={preview}")


if __name__ == "__main__":
    main()
