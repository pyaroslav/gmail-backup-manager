from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255))
    
    # Gmail API credentials
    gmail_access_token = Column(Text)
    gmail_refresh_token = Column(Text)
    gmail_token_expiry = Column(DateTime(timezone=True))
    
    # Settings
    sync_enabled = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"
class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    session_token = Column(String(255), unique=True, index=True, nullable=False)
    
    # Session metadata
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id})>"
