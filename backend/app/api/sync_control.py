from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from ..models.database import get_db, get_frontend_db, SessionLocal, FrontendSessionLocal
from ..models.user import User
from ..models.email import Email, EmailLabel
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

router = APIRouter(tags=["sync_control"])

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
    """Start a quick sync for recent emails (non-blocking, no auth required)"""
    try:
        import asyncio
        import anyio

        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }

        from ..services.sync_service import OptimizedSyncService
        sync_service = OptimizedSyncService()

        user_id = user.id

        def _run_quick_sync_background():
            """Run sync in a worker thread so the HTTP request returns immediately."""
            with SessionLocal() as bg_db:
                bg_user = bg_db.query(User).filter(User.id == user_id).first()
                if not bg_user:
                    return
                sync_service.sync_user_emails_full(bg_user, max_emails)

        # Fire-and-forget background sync (creates its own session internally)
        asyncio.create_task(anyio.to_thread.run_sync(_run_quick_sync_background))

        return {
            "message": "Quick sync started",
            "user_id": user.id,
            "result": {
                "max_emails": max_emails,
                "sync_type": "quick"
            },
            "status": "started"
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
    """Start a full sync without date filtering (non-blocking, no auth required)"""
    try:
        import asyncio
        import anyio

        # Get the first user from database
        user = db.query(User).first()
        if not user:
            return {
                "error": "No users found in database",
                "status": "no_users"
            }

        from ..services.sync_service import OptimizedSyncService
        sync_service = OptimizedSyncService()

        user_id = user.id

        def _run_full_sync_background():
            """Run sync in a worker thread so the HTTP request returns immediately."""
            with SessionLocal() as bg_db:
                bg_user = bg_db.query(User).filter(User.id == user_id).first()
                if not bg_user:
                    return
                sync_service.sync_user_emails_full(bg_user, max_emails)

        # Fire-and-forget background sync (creates its own session internally)
        asyncio.create_task(anyio.to_thread.run_sync(_run_full_sync_background))

        return {
            "message": "Full sync started",
            "user_id": user.id,
            "result": {
                "max_emails": max_emails,
                "sync_type": "full"
            },
            "status": "started"
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
