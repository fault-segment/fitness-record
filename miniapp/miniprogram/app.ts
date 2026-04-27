// app.ts
import { doLogin } from './utils/api'

App<IAppOption>({
  globalData: {
    isNewUser: false,
  },
  onLaunch() {
    doLogin().then(() => {
      console.log('登录成功')
    }).catch(err => {
      console.error('登录失败', err)
    })
  },
})