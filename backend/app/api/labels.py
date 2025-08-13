from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..models.database import get_db
from ..models.user import User
from ..services.auth_service import get_current_user
from ..models.email import EmailLabel, Email
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["labels"])

class LabelResponse(BaseModel):
    id: int
    gmail_label_id: str
    name: str
    label_type: str
    color: dict
    email_count: int = 0

@router.get("/", response_model=List[LabelResponse])
async def get_labels(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all available email labels"""
    try:
        # Get all labels
        labels = db.query(EmailLabel).all()
        
        # For each label, count emails that have this label
        label_responses = []
        for label in labels:
            # Count emails with this label
            email_count = db.query(Email).filter(
                Email.labels.contains([label.name])
            ).count()
            
            label_responses.append(LabelResponse(
                id=label.id,
                gmail_label_id=label.gmail_label_id,
                name=label.name,
                label_type=label.label_type,
                color=label.color or {},
                email_count=email_count
            ))
        
        return label_responses
    except Exception as e:
        logger.error(f"Error getting labels: {e}")
        return []

@router.get("/{label_name}/emails")
async def get_emails_by_label(
    label_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get emails by label name"""
    try:
        from ..services.email_service import EmailService
        email_service = EmailService()
        
        # Get emails that contain this label
        result = email_service.search_emails(
            db=db,
            labels=[label_name],
            page=1,
            page_size=50
        )
        
        return result
    except Exception as e:
        logger.error(f"Error getting emails for label {label_name}: {e}")
        return {"emails": [], "total_count": 0, "page": 1, "page_size": 50, "total_pages": 0}
