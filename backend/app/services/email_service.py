from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging
from ..models.email import Email, EmailAttachment, EmailLabel
from ..models.user import User
from .gmail_service import GmailService
from .ai_service import AIService
from .search_service import SearchService

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.gmail_service = GmailService()
        self.ai_service = AIService()
        self.search_service = SearchService()
    
    def sync_user_emails(self, user: User, db: Session, full_sync: bool = False) -> Dict[str, Any]:
        """Sync emails for a user with improved label handling"""
        try:
            logger.info(f"Starting {'full' if full_sync else 'incremental'} sync for user {user.id}")
            
            if full_sync:
                # Full sync - download all emails with proper pagination
                emails = self.gmail_service.get_all_emails(user, db)
                sync_type = "full"
                synced_count = len(emails)
            else:
                # Incremental sync - only new emails
                synced_count = self.gmail_service.sync_new_emails(user, db)
                emails = []
                sync_type = "incremental"
            
            # Analyze new emails with AI
            if emails:
                analyzed_count = self.ai_service.batch_analyze_emails(emails, db)
            else:
                analyzed_count = 0
            
            logger.info(f"Sync completed: {synced_count} emails synced, {analyzed_count} analyzed")
            
            return {
                "success": True,
                "sync_type": sync_type,
                "emails_synced": synced_count,
                "emails_analyzed": analyzed_count,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error syncing emails for user {user.id}: {e}")
            return {
                "success": False,
                "sync_type": "incremental" if not full_sync else "full",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "emails_synced": 0,
                "emails_analyzed": 0
            }
    
    def sync_labels_only(self, user: User, db: Session) -> Dict[str, Any]:
        """Sync only labels from Gmail"""
        try:
            logger.info(f"Starting label sync for user {user.id}")
            
            synced_count = self.gmail_service.sync_labels_to_database(user, db)
            
            return {
                "success": True,
                "sync_type": "labels_only",
                "labels_synced": synced_count,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error syncing labels for user {user.id}: {e}")
            return {
                "success": False,
                "sync_type": "labels_only",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "labels_synced": 0
            }
    
    def sync_emails_by_label(self, user: User, db: Session, label_id: str, max_results: int = None) -> Dict[str, Any]:
        """Sync emails for a specific label"""
        try:
            logger.info(f"Starting sync for label {label_id}")
            
            emails = self.gmail_service.get_emails_by_label(user, db, label_id, max_results)
            synced_count = len(emails)
            
            # Analyze new emails with AI
            if emails:
                analyzed_count = self.ai_service.batch_analyze_emails(emails, db)
            else:
                analyzed_count = 0
            
            return {
                "success": True,
                "sync_type": "label_sync",
                "label_id": label_id,
                "emails_synced": synced_count,
                "emails_analyzed": analyzed_count,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error syncing emails for label {label_id}: {e}")
            return {
                "success": False,
                "sync_type": "label_sync",
                "label_id": label_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "emails_synced": 0,
                "emails_analyzed": 0
            }
    
    def get_email_by_id(self, email_id: int, db: Session) -> Optional[Email]:
        """Get email by ID with attachments"""
        try:
            return db.query(Email).filter(Email.id == email_id).first()
        except Exception as e:
            logger.error(f"Error getting email {email_id}: {e}")
            return None
    
    def update_email_flags(self, email_id: int, db: Session, **flags) -> bool:
        """Update email flags (read, starred, important, etc.)"""
        try:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email:
                return False
            
            # Update flags
            for flag_name, value in flags.items():
                if hasattr(email, flag_name):
                    setattr(email, flag_name, value)
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating email flags: {e}")
            db.rollback()
            return False
    
    def delete_email(self, email_id: int, db: Session) -> bool:
        """Delete email from database"""
        try:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email:
                return False
            
            # Delete attachments from filesystem
            for attachment in email.attachments:
                try:
                    import os
                    if os.path.exists(attachment.file_path):
                        os.remove(attachment.file_path)
                except Exception as e:
                    logger.warning(f"Could not delete attachment file {attachment.file_path}: {e}")
            
            # Delete email from database
            db.delete(email)
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error deleting email {email_id}: {e}")
            db.rollback()
            return False
    
    def get_email_attachments(self, email_id: int, db: Session) -> List[EmailAttachment]:
        """Get attachments for an email"""
        try:
            return db.query(EmailAttachment).filter(EmailAttachment.email_id == email_id).all()
        except Exception as e:
            logger.error(f"Error getting attachments for email {email_id}: {e}")
            return []
    
    def download_attachment(self, attachment_id: int, db: Session) -> Optional[Dict]:
        """Download attachment file"""
        try:
            attachment = db.query(EmailAttachment).filter(EmailAttachment.id == attachment_id).first()
            if not attachment:
                return None
            
            import os
            if not os.path.exists(attachment.file_path):
                return None
            
            with open(attachment.file_path, 'rb') as f:
                file_data = f.read()
            
            return {
                'filename': attachment.filename,
                'content_type': attachment.content_type,
                'size': attachment.size,
                'data': file_data
            }
            
        except Exception as e:
            logger.error(f"Error downloading attachment {attachment_id}: {e}")
            return None
    
    def get_email_thread(self, thread_id: str, db: Session) -> List[Email]:
        """Get all emails in a thread"""
        try:
            return db.query(Email).filter(Email.thread_id == thread_id).order_by(Email.date_received).all()
        except Exception as e:
            logger.error(f"Error getting email thread {thread_id}: {e}")
            return []
    
    def get_similar_emails(self, email_id: int, db: Session, limit: int = 10) -> List[Email]:
        """Get similar emails based on content and metadata"""
        try:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email:
                return []
            
            # Simple similarity based on sender and subject
            similar = db.query(Email).filter(
                Email.sender == email.sender,
                Email.id != email_id
            ).limit(limit).all()
            
            return similar
            
        except Exception as e:
            logger.error(f"Error getting similar emails: {e}")
            return []
    
    def get_email_clusters(self, db: Session, n_clusters: int = 5) -> Dict:
        """Get email clusters for analytics"""
        # Placeholder implementation
        return {"clusters": []}
    
    def search_emails(self, db: Session, **search_params) -> Dict[str, Any]:
        """Search emails with various filters"""
        try:
            return self.search_service.search_emails(db, **search_params)
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return {"emails": [], "total_count": 0}
    
    def get_email_statistics(self, db: Session, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get email statistics"""
        try:
            query = db.query(Email)
            # Remove user_id filtering since emails are shared

            total_emails = query.count()
            unread_emails = query.filter(Email.is_read == False).count()
            starred_emails = query.filter(Email.is_starred == True).count()

            return {
                "total_emails": total_emails,
                "unread_emails": unread_emails,
                "starred_emails": starred_emails,
                "read_emails": total_emails - unread_emails
            }

        except Exception as e:
            logger.error(f"Error getting email statistics: {e}")
            return {}
    
    def export_emails(self, email_ids: List[int], db: Session, format: str = "json") -> str:
        """Export emails to various formats"""
        # Placeholder implementation
        return "export_data"
    
    def get_email_labels(self, db: Session) -> List[str]:
        """Get all email labels"""
        try:
            labels = db.query(EmailLabel).all()
            return [label.name for label in labels]
        except Exception as e:
            logger.error(f"Error getting email labels: {e}")
            return []
    
    def get_email_suggestions(self, query: str, db: Session, limit: int = 10) -> List[str]:
        """Get search suggestions based on email content"""
        try:
            # Simple implementation - can be enhanced with better search
            emails = db.query(Email).filter(
                Email.subject.contains(query)
            ).limit(limit).all()
            
            suggestions = []
            for email in emails:
                if email.subject and email.subject not in suggestions:
                    suggestions.append(email.subject)
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Error getting email suggestions: {e}")
            return []
    
    def mark_email_as_read(self, email_id: int, db: Session) -> bool:
        """Mark email as read"""
        return self.update_email_flags(email_id, db, is_read=True)
    
    def mark_email_as_unread(self, email_id: int, db: Session) -> bool:
        """Mark email as unread"""
        return self.update_email_flags(email_id, db, is_read=False)
    
    def star_email(self, email_id: int, db: Session) -> bool:
        """Toggle email star status"""
        try:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email:
                return False
            
            email.is_starred = not email.is_starred
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error toggling star for email {email_id}: {e}")
            db.rollback()
            return False
    
    def mark_as_important(self, email_id: int, db: Session) -> bool:
        """Mark email as important"""
        return self.update_email_flags(email_id, db, is_important=True)
    
    def get_email_summary(self, email_id: int, db: Session) -> Optional[str]:
        """Get AI-generated email summary"""
        try:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email:
                return None
            
            # Use AI service to generate summary
            summary = self.ai_service.generate_email_summary(email)
            return summary
            
        except Exception as e:
            logger.error(f"Error generating email summary: {e}")
            return None
    
    def bulk_update_emails(self, email_ids: List[int], db: Session, **updates) -> int:
        """Bulk update multiple emails"""
        try:
            updated_count = 0
            for email_id in email_ids:
                if self.update_email_flags(email_id, db, **updates):
                    updated_count += 1
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error bulk updating emails: {e}")
            return 0
    
    def get_email_analytics(self, db: Session, days: int = 30) -> Dict[str, Any]:
        """Get email analytics for the specified period"""
        try:
            from datetime import timedelta
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            emails = db.query(Email).filter(
                Email.date_received >= start_date,
                Email.date_received <= end_date
            ).all()
            
            # Calculate analytics
            total_emails = len(emails)
            unread_count = sum(1 for e in emails if not e.is_read)
            starred_count = sum(1 for e in emails if e.is_starred)
            
            return {
                "period_days": days,
                "total_emails": total_emails,
                "unread_emails": unread_count,
                "starred_emails": starred_count,
                "read_emails": total_emails - unread_count
            }
            
        except Exception as e:
            logger.error(f"Error getting email analytics: {e}")
            return {}
