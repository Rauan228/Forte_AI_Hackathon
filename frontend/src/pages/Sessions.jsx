import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listSessions, deleteSession } from '../api.js'

export default function Sessions(){
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const load = async ()=>{
    setLoading(true)
    const r = await listSessions()
    setItems(r.items||[])
    setLoading(false)
  }
  useEffect(()=>{ load() },[])
  const onDelete = async (id)=>{ await deleteSession(id); load() }
  return (
    <div className="container">
      <h2 style={{margin:'12px 0'}}>Мои сессии</h2>
      {loading && <div className="skeleton"/>}
      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12}}>
        {items.map(it => (
          <div key={it.id} className="card" style={{animation:'slideUp .25s ease both'}}>
            <div style={{fontWeight:600}}>{it.title||'Без названия'}</div>
            <div style={{fontSize:12,opacity:.8}}>{new Date(it.started_at).toLocaleString()}</div>
            <div style={{marginTop:8}}>
              <Link className="btn" to={`/session/${it.id}`}>Открыть</Link>
              <button className="btn secondary" style={{marginLeft:8}} onClick={()=>onDelete(it.id)}>Удалить</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
