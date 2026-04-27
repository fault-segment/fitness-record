// utils/storage.ts
const TOKEN_KEY = 'auth_token'
const USER_ID_KEY = 'user_id'

export function setToken(token: string): void {
  wx.setStorageSync(TOKEN_KEY, token)
}

export function getToken(): string | undefined {
  return wx.getStorageSync(TOKEN_KEY)
}

export function setUserId(id: number): void {
  wx.setStorageSync(USER_ID_KEY, id)
}

export function getUserId(): number | undefined {
  return wx.getStorageSync(USER_ID_KEY)
}

export function clearAuth(): void {
  wx.removeStorageSync(TOKEN_KEY)
  wx.removeStorageSync(USER_ID_KEY)
}
