from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from ..models.database import get_db, get_frontend_db, SessionLocal, FrontendSessionLocal
from ..models.user import User
from ..models.email import Email, EmailLabel, EmailAttachment
from ..services.auth_service import get_test_user
from pydantic import BaseModel
import logging
import json
from datetime import datetime, timedelta
import random
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from sqlalchemy import text
from pathlib import Path
import psutil

logger = logging.getLogger(__name__)

router = APIRouter(tags=["test"])

class TestEmailResponse(BaseModel):
    id: int
    gmail_id: str
    thread_id: str
    subject: str
    sender: str
    recipients: List[str]
    body_plain: str
    body_html: str
    date_received: str
    is_read: bool
    is_starred: bool
    is_important: bool
    labels: List[str]
    sentiment_score: int
    category: str
    priority_score: int

class TestLabelResponse(BaseModel):
    id: int
    gmail_label_id: str
    name: str
    label_type: str
    color: dict
    email_count: int

class TestEmailListResponse(BaseModel):
    emails: List[TestEmailResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int

def parse_jsonb_field(field_value):
    """Parse JSONB field that might be stored as string or JSON"""
    if field_value is None:
        return []
    if isinstance(field_value, str):
        try:
            return json.loads(field_value)
        except (json.JSONDecodeError, TypeError):
            # If it's a string that looks like a list, try to parse it
            if field_value.startswith('[') and field_value.endswith(']'):
                try:
                    # Remove brackets and split by comma
                    content = field_value[1:-1]
                    if content:
                        return [item.strip().strip('"\'') for item in content.split(',')]
                    return []
                except:
                    return []
            return []
    elif isinstance(field_value, list):
        return field_value
    else:
        return []

@router.get("/labels/", response_model=List[TestLabelResponse])
async def get_test_labels(db: Session = Depends(get_db)):
    """Get test labels (no authentication required)"""
    try:
        # Create test labels if they don't exist
        test_labels = [
            {"name": "INBOX", "label_type": "system", "email_count": 25},
            {"name": "SENT", "label_type": "system", "email_count": 15},
            {"name": "DRAFT", "label_type": "system", "email_count": 3},
            {"name": "TRASH", "label_type": "system", "email_count": 8},
            {"name": "SPAM", "label_type": "system", "email_count": 12},
            {"name": "STARRED", "label_type": "system", "email_count": 7},
            {"name": "IMPORTANT", "label_type": "system", "email_count": 5},
            {"name": "Work", "label_type": "user", "email_count": 18},
            {"name": "Personal", "label_type": "user", "email_count": 22},
            {"name": "Newsletters", "label_type": "user", "email_count": 14},
            {"name": "Bills", "label_type": "user", "email_count": 6},
            {"name": "Travel", "label_type": "user", "email_count": 4}
        ]
        
        labels = []
        for i, label_data in enumerate(test_labels):
            # Check if label exists
            existing_label = db.query(EmailLabel).filter(EmailLabel.name == label_data["name"]).first()
            if not existing_label:
                # Create new label
                new_label = EmailLabel(
                    gmail_label_id=f"label_{i}",
                    name=label_data["name"],
                    label_type=label_data["label_type"],
                    color={"backgroundColor": "#4285f4", "textColor": "#ffffff"}
                )
                db.add(new_label)
                db.commit()
                db.refresh(new_label)
                existing_label = new_label
            
            labels.append(TestLabelResponse(
                id=existing_label.id,
                gmail_label_id=existing_label.gmail_label_id,
                name=existing_label.name,
                label_type=existing_label.label_type,
                color=existing_label.color or {},
                email_count=label_data["email_count"]
            ))
        
        return labels
    except Exception as e:
        logger.error(f"Error getting test labels: {e}")
        return []

@router.get("/emails/", response_model=TestEmailListResponse)
async def get_test_emails(
    page: int = 1,
    page_size: int = 25,
    search: str = "",
    filter: str = "all",
    sort_by: str = "date_received",
    sort_order: str = "desc",
    db: Session = Depends(get_db)
):
    """Get test emails (no authentication required)"""
    try:
        import signal
        
        # Set a timeout for the database query
        def timeout_handler(signum, frame):
            raise TimeoutError("Database query timed out")
        
        # Set 30 second timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)
        
        try:
            # Query emails with pagination
            query = db.query(Email)
            
            # Apply search filter
            if search:
                query = query.filter(
                    Email.subject.contains(search) |
                    Email.sender.contains(search) |
                    Email.body_plain.contains(search)
                )
            
            # Apply read/unread filter
            if filter == "unread":
                query = query.filter(Email.is_read == False)
            elif filter == "read":
                query = query.filter(Email.is_read == True)
            elif filter == "starred":
                query = query.filter(Email.is_starred == True)
            elif filter == "important":
                query = query.filter(Email.is_important == True)
            
            # Apply sorting
            if sort_by == "date_received":
                if sort_order == "desc":
                    query = query.order_by(Email.date_received.desc())
                else:
                    query = query.order_by(Email.date_received.asc())
            elif sort_by == "sender":
                if sort_order == "desc":
                    query = query.order_by(Email.sender.desc())
                else:
                    query = query.order_by(Email.sender.asc())
            elif sort_by == "subject":
                if sort_order == "desc":
                    query = query.order_by(Email.subject.desc())
                else:
                    query = query.order_by(Email.subject.asc())
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            emails = query.offset(offset).limit(page_size).all()
            
            # Convert to response format
            email_responses = []
            for email in emails:
                # Parse JSONB fields properly
                recipients = parse_jsonb_field(email.recipients)
                labels = parse_jsonb_field(email.labels)
                
                email_responses.append(TestEmailResponse(
                    id=email.id,
                    gmail_id=email.gmail_id,
                    thread_id=email.thread_id or "",
                    subject=email.subject or "",
                    sender=email.sender or "",
                    recipients=recipients,
                    body_plain=email.body_plain or "",
                    body_html=email.body_html or "",
                    date_received=email.date_received.isoformat() if email.date_received else "",
                    is_read=email.is_read,
                    is_starred=email.is_starred,
                    is_important=email.is_important,
                    labels=labels,
                    sentiment_score=email.sentiment_score or 0,
                    category=email.category or "",
                    priority_score=email.priority_score or 0
                ))
            
            total_pages = (total_count + page_size - 1) // page_size
            
            return TestEmailListResponse(
                emails=email_responses,
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
            
        finally:
            # Cancel the alarm
            signal.alarm(0)
        
    except TimeoutError:
        logger.error("Database query timed out - sync may be in progress")
        return TestEmailListResponse(
            emails=[],
            total_count=0,
            page=page,
            page_size=page_size,
            total_pages=0
        )
    except Exception as e:
        logger.error(f"Error getting test emails: {e}")
        return TestEmailListResponse(
            emails=[],
            total_count=0,
            page=page,
            page_size=page_size,
            total_pages=0
        )

@router.get("/labels/{label_name}/emails", response_model=TestEmailListResponse)
async def get_test_emails_by_label(
    label_name: str,
    page: int = 1,
    page_size: int = 25,
    search: str = "",
    sort_by: str = "date_received",
    sort_order: str = "desc",
    db: Session = Depends(get_db)
):
    """Get test emails by label (no authentication required)"""
    try:
        # Query emails with the specified label
        query = db.query(Email).filter(Email.labels.contains([label_name]))
        
        # Apply search filter
        if search:
            query = query.filter(
                Email.subject.contains(search) |
                Email.sender.contains(search) |
                Email.body_plain.contains(search)
            )
        
        # Apply sorting
        if sort_by == "date_received":
            if sort_order == "desc":
                query = query.order_by(Email.date_received.desc())
            else:
                query = query.order_by(Email.date_received.asc())
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        emails = query.offset(offset).limit(page_size).all()
        
        # Convert to response format
        email_responses = []
        for email in emails:
            # Parse JSONB fields properly
            recipients = parse_jsonb_field(email.recipients)
            labels = parse_jsonb_field(email.labels)
            
            email_responses.append(TestEmailResponse(
                id=email.id,
                gmail_id=email.gmail_id,
                thread_id=email.thread_id or "",
                subject=email.subject or "",
                sender=email.sender or "",
                recipients=recipients,
                body_plain=email.body_plain or "",
                body_html=email.body_html or "",
                date_received=email.date_received.isoformat() if email.date_received else "",
                is_read=email.is_read,
                is_starred=email.is_starred,
                is_important=email.is_important,
                labels=labels,
                sentiment_score=email.sentiment_score or 0,
                category=email.category or "",
                priority_score=email.priority_score or 0
            ))
        
        total_pages = (total_count + page_size - 1) // page_size
        
        return TestEmailListResponse(
            emails=email_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error getting test emails by label: {e}")
        return TestEmailListResponse(
            emails=[],
            total_count=0,
            page=page,
            page_size=page_size,
            total_pages=0
        )

@router.patch("/emails/{email_id}/read")
async def mark_test_email_as_read(email_id: int, db: Session = Depends(get_db)):
    """Mark test email as read"""
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if email:
            email.is_read = True
            db.commit()
            return {"message": "Email marked as read"}
        else:
            raise HTTPException(status_code=404, detail="Email not found")
    except Exception as e:
        logger.error(f"Error marking email as read: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/emails/{email_id}/unread")
async def mark_test_email_as_unread(email_id: int, db: Session = Depends(get_db)):
    """Mark test email as unread"""
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if email:
            email.is_read = False
            db.commit()
            return {"message": "Email marked as unread"}
        else:
            raise HTTPException(status_code=404, detail="Email not found")
    except Exception as e:
        logger.error(f"Error marking email as unread: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/emails/{email_id}/star")
async def toggle_test_email_star(email_id: int, db: Session = Depends(get_db)):
    """Toggle test email star status"""
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if email:
            email.is_starred = not email.is_starred
            db.commit()
            return {"message": f"Email {'starred' if email.is_starred else 'unstarred'}"}
        else:
            raise HTTPException(status_code=404, detail="Email not found")
    except Exception as e:
        logger.error(f"Error toggling email star: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/emails/{email_id}")
async def delete_test_email(email_id: int, db: Session = Depends(get_db)):
    """Delete test email"""
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if email:
            db.delete(email)
            db.commit()
            return {"message": "Email deleted"}
        else:
            raise HTTPException(status_code=404, detail="Email not found")
    except Exception as e:
        logger.error(f"Error deleting email: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/sync/status")
async def get_test_sync_status(db: Session = Depends(get_frontend_db)):
    """Get sync status for testing (no auth required)"""
    try:
        from ..services.sync_session_service import SyncSessionService

        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        # Get basic sync statistics (fast estimate to avoid slow COUNT(*) on large table)
        total_emails_row = db.execute(text(
            "SELECT reltuples::bigint AS count FROM pg_class WHERE relname = 'emails'"
        )).fetchone()
        total_emails = int(total_emails_row[0]) if total_emails_row else 0
        last_sync = user.last_sync.isoformat() if user.last_sync else None

        # Determine real-time sync status from sync_sessions
        active_session = SyncSessionService.get_active_sync_session(user=user, db=db)
        # Guard against "stuck started" sessions (e.g., client timed out before work began).
        if active_session and active_session.last_activity_at:
            from datetime import datetime, timezone, timedelta
            if datetime.now(timezone.utc) - active_session.last_activity_at > timedelta(minutes=2):
                # Treat as stale; UI should not show "syncing" forever with 0 progress.
                active_session = None
        latest_session = active_session or SyncSessionService.get_latest_sync_session(user=user, db=db)

        # Base payload expected by frontend polling
        payload = {
            "user_id": user.id,
            "user_email": user.email,
            "total_emails_in_database": total_emails,
            "last_sync": last_sync,
            "gmail_access_token_exists": bool(user.gmail_access_token),
            "gmail_refresh_token_exists": bool(user.gmail_refresh_token),
            "status": "ready",
        }

        if latest_session:
            payload["sync_session"] = {
                "session_id": latest_session.id,
                "sync_type": latest_session.sync_type,
                "sync_source": latest_session.sync_source,
                "status": latest_session.status,
                "started_at": latest_session.started_at.isoformat() if latest_session.started_at else None,
                "completed_at": latest_session.completed_at.isoformat() if latest_session.completed_at else None,
                "max_emails": latest_session.max_emails,
                "start_date": latest_session.start_date,
                "end_date": latest_session.end_date,
            }

        # Map DB session status -> UI status and progress object
        if active_session:
            # Frontend expects: data.status === 'syncing' and data.progress.*
            payload["status"] = "syncing"
            payload["progress"] = {
                "emails_synced": active_session.emails_synced or 0,
                "emails_processed": active_session.emails_processed or 0,
                "errors": active_session.error_count or 0,
                "current_batch": active_session.batches_processed or 0,
                # Best-effort progress percentage when max_emails is known
                "batch_progress": (
                    min(
                        100,
                        round(
                            ((active_session.emails_processed or 0) / max(active_session.max_emails or 1, 1)) * 100,
                            1,
                        ),
                    )
                    if (active_session.max_emails or 0) > 0
                    else 0
                ),
                "new_emails": active_session.emails_synced or 0,
                "last_error": active_session.last_error_message,
            }
        elif latest_session and latest_session.status == "completed":
            payload["status"] = "completed"
            payload["emails_synced"] = latest_session.emails_synced or 0
        elif latest_session and latest_session.status in ("failed", "cancelled", "stopped"):
            payload["status"] = "error"
            payload["error"] = latest_session.last_error_message or f"Sync {latest_session.status}"
        
        return payload
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.post("/sync/test-connection")
async def test_gmail_connection(db: Session = Depends(get_db)):
    """Test Gmail API connection (no auth required)"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.gmail_service import GmailService
        gmail_service = GmailService()
        
        # Test authentication
        if not gmail_service.authenticate_user(user):
            return {
                "message": "Gmail API authentication failed",
                "user_id": user.id,
                "status": "failed",
                "error": "Failed to authenticate with Gmail API - check credentials",
                "details": {
                    "user_email": user.email,
                    "has_access_token": bool(user.gmail_access_token),
                    "has_refresh_token": bool(user.gmail_refresh_token)
                }
            }
        
        # Try to get user profile
        try:
            profile = gmail_service.service.users().getProfile(userId='me').execute()
            email = profile.get('emailAddress', 'Unknown')
            
            # Try to get labels
            labels = gmail_service.service.users().labels().list(userId='me').execute()
            label_count = len(labels.get('labels', []))
            
            # Try to get email count
            messages = gmail_service.service.users().messages().list(userId='me', maxResults=1).execute()
            total_emails = messages.get('resultSizeEstimate', 0)
            
            return {
                "message": "Gmail API connection successful",
                "user_id": user.id,
                "gmail_email": email,
                "labels_count": label_count,
                "total_emails_in_gmail": total_emails,
                "status": "connected",
                "details": {
                    "api_version": "v1",
                    "connection_type": "OAuth2",
                    "database": "PostgreSQL"
                }
            }
            
        except Exception as gmail_error:
            return {
                "message": "Gmail API connection failed",
                "user_id": user.id,
                "status": "failed",
                "error": str(gmail_error),
                "details": {
                    "user_email": user.email
                }
            }
        
    except Exception as e:
        logger.error(f"Error testing Gmail connection: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.post("/sync/start")
async def start_test_sync(
    max_emails: int = 100,
    db: Session = Depends(get_db)
):
    """Start a test sync (no auth required)"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.sync_service import OptimizedSyncService
        sync_service = OptimizedSyncService()
        
        # Start sync
        emails_synced = sync_service.sync_user_emails(user, max_emails)
        
        return {
            "message": "Test sync completed",
            "user_id": user.id,
            "result": {
                "emails_synced": emails_synced
            },
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"Error during test sync: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.post("/sync/start-quick")
async def start_quick_sync(
    max_emails: int = 1000,
    db: Session = Depends(get_db)
):
    """Start a quick sync for recent emails (no auth required)"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.sync_service import OptimizedSyncService
        sync_service = OptimizedSyncService()
        
        # Start quick sync (same as full sync but with different name)
        emails_synced = sync_service.sync_user_emails_full(user, max_emails)
        
        return {
            "message": "Quick sync completed",
            "user_id": user.id,
            "result": {
                "emails_synced": emails_synced,
                "max_emails": max_emails,
                "sync_type": "quick"
            },
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error during quick sync: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }

@router.post("/sync/start-full")
async def start_full_sync(
    max_emails: int = 1000,
    db: Session = Depends(get_db)
):
    """Start a full sync without date filtering (no auth required)"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.sync_service import OptimizedSyncService
        sync_service = OptimizedSyncService()
        
        # Start full sync
        emails_synced = sync_service.sync_user_emails_full(user, max_emails)
        
        return {
            "message": "Full sync completed",
            "user_id": user.id,
            "result": {
                "emails_synced": emails_synced,
                "max_emails": max_emails,
                "sync_type": "full"
            },
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error during full sync: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }

@router.post("/sync/start-from-date")
async def start_sync_from_date(
    start_date: str,
    max_emails: int = 1000,
    db: Session = Depends(get_db)
):
    """Start a sync from a specific date (format: YYYY/MM/DD) (no auth required)"""
    try:
        import asyncio
        import anyio
        from ..services.sync_session_service import SyncSessionService
        from ..models.database import SessionLocal

        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.sync_service import OptimizedSyncService
        sync_service = OptimizedSyncService()

        # Create a sync session up-front so UI can track it immediately
        sync_session = SyncSessionService.create_sync_session(
            user=user,
            sync_type="date_range",
            sync_source="api",
            max_emails=max_emails,
            start_date=start_date,
            query_filter=f"after:{start_date}",
            notes=f"Date range sync from {start_date} (background)",
            db=db,
        )

        def _run_date_range_sync_background():
            """Run sync in a worker thread so the HTTP request returns immediately."""
            with SessionLocal() as bg_db:
                bg_user = bg_db.query(User).filter(User.id == user.id).first()
                if not bg_user:
                    return
                # Run sync and persist progress into the existing session
                sync_service.sync_user_emails_from_date(
                    bg_user,
                    start_date=start_date,
                    max_emails=max_emails,
                    existing_session_id=sync_session.id,
                )

        # Fire-and-forget background sync (prevents frontend/node timeouts)
        asyncio.create_task(anyio.to_thread.run_sync(_run_date_range_sync_background))

        return {
            "message": f"Date range sync started from {start_date}",
            "user_id": user.id,
            "session_id": sync_session.id,
            "result": {
                "max_emails": max_emails,
                "start_date": start_date,
                "sync_type": "date_range",
            },
            "status": "started",
        }
        
    except Exception as e:
        logger.error(f"Error during date range sync: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }

@router.post("/sync/reset-last-sync")
async def reset_last_sync(db: Session = Depends(get_db)):
    """Reset the last sync time to allow syncing older emails (no auth required)"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        # Reset the last sync time to None
        user.last_sync = None
        db.commit()
        
        return {
            "message": "Last sync time reset successfully",
            "user_id": user.id,
            "user_email": user.email,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error resetting last sync: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/sync/emails-count")
async def get_emails_count(db: Session = Depends(get_db)):
    """Get emails count by year for analysis"""
    try:
        # Get emails count by year
        from sqlalchemy import extract, func
        
        yearly_counts = db.query(
            extract('year', Email.date_received).label('year'),
            func.count(Email.id).label('count')
        ).filter(
            Email.date_received.isnot(None)
        ).group_by(
            extract('year', Email.date_received)
        ).order_by(
            extract('year', Email.date_received)
        ).all()
        
        # Get total count
        total_count = db.query(Email).count()
        
        # Get emails without date
        no_date_count = db.query(Email).filter(Email.date_received.is_(None)).count()
        
        return {
            "total_emails": total_count,
            "emails_without_date": no_date_count,
            "yearly_breakdown": [
                {"year": int(year), "count": count} 
                for year, count in yearly_counts
            ],
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error getting emails count: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/sync/test-gmail-query")
async def test_gmail_query(db: Session = Depends(get_db)):
    """Test different Gmail API queries to understand the email count issue"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.gmail_service import GmailService
        gmail_service = GmailService()
        
        # Test authentication
        if not gmail_service.authenticate_user(user):
            return {
                "error": "Failed to authenticate with Gmail API",
                "status": "auth_failed"
            }
        
        results = {}
        
        # Test 1: No query (all emails)
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                maxResults=1
            ).execute()
            results["all_emails"] = messages.get('resultSizeEstimate', 0)
        except Exception as e:
            results["all_emails_error"] = str(e)
        
        # Test 2: After 2011 query
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                q='after:2011/01/01',
                maxResults=1
            ).execute()
            results["after_2011"] = messages.get('resultSizeEstimate', 0)
        except Exception as e:
            results["after_2011_error"] = str(e)
        
        # Test 3: After 2020 query
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                q='after:2020/01/01',
                maxResults=1
            ).execute()
            results["after_2020"] = messages.get('resultSizeEstimate', 0)
        except Exception as e:
            results["after_2020_error"] = str(e)
        
        # Test 4: After 2023 query
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                q='after:2023/01/01',
                maxResults=1
            ).execute()
            results["after_2023"] = messages.get('resultSizeEstimate', 0)
        except Exception as e:
            results["after_2023_error"] = str(e)
        
        # Test 5: Get actual messages (first 10)
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                maxResults=10
            ).execute()
            message_list = messages.get('messages', [])
            results["sample_messages"] = len(message_list)
            if message_list:
                # Get details of first message
                first_message = gmail_service.service.users().messages().get(
                    userId='me',
                    id=message_list[0]['id'],
                    format='metadata',
                    metadataHeaders=['Date', 'Subject', 'From']
                ).execute()
                results["first_message_date"] = first_message.get('payload', {}).get('headers', [])
        except Exception as e:
            results["sample_messages_error"] = str(e)
        
        return {
            "user_id": user.id,
            "user_email": user.email,
            "gmail_api_results": results,
            "database_emails": db.query(Email).count(),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error testing Gmail query: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/sync/test-alternative-queries")
async def test_alternative_queries(db: Session = Depends(get_db)):
    """Test alternative Gmail API queries to get more emails"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.gmail_service import GmailService
        gmail_service = GmailService()
        
        # Test authentication
        if not gmail_service.authenticate_user(user):
            return {
                "error": "Failed to authenticate with Gmail API",
                "status": "auth_failed"
            }
        
        results = {}
        
        # Test 1: Try with larger maxResults
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                maxResults=500
            ).execute()
            results["large_batch"] = {
                "count": len(messages.get('messages', [])),
                "has_next_page": bool(messages.get('nextPageToken')),
                "result_size_estimate": messages.get('resultSizeEstimate', 0)
            }
        except Exception as e:
            results["large_batch_error"] = str(e)
        
        # Test 2: Try with specific label (INBOX)
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                maxResults=100
            ).execute()
            results["inbox_only"] = {
                "count": len(messages.get('messages', [])),
                "result_size_estimate": messages.get('resultSizeEstimate', 0)
            }
        except Exception as e:
            results["inbox_only_error"] = str(e)
        
        # Test 3: Try with ALL_MAIL label
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                labelIds=['ALL_MAIL'],
                maxResults=100
            ).execute()
            results["all_mail"] = {
                "count": len(messages.get('messages', [])),
                "result_size_estimate": messages.get('resultSizeEstimate', 0)
            }
        except Exception as e:
            results["all_mail_error"] = str(e)
        
        # Test 4: Try with SENT label
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                labelIds=['SENT'],
                maxResults=100
            ).execute()
            results["sent_mail"] = {
                "count": len(messages.get('messages', [])),
                "result_size_estimate": messages.get('resultSizeEstimate', 0)
            }
        except Exception as e:
            results["sent_mail_error"] = str(e)
        
        # Test 5: Try with different date format
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                q='after:2011/1/1',
                maxResults=100
            ).execute()
            results["date_format_1"] = {
                "count": len(messages.get('messages', [])),
                "result_size_estimate": messages.get('resultSizeEstimate', 0)
            }
        except Exception as e:
            results["date_format_1_error"] = str(e)
        
        # Test 6: Try with timestamp
        try:
            # 2011-01-01 timestamp
            timestamp = "1293840000"
            messages = gmail_service.service.users().messages().list(
                userId='me',
                q=f"after:{timestamp}",
                maxResults=100
            ).execute()
            results["timestamp_query"] = {
                "count": len(messages.get('messages', [])),
                "result_size_estimate": messages.get('resultSizeEstimate', 0)
            }
        except Exception as e:
            results["timestamp_query_error"] = str(e)
        
        # Test 7: Try without any query (just get what's available)
        try:
            messages = gmail_service.service.users().messages().list(
                userId='me',
                maxResults=1000
            ).execute()
            results["no_query_large"] = {
                "count": len(messages.get('messages', [])),
                "has_next_page": bool(messages.get('nextPageToken')),
                "result_size_estimate": messages.get('resultSizeEstimate', 0)
            }
        except Exception as e:
            results["no_query_large_error"] = str(e)
        
        return {
            "user_id": user.id,
            "user_email": user.email,
            "alternative_queries": results,
            "database_emails": db.query(Email).count(),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error testing alternative queries: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/sync/check-quotas")
async def check_gmail_quotas(db: Session = Depends(get_db)):
    """Check Gmail API quotas and try to refresh authentication"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.gmail_service import GmailService
        gmail_service = GmailService()
        
        results = {}
        
        # Test 1: Try to refresh authentication
        try:
            # Force refresh the token
            creds = Credentials(
                token=user.gmail_access_token,
                refresh_token=user.gmail_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GMAIL_CLIENT_ID"),
                client_secret=os.getenv("GMAIL_CLIENT_SECRET"),
                scopes=['https://www.googleapis.com/auth/gmail.readonly']
            )
            
            # Force refresh
            creds.refresh(Request())
            
            # Update user tokens
            user.gmail_access_token = creds.token
            user.gmail_refresh_token = creds.refresh_token
            user.gmail_token_expiry = creds.expiry
            db.commit()
            
            results["token_refresh"] = "success"
            results["new_token_expiry"] = creds.expiry.isoformat() if creds.expiry else None
            
        except Exception as e:
            results["token_refresh_error"] = str(e)
        
        # Test 2: Try authentication with refreshed tokens
        try:
            if gmail_service.authenticate_user(user):
                results["authentication"] = "success"
                
                # Test 3: Try to get user profile
                profile = gmail_service.service.users().getProfile(userId='me').execute()
                results["profile"] = profile
                
                # Test 4: Try different query approaches
                # Test with no query at all
                messages = gmail_service.service.users().messages().list(
                    userId='me',
                    maxResults=1
                ).execute()
                results["no_query_count"] = messages.get('resultSizeEstimate', 0)
                
                # Test with larger maxResults
                messages = gmail_service.service.users().messages().list(
                    userId='me',
                    maxResults=1000
                ).execute()
                results["large_query"] = {
                    "count": len(messages.get('messages', [])),
                    "has_next_page": bool(messages.get('nextPageToken')),
                    "result_size_estimate": messages.get('resultSizeEstimate', 0)
                }
                
                # Test with specific label
                messages = gmail_service.service.users().messages().list(
                    userId='me',
                    labelIds=['INBOX'],
                    maxResults=100
                ).execute()
                results["inbox_count"] = messages.get('resultSizeEstimate', 0)
                
            else:
                results["authentication"] = "failed"
                
        except Exception as e:
            results["authentication_error"] = str(e)
        
        # Test 5: Check if there are any API errors
        try:
            # Try to get a specific message to see if there are permission issues
            messages = gmail_service.service.users().messages().list(
                userId='me',
                maxResults=1
            ).execute()
            
            if messages.get('messages'):
                message_id = messages['messages'][0]['id']
                message = gmail_service.service.users().messages().get(
                    userId='me',
                    id=message_id,
                    format='metadata',
                    metadataHeaders=['Date', 'Subject', 'From']
                ).execute()
                results["message_access"] = "success"
                results["sample_message"] = message
            else:
                results["message_access"] = "no_messages"
                
        except Exception as e:
            results["message_access_error"] = str(e)
        
        return {
            "user_id": user.id,
            "user_email": user.email,
            "quota_check_results": results,
            "database_emails": db.query(Email).count(),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error checking Gmail quotas: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.post("/background-sync/start")
async def start_background_sync(interval_minutes: int = 5):
    """Start the background sync service"""
    try:
        from ..services.background_sync_service import background_sync_service
        
        # Start the background sync in a separate task
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(background_sync_service.start_background_sync(interval_minutes))
        
        return {
            "message": f"Background sync started with {interval_minutes} minute interval",
            "status": "started",
            "interval_minutes": interval_minutes
        }
    except Exception as e:
        logger.error(f"Error starting background sync: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }

@router.post("/background-sync/stop")
async def stop_background_sync():
    """Stop the background sync service"""
    try:
        from ..services.background_sync_service import background_sync_service
        background_sync_service.stop_background_sync()
        
        return {
            "message": "Background sync stopped",
            "status": "stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping background sync: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }

@router.get("/background-sync/status")
async def get_background_sync_status():
    """Get background sync status"""
    try:
        from ..services.background_sync_service import background_sync_service
        
        sync_status = background_sync_service.get_sync_status()
        db_stats = background_sync_service.get_database_stats()
        
        return {
            "sync_status": sync_status,
            "database_stats": db_stats,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error getting background sync status: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }

@router.get("/analytics/overview")
async def get_test_analytics_overview(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get test analytics overview (no authentication required)"""
    try:
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get emails in date range
        emails_in_period = db.query(Email).filter(
            Email.date_received >= start_date,
            Email.date_received <= end_date
        ).count()
        
        # Get total emails
        total_emails = db.query(Email).count()
        
        # Get read/unread counts
        read_emails = db.query(Email).filter(Email.is_read == True).count()
        unread_emails = db.query(Email).filter(Email.is_read == False).count()
        
        # Get starred/important counts
        starred_emails = db.query(Email).filter(Email.is_starred == True).count()
        important_emails = db.query(Email).filter(Email.is_important == True).count()
        
        # Get category distribution
        category_stats = db.query(
            Email.category,
            func.count(Email.id).label('count')
        ).group_by(Email.category).all()
        
        category_distribution = {}
        for category, count in category_stats:
            cat_name = category or "uncategorized"
            category_distribution[cat_name] = count
        
        # Get sentiment distribution
        sentiment_stats = db.query(
            Email.sentiment_score,
            func.count(Email.id).label('count')
        ).group_by(Email.sentiment_score).all()
        
        sentiment_distribution = {"positive": 0, "neutral": 0, "negative": 0}
        for sentiment, count in sentiment_stats:
            if sentiment == 1:
                sentiment_distribution["positive"] = count
            elif sentiment == -1:
                sentiment_distribution["negative"] = count
            else:
                sentiment_distribution["neutral"] = count
        
        # Get top senders
        sender_stats = db.query(
            Email.sender,
            func.count(Email.id).label('count')
        ).group_by(Email.sender).order_by(
            func.count(Email.id).desc()
        ).limit(10).all()
        
        top_senders = []
        for sender, count in sender_stats:
            if sender:  # Skip None senders
                top_senders.append({
                    "sender": sender,
                    "count": count
                })
        
        return {
            "period_days": days,
            "total_emails": total_emails,
            "emails_in_period": emails_in_period,
            "read_emails": read_emails,
            "unread_emails": unread_emails,
            "starred_emails": starred_emails,
            "important_emails": important_emails,
            "category_distribution": category_distribution,
            "sentiment_distribution": sentiment_distribution,
            "top_senders": top_senders
        }
        
    except Exception as e:
        logger.error(f"Error getting test analytics overview: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/statistics")
async def get_test_statistics(db: Session = Depends(get_db)):
    """Get comprehensive test statistics (no authentication required)"""
    try:
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        # Basic counts
        total_emails = db.query(Email).count()
        read_emails = db.query(Email).filter(Email.is_read == True).count()
        unread_emails = db.query(Email).filter(Email.is_read == False).count()
        starred_emails = db.query(Email).filter(Email.is_starred == True).count()
        important_emails = db.query(Email).filter(Email.is_important == True).count()
        
        # Date range analysis
        oldest_email = db.query(Email.date_received).order_by(Email.date_received.asc()).first()
        newest_email = db.query(Email.date_received).order_by(Email.date_received.desc()).first()
        
        # Yearly breakdown
        yearly_counts = db.query(
            func.extract('year', Email.date_received).label('year'),
            func.count(Email.id).label('count')
        ).filter(
            Email.date_received.isnot(None)
        ).group_by(
            func.extract('year', Email.date_received)
        ).order_by(
            func.extract('year', Email.date_received)
        ).all()
        
        # Monthly breakdown (last 12 months)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        monthly_counts = db.query(
            func.extract('year', Email.date_received).label('year'),
            func.extract('month', Email.date_received).label('month'),
            func.count(Email.id).label('count')
        ).filter(
            Email.date_received >= start_date,
            Email.date_received <= end_date
        ).group_by(
            func.extract('year', Email.date_received),
            func.extract('month', Email.date_received)
        ).order_by(
            func.extract('year', Email.date_received),
            func.extract('month', Email.date_received)
        ).all()
        
        # Sender analysis
        unique_senders = db.query(func.count(func.distinct(Email.sender))).scalar()
        top_senders = db.query(
            Email.sender,
            func.count(Email.id).label('count')
        ).group_by(Email.sender).order_by(
            func.count(Email.id).desc()
        ).limit(20).all()
        
        # Category analysis
        categories = db.query(
            Email.category,
            func.count(Email.id).label('count')
        ).group_by(Email.category).order_by(
            func.count(Email.id).desc()
        ).all()
        
        # Sentiment analysis
        sentiment_breakdown = db.query(
            Email.sentiment_score,
            func.count(Email.id).label('count')
        ).group_by(Email.sentiment_score).all()
        
        # Priority analysis
        priority_breakdown = db.query(
            Email.priority_score,
            func.count(Email.id).label('count')
        ).group_by(Email.priority_score).order_by(Email.priority_score).all()
        
        return {
            "total_emails": total_emails,
            "read_emails": read_emails,
            "unread_emails": unread_emails,
            "starred_emails": starred_emails,
            "important_emails": important_emails,
            "read_rate": (read_emails / total_emails * 100) if total_emails > 0 else 0,
            "date_range": {
                "oldest_email": oldest_email[0].isoformat() if oldest_email and oldest_email[0] else None,
                "newest_email": newest_email[0].isoformat() if newest_email and newest_email[0] else None
            },
            "yearly_breakdown": [
                {"year": int(year), "count": count} 
                for year, count in yearly_counts
            ],
            "monthly_breakdown": [
                {"year": int(year), "month": int(month), "count": count}
                for year, month, count in monthly_counts
            ],
            "sender_analysis": {
                "unique_senders": unique_senders,
                "top_senders": [
                    {"sender": sender, "count": count}
                    for sender, count in top_senders if sender
                ]
            },
            "categories": [
                {"category": category or "uncategorized", "count": count}
                for category, count in categories
            ],
            "sentiment_breakdown": [
                {"sentiment": sentiment, "count": count}
                for sentiment, count in sentiment_breakdown
            ],
            "priority_breakdown": [
                {"priority": priority, "count": count}
                for priority, count in priority_breakdown
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting test statistics: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/trends")
async def get_test_trends(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get email trends over time (no authentication required)"""
    try:
        from datetime import datetime, timedelta
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get emails in date range
        emails = db.query(Email).filter(
            Email.date_received >= start_date,
            Email.date_received <= end_date
        ).order_by(Email.date_received).all()
        
        # Group by date
        daily_stats = {}
        for email in emails:
            if email.date_received:
                date_key = email.date_received.date().isoformat()
                if date_key not in daily_stats:
                    daily_stats[date_key] = {
                        "total": 0,
                        "read": 0,
                        "unread": 0,
                        "starred": 0,
                        "important": 0
                    }
                
                daily_stats[date_key]["total"] += 1
                if email.is_read:
                    daily_stats[date_key]["read"] += 1
                else:
                    daily_stats[date_key]["unread"] += 1
                
                if email.is_starred:
                    daily_stats[date_key]["starred"] += 1
                
                if email.is_important:
                    daily_stats[date_key]["important"] += 1
        
        # Convert to list format
        trends = []
        for date_key in sorted(daily_stats.keys()):
            trends.append({
                "date": date_key,
                **daily_stats[date_key]
            })
        
        return {"trends": trends}
        
    except Exception as e:
        logger.error(f"Error getting test trends: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/activity")
async def get_test_activity(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Get email activity patterns (no authentication required)"""
    try:
        from datetime import datetime, timedelta
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get emails in date range
        emails = db.query(Email).filter(
            Email.date_received >= start_date,
            Email.date_received <= end_date
        ).all()
        
        # Analyze by hour of day
        hourly_activity = {}
        for i in range(24):
            hourly_activity[i] = 0
        
        for email in emails:
            if email.date_received:
                hour = email.date_received.hour
                hourly_activity[hour] += 1
        
        # Analyze by day of week
        daily_activity = {}
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i in range(7):
            daily_activity[day_names[i]] = 0
        
        for email in emails:
            if email.date_received:
                day = email.date_received.weekday()
                daily_activity[day_names[day]] += 1
        
        # Get most active hours
        most_active_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Get most active days
        most_active_days = sorted(daily_activity.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "hourly_activity": [{"hour": hour, "count": count} for hour, count in hourly_activity.items()],
            "daily_activity": [{"day": day, "count": count} for day, count in daily_activity.items()],
            "most_active_hours": [{"hour": hour, "count": count} for hour, count in most_active_hours],
            "most_active_days": [{"day": day, "count": count} for day, count in most_active_days]
        }
        
    except Exception as e:
        logger.error(f"Error getting test activity: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/performance")
async def get_test_performance(db: Session = Depends(get_db)):
    """Get system performance metrics (no authentication required)"""
    try:
        from sqlalchemy import func
        
        # Get basic counts
        total_emails = db.query(Email).count()
        
        # Get emails with sentiment analysis
        processed_emails = db.query(Email).filter(
            Email.sentiment_score.isnot(None)
        ).count()
        
        # Get emails with priority scores
        priority_processed = db.query(Email).filter(
            Email.priority_score.isnot(None)
        ).count()
        
        # Get emails with categories
        categorized_emails = db.query(Email).filter(
            Email.category.isnot(None)
        ).count()
        
        # Calculate processing rates
        sentiment_rate = (processed_emails / total_emails * 100) if total_emails > 0 else 0
        priority_rate = (priority_processed / total_emails * 100) if total_emails > 0 else 0
        categorization_rate = (categorized_emails / total_emails * 100) if total_emails > 0 else 0
        
        # Get average email size (character count)
        avg_email_size = db.query(
            func.avg(func.length(Email.body_plain) + func.length(Email.body_html or ''))
        ).scalar() or 0
        
        # Get emails by year for storage estimation
        yearly_counts = db.query(
            func.extract('year', Email.date_received).label('year'),
            func.count(Email.id).label('count')
        ).filter(
            Email.date_received.isnot(None)
        ).group_by(
            func.extract('year', Email.date_received)
        ).order_by(
            func.extract('year', Email.date_received)
        ).all()
        
        return {
            "total_emails": total_emails,
            "processed_emails": {
                "sentiment_analysis": processed_emails,
                "priority_scoring": priority_processed,
                "categorization": categorized_emails
            },
            "processing_rates": {
                "sentiment_analysis": round(sentiment_rate, 2),
                "priority_scoring": round(priority_rate, 2),
                "categorization": round(categorization_rate, 2)
            },
            "avg_email_size_chars": round(avg_email_size, 0),
            "yearly_distribution": [
                {"year": int(year), "count": count}
                for year, count in yearly_counts
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting test performance: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/insights")
async def get_test_insights(db: Session = Depends(get_db)):
    """Get AI-generated insights about email patterns (no authentication required)"""
    try:
        from datetime import datetime, timedelta
        
        # Get recent emails for analysis
        recent_emails = db.query(Email).order_by(
            Email.date_received.desc()
        ).limit(1000).all()
        
        insights = []
        
        # Analyze email volume trends
        if len(recent_emails) > 10:
            recent_count = len([e for e in recent_emails[:100]])
            older_count = len([e for e in recent_emails[100:200]])
            
            if recent_count > older_count * 1.5:
                insights.append({
                    "type": "volume_increase",
                    "title": "Email Volume Increase",
                    "description": f"Recent email volume is {round((recent_count/older_count)*100)}% higher than previous period",
                    "severity": "info",
                    "icon": "📈"
                })
        
        # Analyze unread email patterns
        unread_emails = [e for e in recent_emails if not e.is_read]
        unread_percentage = (len(unread_emails) / len(recent_emails)) * 100
        if unread_percentage > 30:
            insights.append({
                "type": "high_unread",
                "title": "High Unread Email Rate",
                "description": f"{unread_percentage:.1f}% of recent emails are unread ({len(unread_emails)} emails)",
                "severity": "warning",
                "icon": "📬"
            })
        
        # Analyze sender patterns
        sender_counts = {}
        for email in recent_emails:
            sender = email.sender.split('<')[0].strip() if email.sender else "Unknown"
            sender_counts[sender] = sender_counts.get(sender, 0) + 1
        
        top_sender = max(sender_counts.items(), key=lambda x: x[1])
        if top_sender[1] > len(recent_emails) * 0.3:
            insights.append({
                "type": "dominant_sender",
                "title": "Dominant Sender",
                "description": f"{top_sender[0]} accounts for {round((top_sender[1]/len(recent_emails))*100)}% of recent emails",
                "severity": "info",
                "icon": "👤"
            })
        
        # Analyze time patterns
        hourly_counts = {}
        for email in recent_emails:
            if email.date_received:
                hour = email.date_received.hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        if hourly_counts:
            peak_hour = max(hourly_counts.items(), key=lambda x: x[1])
            insights.append({
                "type": "peak_activity",
                "title": "Peak Email Activity",
                "description": f"Most emails arrive at {peak_hour[0]}:00 ({peak_hour[1]} emails in recent period)",
                "severity": "info",
                "icon": "⏰"
            })
        
        # Analyze important emails
        important_emails = [e for e in recent_emails if e.is_important]
        if important_emails:
            important_percentage = (len(important_emails) / len(recent_emails)) * 100
            insights.append({
                "type": "important_emails",
                "title": "Important Email Volume",
                "description": f"{important_percentage:.1f}% of recent emails are marked as important",
                "severity": "info",
                "icon": "⭐"
            })
        
        # Analyze date range
        if recent_emails:
            oldest_recent = min(e.date_received for e in recent_emails if e.date_received)
            newest_recent = max(e.date_received for e in recent_emails if e.date_received)
            if oldest_recent and newest_recent:
                days_span = (newest_recent - oldest_recent).days
                insights.append({
                    "type": "date_span",
                    "title": "Email Time Span",
                    "description": f"Recent emails span {days_span} days ({oldest_recent.strftime('%Y-%m-%d')} to {newest_recent.strftime('%Y-%m-%d')})",
                    "severity": "info",
                    "icon": "📅"
                })
        
        return {"insights": insights}
        
    except Exception as e:
        logger.error(f"Error getting test insights: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/domains")
async def get_test_domain_analysis(db: Session = Depends(get_db)):
    """Get domain analysis for emails (no authentication required)"""
    try:
        from sqlalchemy import func
        import re
        
        # Get all senders
        senders = db.query(Email.sender).filter(Email.sender.isnot(None)).all()
        
        # Extract domains
        domain_counts = {}
        domain_emails = {}
        
        for (sender,) in senders:
            # Extract domain from email address
            domain_match = re.search(r'@([^>]+)', sender)
            if domain_match:
                domain = domain_match.group(1).lower()
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                
                if domain not in domain_emails:
                    domain_emails[domain] = []
                domain_emails[domain].append(sender)
        
        # Get top domains
        top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        
        # Analyze domain types
        domain_types = {
            "social_media": ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "facebook.com", "twitter.com"],
            "shopping": ["amazon.com", "ebay.com", "etsy.com", "shopify.com", "walmart.com", "target.com"],
            "finance": ["chase.com", "bankofamerica.com", "wellsfargo.com", "capitalone.com", "usbank.com"],
            "news": ["cnn.com", "bbc.com", "nytimes.com", "washingtonpost.com", "reuters.com"],
            "tech": ["google.com", "microsoft.com", "apple.com", "github.com", "stackoverflow.com"]
        }
        
        domain_categories = {}
        for domain, count in domain_counts.items():
            category = "other"
            for cat, domains in domain_types.items():
                if any(d in domain for d in domains):
                    category = cat
                    break
            domain_categories[category] = domain_categories.get(category, 0) + count
        
        # Get domain statistics
        domain_stats = []
        for domain, count in top_domains:
            # Get read rate for this domain
            domain_emails_list = domain_emails[domain]
            read_count = db.query(Email).filter(
                Email.sender.in_(domain_emails_list),
                Email.is_read == True
            ).count()
            read_rate = (read_count / count * 100) if count > 0 else 0
            
            domain_stats.append({
                "domain": domain,
                "count": count,
                "read_rate": round(read_rate, 1),
                "percentage": round((count / sum(domain_counts.values())) * 100, 1)
            })
        
        return {
            "total_domains": len(domain_counts),
            "top_domains": domain_stats,
            "domain_categories": [
                {"category": cat, "count": count}
                for cat, count in domain_categories.items()
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting test domain analysis: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/trends-detailed")
async def get_test_detailed_trends(
    days: int = 90,
    db: Session = Depends(get_db)
):
    """Get detailed email trends analysis (no authentication required)"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get emails in date range
        emails = db.query(Email).filter(
            Email.date_received >= start_date,
            Email.date_received <= end_date
        ).order_by(Email.date_received).all()
        
        # Weekly trends
        weekly_stats = {}
        for email in emails:
            if email.date_received:
                week_start = email.date_received - timedelta(days=email.date_received.weekday())
                week_key = week_start.strftime('%Y-%W')
                
                if week_key not in weekly_stats:
                    weekly_stats[week_key] = {
                        "week_start": week_start,
                        "total": 0,
                        "read": 0,
                        "unread": 0,
                        "important": 0,
                        "starred": 0
                    }
                
                weekly_stats[week_key]["total"] += 1
                if email.is_read:
                    weekly_stats[week_key]["read"] += 1
                else:
                    weekly_stats[week_key]["unread"] += 1
                
                if email.is_important:
                    weekly_stats[week_key]["important"] += 1
                
                if email.is_starred:
                    weekly_stats[week_key]["starred"] += 1
        
        # Convert to list and sort
        weekly_trends = []
        for week_key, stats in sorted(weekly_stats.items()):
            weekly_trends.append({
                "week": week_key,
                "week_start": stats["week_start"].strftime('%Y-%m-%d'),
                **stats
            })
        
        # Monthly trends
        monthly_stats = {}
        for email in emails:
            if email.date_received:
                month_key = email.date_received.strftime('%Y-%m')
                
                if month_key not in monthly_stats:
                    monthly_stats[month_key] = {
                        "total": 0,
                        "read": 0,
                        "unread": 0,
                        "important": 0,
                        "starred": 0
                    }
                
                monthly_stats[month_key]["total"] += 1
                if email.is_read:
                    monthly_stats[month_key]["read"] += 1
                else:
                    monthly_stats[month_key]["unread"] += 1
                
                if email.is_important:
                    monthly_stats[month_key]["important"] += 1
                
                if email.is_starred:
                    monthly_stats[month_key]["starred"] += 1
        
        # Convert to list and sort
        monthly_trends = []
        for month_key, stats in sorted(monthly_stats.items()):
            monthly_trends.append({
                "month": month_key,
                **stats
            })
        
        # Calculate growth rates
        if len(weekly_trends) >= 2:
            recent_week = weekly_trends[-1]["total"]
            previous_week = weekly_trends[-2]["total"]
            weekly_growth = ((recent_week - previous_week) / previous_week * 100) if previous_week > 0 else 0
        else:
            weekly_growth = 0
        
        if len(monthly_trends) >= 2:
            recent_month = monthly_trends[-1]["total"]
            previous_month = monthly_trends[-2]["total"]
            monthly_growth = ((recent_month - previous_month) / previous_month * 100) if previous_month > 0 else 0
        else:
            monthly_growth = 0
        
        return {
            "period_days": days,
            "total_emails_in_period": len(emails),
            "weekly_trends": weekly_trends,
            "monthly_trends": monthly_trends,
            "growth_rates": {
                "weekly_growth": round(weekly_growth, 1),
                "monthly_growth": round(monthly_growth, 1)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting test detailed trends: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/categories")
async def get_test_categories(db: Session = Depends(get_db)):
    """Get email categories analytics (no authentication required)"""
    try:
        from sqlalchemy import func
        
        # Get category distribution
        category_stats = db.query(
            Email.category,
            func.count(Email.id).label('count'),
            func.avg(Email.sentiment_score).label('avg_sentiment'),
            func.avg(Email.priority_score).label('avg_priority')
        ).group_by(Email.category).all()
        
        categories = []
        for cat, count, avg_sentiment, avg_priority in category_stats:
            categories.append({
                "category": cat or "uncategorized",
                "count": count,
                "avg_sentiment": float(avg_sentiment) if avg_sentiment else 0,
                "avg_priority": float(avg_priority) if avg_priority else 0
            })
        
        return {"categories": categories}
        
    except Exception as e:
        logger.error(f"Error getting test categories: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/senders")
async def get_test_senders(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get sender analytics (no authentication required)"""
    try:
        from sqlalchemy import func
        
        # Get top senders with basic stats
        sender_stats = db.query(
            Email.sender,
            func.count(Email.id).label('count')
        ).group_by(Email.sender).order_by(
            func.count(Email.id).desc()
        ).limit(limit).all()
        
        senders = []
        for sender, count in sender_stats:
            if sender and sender.strip():  # Skip None and empty senders
                # Get read count for this sender
                read_count = db.query(Email).filter(
                    Email.sender == sender,
                    Email.is_read == True
                ).count()
                
                senders.append({
                    "sender": sender,
                    "count": count,
                    "avg_sentiment": 0,  # Placeholder
                    "avg_priority": 0,   # Placeholder
                    "read_count": read_count,
                    "unread_count": count - read_count,
                    "read_rate": (read_count / count * 100) if count > 0 else 0
                })
        
        return {"senders": senders}
        
    except Exception as e:
        logger.error(f"Error getting test senders: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/sentiment")
async def get_test_sentiment(db: Session = Depends(get_db)):
    """Get sentiment analysis insights (no authentication required)"""
    try:
        from sqlalchemy import func
        
        # Get sentiment distribution
        sentiment_stats = db.query(
            Email.sentiment_score,
            func.count(Email.id).label('count')
        ).group_by(Email.sentiment_score).all()
        
        sentiment_data = {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "total": 0
        }
        
        for sentiment, count in sentiment_stats:
            sentiment_data["total"] += count
            if sentiment == 1:
                sentiment_data["positive"] = count
            elif sentiment == -1:
                sentiment_data["negative"] = count
            else:
                sentiment_data["neutral"] = count
        
        # Calculate percentages
        if sentiment_data["total"] > 0:
            sentiment_data["positive_percent"] = (sentiment_data["positive"] / sentiment_data["total"]) * 100
            sentiment_data["neutral_percent"] = (sentiment_data["neutral"] / sentiment_data["total"]) * 100
            sentiment_data["negative_percent"] = (sentiment_data["negative"] / sentiment_data["total"]) * 100
        else:
            sentiment_data["positive_percent"] = 0
            sentiment_data["neutral_percent"] = 0
            sentiment_data["negative_percent"] = 0
        
        return {"sentiment": sentiment_data}
        
    except Exception as e:
        logger.error(f"Error getting test sentiment: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/analytics/priority")
async def get_test_priority(db: Session = Depends(get_db)):
    """Get priority analysis insights (no authentication required)"""
    try:
        from sqlalchemy import func
        
        # Get priority distribution
        priority_stats = db.query(
            Email.priority_score,
            func.count(Email.id).label('count')
        ).group_by(Email.priority_score).order_by(Email.priority_score).all()
        
        priority_data = {
            "high_priority": 0,  # 8-10
            "medium_priority": 0,  # 4-7
            "low_priority": 0,  # 1-3
            "total": 0,
            "distribution": []
        }
        
        for priority, count in priority_stats:
            priority_data["total"] += count
            priority_data["distribution"].append({
                "priority": priority,
                "count": count
            })
            
            if priority is not None:
                if priority >= 8:
                    priority_data["high_priority"] += count
                elif priority >= 4:
                    priority_data["medium_priority"] += count
                else:
                    priority_data["low_priority"] += count
            else:
                # Handle emails without priority scores
                priority_data["low_priority"] += count
        
        # Calculate percentages
        if priority_data["total"] > 0:
            priority_data["high_priority_percent"] = (priority_data["high_priority"] / priority_data["total"]) * 100
            priority_data["medium_priority_percent"] = (priority_data["medium_priority"] / priority_data["total"]) * 100
            priority_data["low_priority_percent"] = (priority_data["low_priority"] / priority_data["total"]) * 100
        else:
            priority_data["high_priority_percent"] = 0
            priority_data["medium_priority_percent"] = 0
            priority_data["low_priority_percent"] = 0
        
        return {"priority": priority_data}
        
    except Exception as e:
        logger.error(f"Error getting test priority: {e}")
        return {
            "error": str(e),
            "status": "error"
        }

@router.get("/sync/fast-status")
async def get_fast_sync_status(db: Session = Depends(get_db)):
    """Get fast sync status for frontend use during sync operations"""
    try:
        # Get basic info without complex queries
        total_emails = db.query(Email).count()
        
        # Get the first user (simple query)
        user = db.query(User).first()
        last_sync = user.last_sync.isoformat() if user and user.last_sync else None
        
        return {
            "total_emails": total_emails,
            "last_sync": last_sync,
            "status": "ready",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting fast sync status: {e}")
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@router.get("/emails/fast")
async def get_fast_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get emails quickly for frontend use during sync operations"""
    try:
        # Simple count query
        total_count = db.query(Email).count()
        
        # Simple pagination without complex joins
        offset = (page - 1) * page_size
        emails = db.query(Email).order_by(Email.date_received.desc()).offset(offset).limit(page_size).all()
        
        # Convert to simple dict format
        email_list = []
        for email in emails:
            email_list.append({
                "id": email.id,
                "subject": email.subject or "No Subject",
                "sender": email.sender or "Unknown",
                "date_received": email.date_received.isoformat() if email.date_received else None,
                "is_read": email.is_read,
                "is_starred": email.is_starred,
                "body_plain": email.body_plain[:200] + "..." if email.body_plain and len(email.body_plain) > 200 else email.body_plain
            })
        
        return {
            "emails": email_list,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size
        }
        
    except Exception as e:
        logger.error(f"Error getting fast emails: {e}")
        return {
            "emails": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "error": str(e)
        }

@router.get("/search/fast")
async def fast_search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Fast search for frontend use during sync operations"""
    try:
        # Simple search using ILIKE
        search_term = f"%{q}%"
        
        # Count total matches
        total_count = db.query(Email).filter(
            Email.subject.ilike(search_term) | 
            Email.sender.ilike(search_term) |
            Email.body_plain.ilike(search_term)
        ).count()
        
        # Get paginated results
        offset = (page - 1) * page_size
        emails = db.query(Email).filter(
            Email.subject.ilike(search_term) | 
            Email.sender.ilike(search_term) |
            Email.body_plain.ilike(search_term)
        ).order_by(Email.date_received.desc()).offset(offset).limit(page_size).all()
        
        # Convert to simple dict format
        email_list = []
        for email in emails:
            email_list.append({
                "id": email.id,
                "subject": email.subject or "No Subject",
                "sender": email.sender or "Unknown",
                "date_received": email.date_received.isoformat() if email.date_received else None,
                "is_read": email.is_read,
                "is_starred": email.is_starred,
                "body_plain": email.body_plain[:200] + "..." if email.body_plain and len(email.body_plain) > 200 else email.body_plain
            })
        
        return {
            "emails": email_list,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size,
            "search_term": q
        }
        
    except Exception as e:
        logger.error(f"Error in fast search: {e}")
        return {
            "emails": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "search_term": q,
            "error": str(e)
        }

# Global cache for email count to avoid database locks during sync
_email_count_cache = {
    "count": 0,
    "last_updated": None,
    "cache_duration": 300  # 5 minutes
}

def update_email_count_cache(count):
    """Update the email count cache"""
    global _email_count_cache
    _email_count_cache["count"] = count
    _email_count_cache["last_updated"] = datetime.now()

def get_cached_email_count():
    """Get email count from cache if valid, otherwise from database"""
    global _email_count_cache
    
    # Check if cache is still valid
    if (_email_count_cache["last_updated"] and 
        (datetime.now() - _email_count_cache["last_updated"]).total_seconds() < _email_count_cache["cache_duration"]):
        return _email_count_cache["count"]
    
    # Cache expired or doesn't exist, try to update it
    try:
        # Use a very short timeout for database query
        from sqlalchemy import text
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT COUNT(*) FROM emails")).scalar()
            update_email_count_cache(result)
            return result
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error updating email count cache: {e}")
        # Return cached value even if expired, or 0 if no cache
        return _email_count_cache["count"] if _email_count_cache["count"] > 0 else 0

@router.get("/sync/cached-status")
async def get_cached_sync_status():
    """Get sync status using cached email count to avoid database locks"""
    try:
        # Get cached email count
        total_emails = get_cached_email_count()
        
        # Get basic user info (this should be fast)
        db = SessionLocal()
        try:
            user = db.query(User).first()
            last_sync = user.last_sync.isoformat() if user and user.last_sync else None
        finally:
            db.close()
        
        return {
            "total_emails": total_emails,
            "last_sync": last_sync,
            "status": "ready",
            "timestamp": datetime.now().isoformat(),
            "cache_info": {
                "cached": _email_count_cache["last_updated"] is not None,
                "cache_age": (datetime.now() - _email_count_cache["last_updated"]).total_seconds() if _email_count_cache["last_updated"] else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting cached sync status: {e}")
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "total_emails": _email_count_cache["count"] if _email_count_cache["count"] > 0 else 0
        }

@router.post("/sync/update-cache")
async def update_email_count_cache_endpoint():
    """Manually update the email count cache"""
    try:
        db = SessionLocal()
        try:
            count = db.query(Email).count()
            update_email_count_cache(count)
            return {
                "success": True,
                "count": count,
                "timestamp": datetime.now().isoformat()
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error updating cache: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/db/direct-count")
async def get_direct_email_count():
    """Get email count directly from database using raw SQL (bypasses all API processing)"""
    try:
        # Use raw SQL query like the Docker command with frontend session
        db = FrontendSessionLocal()
        try:
            result = db.execute(text("SELECT COUNT(*) FROM emails")).scalar()
            return {
                "total_emails": result,
                "timestamp": datetime.now().isoformat(),
                "method": "direct_sql_frontend"
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in direct count: {e}")
        return {
            "error": str(e),
            "total_emails": 0,
            "timestamp": datetime.now().isoformat()
        }

@router.get("/db/direct-emails")
async def get_direct_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50)
):
    """Get emails directly from database using raw SQL (bypasses all API processing)"""
    try:
        db = FrontendSessionLocal()
        try:
            # Get total count
            total_count = db.execute(text("SELECT COUNT(*) FROM emails")).scalar()
            
            # Get paginated emails with minimal processing
            offset = (page - 1) * page_size
            emails = db.execute(text("""
                SELECT id, subject, sender, date_received, is_read, is_starred,
                       LEFT(body_plain, 200) as body_preview
                FROM emails
                ORDER BY date_received DESC
                LIMIT :page_size OFFSET :offset
            """), {"page_size": page_size, "offset": offset}).fetchall()
            
            # Convert to simple dict format
            email_list = []
            for email in emails:
                email_list.append({
                    "id": email.id,
                    "subject": email.subject or "No Subject",
                    "sender": email.sender or "Unknown",
                    "date_received": email.date_received.isoformat() if email.date_received else None,
                    "is_read": email.is_read,
                    "is_starred": email.is_starred,
                    "body_plain": email.body_preview
                })
            
            return {
                "emails": email_list,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size,
                "method": "direct_sql_frontend"
            }
            
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in direct emails: {e}")
        return {
            "emails": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "error": str(e)
        }

@router.get("/db/direct-search")
async def get_direct_search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50)
):
    """Search emails directly from database using raw SQL (bypasses all API processing)"""
    try:
        db = FrontendSessionLocal()
        try:
            # Use ILIKE for case-insensitive search
            search_term = f"%{q}%"

            # Get total count
            total_count = db.execute(text("""
                SELECT COUNT(*) FROM emails
                WHERE subject ILIKE :search_term
                   OR sender ILIKE :search_term
                   OR body_plain ILIKE :search_term
            """), {"search_term": search_term}).scalar()

            # Get paginated results
            offset = (page - 1) * page_size
            emails = db.execute(text("""
                SELECT id, subject, sender, date_received, is_read, is_starred,
                       LEFT(body_plain, 200) as body_preview
                FROM emails
                WHERE subject ILIKE :search_term
                   OR sender ILIKE :search_term
                   OR body_plain ILIKE :search_term
                ORDER BY date_received DESC
                LIMIT :page_size OFFSET :offset
            """), {"search_term": search_term, "page_size": page_size, "offset": offset}).fetchall()
            
            # Convert to simple dict format
            email_list = []
            for email in emails:
                email_list.append({
                    "id": email.id,
                    "subject": email.subject or "No Subject",
                    "sender": email.sender or "Unknown",
                    "date_received": email.date_received.isoformat() if email.date_received else None,
                    "is_read": email.is_read,
                    "is_starred": email.is_starred,
                    "body_plain": email.body_preview
                })
            
            return {
                "emails": email_list,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size,
                "search_term": q,
                "method": "direct_sql_frontend"
            }
            
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in direct search: {e}")
        return {
            "emails": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "search_term": q,
            "error": str(e)
        }

@router.get("/db/raw-count")
async def get_raw_email_count():
    """Get email count using raw SQL via SessionLocal"""
    try:
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT COUNT(*) FROM emails")).scalar()
            return {
                "total_emails": result,
                "timestamp": datetime.now().isoformat(),
                "method": "raw_sql"
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in raw count: {e}")
        return {
            "error": str(e),
            "total_emails": 0,
            "timestamp": datetime.now().isoformat()
        }

@router.get("/db/raw-emails")
async def get_raw_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50)
):
    """Get emails using raw SQL via SessionLocal"""
    try:
        db = SessionLocal()
        try:
            # Get total count
            total_count = db.execute(text("SELECT COUNT(*) FROM emails")).scalar()

            # Get paginated emails
            offset = (page - 1) * page_size
            rows = db.execute(text("""
                SELECT id, subject, sender, date_received, is_read, is_starred,
                       LEFT(body_plain, 200) as body_preview
                FROM emails
                ORDER BY date_received DESC
                LIMIT :page_size OFFSET :offset
            """), {"page_size": page_size, "offset": offset}).fetchall()

            email_list = []
            for row in rows:
                email_list.append({
                    "id": row.id,
                    "subject": row.subject or "No Subject",
                    "sender": row.sender or "Unknown",
                    "date_received": row.date_received.isoformat() if row.date_received else None,
                    "is_read": row.is_read,
                    "is_starred": row.is_starred,
                    "body_plain": row.body_preview
                })

            return {
                "emails": email_list,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size,
                "method": "raw_sql"
            }

        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in raw emails: {e}")
        return {
            "emails": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "error": str(e)
        }

@router.get("/db/frontend-count")
async def get_frontend_email_count():
    """Get email count using frontend database user (separate from sync user)"""
    try:
        db = FrontendSessionLocal()
        try:
            result = db.execute(text("SELECT COUNT(*) FROM emails")).scalar()
            return {
                "total_emails": result,
                "timestamp": datetime.now().isoformat(),
                "method": "frontend_user"
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in frontend count: {e}")
        return {
            "error": str(e),
            "total_emails": 0,
            "timestamp": datetime.now().isoformat()
        }

@router.get("/cache/file-count")
async def get_file_cache_count():
    """Get email count from file cache (bypasses database entirely)"""
    try:
        cache_file = Path("/app/cache/email_count.json")
        
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                data = json.load(f)
                return {
                    "total_emails": data.get("total_emails", 0),
                    "timestamp": data.get("timestamp", datetime.now().isoformat()),
                    "method": "file_cache"
                }
        else:
            # If cache doesn't exist, try to create it from database
            try:
                db = SessionLocal()
                try:
                    result = db.execute(text("SELECT COUNT(*) FROM emails")).scalar()
                finally:
                    db.close()

                # Create cache directory if it doesn't exist
                cache_file.parent.mkdir(exist_ok=True)
                
                # Write to cache file
                cache_data = {
                    "total_emails": result,
                    "timestamp": datetime.now().isoformat()
                }
                
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f)
                
                return {
                    "total_emails": result,
                    "timestamp": cache_data["timestamp"],
                    "method": "file_cache_created"
                }
                
            except Exception as db_error:
                logger.error(f"Database error creating cache: {db_error}")
                return {
                    "total_emails": 0,
                    "timestamp": datetime.now().isoformat(),
                    "method": "file_cache_missing",
                    "error": "Cache not available and database unreachable"
                }
                
    except Exception as e:
        logger.error(f"Error in file cache count: {e}")
        return {
            "error": str(e),
            "total_emails": 0,
            "timestamp": datetime.now().isoformat()
        }

@router.post("/sync/cleanup-stale")
async def cleanup_stale_sync_sessions():
    """Clean up stale sync sessions (no auth required)"""
    try:
        from ..services.sync_session_service import SyncSessionService
        
        cleaned_count = SyncSessionService.cleanup_stale_sessions(timeout_minutes=30)
        
        return {
            "message": f"Cleaned up {cleaned_count} stale sync sessions",
            "cleaned_count": cleaned_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up stale sync sessions: {e}")
        return {
            "error": str(e),
            "cleaned_count": 0,
            "timestamp": datetime.now().isoformat()
        }

@router.get("/sync/progress")
async def get_sync_progress():
    """Get sync progress for testing (no auth required)"""
    try:
        from ..services.background_sync_service import background_sync_service
        from datetime import datetime, timedelta
        
        # Get background sync status
        sync_status = background_sync_service.get_sync_status()
        
        # Get current database email count
        try:
            db = SessionLocal()
            try:
                current_email_count = db.execute(text("SELECT COUNT(*) FROM emails")).scalar()

                # Get latest sync session
                row = db.execute(text("""
                    SELECT id, status, emails_synced, emails_processed, started_at, completed_at
                    FROM sync_sessions
                    ORDER BY started_at DESC
                    LIMIT 1
                """)).fetchone()
                session_result = tuple(row) if row else None
            finally:
                db.close()
        except Exception as db_error:
            logger.error(f"Database error in sync progress: {db_error}")
            current_email_count = 0
            session_result = None
        
        # Calculate sync progress
        sync_progress = {
            "is_active": sync_status.get("sync_in_progress", False),
            "sync_type": "background" if sync_status.get("sync_in_progress") else "none",
            "emails_processed": 0,
            "emails_synced": 0,
            "progress_percentage": 0,
            "current_email_count": current_email_count
        }
        
        # If there's an active session, get its details
        if session_result:
            session_id, status, emails_synced, emails_processed, started_at, completed_at = session_result
            
            sync_progress.update({
                "session_id": session_id,
                "status": status,
                "emails_synced": emails_synced or 0,
                "emails_processed": emails_processed or 0,
                "started_at": started_at.isoformat() if started_at else None,
                "completed_at": completed_at.isoformat() if completed_at else None
            })
            
            # Calculate progress percentage based on emails processed
            if emails_processed and emails_processed > 0:
                sync_progress["progress_percentage"] = min(100, round((emails_synced / max(emails_processed, 1)) * 100, 1))
        
        return {
            "sync_progress": sync_progress,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting sync progress: {e}")
        return {
            "error": str(e),
            "sync_progress": {
                "is_active": False,
                "sync_type": "none",
                "emails_processed": 0,
                "emails_synced": 0,
                "progress_percentage": 0
            },
            "timestamp": datetime.now().isoformat()
        }

@router.get("/sync/real-time-status")
async def get_real_time_sync_status():
    """Get comprehensive real-time sync status with progress, timing, and logs"""
    try:
        from ..services.background_sync_service import background_sync_service
        from datetime import datetime, timedelta
        import psutil
        import os
        
        # Get background sync status
        sync_status = background_sync_service.get_sync_status()
        db_stats = background_sync_service.get_database_stats()
        
        # Get current database email count
        try:
            db = SessionLocal()
            try:
                current_email_count = db.execute(text("SELECT COUNT(*) FROM emails")).scalar()

                # Get latest email timestamp
                latest_email_date = db.execute(text("SELECT MAX(date_received) FROM emails")).scalar()

                # Get sync start time from background service
                last_sync_row = db.execute(text(
                    "SELECT created_at FROM emails ORDER BY created_at DESC LIMIT 1"
                )).fetchone()
                last_sync_time = last_sync_row[0] if last_sync_row else None
            finally:
                db.close()
        except Exception as db_error:
            logger.error(f"Database error in real-time status: {db_error}")
            current_email_count = 0
            latest_email_date = None
            last_sync_time = None
        
        # Calculate sync progress and timing
        sync_progress = {
            "is_active": sync_status.get("sync_in_progress", False),
            "sync_type": "background" if sync_status.get("sync_in_progress") else "none",
            "start_time": None,
            "elapsed_time": None,
            "estimated_completion": None,
            "progress_percentage": 0,
            "emails_processed": 0,
            "emails_per_minute": 0,
            "current_batch": 0,
            "total_batches": 0
        }
        
        # If sync is active, calculate timing
        if sync_progress["is_active"]:
            # Try to get sync start time from background service stats
            stats = sync_status.get("stats", {})
            last_sync_start = stats.get("last_sync_start")
            
            if last_sync_start:
                try:
                    start_time = datetime.fromisoformat(last_sync_start.replace('Z', '+00:00'))
                    elapsed = datetime.now(start_time.tzinfo) - start_time
                    sync_progress["start_time"] = start_time.isoformat()
                    sync_progress["elapsed_time"] = str(elapsed)
                    
                    # Calculate progress based on emails processed
                    emails_processed = stats.get("emails_synced", 0)
                    sync_progress["emails_processed"] = emails_processed
                    
                    if elapsed.total_seconds() > 0:
                        emails_per_minute = (emails_processed * 60) / elapsed.total_seconds()
                        sync_progress["emails_per_minute"] = round(emails_per_minute, 2)
                        
                        # Estimate completion (assuming average sync size)
                        estimated_total = 1000  # Default estimate
                        if emails_per_minute > 0:
                            remaining_emails = estimated_total - emails_processed
                            remaining_minutes = remaining_emails / emails_per_minute
                            estimated_completion = start_time + timedelta(minutes=remaining_minutes)
                            sync_progress["estimated_completion"] = estimated_completion.isoformat()
                            
                            # Calculate progress percentage
                            sync_progress["progress_percentage"] = min(100, round((emails_processed / estimated_total) * 100, 1))
                    
                except Exception as timing_error:
                    logger.error(f"Error calculating sync timing: {timing_error}")
        
        # Get system information
        system_info = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent if os.path.exists('/') else 0
        }
        
        # Get recent sync logs (last 50 entries)
        try:
            log_file = "/app/background_sync.log"
            recent_logs = []
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    # Get last 50 lines
                    recent_lines = lines[-50:] if len(lines) > 50 else lines
                    for line in recent_lines:
                        line = line.strip()
                        if line and ('sync' in line.lower() or 'email' in line.lower() or 'error' in line.lower()):
                            recent_logs.append(line)
        except Exception as log_error:
            logger.error(f"Error reading sync logs: {log_error}")
            recent_logs = []
        
        return {
            "timestamp": datetime.now().isoformat(),
            "sync_progress": sync_progress,
            "database_stats": {
                "current_email_count": current_email_count,
                "latest_email_date": latest_email_date.isoformat() if latest_email_date else None,
                "last_sync_time": last_sync_time.isoformat() if last_sync_time else None
            },
            "background_sync": sync_status,
            "system_info": system_info,
            "recent_logs": recent_logs[-20:],  # Last 20 log entries
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error getting real-time sync status: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
            "status": "failed"
        }

@router.post("/sync/stop")
async def stop_sync(
    db: Session = Depends(get_db)
):
    """Stop any running sync (no auth required)"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.sync_service import OptimizedSyncService
        
        # Request sync stop
        stopped = OptimizedSyncService.request_stop_sync(user.id)
        
        return {
            "message": "Stop sync requested" if stopped else "No active sync found",
            "user_id": user.id,
            "sync_stopped": stopped,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error stopping sync: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }

@router.get("/sync/status-control")
async def get_sync_status_control(
    db: Session = Depends(get_db)
):
    """Get current sync control status (no auth required)"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.sync_service import OptimizedSyncService
        
        is_active = OptimizedSyncService.is_sync_active(user.id)
        session_id = OptimizedSyncService.get_active_sync_session_id(user.id)
        
        return {
            "user_id": user.id,
            "sync_active": is_active,
            "session_id": session_id,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }
