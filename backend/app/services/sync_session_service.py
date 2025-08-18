"""
Sync Session Service for tracking and managing sync sessions
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models.database import SessionLocal
from ..models.sync_session import SyncSession
from ..models.user import User

logger = logging.getLogger(__name__)

class SyncSessionService:
    """Service for managing sync sessions and tracking sync progress"""
    
    @staticmethod
    def create_sync_session(
        user: User,
        sync_type: str,
        sync_source: str = 'api',
        max_emails: int = None,
        start_date: str = None,
        end_date: str = None,
        query_filter: str = None,
        metadata: Dict[str, Any] = None,
        notes: str = None,
        db: Session = None
    ) -> SyncSession:
        """
        Create a new sync session record
        
        Args:
            user: User performing the sync
            sync_type: Type of sync ('incremental', 'full', 'date_range', 'background')
            sync_source: Source of sync ('api', 'test', 'background', 'manual')
            max_emails: Maximum emails to sync (optional)
            start_date: Start date for date_range syncs
            end_date: End date for date_range syncs
            query_filter: Gmail query filter used
            metadata: Additional metadata
            notes: Human-readable notes
            db: Database session (optional, will create new if not provided)
        
        Returns:
            Created SyncSession instance
        """
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            sync_session = SyncSession(
                user_id=user.id,
                sync_type=sync_type,
                sync_source=sync_source,
                max_emails=max_emails,
                start_date=start_date,
                end_date=end_date,
                query_filter=query_filter,
                sync_metadata=metadata or {},
                notes=notes,
                status='started'
            )
            
            db.add(sync_session)
            db.commit()
            db.refresh(sync_session)
            
            logger.info(f"Created sync session {sync_session.id}: {sync_type} sync for user {user.id}")
            return sync_session
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create sync session: {e}")
            raise
        finally:
            if should_close_db:
                db.close()
    
    @staticmethod
    def get_active_sync_session(user: User, db: Session = None) -> Optional[SyncSession]:
        """
        Get the currently active sync session for a user
        
        Returns:
            Active SyncSession or None if no active sync
        """
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            active_session = (
                db.query(SyncSession)
                .filter(
                    SyncSession.user_id == user.id,
                    SyncSession.status.in_(['started', 'running'])
                )
                .order_by(desc(SyncSession.started_at))
                .first()
            )
            
            return active_session
            
        finally:
            if should_close_db:
                db.close()
    
    @staticmethod
    def get_latest_sync_session(user: User, db: Session = None) -> Optional[SyncSession]:
        """
        Get the most recent sync session for a user (active or completed)
        
        Returns:
            Latest SyncSession or None if no syncs found
        """
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            latest_session = (
                db.query(SyncSession)
                .filter(SyncSession.user_id == user.id)
                .order_by(desc(SyncSession.started_at))
                .first()
            )
            
            return latest_session
            
        finally:
            if should_close_db:
                db.close()
    
    @staticmethod
    def update_sync_progress(
        session_id: int,
        emails_processed: int = None,
        emails_synced: int = None,
        emails_updated: int = None,
        emails_skipped: int = None,
        batches_processed: int = None,
        total_api_calls: int = None,
        error_count: int = None,
        last_error_message: str = None,
        db: Session = None
    ) -> bool:
        """
        Update progress for a sync session
        
        Returns:
            True if update successful, False otherwise
        """
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            sync_session = db.query(SyncSession).filter(SyncSession.id == session_id).first()
            if not sync_session:
                logger.warning(f"Sync session {session_id} not found")
                return False
            
            # Update provided fields
            update_data = {}
            if emails_processed is not None:
                update_data['emails_processed'] = emails_processed
            if emails_synced is not None:
                update_data['emails_synced'] = emails_synced
            if emails_updated is not None:
                update_data['emails_updated'] = emails_updated
            if emails_skipped is not None:
                update_data['emails_skipped'] = emails_skipped
            if batches_processed is not None:
                update_data['batches_processed'] = batches_processed
            if total_api_calls is not None:
                update_data['total_api_calls'] = total_api_calls
            if error_count is not None:
                update_data['error_count'] = error_count
            if last_error_message is not None:
                update_data['last_error_message'] = last_error_message
                update_data['last_error_at'] = datetime.now(timezone.utc)
            
            if update_data:
                sync_session.update_progress(**update_data)
                db.commit()
                
                logger.debug(f"Updated sync session {session_id} progress: {update_data}")
            
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update sync session {session_id}: {e}")
            return False
        finally:
            if should_close_db:
                db.close()
    
    @staticmethod
    def complete_sync_session(
        session_id: int,
        final_stats: Dict[str, Any] = None,
        db: Session = None
    ) -> bool:
        """
        Mark a sync session as completed
        
        Returns:
            True if completion successful, False otherwise
        """
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            sync_session = db.query(SyncSession).filter(SyncSession.id == session_id).first()
            if not sync_session:
                logger.warning(f"Sync session {session_id} not found")
                return False
            
            sync_session.mark_completed(final_stats)
            db.commit()
            
            logger.info(f"Completed sync session {session_id}: {sync_session.emails_synced} emails synced")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to complete sync session {session_id}: {e}")
            return False
        finally:
            if should_close_db:
                db.close()
    
    @staticmethod
    def fail_sync_session(
        session_id: int,
        error_message: str = None,
        db: Session = None
    ) -> bool:
        """
        Mark a sync session as failed
        
        Returns:
            True if failure marking successful, False otherwise
        """
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            sync_session = db.query(SyncSession).filter(SyncSession.id == session_id).first()
            if not sync_session:
                logger.warning(f"Sync session {session_id} not found")
                return False
            
            sync_session.mark_failed(error_message)
            db.commit()
            
            logger.warning(f"Failed sync session {session_id}: {error_message}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark sync session {session_id} as failed: {e}")
            return False
        finally:
            if should_close_db:
                db.close()
    
    @staticmethod
    def get_sync_sessions_history(
        user: User,
        limit: int = 10,
        db: Session = None
    ) -> List[SyncSession]:
        """
        Get sync session history for a user
        
        Returns:
            List of SyncSession objects ordered by start time (newest first)
        """
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            sessions = (
                db.query(SyncSession)
                .filter(SyncSession.user_id == user.id)
                .order_by(desc(SyncSession.started_at))
                .limit(limit)
                .all()
            )
            
            return sessions
            
        finally:
            if should_close_db:
                db.close()
    
    @staticmethod
    def cleanup_old_sessions(days_to_keep: int = 30, db: Session = None) -> int:
        """
        Clean up old sync sessions (keep only recent ones)
        
        Returns:
            Number of sessions cleaned up
        """
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            
            deleted_count = (
                db.query(SyncSession)
                .filter(SyncSession.started_at < cutoff_date)
                .delete()
            )
            
            db.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old sync sessions")
            
            return deleted_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to cleanup old sync sessions: {e}")
            return 0
        finally:
            if should_close_db:
                db.close()
