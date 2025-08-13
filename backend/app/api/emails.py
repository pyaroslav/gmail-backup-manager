from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from ..models.database import get_db
from ..models.user import User
from ..services.auth_service import get_current_user
from ..models.email import Email, EmailAttachment
from ..services.email_service import EmailService
from pydantic import BaseModel, field_validator
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(tags=["emails"])

# Pydantic models for request/response
class EmailResponse(BaseModel):
    id: int
    gmail_id: str
    thread_id: Optional[str]
    subject: Optional[str]
    sender: Optional[str]
    recipients: Optional[List[str]]
    cc: Optional[List[str]]
    bcc: Optional[List[str]]
    body_plain: Optional[str]
    body_html: Optional[str]
    date_received: Optional[datetime]
    date_sent: Optional[datetime]
    is_read: bool
    is_starred: bool
    is_important: bool
    is_spam: bool
    is_trash: bool
    labels: Optional[List[str]]
    sentiment_score: Optional[float]
    category: Optional[str]
    priority_score: Optional[float]
    summary: Optional[str]
    
    @field_validator('recipients', 'cc', 'bcc', 'labels', mode='before')
    @classmethod
    def parse_json_string(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(v, list):
            return v
        return []

    class Config:
        from_attributes = True

class EmailAttachmentResponse(BaseModel):
    id: int
    filename: Optional[str]
    content_type: Optional[str]
    size: Optional[int]
    is_inline: bool
    
    class Config:
        from_attributes = True

class EmailDetailResponse(EmailResponse):
    attachments: List[EmailAttachmentResponse]

# Initialize service
email_service = EmailService()

# Create a response model for paginated emails
class PaginatedEmailsResponse(BaseModel):
    emails: List[EmailResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int

@router.get("/")
async def get_emails(
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),  # Default to 20, max 100
    db: Session = Depends(get_db)
):
    """Get paginated list of emails"""
    try:
        from ..services.email_service import EmailService
        email_service = EmailService()
        result = email_service.search_emails(
            db=db,
            page=page,
            page_size=page_size
        )
        
        # Return the full result structure expected by frontend
        if result and isinstance(result, dict):
            return result
        else:
            return {
                "emails": [],
                "total_count": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }
            
    except Exception as e:
        logger.error(f"Error getting emails: {e}")
        return {
            "emails": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0
        }

@router.get("/{email_id}", response_model=EmailDetailResponse)
async def get_email(
    email_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get email by ID with attachments"""
    try:
        from ..services.email_service import EmailService
        email_service = EmailService()
        email = email_service.get_email_by_id(email_id, db)
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
            
        return email
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email {email_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{email_id}/attachments", response_model=List[EmailAttachmentResponse])
async def get_email_attachments(
    email_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get attachments for a specific email"""
    try:
        from ..services.email_service import EmailService
        email_service = EmailService()
        attachments = email_service.get_email_attachments(email_id, db)
        return attachments
    except Exception as e:
        logger.error(f"Error getting attachments for email {email_id}: {e}")
        return []

@router.get("/{email_id}/attachment/{attachment_id}")
async def download_attachment(email_id: int, attachment_id: int, db: Session = Depends(get_db)):
    """Download attachment file"""
    try:
        attachment_data = email_service.download_attachment(attachment_id, db)
        if not attachment_data:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        from fastapi.responses import Response
        return Response(
            content=attachment_data["data"],
            media_type=attachment_data["content_type"],
            headers={"Content-Disposition": f"attachment; filename={attachment_data['filename']}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{email_id}/thread", response_model=List[EmailResponse])
async def get_email_thread(email_id: int, db: Session = Depends(get_db)):
    """Get all emails in a thread"""
    try:
        email = email_service.get_email_by_id(email_id, db)
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        if not email.thread_id:
            return [email]
        
        thread_emails = email_service.get_email_thread(email.thread_id, db)
        return thread_emails
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{email_id}/similar", response_model=List[EmailResponse])
async def get_similar_emails(
    email_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get similar emails using AI analysis"""
    try:
        similar_emails = email_service.get_similar_emails(email_id, db, limit)
        return similar_emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{email_id}/summary")
async def get_email_summary(email_id: int, db: Session = Depends(get_db)):
    """Get AI-generated summary of email"""
    try:
        summary = email_service.get_email_summary(email_id, db)
        if not summary:
            raise HTTPException(status_code=404, detail="Email not found or summary not available")
        return {"summary": summary}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Email actions
@router.patch("/{email_id}/read")
async def mark_as_read(email_id: int, db: Session = Depends(get_db)):
    """Mark email as read"""
    try:
        success = email_service.mark_email_as_read(email_id, db)
        if not success:
            raise HTTPException(status_code=404, detail="Email not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{email_id}/unread")
async def mark_as_unread(email_id: int, db: Session = Depends(get_db)):
    """Mark email as unread"""
    try:
        success = email_service.mark_email_as_unread(email_id, db)
        if not success:
            raise HTTPException(status_code=404, detail="Email not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{email_id}/star")
async def toggle_star(email_id: int, db: Session = Depends(get_db)):
    """Toggle star status of email"""
    try:
        success = email_service.star_email(email_id, db)
        if not success:
            raise HTTPException(status_code=404, detail="Email not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{email_id}/important")
async def toggle_important(email_id: int, db: Session = Depends(get_db)):
    """Toggle important status of email"""
    try:
        success = email_service.mark_as_important(email_id, db)
        if not success:
            raise HTTPException(status_code=404, detail="Email not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{email_id}")
async def delete_email(email_id: int, db: Session = Depends(get_db)):
    """Delete email from database"""
    try:
        success = email_service.delete_email(email_id, db)
        if not success:
            raise HTTPException(status_code=404, detail="Email not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Bulk operations
class BulkUpdateRequest(BaseModel):
    email_ids: List[int]
    is_read: Optional[bool] = None
    is_starred: Optional[bool] = None
    is_important: Optional[bool] = None

@router.patch("/bulk/update")
async def bulk_update_emails(
    request: BulkUpdateRequest,
    db: Session = Depends(get_db)
):
    """Bulk update multiple emails"""
    try:
        updates = {}
        if request.is_read is not None:
            updates["is_read"] = request.is_read
        if request.is_starred is not None:
            updates["is_starred"] = request.is_starred
        if request.is_important is not None:
            updates["is_important"] = request.is_important
        
        updated_count = email_service.bulk_update_emails(request.email_ids, db, **updates)
        return {"success": True, "updated_count": updated_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BulkDeleteRequest(BaseModel):
    email_ids: List[int]

@router.delete("/bulk/delete")
async def bulk_delete_emails(
    email_ids: str = Query(..., description="Comma-separated list of email IDs"),
    db: Session = Depends(get_db)
):
    """Bulk delete multiple emails"""
    try:
        # Parse email IDs from query parameter
        try:
            email_id_list = [int(id.strip()) for id in email_ids.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid email IDs format")
        
        deleted_count = 0
        for email_id in email_id_list:
            if email_service.delete_email(email_id, db):
                deleted_count += 1
        
        return {"success": True, "deleted_count": deleted_count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
