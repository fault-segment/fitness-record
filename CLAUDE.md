# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-user daily diet recording Agent: WeChat Mini Program client + Python FastAPI backend. Users describe meals via text/voice in a pure-chat interface; a LangGraph ReAct Agent parses food items, retrieves nutrition data via RAG, shows a confirmation card, then saves the record. Supports natural-language history queries and nutrition Q&A.

Active work happens in git worktrees (`.worktrees/`), created via the `using-git-worktrees` skill. The main branch holds the stable scaffold and design docs.

## Repository Layout

```
backend/                        FastAPI backend
  app/main.py                   App entry, CORS, lifespan (init DB + seed RAG)
  app/config.py                 Pydantic Settings, reads .env
  app/database.py               SQLAlchemy async engine + SSL, session factory, init_db()
  app/llm.py                    LLM abstraction layer (openai / anthropic provider switch)
  app/middleware.py              JWT create/verify, get_user_id dependency
  app/models/user.py            User model (id, openid, created_at)
  app/models/record.py           FoodRecord + FoodItem models (one-to-many)
  app/routers/auth.py           POST /api/auth/login — wx.login code → JWT
  app/routers/chat.py           POST /api/chat — SSE streaming with JSON typed messages
  app/routers/speech.py         POST /api/speech-to-text — Whisper base 模型，启动时预加载
  app/agent/tools.py            11 Agent tools (search, CRUD, confirm, query, refuse)
  app/agent/graph.py            LangGraph ReAct graph + run_agent_stream() JSON SSE
  app/agent/prompt.py           Chinese system prompt for the diet assistant
  app/rag/                      Chroma vector store + BGE-small-zh-v1.5 (local)
    store.py                    Chroma PersistentClient wrapper (init, search)
    data.py                     49 common Chinese foods with nutrition per 100g
    seed.py                     CLI seed script

miniapp/                        WeChat Mini Program (native TS)
  miniprogram/
    app.ts                      Auto-login via doLogin() on launch
    app.json                    Single page, no TabBar, navigationBar green #07c160
    pages/index/index.*         Chat UI (text/card/summary/refuse message types)
    utils/api.ts                HTTP client + chatStream() SSE with JSON parsing
    utils/storage.ts            Token/userId in wx.storage
  project.config.json           AppID: wxc5dc80e3116ed628, Skyline enabled

docs/
  api-protocol.md               Frontend-backend API protocol (SSE message types)
  progress.md                   Current implementation progress
  plans/                        Implementation plans for pending features
    2026-04-30_backend-logging.md   Backend structured logging with loguru
  superpowers/
    specs/2026-04-24-diet-recorder-design.md     Full design document
    plans/2026-04-27-diet-agent-implementation.md 7-task implementation plan
```

## Commands

> **Python 环境**：项目使用 Python 3.10，venv 位于 `backend/.venv/`。所有 Python 命令需通过 `.venv/bin/python` 运行。

```bash
# Backend setup
cd backend
cp .env.example .env   # then fill in TIDB_*, WECHAT_SECRET, LLM_*, BGE_MODEL_PATH
.venv/bin/pip install -r requirements.txt

# Copy BGE model to local path (avoids HuggingFace download)
mkdir -p data/bge-small-zh-v1.5
# Fill with model files from ~/.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5/snapshots/<hash>/

# Run backend
uvicorn app.main:app --reload

# Seed the RAG food knowledge base (also runs on first startup)
.venv/bin/python -m app.rag.seed

# Run tests
.venv/bin/python -m pytest tests/ -v

# Test API manually
curl http://localhost:8000/api/health
# Generate JWT for testing (user_id=100000 专用于测试，避免干扰 user_id=1 的开发数据):
.venv/bin/python -c "from app.middleware import create_token; print(create_token(100000))"
# Test chat SSE:
curl -s -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"message":"米饭热量？"}' --max-time 120

# Miniapp: Open miniapp/ directory in WeChat Developer Tools
# IMPORTANT: 勾选「详情」→「本地设置」→「不校验合法域名」
```

## Architecture

### Chat Flow (core loop)

