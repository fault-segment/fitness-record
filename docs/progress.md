# 工作进度

> 最后更新：2026-04-27

## 已完成

### 基础设施

- [x] FastAPI 项目骨架：config、database、middleware、routers
- [x] TiDB Cloud Serverless 连接（SSL + CA 证书，asyncmy 驱动）
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

- [x] 6 个工具：
  - `search_food` — Chroma 向量检索食物营养数据
  - `save_record` — 保存饮食记录到 TiDB
  - `get_daily_summary` — 查询单日饮食汇总
  - `query_history` — 查询日期范围饮食记录
  - `show_confirm_card` — 展示结构化确认卡片
  - `refuse` — 拒绝非饮食话题
- [x] 确认→保存闭环：LLM 调用 show_confirm_card → 前端渲染卡片 → 用户点击确认 → 发送"确认"消息 → LLM 调用 save_record

### SSE 流式对话

- [x] 5 种结构化消息类型：text、card、summary、refuse、done
- [x] 后端 graph.astream(stream_mode="messages") + JSON 编码
- [x] 前端 chatStream 解析 JSON + 按类型分发渲染
- [x] 确认卡片 → 确认/修改按钮 → 回传 Agent

### 测试

- [x] 冒烟测试：test_search_food_finds_rice、test_search_food_no_match、test_food_data_count（3/3 PASS）
- [x] 端到端测试：curl SSE 端点验证 text/card/summary/done 四种消息

## 未完成

### 高优先级

- [ ] **微信小程序未端到端联调**：模拟器域名校验 + 真实 wx.login 流程 + 完整对话测试
- [ ] **ASR 语音转文字**：POST /api/speech-to-text 占位接口，未接入腾讯云 ASR / 讯飞 / Whisper
- [ ] **用户确认→保存的完整闭环测试**：目前只测了"展示确认卡片"，未测"用户确认→保存→查询汇总"完整链路
- [ ] **TiDB Cloud 连接稳定性**：Serverless 空闲休眠导致首次请求失败，需要连接池预热或重试机制

### 中优先级

- [ ] **内容安全**：未接入微信内容安全 API（msgSecCheck），小程序审核可能需要
- [ ] **小程序发布**：需备案域名 + HTTPS + 微信公众平台配置服务器域名
- [ ] **前端聊天 UI 优化**：loading 态、打字机效果（逐 token 渲染）、错误重试
- [ ] **分享卡片功能**：设计文档有但未实现（v2 规划）

### 低优先级

- [ ] **多轮对话记忆优化**：MemorySaver 为内存存储，服务重启丢失
- [ ] **食物数据扩展**：49 种有限，考虑接入开放食品数据库
- [ ] **热量目标设定**：用户设定每日热量目标 + 超额提醒
- [ ] **部署配置**：Dockerfile、docker-compose、环境变量生产配置

## 环境配置

| 组件 | 配置 | 状态 |
|------|------|------|
| TiDB Cloud | gateway01.ap-southeast-1.prod.alicloud.tidbcloud.com:4000 | 已连接 |
| LLM | MiniMax M2.7 via api.minimaxi.com/anthropic | 已调通 |
| Embedding | BGE-small-zh-v1.5 本地路径 data/bge-small-zh-v1.5/ | 已部署 |
| 微信 AppID | wxc5dc80e3116ed628 | 已配置 |

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
  app/agent/graph.py     # LangGraph ReAct 图 + run_agent_stream
  app/agent/tools.py     # 6 个 Agent 工具
  app/agent/prompt.py    # 中文系统提示词
  app/rag/store.py       # Chroma + BGE 向量检索
  app/rag/data.py        # 49 种食物营养数据
  app/models/record.py   # FoodRecord + FoodItem 模型
  tests/test_agent.py    # 3 个冒烟测试

miniapp/miniprogram/
  utils/api.ts           # HTTP 客户端 + chatStream SSE
  pages/index/index.ts   # 聊天页面逻辑
  pages/index/index.wxml # 聊天 UI 模板
  pages/index/index.wxss # 聊天 UI 样式
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
```
