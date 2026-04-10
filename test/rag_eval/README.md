# RAG 评测使用说明

本文档说明 `test/rag_eval` 下两步评测流程的使用方式：

- Step 1：基于测试问题生成 `question + contexts + answer`
- Step 2：基于 Step 1 输出调用 RAGAS 计算指标并生成报告

## 1. 准备配置

1) 复制配置模板：

```bash
cp test/rag_eval/.env.example test/rag_eval/.env
```

2) 填写 `test/rag_eval/.env` 关键项（完整模板见 `.env.example`）：

- **OpenAI**：`RAG_EVAL_OPENAI_API_KEY`、`RAG_EVAL_OPENAI_BASE_URL`
- **模型**：`RAG_EVAL_LLM_MODEL_NAME`、`RAGAS_LLM_MODEL_NAME`（可选，RAGAS 评判）、`RAG_EVAL_EMBEDDING_MODEL_NAME`
- **Step1 生成答案**：`RAG_EVAL_ANSWER_TEMPERATURE`、`RAG_EVAL_MAX_TOKENS`
- **Step2 RAGAS**（长答案建议保留默认）：`RAG_EVAL_RAGAS_LLM_MAX_TOKENS`、`RAG_EVAL_RAGAS_FAITHFULNESS_ANSWER_MAX_CHARS`、`RAG_EVAL_RAGAS_REFERENCE_MAX_CHARS`
- **GT 自动生成**：`RAG_EVAL_AUTO_GENERATE_GT_ANSWER`、`RAG_EVAL_GT_SOURCE`（`travel_plan` 推荐 / `ragas_testset`）、`RAG_EVAL_GT_TESTSET_SIZE`、`RAG_EVAL_GT_CORPUS_SCOPE`（`full` / `city`）、`RAG_EVAL_GT_MAX_CORPUS_DOCS`，以及行程 GT 相关 `RAG_EVAL_GT_PLAN_*`
- **向量库**：`RAG_EVAL_CHROMA_DIR`、`RAG_EVAL_COLLECTION_NAME`、`RAG_EVAL_TOP_K`、`RAG_EVAL_CITY_METADATA_KEY`
- **输出**：`RAG_EVAL_OUTPUT_DIR`、`RAG_EVAL_RUN_NAME_PREFIX`（与 Step2 默认选取 run 目录有关，见下文）

说明：
- 该 `.env` 是评测专用配置，不依赖项目根目录 `.env`。
- 评测程序会把必要参数映射为主项目 `RagRetrievalService` 可读取的环境变量。

## 2. 维护测试问题

测试问题在：

- `test/rag_eval/test_cases.json`

每条样例至少包含：

- `id`
- `city_name`
- `day_count`
- `customization_requirements`（可选，建议使用 intent 提示词中限定的 token）
- `ground_truth_answer`（可选，建议先填 `null`，后续人工补）

示例：

```json
{
  "id": "tc_001",
  "city_name": "北京",
  "day_count": 3,
  "customization_requirements": "companions=家庭;elderly=有老人;kids=有小孩;pace=慢节奏;diet=不吃辣",
  "ground_truth_answer": null
}
```

### Ground-truth 放置位置与建议格式

- 位置：`test/rag_eval/test_cases.json`
- 字段设计：
  - `ground_truth_answer`：字符串或 `null`
    - 建议写你认为“理想回答”的简洁版本

建议：
- 如果一条样例暂时没有标注，保留 `ground_truth_answer: null`。
- 后续增量标注后，Step 1 会自动透传到 `eval_data.jsonl`。
- 当 `ground_truth_answer` 为空且 `RAG_EVAL_AUTO_GENERATE_GT_ANSWER=true` 时，Step 1 会从 Chroma **按配置拉取整库（或按城市子集）文档**生成参考答案（**不使用**单次 RAG top-k 作为 GT 语料；评测用 `contexts` 仍为 top-k 检索），**不会回写** `test_cases.json`。
  - **`RAG_EVAL_GT_SOURCE=travel_plan`（默认）**：用专用中文行程 prompt + 抽样语料生成多日行程形态的 `ground_truth_answer`，结果中会带 `ground_truth_generator: travel_plan_llm`（失败时可能为 `llm_qa_fallback`）。
  - **`RAG_EVAL_GT_SOURCE=ragas_testset`**：先尝试 RAGAS `TestsetGenerator`，失败再回退到行程 LLM / 短 QA 兜底。

## 3. 运行评测

### 方式 A：一步跑完

```bash
python test/rag_eval/run_rag_eval.py --step all
```

### 方式 B：分步执行