```
User text → POST /api/chat (SSE) → LangGraph ReAct Agent
  ├─ agent_node: LLM decides whether to call a tool
  ├─ tool_node: Executes tools (search_food / show_confirm_card / save_record / ...)
  └─ loops back to agent_node until LLM produces a text response
        → SSE stream: JSON typed messages → miniapp renders by type

SSE message types: text, card (confirm), summary, refuse, status, done（6 种）
See docs/api-protocol.md for full spec.
```

### Agent Tools (11)

| Tool | Purpose |
|------|---------|
| `search_food` | Query Chroma for food nutrition data (BGE-small embedding → cosine similarity) |
| `show_confirm_card` | Emit structured confirmation card (foods + totals) for user approval |
| `save_record` | Create new meal record with food items (FoodRecord + FoodItems) |
| `delete_record` | Delete entire meal/day records |
| `replace_record` | Replace all foods in a meal (full swap) |
| `add_food` | Append foods to an existing meal record |
| `remove_food` | Remove specific foods from a meal record |
| `update_food` | Modify a single food item's name/amount/nutrition |
| `get_daily_summary` | Aggregate one day's intake (total kcal + macros + food list) |
| `query_history` | Date-range summary |
| `refuse` | Politely reject non-diet topics |

### Confirmation Flow

```
User: "吃了米饭红烧肉"
  → Agent calls search_food → gets nutrition data
  → Agent calls show_confirm_card(foods_json, totals_json)
  → Backend emits {"type":"card","card_type":"confirm",...}
  → Frontend renders card with [确认] [修改] buttons
  → User clicks [确认] → frontend sends "确认：米饭、红烧肉，共832kcal"
  → Agent calls save_record(...) → data persisted
```

### Auth Flow

1. `wx.login()` → temporary code (silent, no user prompt)
2. `POST /api/auth/login { code }` → backend exchanges with WeChat API → openid
3. Find or create `User` row → issue JWT with `user_id`
4. All subsequent requests: `Authorization: Bearer <jwt>` → `get_user_id` dependency

### Data Model

`users` — (id BIGINT, openid VARCHAR 64 UNIQUE, created_at)
`food_records` — (id BIGINT, user_id BIGINT, record_date DATE, meal_type VARCHAR)
`food_items` — (id BIGINT, record_id FK, food_name, amount_g DECIMAL, kcal INT, protein_g/carbs/fat_g DECIMAL, source VARCHAR)

### RAG: Chroma + BGE-small-zh-v1.5

49 common Chinese foods stored as embeddings in `data/food_chromadb/`. BGE model loaded from local path `data/bge-small-zh-v1.5/` (configurable via `BGE_MODEL_PATH` env var, falls back to HuggingFace if empty). Documents encode food name + nutrition facts + description. Query uses cosine similarity.

### LLM Abstraction

`app/llm.py` provides `get_llm()` factory, switching on `LLM_PROVIDER` env var:
- `"openai"` → `ChatOpenAI` (any OpenAI-compatible endpoint)
- `"anthropic"` → `ChatAnthropic` (DeepSeek v4-flash via `api.deepseek.com/anthropic`)

## Intent Fast Routing

`app/agent/intent.py` provides `classify_intent()` that short-circuits the LLM ReAct loop for deterministic queries. Currently only two routes:

- `query_summary` — "今天吃了什么""看看汇总" → directly calls `get_daily_summary` → emits summary card
- `query_history` — "最近一周""历史记录" → directly calls `query_history` → emits text

`search_food` and `refuse` were removed from fast routing due to regex over-matching (e.g., "兰州牛肉拉面热量这么低吗" was incorrectly routed to food search). When adding new fast routes, always include a negative filter (`_has_record_intent`) to prevent mutation intents from being misrouted.

## WeChat Miniapp Quirks

- **Skyline rendering**: scroll-view padding doesn't work properly with Skyline enabled. Always wrap scroll-view content in a `<view class="chat-inner">` and put padding on the wrapper.
- **wx:else restriction**: `wx:else` must follow a real element with `wx:if`, NOT a `<block>` (virtual node). Use separate `wx:if` conditions instead.
- **Share images**: must be within `miniprogramRoot` (i.e., `miniapp/miniprogram/`), under 128KB, recommended 5:4 ratio.
- **Dev vs Production**: use `wx.getAccountInfoSync().miniProgram.envVersion` to check `'develop'` / `'trial'` / `'release'`.

