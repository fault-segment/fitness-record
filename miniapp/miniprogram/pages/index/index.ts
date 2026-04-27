// index.ts
import { chatStream, SSEMessage, SSEFood, SSETotals } from '../../utils/api'

interface IMsg {
  role: 'user' | 'agent'
  type: 'text' | 'card' | 'summary' | 'refuse'
  content: string
  foods?: SSEFood[]
  totals?: SSETotals
  card_type?: string
  date?: string
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

  addMsg(role: 'user' | 'agent', type: IMsg['type'], content: string, extra?: Partial<IMsg>) {
    const msg: IMsg = { role, type, content, ...extra }
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

    // Agent 回复 — 默认占位
    const msgIdx = this.data.messages.length
    this.addMsg('agent', 'text', '思考中...')

    let hasContent = false

    chatStream(
      text,
      (msg: SSEMessage) => {
        if (!hasContent) {
          // 替换"思考中"占位
          hasContent = true
        }

        switch (msg.type) {
          case 'text': {
            // 如果最后一条消息是 text 类型，追加内容；否则新建
            const msgs = [...this.data.messages]
            const last = msgs[msgs.length - 1]
            if (last && last.role === 'agent' && last.type === 'text') {
              last.content = (last.content === '思考中...' ? '' : last.content) + msg.content
            } else {
              msgs.push({ role: 'agent', type: 'text', content: msg.content })
            }
            this.setData({ messages: msgs }, () => {
              this.setData({ scrollTop: 99999 })
            })
            break
          }

          case 'card': {
            const msgs = [...this.data.messages]
            msgs.push({
              role: 'agent',
              type: 'card',
              card_type: msg.card_type,
              foods: msg.foods,
              totals: msg.totals,
              content: '',
            })
            this.setData({ messages: msgs }, () => {
              this.setData({ scrollTop: 99999 })
            })
            break
          }

          case 'summary': {
            const msgs = [...this.data.messages]
            msgs.push({
              role: 'agent',
              type: 'summary',
              foods: msg.foods,
              totals: msg.totals,
              date: msg.date,
              content: msg.title,
            })
            this.setData({ messages: msgs }, () => {
              this.setData({ scrollTop: 99999 })
            })
            break
          }

          case 'refuse': {
            const msgs = [...this.data.messages]
            msgs.push({ role: 'agent', type: 'refuse', content: msg.content })
            this.setData({ messages: msgs }, () => {
              this.setData({ scrollTop: 99999 })
            })
            break
          }

          case 'done':
            // done 消息不渲染
            break
        }
      },
      () => {
        // onDone — 确保没有残留 "思考中"
        const msgs = [...this.data.messages]
        const last = msgs[msgs.length - 1]
        if (last && last.role === 'agent' && last.content === '思考中...' && !hasContent) {
          last.content = '网络出了点问题，请稍后再试～'
        }
        this.setData({ messages: msgs })
      },
      () => {
        // onError
        const msgs = [...this.data.messages]
        msgs.push({ role: 'agent', type: 'text', content: '网络出了点问题，请稍后再试～' })
        this.setData({ messages: msgs })
      },
    )
  },

  startVoice() {
    const recorder = wx.getRecorderManager()

    recorder.onStart(() => {
      wx.showToast({ title: '正在听...', icon: 'none', duration: 60000 })
    })

    recorder.onStop((res) => {
      wx.hideToast()
      const tempPath = res.tempFilePath
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

    recorder.onError(() => {
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

  // 确认卡片 — 用户点击确认
  onConfirm(e: any) {
    const idx = e.currentTarget.dataset.index
    const msg = this.data.messages[idx]
    const foodNames = (msg.foods || []).map((f: SSEFood) => f.name).join('、')
    const totalKcal = msg.totals?.kcal || 0
    this.setData({ inputValue: `确认：${foodNames}，共${totalKcal}kcal` })
    this.sendText()
  },

  // 确认卡片 — 用户点击修改
  onEditCard(e: any) {
    const idx = e.currentTarget.dataset.index
    const msg = this.data.messages[idx]
    const foodNames = (msg.foods || []).map((f: SSEFood) => f.name).join('、')
    this.setData({ inputValue: `我想修改：${foodNames}，帮我调整一下` })
    this.sendText()
  },
})
