import React, { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom'
import ChatWindow from './components/ChatWindow.jsx'
import Home from './pages/Home.jsx'
import Sessions from './pages/Sessions.jsx'
import ChatSession from './pages/ChatSession.jsx'

function Header({ theme, setTheme }) {
  const nav = useNavigate()
  return (
    <div className="header">
      <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
        <div style={{fontWeight:700}}>Forte AI</div>
        <Link className="link" to="/">Главная</Link>
        <Link className="link" to="/sessions">Мои сессии</Link>
      </div>
      <div style={{display:'flex',gap:'8px'}}>
        <button className="btn" onClick={()=>nav('/session/new')}>Создать новую</button>
        <button className="btn secondary" onClick={()=>setTheme(theme==='dark'?'light':'dark')}>{theme==='dark'?'Светлая':'Тёмная'} тема</button>
      </div>
    </div>
  )
}

export default function App() {
  const [theme, setTheme] = useState(localStorage.getItem('theme')||'light')
  useEffect(()=>{ document.documentElement.setAttribute('data-theme', theme); localStorage.setItem('theme', theme) },[theme])
  return (
    <BrowserRouter>
      <Header theme={theme} setTheme={setTheme} />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/sessions" element={<Sessions />} />
        <Route path="/session/new" element={<ChatSession newSession />} />
        <Route path="/session/:id" element={<ChatSession />} />
      </Routes>
    </BrowserRouter>
  )
}

