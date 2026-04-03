# RAG 数据处理与入库（Chroma + 城市过滤）

本目录下的脚本用于把 `data.csv` 切块（`semantic` 或 `recursive`）并写入本地 Chroma 向量库，metadata 会保留 CSV 的各列字段；检索时可以通过城市字段（默认 `source_city`）进行过滤。

## 1. 前置准备

### 1.1 确认数据与目录

- 输入数据：默认使用 `.\data.csv`
- 输出向量库：由 `CHROMA_DIR` 和 `CHROMA_COLLECTION` 决定（默认在 `../chroma_db` 下的 `travel_docs` 集合）

### 1.2 配置环境变量

1. 将 `.env.example` 复制为 `.env`
2. 至少填写 `OPENAI_API_KEY`（用于：把 chunk 写入 Chroma 向量库的 OpenAI embeddings；即使你只用 `CHUNKER_BACKEND=ollama` 做语义切块，向量写入仍需要 OpenAI）

下面是脚本真正用到的主要环境变量解释：

### 1.2.1 OpenAI / Embeddings（向量写入 & 检索一致性）

- `OPENAI_BASE_URL`：OpenAI 兼容接口地址（默认 `https://api.openai.com/v1`）
- `OPENAI_API_KEY`：OpenAI API Key（必填）
- `EMBEDDING_MODEL`：embedding 模型名（默认 `text-embedding-3-small`）
  - 向量写入 Chroma 使用的也是这个模型
  - 同时：当 `CHUNKER_BACKEND=openai` 时，SemanticChunker 判断语义断点也会使用这个模型
- `EMBEDDING_REQUEST_TIMEOUT`：embedding 请求超时时间（秒，默认 60）
- `EMBEDDING_SHOW_PROGRESS`：是否显示 embedding 进度条（true/false）

### 1.2.2 Chroma（持久化向量库）

- `CHROMA_DIR`：Chroma persist 目录（默认 `../chroma_db`）
- `CHROMA_COLLECTION`：集合名（默认 `travel_docs`）
- `CHROMA_RESET`：是否清空/重建 collection（`true`/`false`）
- `CHROMA_BATCH_ADD`：写入批次大小（避免一次性请求过大；默认 64）
- `CHROMA_FLUSH_MODE`：写入 flush 策略（`batch` / `per_doc`）

### 1.2.3 输入数据（CSV -> Document -> metadata）

- `DATA_CSV`：CSV 路径（默认 `./data.csv`）
- `DATA_CONTENT_COL`：正文列名（默认 `text`）
  - `page_content` 就来自这一列
- `DATA_META_COLS`：metadata 列集合（默认 `*`，即全列）
  - 程序会自动排除 `DATA_CONTENT_COL`，避免把正文重复存进 metadata
  - 你用于城市过滤的字段必须在 metadata 中存在，并且值类型/格式要和检索参数一致

> 城市过滤字段约定：当前 agent / `retrieve_test.py` 默认用 `metadata["source_city"]` 做过滤。
> 因此确保 CSV 中有 `source_city` 列，且写入后该字段值类似 `北京`、`成都`（不要带多余空格/后缀导致不匹配）。

### 1.2.4 切块（chunking）

- `CHUNK_STRATEGY`：`semantic` 或 `recursive`
- `CHUNK_MODE`：`iter`（省内存）或 `bulk`（更快但占内存）
- `CHUNKER_BACKEND`：semantic chunk 的“切块用 embedding”后端，仅对 `CHUNK_STRATEGY=semantic` 生效
  - `ollama`：走本地 Ollama embedding（语义断点判断用）
  - `openai`：走 OpenAI embedding（语义断点判断用，模型名来自 `EMBEDDING_MODEL`）

语义切块参数（`CHUNK_STRATEGY=semantic`）：
- `SEMANTIC_BREAKPOINT_AMOUNT`：语义断点阈值（percentile，默认 90）
- `SEMANTIC_ADD_START_INDEX`：是否在 chunk metadata 里附加 start_index（默认 false）
- `SEMANTIC_MIN_CHUNK_SIZE`：语义 chunk 最小长度（默认 0，不启用强制最小值）

递归切块参数（`CHUNK_STRATEGY=recursive`）：
- `RECURSIVE_CHUNK_SIZE`：切块大小（默认 512）
- `RECURSIVE_CHUNK_OVERLAP`：切块重叠（默认 64）

### 1.2.5 Ollama（仅当 `CHUNKER_BACKEND=ollama`）

如果你设置 `CHUNKER_BACKEND=ollama`，需要提供：

- `OLLAMA_BASE_URL`：Ollama 服务地址（默认 `http://localhost:11434`）
- `OLLAMA_MODEL`：Ollama embedding 模型名

建议模型（更适合中文向量语义切块与检索）：
- `quentinz/bge-large-zh-v1.5:latest`

