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
  app/database.py               SQLAlchemy async engine + session factory, init_db()
  app/middleware.py              JWT create/verify, get_user_id dependency
  app/models/user.py            User model (id, openid, created_at)
  app/models/record.py           FoodRecord + FoodItem models (one-to-many)
  app/routers/auth.py           POST /api/auth/login — wx.login code → JWT
  app/routers/chat.py           POST /api/chat — Agent chat (placeholder, becoming SSE)
  app/routers/speech.py         POST /api/speech-to-text — ASR placeholder
  app/agent/tools.py            Agent tool implementations (search_food, save_record, ...)
  app/agent/graph.py            LangGraph ReAct graph + run_agent_stream()
  app/agent/prompt.py           Chinese system prompt for the diet assistant
  app/rag/                      Chroma vector store for food nutrition data
    store.py                    Chroma PersistentClient wrapper (init, search)
    data.py                     49 common Chinese foods with nutrition per 100g
    seed.py                     CLI seed script

miniapp/                        WeChat Mini Program (native TS)
  miniprogram/
    app.ts                      Auto-login via doLogin() on launch
    app.json                    Single page, no TabBar, navigationBar green #07c160
    pages/index/index.*         Chat UI page (the only page)
    utils/api.ts                HTTP client with auto token-refresh on 401
    utils/storage.ts            Token/userId in wx.storage
  project.config.json           AppID: wxc5dc80e3116ed628, Skyline enabled

docs/superpowers/
  specs/2026-04-24-diet-recorder-design.md     Full design document
  plans/2026-04-27-diet-agent-implementation.md 7-task implementation plan
```

## Commands

```bash
# Backend setup
cd backend
cp .env.example .env   # then fill in DATABASE_URL, WECHAT_SECRET, LLM_API_KEY
pip install -r requirements.txt

# Run backend
uvicorn app.main:app --reload

# Seed the RAG food knowledge base (also runs on first startup)
python -m app.rag.seed

# Run tests
python -m pytest tests/ -v

# Miniapp: Open miniapp/ directory in WeChat Developer Tools
```

## Architecture

### Chat Flow (core loop)

```
User text → POST /api/chat (SSE) → LangGraph ReAct Agent
  ├─ agent_node: LLM decides whether to call a tool
  ├─ tool_node: Executes search_food / save_record / get_daily_summary / ...
  └─ loops back to agent_node until LLM produces a text response
        → Tokens streamed back via SSE to miniapp
```

### Agent Tools (5)

| Tool | Purpose |
|------|---------|
| `search_food` | Query Chroma for food nutrition data (BGE-small embedding → cosine similarity) |
| `save_record` | Write confirmed food items to TiDB Cloud (FoodRecord + FoodItems) |
| `get_daily_summary` | Aggregate one day's intake (total kcal + macros + food list) |
| `query_history` | Date-range summary |
| `refuse` | Politely reject non-diet topics |

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

49 common Chinese foods stored as embeddings in `data/food_chromadb/`. The `SentenceTransformer("BAAI/bge-small-zh-v1.5")` model downloads on first use (~100MB, ~300MB RAM). Documents encode food name + nutrition facts + description. Query uses cosine similarity.

## Key Constraints

- **Multi-tenant**: Every DB query must filter by `user_id`. The `get_user_id` FastAPI dependency enforces this at the HTTP layer.
- **Confirmation flow**: Agent MUST show a confirmation card before calling `save_record`. Never save automatically.
- **Machine budget**: Target deployment is 2-core 2GB. BGE-small chosen over large variant for this reason.
- **TiDB Cloud**: MySQL-compatible Serverless tier. Connection string will be provided later; placeholder `mysql+asyncmy://root:@127.0.0.1:4000/diet_recorder` for now.
- **V2 scope documented only**: Share cards, friend pairing, invite rewards are in the design doc but NOT implemented.

## Environment Variables (backend/.env)

All required, see `.env.example`:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | TiDB Cloud Serverless connection (mysql+asyncmy://) |
| `WECHAT_APPID` / `WECHAT_SECRET` | WeChat Mini Program credentials |
| `JWT_SECRET` | Secret for signing JWT tokens |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | OpenAI-compatible LLM endpoint |
