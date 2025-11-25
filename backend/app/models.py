from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import create_engine
from datetime import datetime
from .config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class DialogSession(Base):
    __tablename__ = "dialog_sessions"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    finished = Column(Boolean, default=False)
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    document = relationship("RequirementDocument", uselist=False, back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("dialog_sessions.id"), index=True)
    sender = Column(String)
    text = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    session = relationship("DialogSession", back_populates="messages")

class RequirementDocument(Base):
    __tablename__ = "requirement_documents"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("dialog_sessions.id"), unique=True)
    title = Column(String)
    content_markdown = Column(Text)
    content_html = Column(Text)
    confluence_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    session = relationship("DialogSession", back_populates="document")

def init_db():
    Base.metadata.create_all(bind=engine)

