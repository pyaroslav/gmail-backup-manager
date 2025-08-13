from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from ..models.database import get_db
from ..models.user import User
from ..services.auth_service import get_current_user
from ..services.email_service import EmailService
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

# Pydantic models
class SearchRequest(BaseModel):
    query: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    category: Optional[str] = None
    sentiment: Optional[int] = None
    priority_min: Optional[int] = None
    priority_max: Optional[int] = None
    is_read: Optional[bool] = None
    is_starred: Optional[bool] = None
    is_important: Optional[bool] = None
    has_attachments: Optional[bool] = None
    labels: Optional[List[str]] = None
    sort_by: str = "date_received"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 50

class SearchResponse(BaseModel):
    emails: List[Dict[str, Any]]
    total_count: int
    page: int
    page_size: int
    total_pages: int

class ExportRequest(BaseModel):
    email_ids: List[int]
    format: str = "json"  # json, csv, eml

# Initialize service
email_service = EmailService()

@router.post("/emails", response_model=SearchResponse)
async def search_emails(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """Advanced email search with multiple filters"""
    try:
        result = email_service.search_emails(
            db=db,
            query=request.query,
            sender=request.sender,
            recipient=request.recipient,
            subject=request.subject,
            date_from=request.date_from,
            date_to=request.date_to,
            category=request.category,
            sentiment=request.sentiment,
            priority_min=request.priority_min,
            priority_max=request.priority_max,
            is_read=request.is_read,
            is_starred=request.is_starred,
            is_important=request.is_important,
            has_attachments=request.has_attachments,
            labels=request.labels,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
            page=request.page,
            page_size=request.page_size
        )
        
        # Convert emails to dict for response
        email_dicts = []
        for email in result["emails"]:
            email_dict = {
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
                "date_received": email.date_received,
                "date_sent": email.date_sent,
                "is_read": email.is_read,
                "is_starred": email.is_starred,
                "is_important": email.is_important,
                "is_spam": email.is_spam,
                "is_trash": email.is_trash,
                "labels": email.labels,
                "category": email.category,
                "sentiment_score": email.sentiment_score,
                "priority_score": email.priority_score,
                "summary": email.summary
            }
            email_dicts.append(email_dict)
        
        return SearchResponse(
            emails=email_dicts,
            total_count=result["total_count"],
            page=result["page"],
            page_size=result["page_size"],
            total_pages=result["total_pages"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/suggestions")
async def get_search_suggestions(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get search suggestions based on email content"""
    try:
        suggestions = email_service.get_email_suggestions(query, db, limit)
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/labels")
async def get_email_labels(db: Session = Depends(get_db)):
    """Get all unique email labels"""
    try:
        labels = email_service.get_email_labels(db)
        return {"labels": labels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories")
async def get_email_categories():
    """Get available email categories"""
    categories = [
        {"id": "work", "name": "Work", "description": "Work-related emails"},
        {"id": "personal", "name": "Personal", "description": "Personal emails"},
        {"id": "spam", "name": "Spam", "description": "Spam emails"},
        {"id": "newsletter", "name": "Newsletter", "description": "Newsletter emails"},
        {"id": "other", "name": "Other", "description": "Other emails"}
    ]
    return {"categories": categories}

@router.get("/statistics")
async def get_email_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get email statistics and analytics"""
    try:
        from ..services.email_service import EmailService
        email_service = EmailService()
        stats = email_service.get_email_statistics(db, current_user.id)
        
        # If stats is empty, return default values
        if not stats:
            stats = {
                "total_emails": 0,
                "unread_emails": 0,
                "starred_emails": 0,
                "read_emails": 0,
                "total_emails_change": "+0%",
                "unread_emails_change": "+0%",
                "starred_emails_change": "+0%",
                "important_emails": 0,
                "important_emails_change": "+0%"
            }
        
        return stats
    except Exception as e:
        logger.error(f"Error getting email statistics: {e}")
        # Return default values on error
        return {
            "total_emails": 0,
            "unread_emails": 0,
            "starred_emails": 0,
            "read_emails": 0,
            "total_emails_change": "+0%",
            "unread_emails_change": "+0%",
            "starred_emails_change": "+0%",
            "important_emails": 0,
            "important_emails_change": "+0%"
        }

@router.get("/threads")
async def get_email_threads(
    thread_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get email threads/conversations"""
    try:
        from ..services.search_service import SearchService
        search_service = SearchService()
        threads = search_service.get_email_threads(db, thread_id)
        return {"threads": threads}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export")
async def export_emails(
    request: ExportRequest,
    db: Session = Depends(get_db)
):
    """Export emails in specified format"""
    try:
        if request.format not in ["json", "csv", "eml"]:
            raise HTTPException(status_code=400, detail="unsupported export format")
        
        export_data = email_service.export_emails(
            request.email_ids, db, request.format
        )
        
        if not export_data:
            raise HTTPException(status_code=404, detail="No emails found for export")
        
        from fastapi.responses import Response
        
        if request.format == "json":
            return Response(
                content=export_data,
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=emails.json"}
            )
        elif request.format == "csv":
            return Response(
                content=export_data,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=emails.csv"}
            )
        elif request.format == "eml":
            return Response(
                content=export_data,
                media_type="message/rfc822",
                headers={"Content-Disposition": "attachment; filename=emails.eml"}
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/clusters")
async def get_email_clusters(
    n_clusters: int = Query(5, ge=2, le=20),
    db: Session = Depends(get_db)
):
    """Get email clusters for analysis"""
    try:
        clusters = email_service.get_email_clusters(db, n_clusters)
        return clusters
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Quick search endpoints
@router.get("/quick/sender/{sender}")
async def search_by_sender(
    sender: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Quick search by sender"""
    try:
        result = email_service.search_emails(
            db=db,
            sender=sender,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quick/subject/{subject}")
async def search_by_subject(
    subject: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Quick search by subject"""
    try:
        result = email_service.search_emails(
            db=db,
            subject=subject,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quick/category/{category}")
async def search_by_category(
    category: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Quick search by category"""
    try:
        result = email_service.search_emails(
            db=db,
            category=category,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quick/unread")
async def get_unread_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get unread emails"""
    try:
        result = email_service.search_emails(
            db=db,
            is_read=False,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quick/starred")
async def get_starred_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get starred emails"""
    try:
        result = email_service.search_emails(
            db=db,
            is_starred=True,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quick/important")
async def get_important_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get important emails"""
    try:
        result = email_service.search_emails(
            db=db,
            is_important=True,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quick/attachments")
async def get_emails_with_attachments(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get emails with attachments"""
    try:
        result = email_service.search_emails(
            db=db,
            has_attachments=True,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
