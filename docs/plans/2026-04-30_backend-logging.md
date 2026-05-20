# 后端日志系统

## Context

当前后端零结构化日志：无 logging 库、无 logger 调用，仅一处 bare `print()`。所有异常被静默吞掉（6 个 `except` 块无 traceback），无请求追踪、无日志文件。调试只能靠 uvicorn 终端输出，重启即丢失。

目标：在 `backend/logs/` 下持久化结构化日志，支持请求级 trace_id 追踪，文件自动轮转。

## 方案

使用 **loguru**（零依赖、内置轮转/压缩/结构化输出），通过 FastAPI middleware 注入 trace_id，全局 `from loguru import logger` 直接使用。

### 组件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/requirements.txt` | 修改 | 添加 `loguru>=0.7.0` |
| `backend/.gitignore` | 新建 | `logs/`、`*.jsonl`、`*.jsonl.gz` |
| `backend/app/logging.py` | 新建 | `setup_logging()`：双 sink（文件 JSON + stderr 彩色），拦截 stdlib logging |
| `backend/app/trace.py` | 新建 | `TraceMiddleware`：每请求生成 trace_id，记录 method/path/status/latency |
| `backend/app/config.py` | 修改 | 添加 `log_level: str = "INFO"` 字段 |
| `backend/app/main.py` | 修改 | lifespan 调用 `setup_logging()`，注册 TraceMiddleware，注册全局 exception handler |
| `backend/app/middleware.py` | 修改 | auth 失败处加 `logger.warning` |
| `backend/app/database.py` | 修改 | init_db 加 info/exception 日志 |
| `backend/app/llm.py` | 修改 | get_llm 加 provider/model 日志 |
| `backend/app/routers/auth.py` | 修改 | login 流程各分支加日志 |
| `backend/app/routers/chat.py` | 修改 | stream 异常加日志 |
| `backend/app/routers/speech.py` | 修改 | except 块加 `logger.exception` |
| `backend/app/rag/store.py` | 修改 | `print` 替换为 `logger.info`，静默 except 加 warning |
| `backend/app/agent/tools.py` | 修改 | 11 个工具：entry debug 日志 + exception 日志 |
| `backend/app/agent/graph.py` | 修改 | 工具调用/失败日志，静默 `pass` 替换为 warning |

### 日志格式

- **文件** (`logs/app.jsonl`)：JSON Lines，含 timestamp/level/trace_id/message/extra
- **控制台**：`HH:mm:ss | LEVEL | trace_id | message`，彩色
- **轮转**：10MB/文件，压缩为 gz，保留 7 天
- **级别**：`LOG_LEVEL` 环境变量控制，默认 INFO，开发可设 DEBUG

### trace_id

- `TraceMiddleware` 从 `X-Trace-Id` 请求头获取，无则生成 12 位 hex
- 通过 `logger.contextualize(trace_id=...)` 注入，下游代码无感知
- 响应头回传 `X-Trace-Id`，方便前后端关联

## 实现顺序

1. `requirements.txt` + `.gitignore` + `app/logging.py` + `app/config.py`（基础）
2. `app/main.py` + `app/trace.py`（middleware + 异常处理）
3. `app/middleware.py` + `app/database.py` + `app/llm.py`（基础设施层）
4. `app/routers/auth.py` + `chat.py` + `speech.py`（路由层）
5. `app/rag/store.py` + `app/agent/tools.py` + `app/agent/graph.py`（核心业务层）

## 验证

```bash
# 启动后端
cd backend && uvicorn app.main:app --reload

# 发送请求，检查控制台日志输出
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"code":"test"}'

# 检查日志文件
cat logs/app.jsonl | jq .

# 设 DEBUG 级别，验证工具调用日志
LOG_LEVEL=DEBUG uvicorn app.main:app --reload

# 运行测试确认无回归
python -m pytest tests/ -v
```
