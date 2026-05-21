// index.ts
import { chatStream, SSEMessage, SSEFood, SSETotals, fetchTodaySummary, TodaySummary } from '../../utils/api'
import { renderMarkdown } from '../../utils/markdown'

interface IMsg {
  role: 'user' | 'agent'
  type: 'text' | 'card' | 'summary' | 'refuse'
  content: string
  contentHtml?: string
  foods?: SSEFood[]
  totals?: SSETotals
  card_type?: string
  date?: string
  isPlaceholder?: boolean
}

const GREETING = '你好！我是你的饮食助手 🍽\n\n你可以直接告诉我吃了什么，我来帮你记录和分析热量。\n\n也可以试试：\n🍚 记录饮食：「中午吃了米饭红烧肉」\n📅 查看记录：「看看今天的饮食」\n💬 营养咨询：「牛油果热量高吗？」'

Page({
  data: {
    messages: [] as IMsg[],
    inputValue: '',
    inputBottom: 0,
    scrollTop: 0,
    voiceMode: false,
    isRecording: false,
    voiceText: '',
    debugLog: [] as string[],
    debugExpanded: false,
    isDev: true,  // 非正式版显示调试栏
    todaySummary: { kcal: 0, protein: 0, carbs: 0, fat: 0, food_count: 0 } as TodaySummary,
  },

  _debug(msg: string) {
    const time = new Date().toLocaleTimeString()
    const logs = [...this.data.debugLog, `[${time}] ${msg}`].slice(-6)
    this.setData({ debugLog: logs })
    console.log('[DEBUG]', msg)
  },

  toggleDebug() {
    this.setData({ debugExpanded: !this.data.debugExpanded })
  },

  onShareAppMessage() {
    return {
      title: '饮食记录助手 — 轻松记录每日饮食',
      path: '/pages/index/index',
      imageUrl: '/images/share_image.png',  // 可放分享图片 5:4 比例，不填用默认截图
    }
  },

  onShareTimeline() {
    return {
      title: '饮食记录助手 — 轻松记录每日饮食',
      imageUrl: '/images/share_image.png',
    }
  },

  onLoad() {
    try {
      const accountInfo = wx.getAccountInfoSync()
      this.setData({ isDev: accountInfo.miniProgram.envVersion !== 'release' })
    } catch (_) {
      // 旧版本不支持 getAccountInfoSync，默认显示调试栏
    }
    this.fetchTodaySummary((summary) => {
      if (summary.food_count > 0) {
        this._todayCardPushed = true
        return
      }
      // 无今日记录，显示欢迎语
      const app = getApp<IAppOption>()
      if (app.globalData.isNewUser) {
        this.addMsg('agent', 'text', GREETING, { contentHtml: renderMarkdown(GREETING) })
      } else {
        const welcomeBack = '欢迎回来！今天还没记录呢，吃了什么？'
        this.addMsg('agent', 'text', welcomeBack, { contentHtml: renderMarkdown(welcomeBack) })
      }
    })
  },

  onShow() {
    this.fetchTodaySummary()
  },

  fetchTodaySummary(onDone?: (summary: TodaySummary) => void) {
    fetchTodaySummary().then((summary: TodaySummary) => {
      this.setData({ todaySummary: summary })
      if (summary.food_count > 0 && !this._todayCardPushed) {
        this._todayCardPushed = true
        const foods = summary.meals.flatMap((m: any) =>
          m.foods.map((f: any) => ({ name: f.name, amount: f.amount, kcal: f.kcal }))
        )
        this.addMsg('agent', 'summary', `${summary.date} 今日饮食`, {
          date: summary.date,
          foods,
          totals: {
            kcal: summary.kcal,
            protein: summary.protein,
            carbs: summary.carbs,
            fat: summary.fat,
          },
        })
      }
      onDone && onDone(summary)
    }).catch(() => {
      // 静默失败，顶部栏显示为空
    })
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

    // 打断当前流：abort SSE 连接，清除上一轮的 agent 消息
    if (this._currentStream) {
      this._aborting = true
      this._currentStream.abort()
      this._currentStream = null
      this._cleanupPartialAgentMsgs()
    }

    this.addMsg('user', 'text', text)
    this.addMsg('agent', 'text', '思考中...', { isPlaceholder: true, contentHtml: renderMarkdown('思考中...') })

    let hasContent = false
    let streamDone = false
    const streamStart = Date.now()

    this._currentStream = chatStream(
      text,
      (msg: SSEMessage) => {
        if (!hasContent) {
          hasContent = true
          this._debug(`第一个消息: type=${msg.type} (${Date.now() - streamStart}ms)`)
        }

        switch (msg.type) {
          case 'text': {
            this._debug(`text: "${msg.content.slice(0, 30)}"`)
            const msgs = this.data.messages.filter((m: IMsg) => !m.isPlaceholder)
            msgs.push({ role: 'agent', type: 'text', content: msg.content, contentHtml: renderMarkdown(msg.content) })
            this.setData({ messages: msgs }, () => {
              this.setData({ scrollTop: 99999 })
            })
            break
          }

          case 'card': {
            this._debug(`card: ${(msg.foods || []).length}种食物`)
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
            this._debug(`summary: ${msg.date}, ${(msg.foods || []).length}种食物`)
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
            this._debug('refuse')
            const msgs = [...this.data.messages]
            msgs.push({ role: 'agent', type: 'refuse', content: msg.content, contentHtml: renderMarkdown(msg.content) })
            this.setData({ messages: msgs }, () => {
              this.setData({ scrollTop: 99999 })
            })
            break
          }

          case 'status': {
            this._debug(`status: ${msg.content}`)
            const msgs = [...this.data.messages]
            const last = msgs[msgs.length - 1]
            if (last && last.isPlaceholder) {
              last.content = msg.content
              last.contentHtml = renderMarkdown(msg.content)
            }
            this.setData({ messages: msgs })
            break
          }

          case 'done':
            // SSE done 是权威结束信号，在此做清理
            this._debug(`done (${Date.now() - streamStart}ms) hasContent=${hasContent}`)
            streamDone = true
            this._currentStream = null
            const doneMsgs = [...this.data.messages]
            const doneLast = doneMsgs[doneMsgs.length - 1]
            if (doneLast && doneLast.role === 'agent' && doneLast.isPlaceholder && !hasContent) {
              this._debug('done: 无内容，显示错误')
              doneLast.content = '网络出了点问题，请稍后再试～'
              doneLast.isPlaceholder = false
              doneLast.contentHtml = renderMarkdown(doneLast.content)
            }
            this.setData({ messages: doneMsgs })
            this.fetchTodaySummary()
            break
        }
      },
      () => {
        // onDone (HTTP success) — 不做错误判断，SSE done 消息是权威结束信号
        this._debug(`HTTP success (${Date.now() - streamStart}ms) streamDone=${streamDone} hasContent=${hasContent}`)
        this._currentStream = null
      },
      () => {
        // onError — 网络层错误才显示，主动 abort 不报错
        this._debug(`HTTP error (${Date.now() - streamStart}ms) streamDone=${streamDone} aborting=${this._aborting}`)
        if (!streamDone && !this._aborting) {
          this._currentStream = null
          const errText = '网络出了点问题，请稍后再试～'
          const msgs = [...this.data.messages]
          msgs.push({ role: 'agent', type: 'text', content: errText, contentHtml: renderMarkdown(errText) })
          this.setData({ messages: msgs })
        }
        this._aborting = false
      },
    )
  },

  // 清除上一次流留下的部分 agent 消息（从最后一个 user 消息之后删起）
  _cleanupPartialAgentMsgs() {
    const msgs = this.data.messages
    let cutIdx = msgs.length
    while (cutIdx > 0 && msgs[cutIdx - 1].role === 'agent') {
      cutIdx--
    }
    if (cutIdx < msgs.length) {
      this.setData({ messages: msgs.slice(0, cutIdx) })
    }
  },

  toggleVoiceMode() {
    wx.showToast({ title: '语音功能开发中，敬请期待～', icon: 'none', duration: 2000 })
  },

  // ── 语音模式 tap 切换 ──

  _recorder: null as any,
  _currentStream: null as any,
  _aborting: false,
  _todayCardPushed: false,

  onVoiceTap() {
    wx.showToast({ title: '语音功能开发中，敬请期待～', icon: 'none', duration: 2000 })
  },

  _startRecording() {
    // 缓存 recorder 引用，确保 stop 的是同一个实例
    this._recorder = wx.getRecorderManager()
    const recorder = this._recorder

    this._debug('▶ 开始录音')

    this.setData({ isRecording: true, voiceText: '正在聆听...' })
    wx.vibrateShort({ type: 'medium' })

    recorder.onStart(() => {})

    recorder.onStop((res) => {
      this._recorder = null
      const startTime = Date.now()
      this._debug('■ 录音结束, 上传到ASR...')

      this.setData({ isRecording: false, voiceText: '识别中...' })

      const sys = wx.getSystemInfoSync()
      const baseUrl = sys.platform === 'devtools' ? 'http://localhost:8000' : 'http://192.168.31.52:8000'

      wx.uploadFile({
        url: `${baseUrl}/api/speech-to-text`,
        filePath: res.tempFilePath,
        name: 'audio',
        success: (resp) => {
          const elapsed = Date.now() - startTime
          const data = JSON.parse(resp.data) as { text: string; error?: string }
          if (data.error) {
            this._debug(`✗ ASR失败: ${data.error}`)
            wx.showToast({ title: data.error, icon: 'none' })
          } else if (data.text && data.text.trim()) {
            this._debug(`✓ 识别: "${data.text}" (${elapsed}ms)`)
            this.setData({ voiceText: '', voiceMode: false })
            wx.showToast({ title: `「${data.text}」(${elapsed}ms)`, icon: 'none', duration: 2000 })
            // 自动填入并发送
            this.setData({ inputValue: data.text.trim() })
            this.sendText()
          } else {
            this._debug('✗ ASR返回空')
            wx.showToast({ title: '没听清，请再说一次', icon: 'none' })
          }
        },
        fail: (err) => {
          this._debug(`✗ 上传失败: ${JSON.stringify(err)}`)
          this.setData({ isRecording: false, voiceText: '' })
          wx.showToast({ title: '识别失败，请检查网络', icon: 'none' })
        },
      })
    })

    recorder.onError(() => {
      this._debug('✗ 录音失败')
      this._recorder = null
      this.setData({ isRecording: false, voiceText: '' })
      wx.showToast({ title: '录音失败，请重试', icon: 'none' })
    })

    recorder.start({
      duration: 60000,
      sampleRate: 16000,
      format: 'mp3',
    })

  },

  _stopRecording() {
    if (this._recorder) {
      this._recorder.stop()
    }
  },

  // 确认卡片 — 用户点击确认
  onConfirm(e: any) {
    const idx = e.currentTarget.dataset.index
    const msg = this.data.messages[idx]
    const foodNames = (msg.foods || []).map((f: SSEFood) => f.name).join('、')
    const totalKcal = (msg.totals && msg.totals.kcal) || 0
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