安装/拉取步骤（在启动脚本前执行）：

```bash
# 1) 安装并启动 Ollama（按你系统选择方式安装）
# 2) 拉取推荐 embedding 模型
ollama pull quentinz/bge-large-zh-v1.5:latest
```

说明：
- 该模型只用于 SemanticChunker 的“语义断点判断”（切块边界），向量写入 Chroma 仍使用 OpenAI embeddings（仍需 `OPENAI_API_KEY`）。

### 1.2.6 其他常用参数

- `MAX_ROWS`：只处理 CSV 前 N 行（默认 0 表示全量；用于快速验证代码）
- `CHECKPOINT_FILE`：断点续传文件路径（默认 `./script/ingest_checkpoint.json`，但建议你直接查看脚本工作目录）
- `PROGRESS_LOG_EVERY_DOCS`：每完成多少“原始 CSV 行”（row）打印一次进度

## 2. 处理与入库流程（跑通顺序）

建议严格按下面顺序执行：

### 2.1 首次入库 / 全量重建

在 `.\script` 目录下执行：

```bash
python run.py
```

脚本内部的逻辑顺序：

1. `env_config.load_config()`：读取 `.env`，生成强类型 `IngestConfig`
2. `csv_loader.iter_documents_from_csv()`：
   - 将 CSV 每一行生成一个原始 `Document`
   - `page_content` 使用 `DATA_CONTENT_COL`（默认 `text`）
   - `metadata` 使用 `DATA_META_COLS`（默认 `*`，即全列；并会自动排除 `DATA_CONTENT_COL`，避免把正文重复塞进 metadata）
   - metadata 里增加 `__row_index`（用于断点续传）
3. 切块阶段：
   - `CHUNK_STRATEGY=semantic`：使用 `SemanticChunker`
   - `CHUNK_STRATEGY=recursive`：使用 `RecursiveCharacterTextSplitter`
   - 两种切块器都会尽量“保留原始 metadata”，保证后续过滤能按城市生效
4. 入库阶段：`vector_store.ChromaWriter.write_documents()`：
   - 使用 `OPENAI_API_KEY + EMBEDDING_MODEL`（默认 `text-embedding-3-small`）对 chunk 向量化
   - 写入本地 Chroma persist 目录
   - 根据 `CHROMA_RESET` 决定是否先清空 collection

### 2.2 断点续传（checkpoint）

- checkpoint 文件：`./script/ingest_checkpoint.json`（实际路径取决于你运行脚本时的工作目录，默认就在 `script/` 目录下）
- 文件内容会记录 `last_completed_row_index`，表示“已成功写入完成的最后一行 CSV 行号”
- `run.py` 会在启动时读取 checkpoint：
  - 如果存在 checkpoint，则从 `last_done + 1` 开始继续入库
  - 如果 checkpoint 不存在，则从 `start_row=0` 开始

全量重建时建议删除 checkpoint 或改 checkpoint 位置/文件名。

### 2.3 入库质量检查（强烈建议）

#### 2.3.1 集合概览

```bash
python inspect_chroma.py
```

输出主要包括：
- collection chunk_total（向量条数）
- token/char 长度分布（粗略评估 chunk 是否过短/过长）
- metadata 覆盖率（检查 `source_city` 等过滤字段是否完整）

#### 2.3.2 城市过滤检索测试

```bash
python retrieve_test.py "北京亲子游行程建议" 5 北京
```

验证点：
- `filter={"source_city": city}` 是否能命中（返回 hits > 0）
- 命中内容是否与 query 偏好匹配（例如亲子游相关）

## 3. 关键配置建议

### 3.1 chunk 选择

- MVP 期：`CHUNK_STRATEGY=semantic` 通常更能保持语义段落（更利于 RAG 检索）
- 如果你希望更稳定的 chunk 长度：`CHUNK_STRATEGY=recursive`（参数 `RECURSIVE_CHUNK_SIZE/OVERLAP`）

### 3.2 语义切块的 embedding 后端

- `CHUNKER_BACKEND=ollama`：依赖本地 Ollama embedding
- `CHUNKER_BACKEND=openai`：使用 OpenAI embeddings 做语义断点

补充：
- 你要让 semantic chunk 边界与向量 embedding 更一致：建议 `CHUNKER_BACKEND=openai` 时保证 `EMBEDDING_MODEL` 与 Chroma 写入用的 `EMBEDDING_MODEL` 相同（当前就是同一配置项）。


## 4. 与 Agent 侧的对齐要求（非常重要）

Agent 侧检索时默认通过 metadata 字段过滤：
- 城市过滤 key：默认 `source_city`

确保你的 `DATA_META_COLS` 保证在 Chroma metadata 中存在 `source_city`，并且其值格式与检索参数（如 `北京`）完全一致。

