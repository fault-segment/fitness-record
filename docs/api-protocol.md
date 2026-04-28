# 前后端接口协议

## 基础信息

- **Base URL**: `http://localhost:8000`（开发）/ 生产域名待定
- **编码**: UTF-8
- **认证**: JWT Bearer Token（`Authorization: Bearer <token>`），登录接口除外

---

## 1. 认证

### POST /api/auth/login

微信小程序静默登录，`wx.login()` 获取临时 code 换取 JWT。

**Request:**
```json
{
  "code": "0b1a2b3c..."  // wx.login() 返回的临时 code
}
```

**Response 200:**
```json
{
  "token": "eyJhbGci...",   // JWT，后续请求携带
  "user_id": 1,
  "is_new": true             // 新用户为 true，前端据此决定是否展示欢迎语
}
```

**Error 400:**
```json
{
  "detail": "invalid code, rid: ..."
}
```

---

## 2. 对话（SSE 流式）

### POST /api/chat

**Request:**
```
Authorization: Bearer <token>
Content-Type: application/json
```
```json
{
  "message": "中午吃了米饭红烧肉"
}
```

**Response:** `text/event-stream`（SSE）

每条 `data:` 行是一个 JSON 对象，`type` 字段区分消息类型：

```
data: {"type":"text","content":"好的"}

data: {"type":"text","content":"，帮你整理"}

data: {"type":"text","content":"好了\n"}

data: {"type":"card","card_type":"confirm","foods":[{"name":"米饭","amount":"200g","kcal":232},{"name":"红烧肉","amount":"150g","kcal":368}],"totals":{"kcal":600,"protein":24,"carbs":56,"fat":38}}

data: {"type":"text","content":"确认无误的话点击确认按钮～"}

data: {"type":"done"}
```

### 消息类型定义

#### text — 文本 token（流式）

LLM 生成的文本片段，前端拼接后逐字显示。

```json
{
  "type": "text",
  "content": "..."
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定 `"text"` |
| content | string | 文本片段，前端累加拼接 |

#### card — 卡片消息

需要前端渲染为卡片组件，目前有确认卡片类型。

```json
{
  "type": "card",
  "card_type": "confirm",
  "foods": [
    {"name": "米饭", "amount": "200g", "kcal": 232},
    {"name": "红烧肉", "amount": "150g", "kcal": 368}
  ],
  "totals": {
    "kcal": 600,
    "protein": 24,
    "carbs": 56,
    "fat": 38
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定 `"card"` |
| card_type | string | `"confirm"` — 确认卡片（含食物列表+营养素合计+确认/修改按钮） |
| foods | array | 食物列表 |
| foods[].name | string | 食物名称 |
| foods[].amount | string | 估算份量（如 "200g"、"1碗"） |
| foods[].kcal | number | 该食物估算热量 |
| totals.kcal | number | 总热量 |
| totals.protein | number | 总蛋白质（g） |
| totals.carbs | number | 总碳水（g） |
| totals.fat | number | 总脂肪（g） |

#### summary — 汇总消息

查询某天或某时间段的饮食汇总时使用。

```json
{
  "type": "summary",
  "title": "📅 2026-04-27 摄入汇总",
  "date": "2026-04-27",
  "foods": [
    {"name": "米饭", "amount": "200g", "kcal": 232}
  ],
  "totals": {
    "kcal": 232,
    "protein": 5,
    "carbs": 52,
    "fat": 0.6
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定 `"summary"` |
| title | string | 汇总标题 |
| date | string | 日期 `YYYY-MM-DD`，或日期范围 `YYYY-MM-DD ~ YYYY-MM-DD` |
| foods | array | 食物列表（同上） |
| totals | object | 营养素合计（同上） |

#### refuse — 拒绝消息

用户话题与饮食无关时的拒绝回复。

```json
{
  "type": "refuse",
  "content": "抱歉，我只能帮你记录饮食和回答食物相关的问题哦～"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 固定 `"refuse"` |
| content | string | 拒绝文案 |

#### done — 流结束

```json
{
  "type": "done"
}
```

标记本次对话回复结束，前端可停止 loading 状态。

### 前端交互流程

```
用户输入文字
  │
  ▼
POST /api/chat { message }
  │
  ▼
SSE stream 开始
  ├─ {"type":"text","content":"..."}  → 逐字追加到聊天气泡
  ├─ {"type":"text","content":"..."}
  ├─ {"type":"card","card_type":"confirm",...} → 渲染确认卡片（含确认/修改按钮）
  ├─ {"type":"text","content":"..."}  → 追加提示文字
  └─ {"type":"done"}                  → 关闭 loading 状态
  │
  ▼
用户点击"确认"按钮
  │
  ▼
POST /api/chat { message: "确认" }    → 触发 Agent 调用 save_record
  │
  ▼
SSE stream
  ├─ {"type":"text","content":"已保存..."}
  └─ {"type":"done"}
```

---

## 3. 语音转文字（ASR）

### POST /api/speech-to-text

**Request:** `multipart/form-data`
| 字段 | 类型 | 说明 |
|------|------|------|
| audio | file | 音频文件，16kHz mp3 |

**Response 200:**
```json
{
  "text": "中午吃了米饭红烧肉"
}
```

---

## 4. 健康检查

### GET /api/health

**Response 200:**
```json
{
  "status": "ok"
}
```

---

## 5. 错误处理

### token 无效或未登录

```json
{
  "detail": "请先登录"
}
```

HTTP Status: `401`

### 参数校验失败

```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

HTTP Status: `422`