## Frontend SSE Conventions

- **One bubble per text event**: Each SSE `text` event creates a new message bubble. The backend controls granularity — emit complete thoughts as single events, not token-by-token.
- **done is authoritative**: The SSE `done` event is the definitive end-of-stream signal. HTTP callbacks are fallback only.
- **Placeholder messages**: The "thinking..." message uses `isPlaceholder: true`. Status events update the placeholder. First real content (text/card) filters out all placeholders.

## Deployment

| Item | Detail |
|------|--------|
| Server | Alibaba Cloud 8.152.168.44, 2C2G, Alibaba Cloud Linux 3 |
| SSH | `ssh root@8.152.168.44` |
| Project path | `/opt/fitness-record/` |
| Conda env | `/opt/miniconda/envs/asr/` (Python 3.10) |
| Backend log | `/var/log/dietrecord.log` |
| Nginx config | `/etc/nginx/conf.d/freeasr.conf` |
| Static page | `/var/www/freeasr/` |
| SSL certs | `/etc/nginx/ssl/` |
| Whisper | **Disabled** to save memory (comment out in main.py lifespan + remove speech router) |
| GitHub push | May need proxy: `git config --local http.proxy http://127.0.0.1:7890` |

## Documentation Conventions

- **Plan documents**: Write to `docs/plans/YYYY-MM-DD_<topic>.md` before implementing any non-trivial feature.
- **Spec documents**: Write to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
- **Progress tracking**: Update `docs/progress.md` after each significant change.

## Key Constraints

- **Multi-tenant**: Every DB query must filter by `user_id`. The `get_user_id` FastAPI dependency enforces this at the HTTP layer.
- **Confirmation flow**: Agent MUST call `show_confirm_card` tool before `save_record`. Frontend renders card with confirm/edit buttons. Never save automatically.
- **Machine budget**: Target deployment is 2-core 2GB. BGE-small chosen over large variant for this reason.
- **TiDB Cloud**: MySQL-compatible Serverless tier. Connection via SSL with CA certificate. Serverless tier sleeps after ~5min idle, first request may fail — consider connection pool warmup or retry logic.
- **V2 scope documented only**: Share cards, friend pairing, invite rewards are in the design doc but NOT implemented.
- **API backward compatibility**: When extending an existing endpoint, keep all existing fields. Add new fields alongside, never remove or rename.
- **Git repo root**: All `git` commands must run from `/Users/segment/Project/fitness-record/`. The `backend/` subdirectory is NOT the repo root.
- **Server Python**: Use full path `/opt/miniconda/envs/asr/bin/python` in SSH commands. `source activate` doesn't work in non-interactive SSH.
- **Fast route verb list**: Any new mutation verb (e.g., "删掉") must be added to `_has_record_intent()` in `intent.py` to prevent misrouting.
- **Deployment workflow**: Never push to server directly after code changes. The correct flow is: (1) make changes locally, (2) start local backend + verify in WeChat DevTools, (3) only after user confirms success, commit + push to GitHub + deploy to server.

## Environment Variables (backend/.env)

All required, see `.env.example`:

| Variable | Purpose |
|----------|---------|
| `TIDB_HOST` / `TIDB_PORT` / `TIDB_USER` / `TIDB_PASSWORD` / `TIDB_DATABASE` / `TIDB_CA_PATH` | TiDB Cloud Serverless connection |
| `WECHAT_APPID` / `WECHAT_SECRET` | WeChat Mini Program credentials |
| `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_EXPIRE_DAYS` | JWT signing config |
| `LLM_PROVIDER` | `"openai"` or `"anthropic"` |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | LLM endpoint (Anthropic protocol for MiniMax) |
| `WHISPER_MODEL` | Whisper 模型大小：`tiny` / `base` / `small` / `medium`，默认 `base`（~139MB） |
| `BGE_MODEL_PATH` | Local BGE model path, e.g. `data/bge-small-zh-v1.5` (empty = HF download) |
