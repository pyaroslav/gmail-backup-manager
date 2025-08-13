from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..models.database import get_db
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
async def get_test_sync_status(db: Session = Depends(get_db)):
    """Get sync status for testing (no auth required)"""
    try:
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        # Get basic sync statistics
        total_emails = db.query(Email).count()
        last_sync = user.last_sync.isoformat() if user.last_sync else None
        
        return {
            "user_id": user.id,
            "user_email": user.email,
            "total_emails_in_database": total_emails,
            "last_sync": last_sync,
            "gmail_access_token_exists": bool(user.gmail_access_token),
            "gmail_refresh_token_exists": bool(user.gmail_refresh_token),
            "status": "ready"
        }
        
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
        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }
        
        from ..services.sync_service import OptimizedSyncService
        sync_service = OptimizedSyncService()
        
        # Start sync from specific date
        emails_synced = sync_service.sync_user_emails_from_date(user, start_date, max_emails)
        
        return {
            "message": f"Date range sync completed from {start_date}",
            "user_id": user.id,
            "result": {
                "emails_synced": emails_synced,
                "max_emails": max_emails,
                "start_date": start_date,
                "sync_type": "date_range"
            },
            "status": "success"
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
