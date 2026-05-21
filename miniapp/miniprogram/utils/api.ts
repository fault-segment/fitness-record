// utils/api.ts
import { getToken, setToken, setUserId, clearAuth } from './storage'

// 生产环境走线上服务器，本地开发可切回 localhost
function getBaseUrl(): string {
  // return 'http://localhost:8000'  // 本地开发
  return 'https://www.dietrecord.top'   // 线上服务器
}
const BASE_URL = getBaseUrl()

interface RequestOptions {
  auth?: boolean
  method?: 'GET' | 'POST'
  data?: Record<string, any>
}

function request<T = any>(path: string, options: RequestOptions = {}): Promise<T> {
  const { auth = true, method = 'POST', data } = options

  const header: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (auth) {
    const token = getToken()
    if (token) {
      header['Authorization'] = `Bearer ${token}`
    }
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${BASE_URL}${path}`,
      method,
      header,
      data,
      success(res) {
        if (res.statusCode === 401) {
          clearAuth()
          doLogin().then(() => {
            // 重试一次
            if (auth) {
              const token = getToken()
              if (token) header['Authorization'] = `Bearer ${token}`
            }
            wx.request({
              url: `${BASE_URL}${path}`, method, header, data,
              success(r) {
                if (r.statusCode === 200) resolve(r.data as T)
                else reject(r.data)
              },
              fail: reject,
            })
          })
          return
        }
        if (res.statusCode === 200) {
          resolve(res.data as T)
        } else {
          reject(res.data)
        }
      },
      fail: reject,
    })
  })
}

let loginPromise: Promise<void> | null = null

export function doLogin(): Promise<void> {
  if (loginPromise) return loginPromise

  loginPromise = new Promise((resolve, reject) => {
    wx.login({
      success(res) {
        if (!res.code) {
          loginPromise = null
          reject(new Error('wx.login 失败'))
          return
        }
        request<{ token: string; user_id: number; is_new: boolean }>(
          '/api/auth/login',
          { auth: false, data: { code: res.code } }
        )
          .then((data) => {
            setToken(data.token)
            setUserId(data.user_id)
            const app = getApp<IAppOption>()
            app.globalData.isNewUser = data.is_new
            loginPromise = null
            resolve()
          })
          .catch((err) => {
            loginPromise = null
            reject(err)
          })
      },
      fail(err) {
        loginPromise = null
        reject(err)
      },
    })
  })

  return loginPromise
}

// ---- 今日汇总 ----

export interface TodaySummary {
  date: string
  kcal: number
  protein: number
  carbs: number
  fat: number
  food_count: number
  meals: {
    meal_type: string
    kcal: number
    foods: {
      name: string
      amount: string
      kcal: number
    }[]
  }[]
}

export function fetchTodaySummary(): Promise<TodaySummary> {
  return request<TodaySummary>('/api/today-summary', { method: 'GET', auth: true })
}

// ---- SSE 消息类型 ----

export interface SSEText {
  type: 'text'
  content: string
}

export interface SSEFood {
  name: string
  amount: string
  kcal: number
  protein?: number
  carbs?: number
  fat?: number
}

export interface SSETotals {
  kcal: number
  protein: number
  carbs: number
  fat: number
}

export interface SSECard {
  type: 'card'
  card_type: 'confirm'
  foods: SSEFood[]
  totals: SSETotals
}

export interface SSESummary {
  type: 'summary'
  title: string
  date: string
  foods: SSEFood[]
  meals?: { meal_type: string; kcal: number; foods: SSEFood[] }[]
  totals: SSETotals
}

export interface SSERefuse {
  type: 'refuse'
  content: string
}

export interface SSEDone {
  type: 'done'
}

export interface SSEStatus {
  type: 'status'
  content: string
}

export type SSEMessage = SSEText | SSECard | SSESummary | SSERefuse | SSEDone | SSEStatus

// ---- SSE 流式对话 ----

export function chatStream(
  message: string,
  onMessage: (msg: SSEMessage) => void,
  onDone: () => void,
  onError: (err: any) => void,
): { abort: () => void } {
  const token = getToken()
  const header: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) header['Authorization'] = `Bearer ${token}`

  const task = wx.request({
    url: `${BASE_URL}/api/chat`,
    method: 'POST',
    header,
    data: { message },
    enableChunked: true,
    success: () => onDone(),
    fail: onError,
  })

  let textBuffer = ''
  let leftover: number[] = []

  task.onChunkReceived((res: any) => {
    // 将上一轮残留的字节拼到当前 chunk 前面，处理跨 chunk 截断
    const raw = new Uint8Array(leftover.length + res.data.byteLength)
    raw.set(new Uint8Array(leftover), 0)
    raw.set(new Uint8Array(res.data), leftover.length)
    leftover = []

    let text = ''
    let i = 0
    while (i < raw.length) {
      const b = raw[i]
      if (b < 0x80) {
        text += String.fromCharCode(b)
        i++
      } else if (b < 0xE0) {
        if (i + 1 >= raw.length) { leftover.push(raw[i]); i++; continue }
        text += String.fromCharCode(((b & 0x1F) << 6) | (raw[i + 1] & 0x3F))
        i += 2
      } else if (b < 0xF0) {
        if (i + 2 >= raw.length) { leftover = Array.from(raw.slice(i)); break }
        text += String.fromCharCode(((b & 0x0F) << 12) | ((raw[i + 1] & 0x3F) << 6) | (raw[i + 2] & 0x3F))
        i += 3
      } else {
        if (i + 3 >= raw.length) { leftover = Array.from(raw.slice(i)); break }
        const cp = ((b & 0x07) << 18) | ((raw[i + 1] & 0x3F) << 12) | ((raw[i + 2] & 0x3F) << 6) | (raw[i + 3] & 0x3F)
        // 超出 BMP 的字符（emoji 等）需要用代理对表示
        if (cp > 0xFFFF) {
          const high = 0xD800 + ((cp - 0x10000) >> 10)
          const low = 0xDC00 + ((cp - 0x10000) & 0x3FF)
          text += String.fromCharCode(high, low)
        } else {
          text += String.fromCharCode(cp)
        }
        i += 4
      }
    }

    textBuffer += text
    const lines = textBuffer.split('\n')
    textBuffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim()
        if (!data) continue
        try {
          const msg = JSON.parse(data) as SSEMessage
          onMessage(msg)
        } catch {
          // 非 JSON 数据（如 ping），忽略
        }
      }
    }
  })

  return { abort: () => task.abort() }
}
