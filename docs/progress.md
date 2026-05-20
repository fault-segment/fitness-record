# 工作进度

> 最后更新：2026-04-30

## 已完成

### 基础设施

- [x] FastAPI 项目骨架：config、database、middleware、routers
- [x] TiDB Cloud Serverless 连接（SSL + CA 证书，asyncmy 驱动）
- [x] TiDB 连接池保活：pool_pre_ping + pool_recycle 应对 Serverless 空闲休眠
- [x] SQLAlchemy async 数据模型：User、FoodRecord、FoodItem
- [x] JWT 认证：wx.login → openid → JWT → get_user_id 依赖注入
- [x] LLM 抽象层（app/llm.py）：支持 openai / anthropic provider 切换
- [x] MiniMax M2.7 接入（Anthropic 协议，端点 `api.minimaxi.com/anthropic`）
- [x] BGE-small-zh-v1.5 嵌入模型本地化（`data/bge-small-zh-v1.5/`，无需联网）

### RAG 食品知识库

- [x] Chroma 向量存储（`data/food_chromadb/`，cosine 相似度）
- [x] 49 种常见中国食物营养数据（每100g：热量/蛋白/碳水/脂肪）
- [x] 启动时自动种子化（lifespan 检测目录是否存在）

### LangGraph ReAct Agent

- [x] 11 个工具：search_food, save_record, delete_record, replace_record, add_food, remove_food, update_food, get_daily_summary, query_history, show_confirm_card, refuse
- [x] 确认→保存闭环：LLM 调用 show_confirm_card → 前端渲染卡片 → 用户点击确认 → 发送"确认"消息 → LLM 调用 save_record
- [x] CRUD 完整链路：新建/全量替换/追加/移除/修改单个食物/删除整餐
- [x] 工具节点改为 async（`await tool_fn.ainvoke()` 替代 `asyncio.run()`），避免阻塞事件循环
- [x] 系统提示词动态日期 + 餐次推断规则（早上→早餐、中午/午饭→午餐、晚上/晚饭→晚餐）
- [x] **意图分类快速路由**：对确定性操作（查询汇总/历史/食物搜索/拒绝）通过关键词匹配直接调工具，跳过 LLM ReAct 循环，延迟从 5-10s 降到 <1s。新增 `app/agent/intent.py` 分类器 + `graph.py` fast route 分支

### SSE 流式对话

- [x] 6 种结构化消息类型：text、card、summary、refuse、status、done
- [x] **summary 消息类型**：`get_daily_summary` 返回结构化 JSON（`_summary` 标记），graph.py ToolMessage 处理 emit summary 卡片
- [x] **status 消息类型**：等待期间显示上下文状态提示（"正在查询食物数据..."等）
- [x] 早期状态发射：用户消息到达后立即根据关键词匹配发出状态提示，不等 LLM 响应
- [x] 工具调用状态映射：检测到 tool_call 时根据工具名发出对应状态提示
- [x] 输出抑制机制（OUTPUT_TOOLS）：卡片/refuse/汇总等结构化输出后跳过冗余文本
- [x] 后端 `graph.astream(stream_mode="messages")` + JSON 编码
- [x] 前端 chatStream 解析 JSON + 按类型分发渲染

### 前端聊天 UI

- [x] 4 种消息气泡：文本（markdown 渲染）、确认卡片、汇总卡片、拒绝消息
- [x] 自定义 Markdown→HTML 渲染器（`utils/markdown.ts`）：支持表格、标题、列表、加粗、斜体、代码、删除线
- [x] UTF-8 跨 chunk 解码：处理多字节字符在 SSE 分块边界被截断的问题
- [x] Emoji 代理对支持：码点 > U+FFFF 的字符正确解码（`String.fromCharCode` → 代理对）
- [x] 文本可选择复制（`user-select: text` + `-webkit-user-select: text`）
- [x] rich-text 内部样式：表格、列表、标题、代码块、段落
- [x] 占位消息机制（`isPlaceholder` 标志）：状态提示通过更新占位内容逐条显示
- [x] 确认卡片交互：确认按钮 / 修改按钮 → 回传 Agent
- [x] 语音输入模式：点按切换录音 → ASR 识别 → 自动填入发送（Whisper base 模型，本地启动时预加载；服务器端部署受阻，见下方 ASR 服务器部署）
- [x] 开发者工具降级：模拟器中弹文字输入框模拟语音输入
- [x] 流中断处理：新消息发送时 abort 当前 SSE + 清除残留 agent 消息（`_aborting` 标记区分主动 abort 和网络错误）
- [x] 错误/空响应兜底："网络出了点问题，请稍后再试～"
- [x] SSE `done` 消息作为权威结束信号（HTTP 回调仅兜底，避免竞态）
- [x] 前端调试日志：SSE 流生命周期事件跟踪

