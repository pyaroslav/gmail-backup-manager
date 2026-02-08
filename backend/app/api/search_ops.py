from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..models.database import get_db
from ..models.email import Email
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search_ops"])


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
