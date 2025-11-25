import React from 'react'
import { Link } from 'react-router-dom'

export default function Home(){
  return (
    <div className="container">
      <div className="hero">
        <div>
          <h1 style={{fontSize:24,margin:'0 0 8px'}}>Умный помощник бизнес-аналитика</h1>
          <p>Ведите диалог, получите готовый документ, экспортируйте в Confluence.</p>
          <Link to="/session/new" className="btn" style={{display:'inline-block',marginTop:12}}>Начать сессию</Link>
        </div>
        <div className="card">
          <div style={{width:340,height:200}} className="skeleton" />
        </div>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:16}}>
        <div className="card" style={{animation:'slideUp .25s ease both'}}> <b>1. Ведите диалог</b><p>ИИ-ассистент задаёт вопросы и уточняет детали.</p></div>
        <div className="card" style={{animation:'slideUp .25s ease .05s both'}}> <b>2. Получите документ</b><p>Автоматический BRD с Use Case и User Stories.</p></div>
        <div className="card" style={{animation:'slideUp .25s ease .1s both'}}> <b>3. Экспорт в Confluence</b><p>Одним кликом публикуйте страницу.</p></div>
      </div>
      <footer style={{marginTop:24,display:'flex',gap:12}}>
        <a className="link" href="https://github.com/" target="_blank" rel="noreferrer">GitHub</a>
        <a className="link" href="https://t.me/" target="_blank" rel="noreferrer">Telegram</a>
      </footer>
    </div>
  )
}
