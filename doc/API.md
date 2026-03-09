# AI-Tourism Agent 服务 API 文档

本文档描述 **ai-tourism-agent** 对外提供的 HTTP 接口，供后端（ai-tourism-backend）或联调测试直接调用。服务默认根路径为 `http://<host>:8291`，所有 Agent 接口统一前缀为 `/agent`。

---

## 1. 通用说明

### 1.1 基础信息

- **Base URL**：`http://<host>:8291`（默认 `host=0.0.0.0`，端口由 `AGENT_PORT` 配置，默认 `8291`）
- **接口前缀**：`/agent`
- **Content-Type**：请求体为 JSON 时使用 `application/json`
- **流式响应**：`/agent/chat-stream` 返回 `text/event-stream`（SSE）

### 1.2 根路径

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 服务信息与运行状态 |

**响应示例：**

```json
{
  "service": "AI-Tourism Agent Service",
  "version": "1.0.0",
  "status": "running"
}
```

---

## 2. 健康检查

用于探测服务是否就绪及 Checkpoint、工具状态。

### GET /agent/health

**请求**：无请求体。

**响应体（JSON）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 固定为 `"healthy"` |
| version | string | 服务版本，如 `"1.0.0"` |
| checkpoint_backend | string | Checkpoint 后端类型：`memory` / `sqlite` / `postgres` |
| tools | object | 工具名到状态的映射，如 `{"get_weather": "available", "search_poi": "available"}` |

**示例：**

```bash
curl -s http://localhost:8291/agent/health
```

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checkpoint_backend": "sqlite",
  "tools": {
    "get_weather": "available",
    "search_poi": "available"
  }
}
```

---

## 3. 工具列表

返回当前已注册的工具名称与描述，便于调试与运维。

### GET /agent/tools

**请求**：无请求体。

**响应体（JSON 数组）：**

每个元素包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 工具名称 |
| description | string | 工具描述 |
| available | boolean | 是否可用，一般为 `true` |

**示例：**

```bash
curl -s http://localhost:8291/agent/tools
```

```json
[
  {
    "name": "get_weather",
    "description": "获取指定城市的天气预报",
    "available": true
  },
  {
    "name": "search_poi",
    "description": "根据城市与关键词搜索景点 POI",
    "available": true
  }
]
```

---

## 4. 流式对话（推荐）

以 SSE 流式返回 AI 回复，适合前端实时展示。后端网关通常直接转发该接口的响应给前端。

### POST /agent/chat-stream

**请求头：**

- `Content-Type: application/json`

**请求体（JSON）：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话 ID，同一会话内保持多轮上下文；由调用方生成并透传 |
| user_id | string | 是 | 用户 ID，用于日志与权限扩展 |
| message | string | 是 | 用户本轮输入文本 |

**示例：**

```json
{
  "session_id": "sess_abc123",
  "user_id": "user_001",
  "message": "我想去北京玩5天"
}
```

**响应：**

- **Content-Type**：`text/event-stream`
- **Body**：每行一条 SSE 事件，格式为 `data: <JSON>\n\n`。  
  JSON 结构与后端约定一致，便于网关透传，例如：
  - 内容块：`{"choices":[{"index":0,"text":"<片段>","finish_reason":"stop","model":"<模型名>"}]}`
  - 结束：`{"choices":[{"finish_reason":"stop"}]}`

**cURL 示例：**

```bash
curl -N -X POST http://localhost:8291/agent/chat-stream \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test_001","user_id":"user_123","message":"我想去北京玩5天"}'
```

**错误与异常：**

- 若发生未捕获异常，会在流中返回一条包含错误提示的 `text` 片段（`finish_reason` 仍为 `stop`），不返回 4xx/5xx 状态码，以便前端统一按流式内容处理。

---

## 5. 非流式对话（测试用）

一次性返回完整回复，便于脚本或接口测试，不适合生产前端使用。

### POST /agent/chat

**请求头：**

- `Content-Type: application/json`

**请求体（JSON）：** 与 `/agent/chat-stream` 相同。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话 ID |
| user_id | string | 是 | 用户 ID |
| message | string | 是 | 用户消息 |

**响应体（JSON）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| response | string | AI 完整回复文本 |
| session_id | string | 与请求中的 session_id 一致 |

**错误响应：**

- 当内部处理失败时返回 HTTP 500，body 为 `{"detail": "<错误信息>"}`。

**示例：**

```bash
curl -X POST http://localhost:8291/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test_001","user_id":"user_123","message":"我想去北京玩5天"}'
```

```json
{
  "response": "好的，我已经了解您想去北京玩5天。正在为您规划路线……",
  "session_id": "test_001"
}
```

---

## 6. 调用约定与注意事项

1. **会话与多轮**：同一 `session_id` 的多轮请求会复用 LangGraph Checkpoint 中的状态，实现多轮对话与规划；`session_id` 建议由后端按会话生成并透传。
2. **流式格式**：`/agent/chat-stream` 的 SSE 数据格式与后端、前端约定一致，后端可直接转发，无需拆包重组。
3. **超时**：流式接口为长连接，网关与客户端应设置合理读超时（建议 ≥ 60s），避免规划耗时较长时被中断。
4. **鉴权**：当前接口未强制鉴权；若通过公网暴露，建议仅在内网调用，或由后端网关做统一鉴权后再转发到 Agent。
5. **内部 Token**：若后端与 Agent 之间配置了内部 Token（如 `JAVA_SERVICE_INTERNAL_TOKEN`），仅用于 Agent 调用后端 POI 等接口，不用于本 API 的入参。

---

## 7. 附录：Pydantic 模型定义参考

以下为服务内部使用的请求/响应模型，便于对接方校验字段。

**ChatRequest（对话请求）：**

```python
class ChatRequest(BaseModel):
    session_id: str  # 必填
    user_id: str     # 必填
    message: str     # 必填
```

**HealthResponse（健康检查响应）：**

```python
class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    checkpoint_backend: str
    tools: dict  # 工具名 -> 状态
```

**ToolInfo（工具列表项）：**

```python
class ToolInfo(BaseModel):
    name: str
    description: str
    available: bool = True
```
