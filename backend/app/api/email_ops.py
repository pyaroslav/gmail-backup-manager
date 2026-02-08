from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from ..models.database import get_db
from ..models.email import Email, EmailLabel
from pydantic import BaseModel
import logging
import json
import signal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["email_ops"])

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
