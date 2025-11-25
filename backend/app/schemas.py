from pydantic import BaseModel
from typing import Optional, List

class ChatMessage(BaseModel):
    session_id: Optional[str] = None
    message: str

class ChatReply(BaseModel):
    session_id: str
    reply: str
    finished: bool = False

class FinishRequest(BaseModel):
    session_id: Optional[str] = None
    title: Optional[str] = None

class DocumentResponse(BaseModel):
    session_id: str
    title: str
    content_markdown: str
    confluence_url: Optional[str]

class HistoryItem(BaseModel):
    sender: str
    text: str

class HistoryResponse(BaseModel):
    session_id: str
    items: List[HistoryItem]

class SessionItem(BaseModel):
    id: str
    started_at: str
    finished: bool
    title: Optional[str]

class SessionsResponse(BaseModel):
    items: List[SessionItem]

