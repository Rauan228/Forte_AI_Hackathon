import uuid
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from markdown2 import Markdown
from .models import SessionLocal, init_db, DialogSession, Message, RequirementDocument
from .schemas import ChatMessage, ChatReply, FinishRequest, DocumentResponse, HistoryResponse, HistoryItem
from .schemas import SessionsResponse, SessionItem
from .ai.model import AIModel
from .ai.session_logic import SessionContextStore, plan_next_question, extract_slots_from_history
from .ai.generators import generate_brd_markdown
from .config import FRONTEND_ORIGIN
from .integrations.confluence import publish_to_confluence, publish_to_confluence_with_diagram

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
md = Markdown(extras=["tables", "fenced-code-blocks"])

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat/message", response_model=ChatReply)
def chat_message(payload: ChatMessage, db: Session = Depends(get_db)):
    """
    Обычный чат с бизнес-аналитиком.
    НЕ публикует в Confluence - только общение и сбор данных.
    Публикация происходит через /chat/finish.
    """
    session_id = payload.session_id or str(uuid.uuid4())
    session = db.get(DialogSession, session_id)
    if not session:
        session = DialogSession(id=session_id)
        db.add(session)
        db.commit()
    
    # Сохраняем сообщение пользователя
    db.add(Message(session_id=session_id, sender="user", text=payload.message))
    
    # Получаем историю и контекст
    history = [(m.sender, m.text) for m in db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp.asc()).all()]
    store = SessionContextStore(db)
    ctx = store.get(session_id)
    
    # Получаем ответ от AI и извлекаем слоты
    reply_text, delta, ready = ai.reply_and_slots(history, payload.message, ctx.slots)
    
    # Если AI не извлёк слоты, пробуем локально
    if not isinstance(delta, dict) or len(delta.keys()) == 0:
        try:
            delta = ai._local_extract_slots(payload.message)
        except Exception:
            delta = {}
    
    # Обновляем контекст
    ctx.update(delta)
    extra = extract_slots_from_history(history)
    if extra:
        ctx.update(extra)
    store.save(session_id, ctx)
    
    # Если нет ответа, генерируем следующий вопрос
    if not reply_text:
        reply_text = plan_next_question(ctx)

    # Сохраняем ответ ассистента
    db.add(Message(session_id=session_id, sender="assistant", text=reply_text))
    db.commit()
    
    # Возвращаем ответ (finished всегда False в обычном чате)
    return {"session_id": session_id, "reply": reply_text, "finished": False}

@app.get("/chat/history/{session_id}", response_model=HistoryResponse)
def get_history(session_id: str, db: Session = Depends(get_db)):
    items = [HistoryItem(sender=m.sender, text=m.text) for m in db.query(Message).filter(Message.session_id == session_id).order_by(Message.timestamp.asc()).all()]
    return {"session_id": session_id, "items": items}

@app.post("/chat/finish", response_model=DocumentResponse)
def chat_finish(payload: FinishRequest, db: Session = Depends(get_db)):
    from .integrations.confluence import generate_diagram_image_with_gemini
    
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
    store = SessionContextStore(db)
    ctx = store.get(sid)
    slots = ctx.slots
    
    # Generate document content
    content_md = ai.generate_document_from_slots(slots, title)
    if not content_md:
        content_md = generate_brd_markdown(ctx, title)
    try:
        content_html = md.convert(content_md)
    except Exception:
        content_html = md.convert(str(content_md or ""))
    
    # Generate diagram description from slots
    diagram_description = _build_diagram_description(slots)
    diagram_image = None
    if diagram_description:
        diagram_image = generate_diagram_image_with_gemini(diagram_description)
    
    # Publish to Confluence with diagram
    try:
        url = publish_to_confluence_with_diagram(title, content_html, diagram_image)
    except Exception:
        url = None

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


def _build_diagram_description(slots: dict) -> str:
    """Build description for diagram generation from slots."""
    parts = []
    
    if slots.get("title"):
        parts.append(f"Проект: {slots['title']}")
    if slots.get("goal"):
        parts.append(f"Цель: {slots['goal']}")
    if slots.get("description"):
        parts.append(f"Описание: {slots['description']}")
    
    # Add business requirements
    br = slots.get("business_requirements", [])
    if br:
        parts.append(f"Бизнес-требования: {', '.join(br[:3])}")
    
    # Add functional requirements
    fr = slots.get("functional_requirements", [])
    if fr:
        parts.append(f"Функциональные требования: {', '.join(fr[:3])}")
    
    # Add use cases flow
    use_cases = slots.get("use_cases", [])
    if use_cases:
        for uc in use_cases[:2]:
            if isinstance(uc, dict):
                name = uc.get("name", "")
                main_flow = uc.get("main_flow", [])
                if name and main_flow:
                    parts.append(f"Use Case '{name}': {' -> '.join(main_flow[:5])}")
    
    # Add KPIs
    kpis = slots.get("kpi", [])
    if kpis:
        parts.append(f"KPI: {', '.join(kpis[:3])}")
    
    return "\n".join(parts)

@app.get("/context/{session_id}")
def get_context(session_id: str, db: Session = Depends(get_db)):
    store = SessionContextStore(db)
    ctx = store.get(session_id)
    return {"session_id": session_id, "slots": ctx.slots}

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
    return {
        "session_id": session_id,
        "title": doc.title or "Бизнес-требования",
        "content_markdown": doc.content_markdown or "",
        "confluence_url": doc.confluence_url,
    }

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    s = db.get(DialogSession, session_id)
    if s:
        db.delete(s)
        db.commit()
    return {"deleted": True}


@app.post("/diagram/generate")
def generate_diagram(payload: dict, db: Session = Depends(get_db)):
    """Generate a process diagram image using Gemini API."""
    session_id = payload.get("session_id")
    if not session_id:
        return {"error": "session_id required", "image_base64": None}
    
    store = SessionContextStore(db)
    ctx = store.get(session_id)
    
    # Build description for diagram from slots
    slots = ctx.slots
    description_parts = []
    
    if slots.get("title"):
        description_parts.append(f"Проект: {slots['title']}")
    if slots.get("goal"):
        description_parts.append(f"Цель: {slots['goal']}")
    if slots.get("description"):
        description_parts.append(f"Описание: {slots['description']}")
    
    # Add use cases flow
    use_cases = slots.get("use_cases", [])
    if use_cases:
        for uc in use_cases:
            if isinstance(uc, dict):
                name = uc.get("name", "")
                main_flow = uc.get("main_flow", [])
                if name and main_flow:
                    description_parts.append(f"Use Case '{name}': {' -> '.join(main_flow[:5])}")
    
    # Add KPIs if available
    kpis = slots.get("kpi", [])
    if kpis:
        description_parts.append(f"KPI: {', '.join(kpis[:3])}")
    
    if not description_parts:
        return {"error": "No data to generate diagram", "image_base64": None}
    
    description = "\n".join(description_parts)
    
    # Generate diagram using Gemini
    from .integrations.confluence import generate_diagram_image_with_gemini
    import base64
    
    image_bytes = generate_diagram_image_with_gemini(description)
    
    if image_bytes:
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return {"image_base64": image_base64, "error": None}
    
    return {"error": "Failed to generate diagram", "image_base64": None}

