// 轻量 markdown → HTML 转换，覆盖 LLM 常用输出格式

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function convertTable(md: string): string {
  // 匹配完整的 markdown 表格（表头行 + 分隔行 + 数据行）
  return md.replace(
    /^\|(.+)\|\n\|(?:[-: ]+\|)+\n((?:\|.+\|\n?)*)/gm,
    (_match: string, headerRow: string, bodyRows: string) => {
      const headers = headerRow.split('|').map((c: string) => c.trim())
      const headerHtml = '<tr>' + headers.map((h: string) => `<th>${h}</th>`).join('') + '</tr>'

      const rows = bodyRows.trim().split('\n')
      const bodyHtml = rows
        .map((row: string) => {
          const cells = row.replace(/^\||\|$/g, '').split('|').map((c: string) => c.trim())
          return '<tr>' + cells.map((c: string) => `<td>${c}</td>`).join('') + '</tr>'
        })
        .join('')

      return `<table><thead>${headerHtml}</thead><tbody>${bodyHtml}</tbody></table>`
    },
  )
}

function convertInline(md: string): string {
  return (
    md
      // bold **text**
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      // italic *text* (single *, not **)
      .replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')
      // inline code `text`
      .replace(/`([^`\n]+?)`/g, '<code>$1</code>')
      // strikethrough ~~text~~
      .replace(/~~(.+?)~~/g, '<del>$1</del>')
  )
}

export function renderMarkdown(text: string): string {
  if (!text) return ''

  let html = escapeHtml(text)

  // 1. 表格（在转义后的文本上匹配 markdown 原样）
  html = convertTable(html)

  // 2. 标题
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')

  // 3. 分割线
  html = html.replace(/^---+$/gm, '<hr>')

  // 4. 无序列表：将连续的 "- item" 行包裹在 <ul> 中
  html = html.replace(/((?:^- .+\n?)+)/gm, (block: string) => {
    const items = block
      .trim()
      .split('\n')
      .map((line: string) => `<li>${line.replace(/^- /, '')}</li>`)
      .join('')
    return `<ul>${items}</ul>`
  })

  // 5. 有序列表：将连续的 "1. item" 行包裹在 <ol> 中
  html = html.replace(/((?:^\d+\. .+\n?)+)/gm, (block: string) => {
    const items = block
      .trim()
      .split('\n')
      .map((line: string) => `<li>${line.replace(/^\d+\. /, '')}</li>`)
      .join('')
    return `<ol>${items}</ol>`
  })

  // 6. 行内格式（加粗、斜体、代码）
  html = convertInline(html)

  // 7. 段落：双换行 → </p><p>，单换行 → <br>
  const paragraphs = html.split('\n\n')
  html = paragraphs
    .map((p: string) => {
      const trimmed = p.trim()
      if (!trimmed) return ''
      // 已经是块级元素（表格、列表、标题、分割线）就不包 <p>
      if (/^<(table|ul|ol|h[1-6]|hr)/.test(trimmed)) return trimmed
      return `<p>${trimmed.replace(/\n/g, '<br>')}</p>`
    })
    .join('')

  return html
}
