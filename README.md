# 饮食记录助手

微信小程序 + FastAPI 后端的饮食记录 Agent。用户通过文字描述吃了什么，LangGraph ReAct Agent 自动解析食物、RAG 检索营养数据、展示确认卡片后保存记录。支持自然语言历史查询和营养问答。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | 微信小程序（原生 TypeScript） |
| 后端 | Python FastAPI + LangGraph |
| LLM | DeepSeek V4 Flash（Anthropic 协议） |
| RAG | Chroma + BGE-small-zh-v1.5 |
| 数据库 | TiDB Cloud Serverless（MySQL 兼容） |
| ASR | Whisper base（本地，暂未上线） |

## 项目结构

```
backend/          FastAPI 后端
  app/
    agent/        LangGraph ReAct Agent（图、工具、意图分类）
    rag/          Chroma 向量存储 + 49 种食物营养数据
    routers/      API 路由（auth、chat、speech）
    models/       数据模型（User、FoodRecord、FoodItem）
miniapp/          微信小程序
  miniprogram/
    pages/index/  聊天页面
    utils/        API 客户端、Markdown 渲染
docs/             文档（接口协议、进度、设计文档）
```

## 本地运行

```bash
cd backend
cp .env.example .env   # 编辑填入密钥
pip install -r requirements.txt
uvicorn app.main:app --reload

# 运行测试
python -m pytest tests/ -v
```

## 许可证

MIT
