# AI-Tourism Agent Service

基于 LangGraph 的智能旅游规划 Agent 服务，提供智能意图识别、对话引导、多轮对话、并行数据获取和个性化路线规划功能。

## 核心特性

### 🎯 智能意图识别
- **LLM 意图识别**：使用大语言模型识别用户意图（旅游/非旅游/需要引导）
- **信息提取**：自动提取城市、天数等关键信息
- **规则匹配降级**：LLM 失败时自动降级到规则匹配策略

### 💬 智能对话引导
- **多轮对话**：通过友好对话引导用户提供完整信息
- **上下文理解**：基于对话历史理解用户意图
- **分步提取**：先提取信息，再生成引导回复

### 🚀 高性能架构
- **并行数据获取**：天气和景点信息并行获取，提升响应速度
- **流式响应**：支持 SSE 流式输出，实时展示规划过程
- **状态持久化**：支持 SQLite/PostgreSQL Checkpoint，实现会话恢复

### 🛠️ 工具集成
- **天气预报**：支持 OpenWeather API 和和风天气 API，可通过环境变量切换
- **景点搜索**：通过 HTTP 调用 Java 后端服务
- **结构化输出**：自动生成 JSON 格式的旅游攻略

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，并配置以下参数：

```bash
# OpenAI 配置
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4o-mini
OPENAI_MAX_OUTPUT_TOKENS=4096

# Checkpoint 配置（默认使用内存，可选 memory | sqlite | postgres）
CHECKPOINT_TYPE=sqlite
SQLITE_DB_PATH=./checkpoints.db
POSTGRES_CONN_STRING=postgresql://user:password@localhost:5432/dbname

# Java 服务配置
# 请启动 https://github.com/1937983507/ai-tourism-backend 后端项目
JAVA_SERVICE_URL=http://localhost:8080
JAVA_SERVICE_INTERNAL_TOKEN=your_internal_token

# 本Agent服务配置
AGENT_PORT=8291
AGENT_HOST=0.0.0.0

# 天气 API 配置
# 天气服务提供商: "openweathermap" (默认) 或 "qweather" (和风天气)
WEATHER_PROVIDER=openweathermap
# Open Weather API Key（当WEATHER_PROVIDER=openweathermap 时需要配置）
# 申请地址：http://api.openweathermap.org
OPENWEATHER_API_KEY=your_openweather_api_key
# 和风天气的各项配置 (当 WEATHER_PROVIDER=qweather 时需要配置)
# 申请地址: https://dev.qweather.com/
QWEATHER_API_HOST=your_qweather_api_host
QWEATHER_JWT_PROJECT_ID=your_qweather_jwt_project_id
QWEATHER_JWT_KEY_ID=your_qweather_jwt_key_id
QWEATHER_JWT_PRIVATE_KEY_PATH=your_qweather_qweather_jwt_private_key_path

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=./logs
LOG_RETENTION_DAYS=7
LOG_ROTATION=00:00
LOG_ENCODING=utf-8

# LangSmith 配置
LANGSMITH_ENABLED=true
LANGSMITH_API_KEY="xxx"
LANGSMITH_PROJECT=ai-tourism-agent
LANGSMITH_WORKSPACE_ID="Workspace 1"

```

### 3. 运行服务

```bash
# 方式1：使用 uvicorn（推荐）
uvicorn app.main:app --host 0.0.0.0 --port 8291 --reload

# 方式2：使用 run.py
python run.py
```

### 4. 测试接口

```bash
# 健康检查
curl http://localhost:8291/agent/health

# 工具列表
curl http://localhost:8291/agent/tools

# 流式对话（推荐）
curl -X POST http://localhost:8291/agent/chat-stream \
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

## 项目架构

### 目录结构

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

### 架构设计

#### 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                     API 层 (FastAPI)                     │
│  - 接收 HTTP 请求                                         │
│  - 参数验证                                               │
│  - 流式响应（SSE）                                        │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                  工作流层 (LangGraph)                     │
│  - 状态管理（AgentState）                                 │
│  - 节点编排（显式定义节点和边）                            │
│  - 条件路由                                               │
│  - Checkpoint 持久化                                      │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                   领域层 (Services)                       │
│  - 业务逻辑实现                                           │
│  - LLM 调用封装                                           │
│  - 数据处理                                               │
│  - 统一接口：接收 State 对象                              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                 基础设施层 (Infrastructure)                │
│  - LLM 工厂（OpenAI）                                     │
│  - HTTP 客户端（Java 服务调用）                           │
│  - Checkpoint 管理（SQLite/PostgreSQL）                   │
│  - 工具实现（天气、POI）                                   │
└─────────────────────────────────────────────────────────┘
```

#### 工作流程图

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

## 核心设计

### 1. 意图识别与对话引导

系统采用 **LLM 意图识别 + 规则匹配降级** 的双重策略，并通过分步处理实现精准的信息提取和友好的对话引导。

### 2. Service 层接口设计

**设计原则**：Service 层直接接收 `AgentState` 对象，自己提取需要的信息。

