from fastapi import APIRouter, Query
from sqlalchemy import text
from ..models.database import SessionLocal, FrontendSessionLocal
from ..models.email import Email
import logging
import json
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["db_direct"])


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
