import React, { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { sendMessage, finishDialog, getHistory, getDocument } from '../api.js'

function ChatBubble({ role, text }){
  return <div className={`bubble ${role==='user'?'user':'bot'}`}>{text}</div>
}

function DocumentPreview({ sessionId, doc, setDoc }){
  const [loading, setLoading] = useState(false)
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
    const pdf = new jsPDF()
    const lines = (doc?.content_markdown||'').split('\n')
    let y = 10
    lines.forEach(line => { pdf.text(line, 10, y); y += 8 })
    pdf.save((doc?.title||'document') + '.pdf')
  }
  return (
    <div className="doc-panel">
      <h3>Итоговый документ</h3>
      {loading && <div className="skeleton"/>}
      <pre style={{whiteSpace:'pre-wrap'}}>{doc?.content_markdown||''}</pre>
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
