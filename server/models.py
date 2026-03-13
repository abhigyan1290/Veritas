from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone
from server.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    projects = relationship("Project", back_populates="owner")

class Project(Base):
    """A developer project that consumes Veritas"""
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    created_at = Column(DateTime)
    # The developer's hashed API Key for authentication
    api_key_hash = Column(String, nullable=False, default="")
    user_id = Column(String, ForeignKey("users.id"), nullable=True) # nullable=True for backward compat
    
    owner = relationship("User", back_populates="projects")

class Event(Base):
    """The central unified table for all cost events"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, index=True)
    
    feature = Column(String, index=True)
    model = Column(String, index=True)
    tokens_in = Column(Integer)
    tokens_out = Column(Integer)
    cache_creation_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    latency_ms = Column(Float)
    cost_usd = Column(Float)
    code_version = Column(String, index=True)
    timestamp = Column(String, index=True)
    status = Column(String, default="ok")
    estimated = Column(Boolean, default=False)

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    nps_score = Column(Integer, nullable=False)
    willing_to_pay = Column(String, nullable=False)
    valuable_features = Column(Text, nullable=True)
    feedback_text = Column(Text, nullable=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
