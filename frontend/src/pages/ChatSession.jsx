import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { sendMessage, finishDialog, getHistory, getDocument } from '../api.js'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import mermaid from 'mermaid'

function ChatBubble({ role, text }){
  const looksLikeMermaid = /\b(graph|flowchart)\s+[A-Za-z]+/.test(text) || text.includes('subgraph') || text.includes('-->')
  const content = useMemo(()=>{
    let m = text || ''
    if (looksLikeMermaid && !/```\s*mermaid/.test(m)){
      const pattern = /(graph\s+[A-Za-z]+[\s\S]*?)(?=\n\n|$)|((flowchart)\s+[A-Za-z]+[\s\S]*?)(?=\n\n|$)/ig
      m = m.replace(pattern, (full)=>{
        let src = full.replace(/\r/g,'')
        src = src.replace(/^\s*graph\s+/i, 'flowchart ')
        if (!src.includes('\n')){
          src = src.split(';').map(s=>s.trim()).filter(Boolean).join('\n')
        }
        src = src.replace(/^(flowchart\s+[A-Za-z]+)\s+/i, '$1\n')
        src = src.replace(/\bsubgraph\s+([^\n;]+)/gi, (m,g)=>`subgraph ${g}\n`)
        src = src.replace(/\s+end\s*/gi, '\nend\n')
        return '```mermaid\n' + src.trim() + '\n```'
      })
    }
    return m
  }, [text])
  return (
    <div className={`bubble ${role==='user'?'user':'bot'}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p({children}){
            const raw = Array.isArray(children) ? children.map(c => typeof c === 'string' ? c : (c?.props?.children ?? '')).join('') : String(children ?? '')
            const txt = raw.trim()
            const mer = /\b(graph|flowchart)\s+\w+/.test(txt) || txt.includes('subgraph') || txt.includes('-->')
            if (mer){
              const m = txt.match(/(graph\s+[A-Za-z]+[\s\S]*)|(flowchart\s+[A-Za-z]+[\s\S]*)/i)
              return <MermaidBlock code={(m ? m[0] : txt)} />
            }
            return <p>{children}</p>
          },
          li({children}){
            const raw = Array.isArray(children) ? children.map(c => typeof c === 'string' ? c : (c?.props?.children ?? '')).join('') : String(children ?? '')
            const txt = raw.trim()
            const mer = /\b(graph|flowchart)\s+\w+/.test(txt) || txt.includes('subgraph') || txt.includes('-->')
            if (mer){
              const m = txt.match(/(graph\s+[A-Za-z]+[\s\S]*)|(flowchart\s+[A-Za-z]+[\s\S]*)/i)
              return <MermaidBlock code={(m ? m[0] : txt)} />
            }
            return <li>{children}</li>
          },
          pre({children}){
            const child = Array.isArray(children) ? children[0] : children
            const className = child?.props?.className || ''
            const raw = child?.props?.children
            const codeText = Array.isArray(raw) ? raw.join('') : String(raw ?? '')
            const match = /language-(\w+)/.exec(className)
            const mer = /\b(graph|flowchart)\s+\w+/.test(codeText) || codeText.includes('subgraph') || codeText.includes('-->')
            if ((match && match[1] === 'mermaid') || mer){
              return <MermaidBlock code={codeText} />
            }
            return <pre>{children}</pre>
          },
          code({inline, className, children}){
            const txt = Array.isArray(children) ? children.join('') : String(children)
            const clean = txt.replace(/\n$/, '')
            const match = /language-(\w+)/.exec(className || '')
            if (!inline && match && match[1] === 'mermaid'){
              return <MermaidBlock code={clean} />
            }
            return <pre><code className={className}>{children}</code></pre>
          }
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

function MermaidBlock({ code }){
  const ref = useRef(null)
  useEffect(()=>{
    let cancelled = false
    const render = async ()=>{
      try {
        let src = (code || '').replace(/\r/g,'')
        const idxStart = src.search(/\b(graph|flowchart)\s+[A-Za-z]+/i)
        if (idxStart > -1) src = src.slice(idxStart)
        src = src.replace(/[“”«»]/g, '"').replace(/[–—]/g, '-')
        const hasSubgraphs = (src.match(/\bsubgraph\b/gi)||[]).length >= 2
        src = src.replace(/^\s*graph\s+([A-Za-z]+)/i, (_,dir)=>`flowchart ${hasSubgraphs ? 'LR' : dir}`)
        src = src.replace(/^\s*flowchart\s+TD/i, 'flowchart LR')
        src = src.replace(/^(flowchart\s+[A-Za-z]+)\s+/i, '$1\n')
        if (!src.includes('\n') && src.includes(';')) {
          src = src.split(';').map(s => s.trim()).filter(Boolean).join('\n')
        }
        src = src.replace(/\bsubgraph\s+([^\n;]+)/gi, (m,g)=>`subgraph ${g}\n`)
        src = src.replace(/\bend\b/g, '\nend\n')
        const map = {"А":"A","В":"B","С":"C","Е":"E","Н":"H","К":"K","М":"M","Т":"T","О":"O","Р":"P","Х":"X","У":"Y","а":"a","в":"b","с":"c","е":"e","н":"h","к":"k","м":"m","т":"t","о":"o","р":"p","х":"x","у":"y"}
        const fixId = (id)=>{
          let out = id.replace(/[А-Яа-я]/g, ch => map[ch] || ch)
          if (/^[0-9]/.test(out)) out = 'n' + out
          return out
        }
        const quoteLabel = (label)=>{
          const t = String(label || '').trim()
          if (!t) return '""'
          if (/^['"]/u.test(t) && /['"]$/u.test(t)) return t
          const esc = t.replace(/\\/g, '\\\\').replace(/\"/g, '\\\"').replace(/"/g, '\\"')
          return `"${esc}"`
        }
        src = src.split('\n').map(line => {
          let l = line
          l = l.replace(/^\s*([^\s\[\(\{]+)\s*(\[|\(|\{)/, (m,id,br)=> fixId(id)+br)
          l = l.replace(/(^|\s)([^\s\-]+)\s*--.*?-->\s*([^\s\-\[\(\{]+)/, (m,prefix,left,right)=> `${prefix}${fixId(left)} -- --> ${fixId(right)}`)
          l = l.replace(/(^|\s)([^\s\[\(\{]+)\s*\[([^\]]+)\]/g, (m,pre,id,label)=> `${pre}${fixId(id)}[${quoteLabel(label)}]`)
          l = l.replace(/(^|\s)([^\s\[\(\{]+)\s*\(([^\)]+)\)/g, (m,pre,id,label)=> `${pre}${fixId(id)}(${quoteLabel(label)})`)
          l = l.replace(/(^|\s)([^\s\[\(\{]+)\s*\{([^\}]+)\}/g, (m,pre,id,label)=> `${pre}${fixId(id)}{${quoteLabel(label)}}`)
          l = l.replace(/^\s*\/\//, '%%')
          return l
        }).join('\n')
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          theme: 'default',
          flowchart: { htmlLabels: true, nodeSpacing: 60, rankSpacing: 80, curve: 'linear', useMaxWidth: true, padding: 24, diagramPadding: 16 }
        })
        await mermaid.parse(src)
        const id = 'mmd-' + Math.random().toString(36).slice(2)
        const { svg } = await mermaid.render(id, src)
        if (!cancelled && ref.current){
          ref.current.innerHTML = svg
          const el = ref.current.querySelector('svg')
          if (el){
            el.style.maxWidth = '100%'; el.style.height = 'auto'; el.setAttribute('preserveAspectRatio','xMidYMid meet')
            const vb = (el.getAttribute('viewBox')||'').split(' ').map(Number)
            if (vb.length===4){ const w = vb[2], h = vb[3]; if (w > h*1.6) {
              const srcTB = src.replace(/flowchart\s+LR/i, 'flowchart TB').replace(/flowchart\s+TD/i, 'flowchart TB')
              const { svg: svg2 } = await mermaid.render('mmd-' + Math.random().toString(36).slice(2), srcTB)
              ref.current.innerHTML = svg2
            } }
          }
        }
      } catch(e) {
        if (ref.current){ ref.current.textContent = code }
      }
    }
    render()
    return ()=>{ cancelled = true }
  }, [code])
  return <div ref={ref} className="mermaid-chart" />
}

function DocumentPreview({ sessionId, doc, setDoc }){
  const [loading, setLoading] = useState(false)
  const docRef = useRef(null)
  const renderMd = useMemo(()=>{
    let m = doc?.content_markdown || ''
    if (m && !/```\s*mermaid/.test(m)){
      const pattern = /(graph\s+[A-Za-z]+[\s\S]*?)(?=\n\n|$)|((flowchart)\s+[A-Za-z]+[\s\S]*?)(?=\n\n|$)/ig
      m = m.replace(pattern, (full)=>{
        let src = full.replace(/\r/g,'')
        src = src.replace(/^\s*graph\s+/i, 'flowchart ')
        if (!src.includes('\n')){
          src = src.split(';').map(s=>s.trim()).filter(Boolean).join('\n')
        }
        src = src.replace(/\bsubgraph\s+([^\n;]+)/gi, (m,g)=>`subgraph ${g}\n`)
        src = src.replace(/\s+end\s*/gi, '\nend\n')
        return '```mermaid\n' + src.trim() + '\n```'
      })
    }
    return m
  }, [doc])
  useEffect(()=>{
    const load = async ()=>{
      if (!sessionId) return
      const d = await getDocument(sessionId)
      setDoc(d)
    }
    load()
  },[sessionId])
  const onExport = async ()=>{
    if (!sessionId) return
    setLoading(true)
    const d = await finishDialog(sessionId)
    setDoc(d)
    setLoading(false)
  }
  const onPdf = async ()=>{
    const { jsPDF } = await import('jspdf')
    const html2canvas = (await import('html2canvas')).default
    const element = document.getElementById('doc-markdown')
    if (!element) return
    const canvas = await html2canvas(element, { scale: 2, useCORS: true })
    const pdf = new jsPDF('p','pt','a4')
    const margin = 20
    const pageWidth = pdf.internal.pageSize.getWidth() - margin*2
    const pageHeight = pdf.internal.pageSize.getHeight() - margin*2
    const imgWidth = pageWidth
    const ratio = canvas.width / imgWidth
    const pageHeightPx = pageHeight * ratio
    let pageY = 0
    while (pageY < canvas.height) {
      const pageCanvas = document.createElement('canvas')
      pageCanvas.width = canvas.width
      pageCanvas.height = Math.min(pageHeightPx, canvas.height - pageY)
      const ctx = pageCanvas.getContext('2d')
      ctx.drawImage(canvas, 0, pageY, pageCanvas.width, pageCanvas.height, 0, 0, pageCanvas.width, pageCanvas.height)
      const data = pageCanvas.toDataURL('image/png')
      const imgHeight = (pageCanvas.height / canvas.width) * imgWidth
      pdf.addImage(data, 'PNG', margin, margin, imgWidth, imgHeight, undefined, 'FAST')
      pageY += pageHeightPx
      if (pageY < canvas.height) pdf.addPage()
    }
    pdf.save((doc?.title||'document') + '.pdf')
  }
  return (
    <div className="doc-panel">
      <h3>Итоговый документ</h3>
      {loading && <div className="skeleton"/>}
      <div id="doc-markdown" ref={docRef} className="markdown-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            p({children}){
              const raw = Array.isArray(children) ? children.map(c => typeof c === 'string' ? c : (c?.props?.children ?? '')).join('') : String(children ?? '')
              const text = raw.trim()
              const looksLikeMermaid = /\b(graph|flowchart)\s+\w+/.test(text) || text.includes('subgraph') || text.includes('-->')
              if (looksLikeMermaid){
                const m = text.match(/(graph\s+[A-Za-z]+[\s\S]*)|(flowchart\s+[A-Za-z]+[\s\S]*)/i)
                return <MermaidBlock code={(m ? m[0] : text)} />
              }
              return <p>{children}</p>
            },
            li({children}){
              const raw = Array.isArray(children) ? children.map(c => typeof c === 'string' ? c : (c?.props?.children ?? '')).join('') : String(children ?? '')
              const text = raw.trim()
              const looksLikeMermaid = /\b(graph|flowchart)\s+\w+/.test(text) || text.includes('subgraph') || text.includes('-->')
              if (looksLikeMermaid){
                const m = text.match(/(graph\s+[A-Za-z]+[\s\S]*)|(flowchart\s+[A-Za-z]+[\s\S]*)/i)
                return <MermaidBlock code={(m ? m[0] : text)} />
              }
              return <li>{children}</li>
            },
            pre({children}){
              const child = Array.isArray(children) ? children[0] : children
              const className = child?.props?.className || ''
              const raw = child?.props?.children
              const codeText = Array.isArray(raw) ? raw.join('') : String(raw ?? '')
              const match = /language-(\w+)/.exec(className)
              const looksLikeMermaid = /\b(graph|flowchart)\s+\w+/.test(codeText) || codeText.includes('subgraph') || codeText.includes('-->')
              if ((match && match[1] === 'mermaid') || looksLikeMermaid){
                return <MermaidBlock code={codeText} />
              }
              return <pre>{children}</pre>
            },
            code({inline, className, children, ...props}){
              const txt = Array.isArray(children) ? children.join('') : String(children)
              const clean = txt.replace(/\n$/, '')
              const match = /language-(\w+)/.exec(className || '')
              if (!inline && match && match[1] === 'mermaid'){
                return <MermaidBlock code={clean} />
              }
              return <pre><code className={className}>{children}</code></pre>
            }
          }}
        >
          {renderMd}
        </ReactMarkdown>
      </div>
      <div style={{display:'flex',gap:8}}>
        <button className="btn" onClick={onExport}>Экспорт в Confluence</button>
        <button className="btn secondary" onClick={onPdf}>Скачать PDF</button>
      </div>
      {doc?.confluence_url && (
        <div style={{marginTop:8}}>
          <a className="link" href={doc.confluence_url} target="_blank" rel="noreferrer">Открыть в Confluence</a>
        </div>
      )}
    </div>
  )
}

export default function ChatSession({ newSession }){
  const params = useParams()
  const navigate = useNavigate()
  const [sessionId, setSessionId] = useState(newSession?null:(params.id||null))
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [hint, setHint] = useState('')
  const [doc, setDoc] = useState(null)
  const [toast, setToast] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const listRef = useRef()

  useEffect(()=>{
    let t = setTimeout(()=>{
      setHint('Можете описать цель проекта в 1–2 предложениях?')
    }, 5000)
    return ()=> clearTimeout(t)
  },[messages.length])

  useEffect(()=>{ if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight },[messages])
  useEffect(()=>{
    const load = async ()=>{
      if (!sessionId) return
      const h = await getHistory(sessionId)
      setMessages(h.items.map(i => ({ role: i.sender==='user'?'user':'bot', text: i.text })))
    }
    load()
  },[sessionId])

  const onSend = async ()=>{
    if (!input.trim()) return
    setLoading(true)
    const resp = await sendMessage(sessionId, input)
    setSessionId(resp.session_id)
    setMessages(m => [...m, { role: 'user', text: input }, { role: 'bot', text: resp.reply }])
    setInput('')
    setHint('')
    if (newSession && !params.id) navigate(`/session/${resp.session_id}`)
    setLoading(false)
  }

  return (
    <div className="chat-wrap">
      <div className="sidebar">
        <div style={{marginBottom:8,fontWeight:600}}>Навигация</div>
        <button className="btn" onClick={()=>navigate('/sessions')}>Мои сессии</button>
        <button className="btn secondary" style={{marginTop:8}} onClick={()=>navigate('/session/new')}>Новая сессия</button>
      </div>
      <div className="chat">
        <div ref={listRef} className="chat-list">
          {messages.map((m, idx) => (
            <div key={idx} style={{display:'flex',justifyContent:m.role==='user'?'flex-end':'flex-start',margin:'6px 0'}}>
              <ChatBubble role={m.role} text={m.text} />
            </div>
          ))}
          {loading && <div className="typing"><span className="dot"></span><span className="dot"></span><span className="dot"></span></div>}
          {!loading && !messages.length && hint && <div className="toast">{hint}</div>}
        </div>
        <div className="chat-input">
          <input value={input} onChange={e=>setInput(e.target.value)} placeholder="Введите сообщение" style={{flex:1,padding:'10px'}} />
          <button className="btn" onClick={onSend} disabled={loading}>Отправить</button>
        </div>
      </div>
      <DocumentPreview sessionId={sessionId} doc={doc} setDoc={(d)=>{ setDoc(d); setToast(d?.confluence_url ? 'Опубликовано в Confluence' : 'Документ сформирован'); setTimeout(()=>setToast(''),2500) }} />
      {sessionId && (
        <button className="fab" onClick={()=>setConfirmOpen(true)}>Завершить и сгенерировать</button>
      )}
      {toast && <div className="toast">{toast}</div>}
      {confirmOpen && (
        <div className="modal-overlay">
          <div className="modal">
            <div style={{fontWeight:600, marginBottom:8}}>Подтвердить генерацию документа</div>
            <div style={{display:'flex',gap:8}}>
              <button className="btn" onClick={async()=>{ setConfirmOpen(false); const d = await finishDialog(sessionId); setDoc(d); setToast(d?.confluence_url ? 'Опубликовано в Confluence' : 'Документ сформирован'); setTimeout(()=>setToast(''),2500) }}>Сгенерировать</button>
              <button className="btn secondary" onClick={()=>setConfirmOpen(false)}>Отмена</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
