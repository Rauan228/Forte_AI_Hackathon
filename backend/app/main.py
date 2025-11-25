import uuid
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from markdown2 import Markdown
from .models import SessionLocal, init_db, DialogSession, Message, RequirementDocument
from .schemas import ChatMessage, ChatReply, FinishRequest, DocumentResponse, HistoryResponse, HistoryItem
from .schemas import SessionsResponse, SessionItem
from .ai.model import AIModel
from .config import FRONTEND_ORIGIN
from .integrations.confluence import publish_to_confluence

init_db()
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

ai = AIModel()
md = Markdown()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat/message", response_model=ChatReply)
def chat_message(payload: ChatMessage, db: Session = Depends(get_db)):
    session_id = payload.session_id or str(uuid.uuid4())
    session = db.get(DialogSession, session_id)
    if not session:
        session = DialogSession(id=session_id)
        db.add(session)
        db.commit()
    db.add(Message(session_id=session_id, sender="user", text=payload.message))
    history = [(m.sender, m.text) for m in db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp.asc()).all()]
    reply = ai.reply(history, payload.message)
    db.add(Message(session_id=session_id, sender="assistant", text=reply))
    db.commit()
    return {"session_id": session_id, "reply": reply, "finished": False}

@app.get("/chat/history/{session_id}", response_model=HistoryResponse)
def get_history(session_id: str, db: Session = Depends(get_db)):
    items = [HistoryItem(sender=m.sender, text=m.text) for m in db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp.asc()).all()]
    return {"session_id": session_id, "items": items}

@app.post("/chat/finish", response_model=DocumentResponse)
def chat_finish(payload: FinishRequest, db: Session = Depends(get_db)):
    sid = payload.session_id
    if not sid:
        last = db.query(DialogSession).order_by(DialogSession.started_at.desc()).first()
        sid = last.id if last else str(uuid.uuid4())
    session = db.get(DialogSession, sid)
    if not session:
        session = DialogSession(id=sid)
        db.add(session)
        db.commit()
    history = [(m.sender, m.text) for m in db.query(Message).filter(Message.session_id == sid).order_by(Message.timestamp.asc()).all()]
    title = payload.title or "Бизнес-требования"
    content_md = ai.generate_document(history, title)
    content_html = md.convert(content_md)
    url = publish_to_confluence(title, content_html)
    doc = db.query(RequirementDocument).filter(RequirementDocument.session_id == sid).one_or_none()
    if not doc:
        doc = RequirementDocument(session_id=sid)
        db.add(doc)
    doc.title = title
    doc.content_markdown = content_md
    doc.content_html = content_html
    doc.confluence_url = url
    session.finished = True
    db.commit()
    return {"session_id": sid, "title": title, "content_markdown": content_md, "confluence_url": url}

@app.get("/sessions", response_model=SessionsResponse)
def list_sessions(db: Session = Depends(get_db)):
    sessions = db.query(DialogSession).order_by(DialogSession.started_at.desc()).all()
    items = []
    for s in sessions:
        doc = db.query(RequirementDocument).filter(RequirementDocument.session_id == s.id).one_or_none()
        items.append(SessionItem(id=s.id, started_at=s.started_at.isoformat(), finished=s.finished, title=(doc.title if doc else None)))
    return {"items": items}

@app.get("/document/{session_id}", response_model=DocumentResponse)
def get_document(session_id: str, db: Session = Depends(get_db)):
    doc = db.query(RequirementDocument).filter(RequirementDocument.session_id == session_id).one_or_none()
    if not doc:
        return {"session_id": session_id, "title": "Бизнес-требования", "content_markdown": "", "confluence_url": None}
    return {"session_id": session_id, "title": doc.title or "Бизнес-требования", "content_markdown": doc.content_markdown or "", "confluence_url": doc.confluence_url}

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    s = db.get(DialogSession, session_id)
    if s:
        db.delete(s)
        db.commit()
    return {"deleted": True}

