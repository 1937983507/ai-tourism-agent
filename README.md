## AI 智能旅游规划助手（Agent 服务）

> **访问地址**：[https://www.aitrip.chat/](https://www.aitrip.chat/)  
> **欢迎体验智能旅游规划服务！**

## 目录

- [项目简介](#项目简介)
- [核心特性](#核心特性)
- [演示](#演示)
- [核心特性与架构特点](#核心特性与架构特点)
- [系统整体架构](#系统整体架构)
- [技术栈与依赖](#技术栈与依赖)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [接口与集成](#接口与集成)
- [开发扩展指南](#开发扩展指南)
- [TODO](#todo)
- [参考文档](#参考文档)
- [License](#license)
- [联系与贡献](#联系与贡献)

## 项目简介

**AI-Tourism Agent** 是智能旅游规划系统中的 **AI 规划引擎**，基于 **LangGraph、FastAPI、OpenAI** 等技术栈构建。

本服务接收后端转发的用户对话请求，通过 LangGraph 工作流完成意图识别、对话引导、并行获取天气与景点数据，并生成个性化旅游路线与结构化攻略。不直接面向用户，仅与 **ai-tourism-backend** 通过 HTTP/SSE 通信；会话与历史由后端管理，本服务负责 Checkpoint 状态持久化以支持多轮规划。

## 核心特性

- **意图识别与对话引导**：LLM 意图识别 + 规则降级，支持多轮对话以补齐城市/天数等用户需求信息
- **偏好/定制需求抽取**：在意图识别阶段提取用户定制化需求（如家庭/情侣/不吃辣/人文/自然等），并支持多轮追加/覆盖
- **高性能链路**：天气与 POI 并行获取、SSE 流式输出、SQLite/PostgreSQL 会话持久化
- **RAG 检索增强**：在旅游推荐链路并行检索向量库片段（按城市过滤），将检索结果注入规划提示以增强路线参考
- **工具与输出**：天气（OpenWeather/和风）、POI 调用后端接口，输出 JSON 攻略并可回调后端落库


---

## 演示

### 前端效果截图
![前端效果图](./assets/界面图.png)

### 视频效果
![演示视频](./assets/demo.gif)

---

## 核心特性与架构特点

### 1. 智能意图识别

- **LLM 意图识别**：使用大语言模型识别用户意图（旅游 / 非旅游 / 需要引导），并抽取城市、天数等关键信息；支持与下游对话引导、并行数据获取无缝衔接。
- **规则匹配降级**：当 LLM 调用失败或超时时，自动降级到基于规则的 `SimpleIntentExtractor`，保证基础可用的同时减少对单一模型的依赖。

### 2. 智能对话引导

- **多轮对话**：在信息不完整时，通过友好追问（如「请问您想去哪个城市？」「计划玩几天？」）引导用户补全信息，再进入规划流程。
- **上下文理解**：基于 LangGraph 的 Checkpoint 与对话历史，在同一会话内保持上下文，避免重复询问。
- **分步处理**：先由 LLM 从当前轮次提取结构化信息（JSON），再生成面向用户的自然语言回复，便于后续扩展与调试。

### 3. 高性能架构

- **RAG 并行检索**：在旅游推荐链路并行触发RAG检索召回，与天气/景点获取同一批次完成以降低总体延迟
- **并行数据获取**：在意图为「旅游且信息完整」时，通过 LangGraph 的并行节点同时请求天气与 POI，缩短首字响应时间。
- **流式响应**：使用 SSE 将 LLM 生成内容实时推送到后端再至前端，提升体验；格式与后端约定一致，便于网关透传。
- **状态持久化**：支持 memory / sqlite / postgres 三种 Checkpoint 后端，单机推荐 sqlite，多实例或分布式部署可选用 postgres，便于会话恢复与水平扩展。

### 4. 工具集成

- **天气预报**：支持 OpenWeather API 与和风天气 API，通过环境变量 `WEATHER_PROVIDER` 切换；和风需配置 JWT 与私钥，详见配置说明。
- **景点搜索**：通过 HTTP 调用 **ai-tourism-backend** 提供的 POI 接口（如 `/tool/poi`），依赖后端完成鉴权与数据源封装。
- **结构化输出**：规划结果生成 JSON 格式旅游攻略，并可通过回调接口提交给后端落库或展示，便于前端地图与行程展示。

### 5. RAG 向量检索增强

- **RAG 节点**：新增 `rag_retrieve` 节点，在 `weather` 与 `poi` 并行获取的同时检索游记/攻略片段。
- **城市筛选**：检索时通过 `metadata["source_city"]`（可配置）过滤，仅返回当前城市相关内容。
- **向量化模型**：默认使用 `text-embedding-3-small`（可配置），embedding 的 `base_url/api_key` 与 LLM 一致。
- **输出注入**：检索结果生成 `rag_context`，并在 `route-planning-user-prompt.txt` 中作为 `{rag_info}` 注入路线规划 LLM 提示中，作为“补充灵感”；天气/POI 仍然是主要依据。
- **数据准备**：向量库由 `script/run.py` 通过离线切块/入库流程构建，详见 `script/RAG_DATA_PROCESSING_README.md`。

---

## 系统整体架构

**AI 智能旅游规划系统**采用前后端分离架构。用户在前端输入自然语言后，请求经过后端 API 服务转发到 **Python Agent 服务**，由 Agent 服务调用工具获取天气、景点等信息，生成旅游路线规划。后端 API 服务负责处理流式返回、会话管理和数据持久化。

> 默认联调端口（以各项目配置为准）：前端 `3001`，后端 `8290`，Agent `8291`。本服务由后端网关转发请求，不直接对公网暴露时请注意防火墙与鉴权配置。

### 分层架构

整体为前端 → 后端 → Agent 三层，下图**侧重 Agent** 结构；前端与后端仅作概要。

```
┌─────────────────────────────────────────┐
│  前端 (Vue) · ai-tourism-frontend       │
│  - 对话与地图组件                        │
│  - SSE 消费                             │
│  - 会话列表                             │
│  - 用户认证                             │
└─────────────────┬──────────────────────┘
                  │ HTTP/SSE
┌─────────────────▼────────────────────────────┐
│   后端 API 服务 (Spring Boot)                 │
│   ai-tourism-backend                          │
│   - API 网关与请求路由                         │
│   - 会话与消息管理                             │
│   - 用户认证与权限管理                         │
└─────────────────┬────────────────────────────┘
                  │ HTTP/SSE
┌─────────────────▼───────────────────────────────────────────────────────┐
│  Python Agent 服务 · ai-tourism-agent                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ API 层 (FastAPI)                                                  │   │
│  │  - /agent/health, /agent/tools                                    │   │
│  │  - /agent/chat-stream (SSE), /agent/chat                          │   │
│  │  - 参数校验 (ChatRequest)、EventSourceResponse                    │   │
│  └───────────────────────────┬─────────────────────────────────────┘   │
│  ┌───────────────────────────▼─────────────────────────────────────┐   │
│  │ 工作流层 (LangGraph)                                               │   │
│  │  - 状态 (AgentState)、节点编排、条件路由                            │   │
│  │  - Checkpoint 持久化 (memory/sqlite/postgres)                      │   │
│  └───────────────────────────┬─────────────────────────────────────┘   │
│  ┌───────────────────────────▼─────────────────────────────────────┐   │
│  │ 领域层 (Services)                                                 │   │
│  │  - 意图识别、对话引导、通用回复、数据获取、路线规划、格式化、回调     │   │
│  └───────────────────────────┬─────────────────────────────────────┘   │
│  ┌───────────────────────────▼─────────────────────────────────────┐   │
│  │ 基础设施层                                                        │   │
│  │  - LLM 工厂、HTTP 客户端(调后端 POI)、Checkpoint、天气/POI 工具     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### LangGraph 工作流程图

```
用户输入
  ↓
┌─────────────────────────────────────────────────────────┐
│ validate_input_node (输入验证)                            │
│  - 检查输入长度                                           │
│  - 敏感词过滤                                             │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ llm_intent_recognition_node (LLM 意图识别)                │
│  - 调用: LLMIntentService.recognize_intent(state)        │
│  - 识别意图类型（tourism/non_tourism/tourism_need_guidance）│
│  - 提取城市和天数                                         │
│  - 失败时降级到 SimpleIntentExtractor（规则匹配）         │
└─────────────────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────────────────┐
│ 路由判断 (check_intent_result)                           │
└─────────────────────────────────────────────────────────┘
  ↓                    ↓                    ↓
tourism          tourism_need_guidance   non_tourism
(信息完整)         (信息不完整)            (非旅游意图)
  ↓                    ↓                    ↓
parallel_trigger   conversation_guidance  general_response
  ↓                    ↓                    ↓
┌──────────┐      ┌─────────────────────────────────────┐
│ 并行执行  │      │ conversation_guidance_node          │
├──────────┤      │  - 步骤1: LLM 提取信息（JSON）       │
│ weather  │      │  - 步骤2: 生成引导回复               │
│ poi      │      │  - 检查信息完整性                    │
│ rag      │      │                                     │
└──────────┘      └─────────────────────────────────────┘
  ↓                    ↓                    ↓
plan_route        complete? → parallel    END
  ↓                    ↓
format_output     incomplete? → END
  ↓                (等待下一轮输入)
callback_java
  ↓
END
```

### 架构说明

- **前端（ai-tourism-frontend）**：`Vue 3` 应用，负责交互、地图渲染与对话展示；通过 `SSE` 调用后端 `POST /ai_assistant/chat-stream` 实时消费模型输出

- **后端 API 服务（ai-tourism-backend）**：
  - **接入层（Controller + 鉴权）**：基于 `Spring Boot REST`，使用 `Sa-Token` 进行登录与权限校验，提供 RESTful API 接口
  - **业务服务层**：会话管理、消息入库、流式返回转发、API 网关功能
  - **数据访问层（MyBatis）**：通过 `MyBatis` 实现数据持久化，管理会话表、消息表、用户表等

- **Python Agent 服务（ai-tourism-agent）**：
  - **AI 对话处理**：LangGraph 工作流编排
  - **工具调用管理**：Function Call + MCP 工具
  - **状态管理**：使用 LangGraph Checkpoint 机制
  - **流式响应**：SSE 流式返回
  - **结构化输出**：JSON Schema 输出

---

## 技术栈与依赖

| 技术分类 | 技术栈 | 版本/说明 |
|---------|--------|----------|
| **Web 框架** | FastAPI | 0.115+ |
| **ASGI 服务器** | Uvicorn | 0.32+ |
| **工作流引擎** | LangGraph | 0.2+ |
| **LLM 集成** | LangChain / LangChain-OpenAI | 0.3+ / 0.2+ |
| **LLM** | OpenAI API | 推荐 GPT-4o-mini，可配置 |
| **Checkpoint** | LangGraph-Checkpoint-SQLite | 0.1+（可选 PostgreSQL） |
| **HTTP 客户端** | httpx | 0.27+（调用后端 POI 等） |
| **配置与校验** | Pydantic / Pydantic-Settings | 2.9+ / 2.0+ |
| **日志** | Loguru / Structlog | 0.7+ / 24.1+ |
| **可观测** | LangSmith | 可选，用于追踪与调试 |
| **JWT / 加密** | PyJWT[crypto]、cryptography | 和风天气 JWT 等 |

> 详见 [requirements.txt](requirements.txt) 依赖配置。 

---

## 目录结构

```
ai-tourism-agent/
├── app/
│   ├── main.py                      # FastAPI 应用入口
│   ├── config.py                    # 配置管理（Pydantic Settings）
│   │
│   ├── api/                         # API 路由层
│   │   ├── routes/
│   │   │   └── agent.py            # Agent 相关接口
│   │   └── models/
│   │       └── request.py          # 请求/响应模型
│   │
│   ├── domain/                      # 领域层（业务逻辑）
│   │   └── services/
│   │       ├── simple_intent_extractor.py      # 规则匹配提取器
│   │       ├── llm_intent_service.py           # LLM 意图识别
│   │       ├── conversation_guidance_service.py # 对话引导
│   │       ├── general_response_service.py     # 通用回复
│   │       ├── data_service.py                 # 数据获取
│   │       ├── planning_service.py             # 路线规划
│   │       ├── rag_retrieval_service.py        # RAG 检索服务（向量检索）
│   │       ├── formatting_service.py           # 格式化输出
│   │       ├── validation_service.py           # 输入验证
│   │       └── callback_service.py             # Java 回调
│   │
│   ├── graph/                       # LangGraph 工作流层
│   │   ├── state.py                # 状态定义
│   │   ├── workflow.py             # 工作流编排
│   │   └── nodes/                  # 工作流节点
│   │       ├── validation.py       # 输入验证节点
│   │       ├── llm_intent.py       # LLM 意图识别节点
│   │       ├── conversation_guidance.py  # 对话引导节点
│   │       ├── general_response.py # 通用回复节点
│   │       ├── parallel_trigger.py # 并行触发节点
│   │       ├── data_fetch.py       # 数据获取节点
│   │       ├── rag_retrieve.py     # RAG 向量检索节点
│   │       ├── planning.py         # 路线规划节点
│   │       ├── formatting.py       # 格式化输出节点
│   │       ├── error.py            # 错误处理节点
│   │       └── routing.py          # 路由判断函数
│   │
│   ├── infrastructure/              # 基础设施层
│   │   ├── llm/
│   │   │   └── factory.py          # LLM 工厂
│   │   ├── checkpoint/
│   │   │   └── saver.py            # Checkpoint 管理
│   │   └── http/
│   │       └── client.py           # HTTP 客户端
│   │
│   └── tools/                       # 工具层
│       ├── weather.py              # 天气工具
│       └── poi.py                  # POI 搜索工具
│
├── prompt/                          # Prompt 模板目录
│   ├── intent-recognition-system-prompt.txt
│   ├── conversation-guidance-system-prompt.txt
│   ├── general-response-system-prompt.txt
│   ├── tour-route-planning-system-prompt.txt
│   └── route-planning-user-prompt.txt
│
├── data/                            # 数据目录
│   └── checkpoints.db              # SQLite Checkpoint 数据库
│
├── requirements.txt                 # Python 依赖
├── .env.example                     # 环境变量示例
├── run.py                          # 启动脚本
└── README.md                       # 项目说明
```

---

## 快速开始

> 建议启动顺序：`ai-tourism-agent` → `ai-tourism-backend` → `ai-tourism-frontend`。

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制 `.env.example` 为 `.env`，准备配置参数
cp .env.example .env
```

```bash
# OpenAI 配置
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=4096
OPENAI_EMBEDDING_MODEL_NAME=text-embedding-3-small

# RAG 配置
RAG_ENABLED=true
RAG_CHROMA_DIR=./chroma_db
RAG_COLLECTION_NAME=travel_docs
RAG_TOP_K=5
RAG_CITY_METADATA_KEY=source_city

# Checkpoint 配置（默认使用内存，可选 memory | sqlite | postgres）
CHECKPOINT_TYPE=sqlite
SQLITE_DB_PATH=./checkpoints.db
POSTGRES_CONN_STRING=postgresql://user:password@localhost:5432/dbname

# Java 服务配置（工具接口由后端提供）
# 请启动 https://github.com/1937983507/ai-tourism-backend 后端项目
JAVA_SERVICE_URL=http://localhost:8290
JAVA_SERVICE_INTERNAL_TOKEN=your_internal_token

# 本Agent服务配置
AGENT_PORT=8291
AGENT_HOST=0.0.0.0

# 天气 API 配置
# 天气服务提供商: "openweathermap" 或 "qweather" (和风天气)
WEATHER_PROVIDER=qweather

# Open Weather API Key（当WEATHER_PROVIDER=openweathermap 时需要配置）
# 申请地址：http://api.openweathermap.org
OPENWEATHER_API_KEY=your_openweather_api_key

# 和风天气的各项配置 (当 WEATHER_PROVIDER=qweather 时需要配置)
# 申请地址: https://dev.qweather.com/
QWEATHER_API_HOST=your_qweather_api_host
QWEATHER_JWT_PROJECT_ID=your_qweather_jwt_project_id
QWEATHER_JWT_KEY_ID=your_qweather_jwt_key_id
QWEATHER_JWT_PRIVATE_KEY_PATH=./secrets/qweather_private_key.pem

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=./logs
LOG_RETENTION_DAYS=7
LOG_ROTATION=00:00
LOG_ENCODING=utf-8

# LangSmith 配置
# 是否启动 LangSmith 监测
LANGSMITH_ENABLED=true
# API Key 在 https://smith.langchain.com/ 申请
LANGSMITH_API_KEY="xxx"
LANGSMITH_PROJECT=ai-tourism-agent
LANGSMITH_WORKSPACE_ID="Workspace 1"

```

#### 和风天气 JWT 配置详细步骤

如果选择使用和风天气（`WEATHER_PROVIDER=qweather`），需要先生成密钥对并申请 JWT。步骤如下：

##### 步骤 1: 生成 ED25519 密钥对

**Linux / macOS 系统：**

```bash
# 生成私钥
openssl genpkey -algorithm ED25519 -out ed25519-private.pem

# 从私钥提取公钥
openssl pkey -pubout -in ed25519-private.pem -out ed25519-public.pem
```

**Windows 系统：**

如果已安装 OpenSSL（可通过 Git Bash 或 WSL 使用），命令与 Linux 相同：

```bash
# 在 Git Bash 或 WSL 中执行
openssl genpkey -algorithm ED25519 -out ed25519-private.pem
openssl pkey -pubout -in ed25519-private.pem -out ed25519-public.pem
```

如果未安装 OpenSSL，可以使用 PowerShell（需要 Windows 10 1809+）：

```powershell
# 使用 PowerShell 生成 ED25519 密钥对
$key = [System.Security.Cryptography.ECDsa]::Create([System.Security.Cryptography.ECCurve]::CreateFromFriendlyName("Ed25519"))
$privateKeyBytes = $key.ExportECPrivateKey()
$publicKeyBytes = $key.ExportSubjectPublicKeyInfo()

# 保存私钥（需要转换为 PEM 格式，建议使用 OpenSSL）
# 或者直接使用 OpenSSL for Windows: https://slproweb.com/products/Win32OpenSSL.html
```

> **推荐**：Windows 用户建议安装 [OpenSSL for Windows](https://slproweb.com/products/Win32OpenSSL.html) 或使用 WSL/Git Bash。

##### 步骤 2: 保存私钥文件

将生成的 `ed25519-private.pem` 文件保存到项目的 `secrets/` 目录。

```bash
# 创建 secrets 目录
mkdir -p secrets

# 移动私钥文件（保留完整 PEM 格式，包括 -----BEGIN PRIVATE KEY----- 和 -----END PRIVATE KEY-----）
mv ed25519-private.pem secrets/qweather_private_key.pem

# 确保私钥文件权限安全（Linux/macOS）
chmod 600 secrets/qweather_private_key.pem
```

**重要提示**：
- 私钥文件必须包含完整的 PEM 格式（包括 `-----BEGIN PRIVATE KEY-----` 和 `-----END PRIVATE KEY-----` 及中间所有行）
- 不要只复制中间的内容，必须保留完整的 PEM 格式
- 私钥文件应添加到 `.gitignore`，不要提交到版本控制

##### 步骤 3: 上传公钥到和风天气官网

1. 访问 [和风天气开发者平台](https://dev.qweather.com/)
2. 登录账号，进入项目管理
3. 创建新项目或选择现有项目
4. 在项目设置中，上传 `ed25519-public.pem` 公钥文件
5. 记录下系统分配的：
   - **Project ID**（对应 `QWEATHER_JWT_PROJECT_ID`）
   - **Key ID**（对应 `QWEATHER_JWT_KEY_ID`）
   - **API Host**（对应 `QWEATHER_API_HOST`，可能是网关地址或官方域名）

##### 步骤 4: 配置环境变量

在 `.env` 文件中配置：

```bash
# 启用和风天气
WEATHER_PROVIDER=qweather

# 和风天气配置
QWEATHER_API_HOST=https://your_api_host                    # 从官网获取的 API Host
QWEATHER_JWT_PROJECT_ID=your_project_id                    # 从官网获取的 Project ID
QWEATHER_JWT_KEY_ID=your_key_id                           # 从官网获取的 Key ID
QWEATHER_JWT_PRIVATE_KEY_PATH=./secrets/qweather_private_key.pem  # 私钥文件路径
```

##### 步骤 5: 验证配置

重启服务后，系统会自动：
1. 读取私钥文件
2. 使用 Project ID 和 Key ID 生成 JWT Token
3. 使用 JWT Token 调用和风天气 API

如果配置正确，日志中会显示和风天气调用成功的信息。

### 3. 运行服务

#### 方式一：本地开发（使用 `run.py`）

```bash
python run.py
```

#### 方式二：本地开发（直接使用 `uvicorn`）

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8291 --reload
```

#### 方式三：Linux 生产环境使用 `systemd` 守护进程运行（推荐）

在 Linux 服务器上，建议使用 `systemd` 以服务方式常驻运行，支持**自动重启**和**开机自启**。

**1）创建 systemd 服务文件**

```bash
sudo vim /etc/systemd/system/ai-tourism-agent.service
```

写入内容示例（请根据你的实际部署路径和运行用户进行调整）：

```ini
[Unit]
Description=AI Tourism Agent
After=network.target

[Service]
# 建议使用非 root 用户运行，例如 www-data 或你的业务账号
User=root
# 项目所在目录，例如 /www/wwwroot/ai/ai-tourism-agent
WorkingDirectory=/www/wwwroot/ai/ai-tourism-agent
# 使用虚拟环境里的 python + -m uvicorn，更稳妥
ExecStart=/usr/local/bin/uvicorn app.main:app --host 0.0.0.0 --port 8291 --workers 4
# 异常退出时自动重启
Restart=always
RestartSec=3
# 可选：如果需要，自行设置 PYTHONPATH 等环境变量
Environment="PYTHONPATH=/path/to/ai-tourism-agent"

[Install]
WantedBy=multi-user.target
```

**2）让 `systemd` 识别并启用服务**

```bash
sudo systemctl daemon-reload
# 设置开机自启
sudo systemctl enable ai-tourism-agent
```

**3）启动 / 停止 / 重启 / 查看状态**

```bash
# 启动服务
sudo systemctl start ai-tourism-agent

# 停止服务
sudo systemctl stop ai-tourism-agent

# 重启服务（修改配置后常用）
sudo systemctl restart ai-tourism-agent

# 查看服务运行状态
sudo systemctl status ai-tourism-agent
```

**4）查看运行日志（排查启动问题）**

```bash
# 查看最近 50 行日志
journalctl -u ai-tourism-agent -n 50 --no-pager

# 持续跟踪日志输出（类似 tail -f）
journalctl -u ai-tourism-agent -f
```

### 4. 测试接口

```bash
# 健康检查
curl http://localhost:8291/agent/health

# 工具列表
curl http://localhost:8291/agent/tools

# 流式对话（推荐）
curl -N -v -X POST http://localhost:8291/agent/chat-stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session_001",
    "user_id": "user_123",
    "message": "我想去北京玩5天"
  }'

# 非流式对话（测试用）
curl -X POST http://localhost:8291/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session_001",
    "user_id": "user_123",
    "message": "我想去北京玩5天"
  }'
```

---

## 配置说明

### Checkpoint 与会话恢复

- `CHECKPOINT_TYPE=memory|sqlite|postgres`
- 单机推荐 `sqlite`；分布式/多实例可选 `postgres`

### 天气服务提供商

- `WEATHER_PROVIDER=openweathermap|qweather`
- 使用和风天气时，需要按上文「和风天气 JWT 配置详细步骤」准备私钥与相关变量

### RAG 向量检索配置

- `RAG_ENABLED=true|false`：是否启用 RAG 检索节点（默认 true）
- `RAG_CHROMA_DIR`：Chroma 持久化目录
- `RAG_COLLECTION_NAME`：Chroma 集合名（默认 `travel_docs`）
- `RAG_TOP_K`：每次检索返回的 top-k（默认 5）
- `RAG_CITY_METADATA_KEY`：用于城市过滤的 metadata 字段名（默认 `source_city`）
- 说明：当 `RAG_ENABLED=true` 但 `RAG_CHROMA_DIR` 为空/不存在时，会降级为 `rag_context=""`，主流程仍可运行。

### 与后端（Java/Spring Boot）集成

- Agent 通过 `JAVA_SERVICE_URL` 调用后端工具接口（如 POI 查询）
- 后端默认端口为 `8290`（以 `ai-tourism-backend` 配置为准）

---

## 接口与集成

### 1. 健康检查

```bash
GET /agent/health
```

### 2. 工具列表

```bash
GET /agent/tools
```

### 3. 流式对话（推荐）

```bash
POST /agent/chat-stream
```

### 4. 非流式对话

```bash
POST /agent/chat
```

详细请求/响应说明、示例与约定见 [doc/API.md](doc/API.md)。

### 对话示例

#### 示例1：完整信息输入

```
用户: 我想去北京玩5天
助手: 好的，我已经了解您想去北京玩5天。正在为您规划路线...

[系统并行获取天气和景点信息]

助手: 根据北京未来5天的天气情况和热门景点，为您规划如下路线：

第一天：故宫、天安门广场
- 上午：参观故宫博物院...
- 下午：游览天安门广场...

第二天：长城、明十三陵
...
```

#### 示例2：需要引导的对话

```
用户: 我想去旅游
助手: 好的！请问您想去哪个城市旅游呢？

用户: 北京
助手: 明白了，您想去北京旅游。请问您计划玩几天呢？

用户: 5天
助手: 好的，我已经了解您想去北京玩5天。正在为您规划路线...
```

#### 示例3：非旅游意图

```
用户: 今天天气怎么样？
助手: 您好！我是旅游规划助手，主要帮助您规划旅游路线。
如果您想了解某个城市的天气情况，可以告诉我您想去哪里旅游，
我会为您提供该城市的天气预报和旅游建议。
```

---

## 开发扩展指南

### 可视化工作流图

使用 Jupyter Notebook 可视化工作流：

```bash
# 安装 jupyter
pip install jupyter

# 启动 jupyter notebook
jupyter notebook
```

在 Notebook 中运行：

```python
from app.graph.workflow import init_agent_graph

# 初始化并显示工作流图
graph = await init_agent_graph()
```

### 添加新节点

1. 在 `app/graph/nodes/` 创建新节点文件
2. 在 `app/domain/services/` 创建对应的服务
3. 在 `app/graph/workflow.py` 中注册节点
4. 更新 `app/graph/nodes/__init__.py`

### 添加新工具

1. 在 `app/tools/` 创建新工具文件
2. 实现工具逻辑
3. 在需要的 Service 中调用

### 安全注意事项

1. **密钥与私钥文件**：
   - ⚠️ 不要提交 `.env` 与 `secrets/` 下的私钥文件到版本控制
   - ✅ 使用 `.env.example` 作为模板，只提交占位符

2. **服务间调用安全**：
   - ✅ 建议为后端工具接口开启并校验内部 Token（`JAVA_SERVICE_INTERNAL_TOKEN`）
   - ✅ Agent 对外暴露时，推荐仅通过后端统一入口访问

3. **生产环境建议**：
   - 使用 HTTPS、合理设置超时/重试
   - 关注 SSE 长连接资源占用，必要时做限流与并发控制

### 常见问题（FAQ）

#### 1）POI/工具调用失败（连接拒绝 / 401 / 超时）

- 确认 `ai-tourism-backend` 已启动，且 `JAVA_SERVICE_URL` 指向可达地址（默认 `http://localhost:8290`）
- 如果后端开启了内部鉴权，确认 `JAVA_SERVICE_INTERNAL_TOKEN` 与后端配置一致

#### 2）路线规划没有记忆/会话无法恢复

- 确认 `CHECKPOINT_TYPE` 与对应配置已正确填写（`sqlite` 需要 `SQLITE_DB_PATH`，`postgres` 需要 `POSTGRES_CONN_STRING`）

---

## TODO

### 1. 稳定性与错误处理
- [ ] 完善异常处理与统一错误码（工具调用 / LLM / 回调 / SSE）
- [ ] 添加重试机制（指数退避 + 可配置最大重试次数）
- [ ] 超时控制（请求级/工具级/LLM 级）与取消机制

### 2. 性能优化
- [ ] 工具调用缓存（Redis，可按城市/日期/查询参数分层缓存）
- [ ] HTTP 连接池与并发限制（防止工具调用打爆后端）
- [ ] 消息窗口修剪策略（多轮对话 token 成本可控）

### 3. 规划质量与路线优化
- [ ] 路线绕路优化：基于距离/通勤时间对每日 POI 排序与聚类，减少折返
- [ ] 约束与评分函数：将「预算/节奏/人群类型/偏好」显式纳入规划目标（可解释的打分）
- [ ] 支持“二次优化”指令：用户提出“更紧凑/更休闲/少走路/少换酒店”等需求时可增量重排

### 4. 多轮对话与偏好确认
- [ ] 偏好收集：通过多轮问答确认 **偏好**、**人数**、**预算**、**节奏**（以及可选：亲子/老人、出行方式、是否自驾/是否带行李）
- [ ] 槽位抽取与校验：将偏好结构化落到 `AgentState`，缺失项自动追问、冲突项澄清
- [ ] 偏好记忆：同一会话内保持一致；跨会话可选写入后端用户画像（需鉴权与隐私策略）

### 5. 工具调用可视化（前端联动）
- [ ] 将工具调用过程（工具名、入参、耗时、结果摘要、错误）以事件流形式下发，前端渲染展示
- [ ] 设计统一事件协议：区分「模型输出 token」「工具调用开始/结束」「检索命中/未命中」「规划阶段切换」
- [ ] 支持“调试模式”：允许在 UI 上展开查看完整工具入参/原始结果（默认脱敏）

---

## 参考文档

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [OpenAI API 文档](https://platform.openai.com/docs/)

---

## License

本项目仅供学习使用，**禁止未经授权的商用**。

---

## 联系与贡献

欢迎任何建议、反馈与贡献！如需交流或有合作意向，欢迎通过以下方式联系：

- **微信**：`13859211947`
- **GitHub**：提交 Issue 或 PR 到本仓库
- **前端项目**：[ai-tourism-frontend 仓库](https://github.com/1937983507/ai-tourism-frontend)
- **后端项目**：[ai-tourism-backend 仓库](https://github.com/1937983507/ai-tourism-backend) - Spring Boot 后端服务，提供 API 网关、会话管理、用户认证等功能

如有 Bug、需求或想法，欢迎随时提出，我们会积极响应。
也欢迎 AI 应用开发相关的同学一起交流讨论。
