# AI-Tourism Agent Service

基于 LangGraph 的智能旅游规划 Agent 服务。

## 功能特性

- ✅ LangGraph 工作流编排（显式定义节点和边）
- ✅ Checkpoint 状态持久化（默认内存）
- ✅ 输入验证节点（替代护轨机制）
- ✅ 显式节点：意图理解、获取天气、获取POI、路线规划
- ✅ 工具调用（天气、POI 搜索）
- ✅ 流式响应（SSE）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入必要的配置
```

复制 `.env.example` 为 `.env`，并配置：
- `OPENAI_API_KEY`: OpenAI API Key
- `OPENAI_BASE_URL`: OpenAI API 地址
- `OPENAI_MODEL_NAME`: 模型名称
- `JAVA_SERVICE_URL`: Java 服务地址
- `OPENWEATHER_API_KEY`: 天气 API Key（可选）

### 3. 运行服务

```bash
# 方式1：使用 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8291 --reload

# 方式2：使用 run.py
python run.py
```

### 4.测试接口

```bash
# 健康检查
curl http://localhost:8291/agent/health

# 工具列表
curl http://localhost:8291/agent/tools

# 流式对话
curl -X POST http://localhost:8291/agent/chat-stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test_session",
    "user_id": "test_user",
    "message": "请为我规划北京市3日旅游攻略"
  }'
```

## 项目结构

```
ai-tourism-agent/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理
│   ├── agent/                # Agent 核心模块
│   ├── tools/                # 工具模块
│   ├── checkpoint/           # Checkpoint 管理
│   └── api/                  # API 路由
├── prompts/                  # Prompt 模板
├── requirements.txt          # Python 依赖
└── README.md                 # 项目说明
```

## 架构说明

- **LangGraph 工作流**：使用条件节点实现输入验证和流程控制
- **Checkpoint 机制**：默认使用内存（开发），支持 SQLite 或 PostgreSQL（生产）
- **工具化交互**：通过工具调用 Java 服务，实现解耦
- **流式响应**：使用 SSE 实现实时流式输出


# 项目状态

## ✅ 已完成

### 核心功能
1. **LangGraph 工作流**
   - ✅ 使用预构建的 ReAct Agent
   - ✅ 输入验证节点（替代护轨机制）
   - ✅ 错误处理节点
   - ✅ 条件路由控制

2. **Checkpoint 机制**
   - ✅ SQLite Checkpoint 支持（开发环境）
   - ✅ PostgreSQL Checkpoint 支持（生产环境）
   - ✅ 内存 Checkpoint 降级（备用）

3. **工具实现**
   - ✅ 天气预报工具（weather_forecast）
   - ✅ POI 搜索工具（poi_search，通过 HTTP 调用 Java 服务）
   - ✅ 工具管理器

4. **API 接口**
   - ✅ 健康检查接口（GET /agent/health）
   - ✅ 工具列表接口（GET /agent/tools）
   - ✅ 流式对话接口（POST /agent/chat-stream，SSE 格式）
   - ✅ 非流式对话接口（POST /agent/chat，用于测试）

5. **配置管理**
   - ✅ 环境变量配置（.env）
   - ✅ Pydantic Settings 配置管理

6. **项目结构**
   - ✅ 完整的项目目录结构
   - ✅ 模块化设计
   - ✅ 代码规范

## ⏳ 待实现（按优先级）

### 高优先级
1. **流式响应优化**
   - [ ] 优化流式响应逻辑，确保正确输出增量内容
   - [ ] 处理 LangGraph 流式事件的增量更新

2. **Java 服务集成**
   - [ ] Java 服务需要提供 `/api/tools/poi` 接口
   - [ ] 实现内部 Token 认证机制

3. **错误处理**
   - [ ] 完善错误处理逻辑
   - [ ] 添加重试机制

### 中优先级
4. **监控与日志**
   - [ ] 添加结构化日志
   - [ ] 集成 Prometheus 指标（暂缓）
   - [ ] 添加分布式追踪

5. **性能优化**
   - [ ] 工具调用缓存（可选 Redis）
   - [ ] 连接池优化
   - [ ] 消息窗口修剪策略

### 低优先级
6. **MCP 工具支持**（暂缓）
   - [ ] MCP 客户端实现
   - [ ] MCP 工具提供者
   - [ ] 结果裁剪功能

7. **长期记忆**（可选）
   - [ ] 向量数据库集成
   - [ ] 语义检索功能

## 📚 参考文档

- [迁移文档](../ai-tourism/doc/migration-plan.md)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)