### 测试

- [x] 112/112 全部通过
- 8 个测试文件：test_agent_tools(10)、test_api(5)、test_config(8)、test_e2e_chat(7)、test_graph(8)、test_intent(58)、test_rag(9)、test_sse_format(14)

## 未完成

### 高优先级（文字功能上线）

- [x] **意图分类快速路由**：确定性操作（查询汇总/历史/拒绝）跳过 LLM ReAct，关键词直接调工具，延迟从 5-10s 降到 <1s。方案：graph 入口加 `classify_intent` 节点 → query/refuse/agent 三条分支
- [x] **备案 + HTTPS**：ICP 备案通过（苏ICP备2026026991号），SSL 证书已部署，备案号已挂网站底部
- [ ] **小程序发布**：微信公众平台配置服务器域名 + 提交审核
- [ ] **内容安全**：未接入微信内容安全 API（msgSecCheck），小程序审核可能需要
- [ ] **后端日志系统**：当前 uvicorn 日志仅输出到终端，无持久化、无分级、无请求追踪。需接入结构化日志（如 loguru），支持请求级别 trace_id、日志文件轮转、按级别过滤

### 中优先级

- [ ] **多轮对话记忆持久化**：MemorySaver 为内存存储，服务重启丢失
- [ ] **分享卡片功能**：设计文档有但未实现（v2 规划）

### 低优先级

- [ ] **语音功能上线**：当前本地 Whisper base 可用但中文识别一般。服务器端部署 SenseVoiceSmall 需 2C4G 或换阿里云 API。先聚焦文字功能发布，语音后续再议。详见 `docs/freeasr-deploy-progress.md`
- [ ] **TiDB Cloud 连接稳定性长期观察**：7 分钟空闲测试通过，pool_pre_ping + pool_recycle 有效。生产环境需持续观察
- [ ] **食物数据扩展**：49 种有限，考虑接入开放食品数据库
- [ ] **热量目标设定**：用户设定每日热量目标 + 超额提醒
- [ ] **部署配置**：Dockerfile、docker-compose、环境变量生产配置
- [ ] **SSE StreamSession 状态机重构**：当前 SSE 流生命周期靠散落 bool 标志（`_aborting`、`hasContent`、`streamDone`、`isPlaceholder`、`_currentStream`）在回调间传递状态，bug 多。理想设计：`StreamSession(idle→connecting→streaming→done/aborted/error)` 状态机，封装 abort/onMessage/onDone/onError，Page 只持有一个 `_session` 引用
- [ ] **LangGraph 真 interrupt 替代伪 interrupt**：确认卡片流程改为 graph 内 `interrupt()` + `Command(resume=...)`，消除两次独立请求带来的 abort 竞态
- [ ] **tool_node 并行化**：同一轮多个 tool_calls 之间无依赖（如 5 个 search_food），改为 `asyncio.gather()` 并行执行，减少串行等待
- [ ] **确认保存不经过 Agent**：用户点击确认后前端直接 `POST /api/records` 保存，跳过 LLM ReAct（当前每次确认浪费 3-5 秒）。是最频繁的操作，优化收益最大

## 环境配置

| 组件 | 配置 | 状态 |
|------|------|------|
| TiDB Cloud | gateway01.ap-southeast-1.prod.alicloud.tidbcloud.com:4000 | 已连接 |
| LLM | MiniMax M2.7 via api.minimaxi.com/anthropic | 已调通 |
| Embedding | BGE-small-zh-v1.5 本地路径 data/bge-small-zh-v1.5/ | 已部署 |
| 微信 AppID | wxc5dc80e3116ed628 | 已配置 |

## 已知问题与修复记录

