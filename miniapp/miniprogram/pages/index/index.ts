// index.ts
import { chat as chatApi } from '../../utils/api'

interface IMsg {
  role: 'user' | 'agent'
  type: 'text' | 'confirm' | 'calendar' | 'refuse'
  content: string
  foods?: IFood[]
}

interface IFood {
  name: string
  amount: string
  kcal: number
}

const GREETING = '你好！我是你的饮食助手 🍽\n\n你可以直接告诉我吃了什么，我来帮你记录和分析热量。\n\n也可以试试：\n🍚 记录饮食：「中午吃了米饭红烧肉」\n📅 查看记录：「看看今天的饮食」\n💬 营养咨询：「牛油果热量高吗？」'

Page({
  data: {
    messages: [] as IMsg[],
    inputValue: '',
    inputBottom: 0,
    scrollTop: 0,
  },

  onLoad() {
    // 检查是否新用户，老用户不弹出完整开场白
    const app = getApp<IAppOption>()
    const isNew = app.globalData.isNewUser
    if (isNew) {
      this.addMsg('agent', 'text', GREETING)
    } else {
      this.addMsg('agent', 'text', '欢迎回来！今天还没记录呢，吃了什么？')
    }
  },

  onKeyboardHeightChange(e: any) {
    this.setData({ inputBottom: e.detail.height })
  },

  addMsg(role: 'user' | 'agent', type: string, content: string, foods?: IFood[]) {
    const msg: IMsg = { role, type: type as IMsg['type'], content, foods }
    const msgs = [...this.data.messages, msg]
    this.setData({ messages: msgs }, () => {
      this.setData({ scrollTop: 99999 })
    })
  },

  onInput(e: any) {
    this.setData({ inputValue: e.detail.value })
  },

  sendText() {
    const text = this.data.inputValue.trim()
    if (!text) return
    this.setData({ inputValue: '' })
    this.addMsg('user', 'text', text)

    // 调后端
    chatApi(text).then(res => {
      this.addMsg('agent', 'text', res.reply)
    }).catch(() => {
      this.addMsg('agent', 'text', '网络出了点问题，请稍后再试～')
    })
  },

  startVoice() {
    const recorder = wx.getRecorderManager()

    recorder.onStart(() => {
      wx.showToast({ title: '正在听...', icon: 'none', duration: 60000 })
    })

    recorder.onStop((res) => {
      wx.hideToast()
      const tempPath = res.tempFilePath
      // 上传音频到后端做 ASR
      wx.showLoading({ title: '识别中...' })
      wx.uploadFile({
        url: 'http://localhost:8000/api/speech-to-text',
        filePath: tempPath,
        name: 'audio',
        success: (resp) => {
          wx.hideLoading()
          const data = JSON.parse(resp.data) as { text: string }
          this.setData({ inputValue: data.text })
          this.sendText()
        },
        fail: () => {
          wx.hideLoading()
          wx.showToast({ title: '语音识别失败，请重试', icon: 'none' })
        },
      })
    })

    recorder.onError((err) => {
      wx.hideToast()
      wx.showToast({ title: '录音失败，请重试', icon: 'none' })
    })

    recorder.start({
      duration: 60000,
      sampleRate: 16000,
      format: 'mp3',
    })

    setTimeout(() => recorder.stop(), 15000)
  },

  // 确认卡片操作
  onConfirm(e: any) {
    const idx = e.currentTarget.dataset.index
    this.addMsg('user', 'text', '确认 ✓')
    // TODO: 后续接入 save_record
  },

  onEditCard(e: any) {
    const idx = e.currentTarget.dataset.index
    this.addMsg('user', 'text', '我需要修改一下...')
    // TODO: 后续接入修改逻辑
  },
})
