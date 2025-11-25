const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function sendMessage(sessionId, message) {
  const r = await fetch(`${BASE}/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message })
  })
  return await r.json()
}

export async function getHistory(sessionId) {
  const r = await fetch(`${BASE}/chat/history/${sessionId}`)
  return await r.json()
}

export async function finishDialog(sessionId, title) {
  const r = await fetch(`${BASE}/chat/finish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, title })
  })
  return await r.json()
}

export async function listSessions() {
  const r = await fetch(`${BASE}/sessions`)
  return await r.json()
}

export async function deleteSession(id) {
  const r = await fetch(`${BASE}/sessions/${id}`, { method: 'DELETE' })
  return await r.json()
}

export async function getDocument(id) {
  const r = await fetch(`${BASE}/document/${id}`)
  return await r.json()
}