| 问题 | 原因 | 修复 |
|------|------|------|
| UTF-8 中文乱码（如 `ߍݯ؏`） | UTF-8 多字节字符被 SSE chunk 边界截断 | 添加 leftover buffer，跨 chunk 拼接后解码 |
| Emoji 仍乱码 | `String.fromCharCode` 无法处理 > U+FFFF 码点 | 代理对转换（high/low surrogate） |
| 卡片后重复输出内容 | LLM 在调用 show_confirm_card 的同时输出 markdown 表格 | OUTPUT_TOOLS 机制，检测到结构工具时跳过文本 |
| 汇总卡片显示两遍空卡片 | get_daily_summary 在 OUTPUT_TOOLS 中但还 emit 空卡片 | 移除空卡片 emit，保留文本抑制 |
| 状态和内容同时出现 | ① asyncio.run 阻塞事件循环 ② status 在 LLM 思考后才 emit | ① tool_node 改为 async/await ② 早期关键词匹配 emit |
| 状态文字前端不显示 | 占位消息未设置 contentHtml，rich-text 渲染为空 | 占位创建时设置 contentHtml + status handler 同步更新 |
| status emit 报 UnboundLocalError | `_emit` 在定义前调用 | 将 `_emit` 定义移到早期 status 发射代码之前 |
| `test_query_todays_summary` e2e 失败 | `graph.py` 未实现 `summary` 类型的 emit（协议和前端都定义了，但后端只抑制文本、没发结构化 summary） | `get_daily_summary` 返回结构化 JSON（`_summary` 标记），`graph.py` 处理 ToolMessage 检测并 emit `summary` 消息 |
| 确认后弹出"网络问题"然后正确内容追加在后面 | `sendText()` 中 `abort()` 触发 `wx.request` fail 回调，被误判为网络错误 | `_aborting` 标记：主动 abort 前设 true，error 回调检查跳过 |
| 微信开发者工具 wx:key 重复警告 | 食物列表用 `wx:key="name"`，同名食物导致 key 重复 | 改为 `wx:key="*this"`，用对象引用做唯一 key |
| Whisper 首次请求超时 | 模型懒加载 + base.pt 文件 SHA256 不匹配（24MB 损坏文件） | 改为 lifespan 启动时预加载，自动重新下载完整模型（139MB） |
| 语音 15s 自动停止 | 按住说话模式遗留的 300ms 防误触 + 15s 自动停止定时器 | 改为点按切换模式后移除防误触和自动停止，仅保留 60s 上限 |

## 关键文件

```
docs/
  api-protocol.md       # 前后端接口协议
  progress.md            # 本文件

backend/
  app/main.py            # FastAPI 入口 + lifespan
  app/config.py          # Pydantic Settings（.env）
  app/database.py        # SQLAlchemy async engine + SSL
  app/llm.py             # LLM 抽象层（openai/anthropic）
  app/middleware.py       # JWT create/verify/get_user_id
  app/agent/graph.py     # LangGraph ReAct 图 + run_agent_stream (SSE status + fast route)
  app/agent/tools.py     # 11 个 Agent 工具
  app/agent/prompt.py    # 中文系统提示词（动态日期 + 输出约束）
  app/agent/intent.py    # 意图分类快速路由（关键词匹配 + 日期解析）
  app/rag/store.py       # Chroma + BGE 向量检索
  app/rag/data.py        # 49 种食物营养数据
  app/models/record.py   # FoodRecord + FoodItem 模型
  tests/test_agent_tools.py  # 工具回归测试
  tests/test_e2e_chat.py     # 端到端对话测试
  tests/test_intent.py       # 意图分类单元测试

miniapp/miniprogram/
  utils/api.ts           # HTTP 客户端 + chatStream SSE + UTF-8 解码
  utils/markdown.ts      # 自定义 Markdown→HTML 渲染器（无 npm 依赖）
  pages/index/index.ts   # 聊天页面逻辑（占位/status/卡片/语音）
  pages/index/index.wxml # 聊天 UI 模板（rich-text 渲染）
  pages/index/index.wxss # 聊天 UI 样式（表格/列表/代码/语音动画）
```

## 启动命令

```bash
# 后端
cd backend
cp .env.example .env   # 编辑填入密钥
pip install -r requirements.txt
uvicorn app.main:app --reload

# 测试
curl http://localhost:8000/api/health
python -m pytest tests/ -v

# 测试 SSE 流（需先生成 token）
python -c "from app.middleware import create_token; print(create_token(1))"
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"message":"今天吃了啥"}'
```
