from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma as LCChroma


@dataclass(frozen=True)
class ChromaWriter:
    # Chroma 持久化目录，明确为 Path 便于类型检查与 IDE 提示
    chroma_dir: Path
    collection: str
    reset: bool
    batch_add: int
    flush_mode: str  # batch|per_doc

    openai_base_url: str
    openai_api_key: str
    embedding_model: str
    embedding_request_timeout: float
    embedding_show_progress: bool
    checkpoint_file: Path
    progress_log_every_docs: int

    def _safe_int(self, value: object, default: int = -1) -> int:
        try:
            return int(str(value))
        except Exception:
            return default

    def _read_checkpoint(self) -> dict:
        if not self.checkpoint_file.exists():
            return {
                "version": 1,
                "last_completed_row_index": -1,
                "next_row_index": 0,
                "last_completed_url": "",
                "last_completed_title": "",
            }
        try:
            return json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
        except Exception:
            return {
                "version": 1,
                "last_completed_row_index": -1,
                "next_row_index": 0,
                "last_completed_url": "",
                "last_completed_title": "",
            }

    def _save_checkpoint(self, *, row_idx: int, url: str, title: str) -> None:
        old = self._read_checkpoint()
        old_idx = self._safe_int(old.get("last_completed_row_index", -1))
        # 仅向前推进，避免异常场景把断点回退。
        if row_idx <= old_idx:
            return

        payload = {
            "version": 1,
            "last_completed_row_index": row_idx,
            "next_row_index": row_idx + 1,
            "last_completed_url": url,
            "last_completed_title": title,
            "estimated_by": "runtime_successful_writes",
            "notes": "Updated only after successful add_documents batches.",
        }
        self.checkpoint_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _build_embeddings(self) -> OpenAIEmbeddings:
        return OpenAIEmbeddings(
            openai_api_base=self.openai_base_url,
            openai_api_key=self.openai_api_key,
            model=self.embedding_model,
            request_timeout=self.embedding_request_timeout,
            show_progress_bar=self.embedding_show_progress,
        )

    def write_documents(self, documents: Iterable[Document]) -> None:
        """把 chunk documents 写入 Chroma（持久化）。

        关键点：
        - 使用 OpenAIEmbeddings 把 `Document.page_content` 向量化
        - `Document.metadata` 会随向量一起存入 Chroma，便于后续精确过滤
        - 为了控制 API/写入压力：按 `batch_add` 批次 add_documents
        - `reset=True` 时，会先 delete_collection 再重新写入
        """
        # 防御式校验：避免 batch_add <= 0 导致批处理逻辑异常。
        if self.batch_add <= 0:
            raise ValueError("CHROMA_BATCH_ADD 必须是正整数")
        if self.progress_log_every_docs <= 0:
            raise ValueError("PROGRESS_LOG_EVERY_DOCS 必须是正整数")

        embeddings = self._build_embeddings()

        # 注意：Chroma 的 persist_directory 是本地存储目录
        vectorstore = LCChroma(
            collection_name=self.collection,
            embedding_function=embeddings,
            persist_directory=str(self.chroma_dir),
        )

        if self.reset:
            # delete_collection 会让整个 collection 相关索引/数据重新开始
            print(f"[chroma] reset collection: {self.collection}")
            # 兼容“首次写入还没有 collection”场景：删除失败不应中断流程。
            try:
                vectorstore.delete_collection()
            except Exception as e:  # noqa: BLE001 - 删除不存在集合时允许继续
                print(f"[chroma] skip delete_collection: {e}")
            vectorstore = LCChroma(
                collection_name=self.collection,
                embedding_function=embeddings,
                persist_directory=str(self.chroma_dir),
            )

        if self.flush_mode == "per_doc":
            # 每次检测到 row_index（原始 CSV 行）变化，就立即写入上一篇的 chunks。
            batch: List[Document] = []
            total_added = 0
            current_doc_row_idx = -1
            current_doc_url = ""
            current_doc_title = ""

            def flush_doc(doc_batch: List[Document]) -> None:
                nonlocal total_added
                if not doc_batch:
                    return
                try:
                    vectorstore.add_documents(doc_batch)
                except Exception:
                    first_md = doc_batch[0].metadata if doc_batch else {}
                    print(
                        "[chroma][error] per_doc write failed "
                        f"first_row_index={first_md.get('__row_index', '')} "
                        f"first_url={first_md.get('url', '')} "
                        f"first_title={first_md.get('title', '')}"
                    )
                    raise

                md0 = doc_batch[0].metadata or {}
                row_idx = self._safe_int(md0.get("__row_index", -1))
                url = str(md0.get("url", ""))
                title = str(md0.get("title", ""))
                total_added += len(doc_batch)

                if row_idx >= 0:
                    self._save_checkpoint(row_idx=row_idx, url=url, title=title)
                    if (row_idx + 1) % self.progress_log_every_docs == 0:
                        print(
                            "[progress] "
                            f"当前已完成第 {row_idx + 1} 篇游记 "
                            f"url={url}"
                        )
                print(f"[chroma] added per_doc batch={len(doc_batch)} total_added={total_added}")

            for cd in documents:
                md = cd.metadata or {}
                row_idx = self._safe_int(md.get("__row_index", -1))

                if not batch:
                    current_doc_row_idx = row_idx
                    current_doc_url = str(md.get("url", ""))
                    current_doc_title = str(md.get("title", ""))
                elif row_idx != current_doc_row_idx:
                    flush_doc(batch)
                    batch = []
                    current_doc_row_idx = row_idx
                    current_doc_url = str(md.get("url", ""))
                    current_doc_title = str(md.get("title", ""))

                batch.append(cd)

            if batch:
                flush_doc(batch)

            print(f"[chroma] done. total_added={total_added}")
            return

        # 默认：batch 模式（按 CHROMA_BATCH_ADD 累积 chunk，再写入）
        batch: List[Document] = []
        total_added = 0
        current_row_idx = -1
        current_url = ""
        current_title = ""

        for cd in documents:
            batch.append(cd)
            if len(batch) >= self.batch_add:
                try:
                    vectorstore.add_documents(batch)
                except Exception:
                    # 失败时打印当前批次首条，便于快速定位到具体游记。
                    first_md = batch[0].metadata if batch else {}
                    print(
                        "[chroma][error] batch write failed "
                        f"first_row_index={first_md.get('__row_index', '')} "
                        f"first_url={first_md.get('url', '')} "
                        f"first_title={first_md.get('title', '')}"
                    )
                    raise
                total_added += len(batch)
                for c in batch:
                    md = c.metadata or {}
                    row_idx = self._safe_int(md.get("__row_index", -1))
                    if row_idx < 0:
                        continue
                    url = str(md.get("url", ""))
                    title = str(md.get("title", ""))
                    if current_row_idx < 0:
                        current_row_idx = row_idx
                        current_url = url
                        current_title = title
                    elif row_idx != current_row_idx:
                        self._save_checkpoint(
                            row_idx=current_row_idx,
                            url=current_url,
                            title=current_title,
                        )
                        if (current_row_idx + 1) % self.progress_log_every_docs == 0:
                            print(
                                "[progress] "
                                f"当前已完成第 {current_row_idx + 1} 篇游记 "
                                f"url={current_url}"
                            )
                        current_row_idx = row_idx
                        current_url = url
                        current_title = title
                print(f"[chroma] added batch={len(batch)} total_added={total_added}")
                batch = []

        if batch:
            try:
                vectorstore.add_documents(batch)
            except Exception:
                first_md = batch[0].metadata if batch else {}
                print(
                    "[chroma][error] final batch write failed "
                    f"first_row_index={first_md.get('__row_index', '')} "
                    f"first_url={first_md.get('url', '')} "
                    f"first_title={first_md.get('title', '')}"
                )
                raise
            total_added += len(batch)
            for c in batch:
                md = c.metadata or {}
                row_idx = self._safe_int(md.get("__row_index", -1))
                if row_idx < 0:
                    continue
                url = str(md.get("url", ""))
                title = str(md.get("title", ""))
                if current_row_idx < 0:
                    current_row_idx = row_idx
                    current_url = url
                    current_title = title
                elif row_idx != current_row_idx:
                    self._save_checkpoint(
                        row_idx=current_row_idx,
                        url=current_url,
                        title=current_title,
                    )
                    if (current_row_idx + 1) % self.progress_log_every_docs == 0:
                        print(
                            "[progress] "
                            f"当前已完成第 {current_row_idx + 1} 篇游记 "
                            f"url={current_url}"
                        )
                    current_row_idx = row_idx
                    current_url = url
                    current_title = title

        # 任务正常结束时，最后一篇也标记为已完成。
        if current_row_idx >= 0:
            self._save_checkpoint(
                row_idx=current_row_idx,
                url=current_url,
                title=current_title,
            )

        print(f"[chroma] done. total_added={total_added}")