```bash
# Step 1: 生成评测数据
python test/rag_eval/run_step1_generate_eval_data.py

# Step 2: 运行 RAGAS 指标
python test/rag_eval/run_step2_ragas_eval.py
```

#### Step 2：未指定 `--run-dir` 时默认用哪个目录？

未传 `--run-dir` 时，脚本会：

1. 读取 `.env` 中的 **`RAG_EVAL_OUTPUT_DIR`**（默认 `./test/rag_eval/outputs`）。
2. 在该目录下查找**子目录**名称以 **`RAG_EVAL_RUN_NAME_PREFIX` + `_`** 开头的文件夹（默认前缀 `rag_eval`，即匹配 `rag_eval_*`）。
3. 在候选目录中按**最后修改时间（mtime）降序**，取**最新一个**作为本次 Step 2 的 run 目录。

因此默认等价于：**总是对「输出根目录下、最新的 `rag_eval_时间戳` 目录」跑 Step 2**。若你希望固定某次 Step 1 的结果，请显式传入：

```bash
python test/rag_eval/run_step2_ragas_eval.py --run-dir test/rag_eval/outputs/rag_eval_YYYYMMDD_HHMMSS
```

路径可为相对项目根目录的相对路径，或绝对路径。

#### Step 2：日志与调试

- 默认在 stderr 打印 **INFO** 级日志：启动信息、每条用例摘要（context 条数字数、各指标、耗时）、收尾汇总。
- **`python test/rag_eval/run_step2_ragas_eval.py -v`**：输出 **DEBUG**（各 RAGAS 子阶段）。
- **`python test/rag_eval/run_step2_ragas_eval.py -q`**：不打印逐条用例详情，仍保留启动与收尾汇总；与 `-v` 同时使用时不会逐条刷 DEBUG。

## 4. 输出结果说明

每次运行会在 `test/rag_eval/outputs/` 下生成一个时间戳目录，包含：

- `eval_data.jsonl`：Step 1 产物，每条包含
  - `question`
  - `contexts`
  - `answer`
  - `ground_truth_answer`
  - `ground_truth_generator`（自动生成 GT 时：`travel_plan_llm` / `ragas_testset` / `llm_qa_fallback` 等；手工填写则为 `null`）
  - `ground_truth_corpus_scope` / `ground_truth_corpus_doc_count`（自动生成 GT 时：整库或按城市子集及加载条数）
  - 检索 metadata（用于排查）
- `step1_meta.json`：Step 1 的配置快照和数据文件路径
- `ragas_results.jsonl`：Step 2 每条样本的指标结果
- `summary.json`：聚合指标（mean/median）和配置快照
  - 包含 `ground_truth_coverage`，用于查看当前样本集 GT 覆盖率

## 5. Step 2 指标说明

当前仅维护 `ground_truth_answer`，不维护 `ground_truth_contexts`。

### 5.1 每条样本都会算的指标

| 指标 | 含义（简要） |
|------|----------------|
| `faithfulness` | 答案中的陈述有多少能被**本次检索到的 contexts** 支持（长答案会按 `RAG_EVAL_RAGAS_FAITHFULNESS_ANSWER_MAX_CHARS` 截断后再评）。 |
| `context_relevance` | 检索到的上下文与**用户问题**的相关程度。 |
| `answer_relevancy` | 答案与问题的相关度（RAGAS 实现；长结构化行程下绝对值可能偏低，宜做版本对比）。 |

### 5.2 需要非空 `ground_truth_answer` 的指标

若该条 `ground_truth_answer` 为空，下列项在 `ragas_results.jsonl` 中为 `null`，且汇总里对应 `scored_count` 会少于样本数。

| 指标 | 含义（简要） |
|------|----------------|
| `context_recall` | 参考答案中的陈述，有多少可归因到**当前检索上下文**（检索是否“够全”）。reference 会按 `RAG_EVAL_RAGAS_REFERENCE_MAX_CHARS` 截断。 |
| `context_precision_with_reference` | 各检索块对**写出该参考答案**是否有用（检索噪声与精度）。 |
| `gt_answer_embedding_similarity` | `answer` 与 `ground_truth_answer` 的 embedding **余弦相似度**（约 `[-1, 1]`，越高越接近）。 |

`summary.json` 中部分指标含 `failed_count`，表示该 RAGAS 调用在少数样本上异常（其余样本仍写入结果）。

### 5.3 与经典 IR recall 的区别

RAGAS 的 **context recall** 是「参考答案 + LLM 归因」下的检索覆盖度，**不是**带人工标注 doc id 的 **recall@k**。若需要 recall@k，需另行准备 qrels 与检索 doc id 列表再实现。
