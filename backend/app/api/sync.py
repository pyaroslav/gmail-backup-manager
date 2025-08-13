"""
API endpoints for optimized email synchronization
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from ..models.database import get_db
from ..models.user import User
from ..services.sync_service import OptimizedSyncService
from ..services.gmail_service import GmailService
from ..services.auth_service import get_current_user

router = APIRouter(prefix="/sync", tags=["sync"])
logger = logging.getLogger(__name__)

@router.post("/start")
async def start_sync(
    background_tasks: BackgroundTasks,
    max_emails: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Start an optimized email synchronization process
    """
    try:
        sync_service = OptimizedSyncService()
        
        # Start sync in background
        background_tasks.add_task(sync_service.sync_user_emails, current_user, max_emails)
        
        return {
            "message": "Sync started successfully",
            "user_id": current_user.id,
            "max_emails": max_emails,
            "status": "started"
        }
        
    except Exception as e:
        logger.error(f"Error starting sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-now")
async def sync_now(
    max_emails: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Perform immediate email synchronization (synchronous)
    """
    try:
        sync_service = OptimizedSyncService()
        result = sync_service.sync_user_emails(current_user, max_emails)
        
        return {
            "message": "Sync completed",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error during sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_sync_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get synchronization status and statistics
    """
    try:
        sync_service = OptimizedSyncService()
        stats = sync_service.get_sync_stats(current_user)
        
        return {
            "user_id": current_user.id,
            "stats": stats,
            "last_sync": current_user.last_sync.isoformat() if current_user.last_sync else None
        }
        
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress")
async def get_sync_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get real-time sync progress (placeholder for future implementation)
    """
    # This would typically connect to a Redis cache or database to get real-time progress
    return {
        "user_id": current_user.id,
        "status": "completed",  # Placeholder
        "progress_percentage": 100,  # Placeholder
        "emails_processed": 0,  # Placeholder
        "estimated_time_remaining": 0  # Placeholder
    }

@router.post("/test-connection")
async def test_gmail_connection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Test Gmail API connection and credentials
    """
    try:
        gmail_service = GmailService()
        
        # Test basic Gmail API connection
        try:
            # Authenticate the user first
            if not gmail_service.authenticate_user(current_user):
                return {
                    "message": "Gmail API authentication failed",
                    "user_id": current_user.id,
                    "status": "failed",
                    "error": "Failed to authenticate with Gmail API - check credentials",
                    "details": {
                        "api_version": "v1",
                        "connection_type": "OAuth2",
                        "database": "PostgreSQL",
                        "user_email": current_user.email
                    }
                }
            
            # Try to get user profile to test connection
            profile = gmail_service.service.users().getProfile(userId='me').execute()
            email = profile.get('emailAddress', 'Unknown')
            
            # Try to get labels to test API access
            labels = gmail_service.service.users().labels().list(userId='me').execute()
            label_count = len(labels.get('labels', []))
            
            return {
                "message": "Gmail API connection successful",
                "user_id": current_user.id,
                "gmail_email": email,
                "labels_count": label_count,
                "status": "connected",
                "details": {
                    "api_version": "v1",
                    "connection_type": "OAuth2",
                    "database": "PostgreSQL",
                    "user_email": current_user.email
                }
            }
            
        except Exception as gmail_error:
            logger.error(f"Gmail API connection failed: {gmail_error}")
            return {
                "message": "Gmail API connection failed",
                "user_id": current_user.id,
                "status": "failed",
                "error": str(gmail_error),
                "details": {
                    "api_version": "v1",
                    "connection_type": "OAuth2",
                    "database": "PostgreSQL",
                    "user_email": current_user.email
                }
            }
        
    except Exception as e:
        logger.error(f"Error testing Gmail connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))
