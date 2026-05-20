# 意图分类快速路由

## Context

当前每条用户消息都走 LLM ReAct 循环（2-4 次 LLM 调用），即使"看看今天吃了什么"这种确定性查询也要 5-10 秒延迟。实际上 5 个工具不需要 LLM 推理：`get_daily_summary`、`query_history`、`search_food`、`refuse`、以及部分确定性确认操作。

目标：对可确定性路由的意图，关键词匹配后直接调工具，延迟降到 <1s。

## 分类策略

### 快速路由意图 → 直接调工具

| 意图 | 关键词 | 动作 |
|------|--------|------|
| `query_summary` | 今天吃了啥/看看汇总/今天吃/昨天吃/前天吃/饮食记录/摄入汇总 | 解析日期 → 直接调 `get_daily_summary` → emit summary → done |
| `query_history` | 最近一周/过去几天/这周/本周/历史记录/统计 | 计算日期范围 → 调 `query_history` → 返回文本 → done |
| `search_food` | 热量/营养/多少卡/kcal/脂肪/蛋白/碳水（不包含"吃了/记录"） | 提取食物名 → 调 `search_food` → 返回文本 → done |
| `refuse` | 天气/新闻/股票/电影/音乐/游戏（明确非饮食话题） | 调 `refuse` → emit refuse → done |

### 回退至 LLM ReAct

- 包含"吃了"、"记录了"、具体食物+分量 → 需要 LLM 解析食物、生成确认卡片
- 确认/修改/删除/替换/追加/移除 → 需要 LLM 理解修改意图
- 复合意图（同时问热量+汇总） → 需要 LLM 多工具编排
- 无法匹配任何快速路由关键词

## 方案

在 `run_agent_stream()` 入口处加 `classify_intent(message)` 预检，命中快速路由则直接调工具返回，未命中走原 LLM ReAct 流程。不修改 graph 结构。

### 实现

**新文件：`backend/app/agent/intent.py`**

核心函数：
- `classify_intent(message: str) -> tuple[str, str | None, dict | None]`
- 关键词匹配优先级：refuse > query_summary > query_history > search_food > agent
- 日期解析辅助：从消息中提取"今天/昨天/前天/周几"等

**修改文件：`backend/app/agent/graph.py`**

在 `run_agent_stream()` 开头加入快速路由分支：

```python
intent, tool_name, tool_args = classify_intent(user_message)
if intent == "fast":
    # 直接调工具，emit 结果，yield done，return
    result = await tool_fn.ainvoke(tool_args)
    yield _emit(...)  # 根据工具类型 emit 不同消息
    yield _emit("done")
    return
# 否则走原有 LLM ReAct
```

### 日期解析

- "今天" → `date.today()`
- "昨天" → `date.today() - timedelta(days=1)`
- "前天" → `date.today() - timedelta(days=2)`
- "最近N天" → 范围查询
- 默认 → 今天

### SSE 输出

快速路由的输出要兼容现有前端渲染：
- `query_summary` → emit `summary` 消息（同现有格式）
- `search_food` → emit `text` 消息（搜索结果文本）
- `query_history` → emit `text` 消息（汇总文本）
- `refuse` → emit `refuse` 消息

### 日志

快速路由命中时记录 `logger.info("fast_route: {intent} matched")`，方便观察命中率。

## 实施顺序

1. 创建 `app/agent/intent.py` — 关键词列表 + `classify_intent()` + 日期解析
2. 修改 `app/agent/graph.py` — `run_agent_stream()` 入口加快速路由分支
3. 测试：添加 `tests/test_intent.py` — 覆盖各意图分类正确性 + 边界情况
4. 端到端验证：curl 测试快速路由响应时间 < 1s

## 验证

```bash
# 快速路由 — 应 < 1s 返回 summary
curl -s -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"message":"看看今天的饮食汇总"}' --max-time 5

# 快速路由 — 食物搜索
curl ... -d '{"message":"米饭热量多少"}'

# 快速路由 — 拒绝
curl ... -d '{"message":"今天天气怎么样"}'

# 回退 LLM — 记录饮食
curl ... -d '{"message":"我今天中午吃了200g米饭和150g红烧肉"}'

# 运行测试
python -m pytest tests/ -v
```

## 影响范围

| 文件 | 操作 | 风险 |
|------|------|------|
| `app/agent/intent.py` | 新建 | 低 — 独立模块 |
| `app/agent/graph.py` | 修改 `run_agent_stream()` | 中 — 核心流程，需保持向后兼容 |
| `tests/test_intent.py` | 新建 | 低 |
| `docs/progress.md` | 更新 | 低 |
