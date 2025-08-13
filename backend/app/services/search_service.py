from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import re
from ..models.email import Email, EmailAttachment
import logging

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self):
        pass
    
    def search_emails(
        self,
        db: Session,
        query: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        subject: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        category: Optional[str] = None,
        sentiment: Optional[int] = None,
        priority_min: Optional[int] = None,
        priority_max: Optional[int] = None,
        is_read: Optional[bool] = None,
        is_starred: Optional[bool] = None,
        is_important: Optional[bool] = None,
        has_attachments: Optional[bool] = None,
        labels: Optional[List[str]] = None,
        sort_by: str = "date_received",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Search emails with pagination"""
        try:
            # Start with base query - optimize for large datasets
            query_obj = db.query(Email)
            
            # Apply filters
            filters = []
            
            # Apply text search if provided
            if query:
                filters.append(
                    or_(
                        Email.subject.ilike(f"%{query}%"),
                        Email.sender.ilike(f"%{query}%"),
                        Email.body_plain.ilike(f"%{query}%")
                    )
                )
            
            # Apply other filters
            if sender:
                filters.append(Email.sender.ilike(f"%{sender}%"))
            if recipient:
                filters.append(Email.recipients.ilike(f"%{recipient}%"))
            if subject:
                filters.append(Email.subject.ilike(f"%{subject}%"))
            if date_from:
                filters.append(Email.date_received >= date_from)
            if date_to:
                filters.append(Email.date_received <= date_to)
            if is_read is not None:
                filters.append(Email.is_read == is_read)
            if is_starred is not None:
                filters.append(Email.is_starred == is_starred)
            if is_important is not None:
                filters.append(Email.is_important == is_important)
            
            # Apply all filters
            for filter_condition in filters:
                query_obj = query_obj.filter(filter_condition)
            
            # Apply sorting
            if sort_by == "date_received":
                if sort_order == "desc":
                    query_obj = query_obj.order_by(Email.date_received.desc())
                else:
                    query_obj = query_obj.order_by(Email.date_received.asc())
            elif sort_by == "subject":
                if sort_order == "desc":
                    query_obj = query_obj.order_by(Email.subject.desc())
                else:
                    query_obj = query_obj.order_by(Email.subject.asc())
            
            # Get total count for pagination
            total_count = query_obj.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            emails = query_obj.offset(offset).limit(page_size).all()
            
            # Calculate total pages
            total_pages = (total_count + page_size - 1) // page_size
            
            return {
                "emails": emails,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
            
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }
    
    def get_email_statistics(self, db: Session, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get email statistics and analytics"""
        try:
            query = db.query(Email)
            
            # Filter by user if specified
            if user_id:
                # This would need to be implemented based on your user-email relationship
                pass
            
            # Total emails
            total_emails = query.count()
            
            # Read vs unread
            read_emails = query.filter(Email.is_read == True).count()
            unread_emails = total_emails - read_emails
            
            # Starred emails
            starred_emails = query.filter(Email.is_starred == True).count()
            
            # Important emails
            important_emails = query.filter(Email.is_important == True).count()
            
            # Emails with attachments
            emails_with_attachments = query.join(EmailAttachment).distinct().count()
            
            # Total attachments
            total_attachments = db.query(EmailAttachment).count()
            
            # Category distribution
            category_stats = db.query(
                Email.category,
                func.count(Email.id).label('count')
            ).group_by(Email.category).all()
            
            # Sentiment distribution
            sentiment_stats = db.query(
                Email.sentiment_score,
                func.count(Email.id).label('count')
            ).group_by(Email.sentiment_score).all()
            
            # Top senders
            top_senders = db.query(
                Email.sender,
                func.count(Email.id).label('count')
            ).group_by(Email.sender).order_by(
                desc(func.count(Email.id))
            ).limit(10).all()
            
            # Recent activity (last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_emails = query.filter(Email.date_received >= thirty_days_ago).count()
            
            # Calculate additional statistics
            total_storage_mb = 0  # Placeholder - would calculate actual storage
            avg_email_size_chars = 0
            processed_emails = total_emails
            processing_rate_percent = 100.0
            
            if total_emails > 0:
                # Calculate average email size
                total_chars = sum(len(email.body_plain or "") + len(email.subject or "") for email in query.all())
                avg_email_size_chars = total_chars // total_emails
            
            return {
                "total_emails": total_emails,
                "read_emails": read_emails,
                "unread_emails": unread_emails,
                "starred_emails": starred_emails,
                "important_emails": important_emails,
                "emails_with_attachments": emails_with_attachments,
                "total_attachments": total_attachments,
                "total_storage_mb": total_storage_mb,
                "avg_email_size_chars": avg_email_size_chars,
                "processed_emails": processed_emails,
                "processing_rate_percent": processing_rate_percent,
                "category_distribution": {cat: count for cat, count in category_stats},
                "sentiment_distribution": {sent: count for sent, count in sentiment_stats},
                "top_senders": [{"sender": sender, "count": count} for sender, count in top_senders],
                "recent_emails_30_days": recent_emails
            }
            
        except Exception as e:
            logger.error(f"Error getting email statistics: {e}")
            return {}
    
    def get_email_threads(self, db: Session, thread_id: Optional[str] = None) -> List[Dict]:
        """Get email threads/conversations"""
        try:
            if thread_id:
                # Get specific thread
                emails = db.query(Email).filter(
                    Email.thread_id == thread_id
                ).order_by(Email.date_received).all()
                
                return [{
                    "thread_id": thread_id,
                    "emails": emails,
                    "count": len(emails)
                }]
            else:
                # Get all threads
                threads = db.query(
                    Email.thread_id,
                    func.count(Email.id).label('count'),
                    func.min(Email.date_received).label('first_email'),
                    func.max(Email.date_received).label('last_email')
                ).filter(
                    Email.thread_id.isnot(None)
                ).group_by(Email.thread_id).order_by(
                    desc(func.max(Email.date_received))
                ).all()
                
                return [{
                    "thread_id": thread.thread_id,
                    "count": thread.count,
                    "first_email": thread.first_email,
                    "last_email": thread.last_email
                } for thread in threads]
                
        except Exception as e:
            logger.error(f"Error getting email threads: {e}")
            return []
    
    def get_email_labels(self, db: Session) -> List[str]:
        """Get all unique email labels"""
        try:
            # This is a simplified approach - in practice you might want to use a separate labels table
            all_emails = db.query(Email.labels).all()
            all_labels = set()
            
            for email_labels in all_emails:
                if email_labels[0]:  # labels column
                    all_labels.update(email_labels[0])
            
            return sorted(list(all_labels))
            
        except Exception as e:
            logger.error(f"Error getting email labels: {e}")
            return []
    
    def get_email_suggestions(self, db: Session, query: str, limit: int = 10) -> List[str]:
        """Get search suggestions based on email content"""
        try:
            # Search in subjects and senders for suggestions
            subjects = db.query(Email.subject).filter(
                Email.subject.ilike(f"%{query}%")
            ).distinct().limit(limit // 2).all()
            
            senders = db.query(Email.sender).filter(
                Email.sender.ilike(f"%{query}%")
            ).distinct().limit(limit // 2).all()
            
            suggestions = []
            
            # Add subject suggestions
            for subject in subjects:
                if subject[0]:
                    suggestions.append(subject[0])
            
            # Add sender suggestions
            for sender in senders:
                if sender[0]:
                    suggestions.append(sender[0])
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Error getting email suggestions: {e}")
            return []
    
    def export_emails(
        self,
        db: Session,
        email_ids: List[int],
        format: str = "json"
    ) -> str:
        """Export emails in specified format"""
        try:
            emails = db.query(Email).filter(Email.id.in_(email_ids)).all()
            
            if format.lower() == "json":
                return self._export_to_json(emails)
            elif format.lower() == "csv":
                return self._export_to_csv(emails)
            elif format.lower() == "eml":
                return self._export_to_eml(emails)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
        except Exception as e:
            logger.error(f"Error exporting emails: {e}")
            return ""
    
    def _export_to_json(self, emails: List[Email]) -> str:
        """Export emails to JSON format"""
        import json
        
        email_data = []
        for email in emails:
            email_data.append({
                "id": email.id,
                "gmail_id": email.gmail_id,
                "thread_id": email.thread_id,
                "subject": email.subject,
                "sender": email.sender,
                "recipients": email.recipients,
                "cc": email.cc,
                "bcc": email.bcc,
                "body_plain": email.body_plain,
                "body_html": email.body_html,
                "date_received": email.date_received.isoformat() if email.date_received else None,
                "date_sent": email.date_sent.isoformat() if email.date_sent else None,
                "labels": email.labels,
                "category": email.category,
                "sentiment_score": email.sentiment_score,
                "priority_score": email.priority_score,
                "summary": email.summary,
                "attachments": [
                    {
                        "filename": att.filename,
                        "content_type": att.content_type,
                        "size": att.size
                    } for att in email.attachments
                ]
            })
        
        return json.dumps(email_data, indent=2)
    
    def _export_to_csv(self, emails: List[Email]) -> str:
        """Export emails to CSV format"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "ID", "Subject", "Sender", "Recipients", "Date Received",
            "Category", "Sentiment", "Priority", "Summary"
        ])
        
        # Write data
        for email in emails:
            writer.writerow([
                email.id,
                email.subject or "",
                email.sender or "",
                ", ".join(email.recipients) if email.recipients else "",
                email.date_received.isoformat() if email.date_received else "",
                email.category or "",
                email.sentiment_score or "",
                email.priority_score or "",
                email.summary or ""
            ])
        
        return output.getvalue()
    
    def _export_to_eml(self, emails: List[Email]) -> str:
        """Export emails to EML format"""
        import email as email_lib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        eml_content = ""
        
        for email in emails:
            msg = MIMEMultipart()
            msg['Subject'] = email.subject or ""
            msg['From'] = email.sender or ""
            msg['To'] = ", ".join(email.recipients) if email.recipients else ""
            msg['Date'] = email.date_received.strftime('%a, %d %b %Y %H:%M:%S %z') if email.date_received else ""
            
            # Add body
            if email.body_html:
                msg.attach(MIMEText(email.body_html, 'html'))
            elif email.body_plain:
                msg.attach(MIMEText(email.body_plain, 'plain'))
            
            eml_content += msg.as_string() + "\n\n"
        
        return eml_content
