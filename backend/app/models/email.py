from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, BYTEA
from .database import Base
import json

class Email(Base):
    __tablename__ = "emails"
    
    id = Column(Integer, primary_key=True, index=True)
    gmail_id = Column(String(255), unique=True, index=True, nullable=False)
    thread_id = Column(String(255), index=True)
    
    # Email metadata
    subject = Column(String(1000))
    sender = Column(String(500), index=True)
    recipients = Column(JSONB)  # Use JSONB for better performance in PostgreSQL
    cc = Column(JSONB)  # List of CC emails
    bcc = Column(JSONB)  # List of BCC emails
    
    # Content
    body_plain = Column(Text)
    body_html = Column(Text)
    
    # Timestamps
    date_received = Column(DateTime(timezone=True), default=func.now(), index=True)
    date_sent = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Flags
    is_read = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)
    is_important = Column(Boolean, default=False)
    is_spam = Column(Boolean, default=False)
    is_trash = Column(Boolean, default=False)
    
    # Labels
    labels = Column(JSONB)  # List of Gmail labels - use JSONB for better performance
    
    # AI analysis results
    sentiment_score = Column(Integer)  # -1 to 1
    category = Column(String(100))  # work, personal, spam, etc.
    priority_score = Column(Integer)  # 1-10
    summary = Column(Text)
    
    # Relationships
    attachments = relationship("EmailAttachment", back_populates="email", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Email(id={self.id}, subject='{self.subject}', sender='{self.sender}')>"

class EmailAttachment(Base):
    __tablename__ = "email_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    
    # Attachment metadata
    filename = Column(String(500))
    content_type = Column(String(200))
    size = Column(Integer)  # Size in bytes
    content_id = Column(String(255))  # For inline attachments
    
    # Storage - Store as BLOB in database for better performance
    file_data = Column(BYTEA)  # PostgreSQL BLOB field for file content
    file_path = Column(String(1000))  # Keep for backward compatibility
    is_inline = Column(Boolean, default=False)
    
    # Additional metadata for better search
    checksum = Column(String(64))  # SHA256 hash for deduplication
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    email = relationship("Email", back_populates="attachments")
    
    def __repr__(self):
        return f"<EmailAttachment(id={self.id}, filename='{self.filename}')>"

class EmailLabel(Base):
    __tablename__ = "email_labels"
    
    id = Column(Integer, primary_key=True, index=True)
    gmail_label_id = Column(String(255), unique=True, index=True)
    name = Column(String(200), index=True)
    label_type = Column(String(50))  # system, user, etc.
    color = Column(JSONB)  # Label color information - use JSONB
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<EmailLabel(id={self.id}, name='{self.name}')>"

# Create indexes for better search performance
Index('idx_emails_sender_date', Email.sender, Email.date_received)
Index('idx_emails_subject', Email.subject)
Index('idx_emails_labels', Email.labels, postgresql_using='gin')  # GIN index for JSONB
Index('idx_emails_category', Email.category)
Index('idx_emails_sentiment', Email.sentiment_score)
Index('idx_emails_gmail_id', Email.gmail_id)
Index('idx_emails_thread_id', Email.thread_id)
Index('idx_emails_date_received', Email.date_received)

# Additional indexes for attachments
Index('idx_attachments_email_id', EmailAttachment.email_id)
Index('idx_attachments_filename', EmailAttachment.filename)
Index('idx_attachments_content_type', EmailAttachment.content_type)
Index('idx_attachments_checksum', EmailAttachment.checksum)