**优势**：
- ✅ Node 层极简（从 20+ 行减少到 1 行）
- ✅ Service 层自主决定需要什么数据
- ✅ 易于扩展，新增 state 字段不影响 Node 层
- ✅ 减少重复代码
- ✅ 职责清晰：Node 负责流程控制，Service 负责业务逻辑

### 3. 并行数据获取

使用 LangGraph 的并行节点特性，同时获取天气和景点信息：

**性能提升**：
- 串行执行：天气 API (2s) + POI API (3s) = 5s
- 并行执行：max(2s, 3s) = 3s
- **提升 40% 响应速度**

### 4. Checkpoint 状态持久化

支持多种 Checkpoint 后端：
- `memory`: 内存（开发环境）
- `sqlite`: SQLite（单机生产）
- `postgres`: PostgreSQL（分布式生产）

### 5. 流式响应

使用 SSE (Server-Sent Events) 实现流式输出，实时展示 LLM 生成过程，提升用户体验。

## API 接口

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

详细接口文档请参考代码注释。

## 对话示例

### 示例1：完整信息输入

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

### 示例2：需要引导的对话

```
用户: 我想去旅游
助手: 好的！请问您想去哪个城市旅游呢？

用户: 北京
助手: 明白了，您想去北京旅游。请问您计划玩几天呢？

用户: 5天
助手: 好的，我已经了解您想去北京玩5天。正在为您规划路线...
```

### 示例3：非旅游意图

```
用户: 今天天气怎么样？
助手: 您好！我是旅游规划助手，主要帮助您规划旅游路线。
如果您想了解某个城市的天气情况，可以告诉我您想去哪里旅游，
我会为您提供该城市的天气预报和旅游建议。
```

## 项目状态

### ✅ 已完成功能

#### 1. 核心工作流
- ✅ LangGraph 工作流编排（显式定义节点和边）
- ✅ 输入验证节点（长度检查、敏感词过滤）
- ✅ LLM 意图识别节点（识别旅游/非旅游/需要引导）
- ✅ 对话引导节点（多轮对话，信息提取）
- ✅ 并行数据获取节点（天气 + POI）
- ✅ 路线规划节点（基于天气和景点生成攻略）
- ✅ 格式化输出节点（生成 JSON 结构化数据）
- ✅ 错误处理节点
- ✅ 条件路由控制

#### 2. 意图识别与对话引导
- ✅ LLM 意图识别（主策略）
- ✅ 规则匹配降级（SimpleIntentExtractor）
- ✅ 信息提取与回复生成分离
- ✅ 多轮对话支持
- ✅ 上下文理解

#### 3. Service 层优化
- ✅ 统一接口设计（接收 State 对象）
- ✅ Node 层简化（从 20+ 行减少到 1 行）
- ✅ 降低耦合度
- ✅ 提高可维护性和可扩展性

#### 4. Checkpoint 机制
- ✅ 内存 Checkpoint（开发环境）
- ✅ SQLite Checkpoint（单机生产）
- ✅ PostgreSQL Checkpoint（分布式生产）
- ✅ 会话恢复功能

#### 5. 工具集成
- ✅ 天气预报工具（OpenWeather API）
- ✅ POI 搜索工具（HTTP 调用 Java 服务）
- ✅ 工具管理器

#### 6. API 接口
- ✅ 健康检查接口（GET /agent/health）
- ✅ 工具列表接口（GET /agent/tools）
- ✅ 流式对话接口（POST /agent/chat-stream，SSE）
- ✅ 非流式对话接口（POST /agent/chat）

#### 7. 配置与部署
- ✅ 环境变量配置（.env）
- ✅ Pydantic Settings 配置管理
- ✅ 完整的项目目录结构
- ✅ 模块化设计
- ✅ 代码规范

### ⏳ 待优化（按优先级）

#### 高优先级
1. **错误处理增强**
   - [ ] 完善异常处理逻辑
   - [ ] 添加重试机制（指数退避）
   - [ ] 超时控制

#### 中优先级
2. **监控与日志**
   - [ ] 结构化日志（JSON 格式）
   - [ ] 请求追踪（Trace ID）
   - [ ] 性能指标收集

3. **性能优化**
   - [ ] 工具调用缓存（Redis）
   - [ ] 连接池优化
   - [ ] 消息窗口修剪策略

#### 低优先级
4. **功能扩展**
   - [ ] 支持更多城市
   - [ ] 支持自定义偏好（美食、购物等）
   - [ ] 支持多语言

5. **长期记忆**（可选）
   - [ ] 向量数据库集成
   - [ ] 用户偏好记忆
   - [ ] 语义检索

## 技术栈

- **框架**: FastAPI 0.104+
- **工作流**: LangGraph 0.2+
- **LLM**: OpenAI GPT-4o-mini
- **数据库**: SQLite / PostgreSQL（Checkpoint）
- **HTTP 客户端**: httpx
- **配置管理**: Pydantic Settings
- **日志**: Python logging

## 开发指南

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

## 参考文档

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [OpenAI API 文档](https://platform.openai.com/docs/)

## License

MIT License

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。
