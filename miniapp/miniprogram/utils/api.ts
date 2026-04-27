// utils/api.ts
import { getToken, setToken, setUserId, clearAuth } from './storage'

const BASE_URL = 'http://localhost:8000'  // TODO: 替换为正式域名

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

export function chat(message: string): Promise<{ reply: string }> {
  return request('/api/chat', { data: { message } })
}
