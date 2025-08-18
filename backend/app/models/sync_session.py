from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from .database import Base

class SyncSession(Base):
    __tablename__ = "sync_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Sync identification and type
    sync_type = Column(String(50), nullable=False, index=True)  # 'incremental', 'full', 'date_range', 'background'
    sync_source = Column(String(50), nullable=False)  # 'api', 'test', 'background', 'manual'
    
    # Sync parameters
    max_emails = Column(Integer)  # Max emails limit set for this sync
    start_date = Column(String(20))  # For date_range syncs, format: YYYY/MM/DD or YYYY-MM-DD
    end_date = Column(String(20))  # For date_range syncs (optional)
    query_filter = Column(Text)  # Gmail query filter used
    
    # Session status and timing
    status = Column(String(20), nullable=False, default='started', index=True)  # 'started', 'running', 'completed', 'failed', 'cancelled'
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True))
    last_activity_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Progress tracking
    emails_processed = Column(Integer, default=0)  # Total emails processed in this session
    emails_synced = Column(Integer, default=0)  # New emails actually saved to database
    emails_updated = Column(Integer, default=0)  # Existing emails updated
    emails_skipped = Column(Integer, default=0)  # Emails skipped (already exist, no changes)
    batches_processed = Column(Integer, default=0)  # Number of API batches processed
    
    # Performance metrics
    total_api_calls = Column(Integer, default=0)  # Total Gmail API calls made
    avg_batch_time_ms = Column(Integer)  # Average time per batch in milliseconds
    total_duration_seconds = Column(Integer)  # Total sync duration when completed
    
    # Error tracking
    error_count = Column(Integer, default=0)  # Number of errors encountered
    last_error_message = Column(Text)  # Last error message if any
    last_error_at = Column(DateTime(timezone=True))  # When last error occurred
    
    # Additional metadata
    sync_metadata = Column(JSONB)  # Additional flexible data (API response info, etc.)
    notes = Column(Text)  # Human-readable notes about this sync session
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", backref="sync_sessions")
    
    def __repr__(self):
        return f"<SyncSession(id={self.id}, type={self.sync_type}, status={self.status}, emails_synced={self.emails_synced})>"
    
    @property
    def is_active(self) -> bool:
        """Check if this sync session is currently active"""
        return self.status in ['started', 'running']
    
    @property
    def duration_seconds(self) -> int:
        """Get current or final duration of the sync session"""
        if self.completed_at:
            return self.total_duration_seconds or 0
        elif self.started_at:
            from datetime import datetime, timezone
            return int((datetime.now(timezone.utc) - self.started_at).total_seconds())
        return 0
    
    @property
    def emails_per_minute(self) -> float:
        """Calculate emails processed per minute"""
        duration_minutes = self.duration_seconds / 60.0 if self.duration_seconds > 0 else 0
        if duration_minutes > 0 and self.emails_processed > 0:
            return round(self.emails_processed / duration_minutes, 2)
        return 0.0
    
    def mark_completed(self, final_stats: dict = None):
        """Mark sync session as completed and update final stats"""
        from datetime import datetime, timezone
        self.status = 'completed'
        self.completed_at = datetime.now(timezone.utc)
        self.total_duration_seconds = self.duration_seconds
        
        if final_stats:
            for key, value in final_stats.items():
                if hasattr(self, key):
                    setattr(self, key, value)
    
    def mark_failed(self, error_message: str = None):
        """Mark sync session as failed"""
        from datetime import datetime, timezone
        self.status = 'failed'
        self.completed_at = datetime.now(timezone.utc)
        self.total_duration_seconds = self.duration_seconds
        
        if error_message:
            self.last_error_message = error_message
            self.last_error_at = datetime.now(timezone.utc)
            self.error_count += 1
    
    def update_progress(self, **kwargs):
        """Update progress counters"""
        from datetime import datetime, timezone
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        self.last_activity_at = datetime.now(timezone.utc)
        if self.status == 'started':
            self.status = 'running'
