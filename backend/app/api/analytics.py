from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from ..models.database import get_db
from ..services.email_service import EmailService
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter(tags=["analytics"])

# Pydantic models
class AnalyticsResponse(BaseModel):
    period_days: int
    total_emails: int
    read_emails: int
    unread_emails: int
    starred_emails: int
    important_emails: int
    category_distribution: Dict[str, int]
    sentiment_distribution: Dict[str, int]
    top_senders: List[Dict[str, Any]]

class EmailClusterResponse(BaseModel):
    clusters: List[List[Dict[str, Any]]]
    centroids: List[List[float]]

# Initialize service
email_service = EmailService()

@router.get("/overview", response_model=AnalyticsResponse)
async def get_email_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get email analytics overview for the specified period"""
    try:
        analytics = email_service.get_email_analytics(db, days)
        return AnalyticsResponse(**analytics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_email_statistics(db: Session = Depends(get_db)):
    """Get comprehensive email statistics"""
    try:
        stats = email_service.get_email_statistics(db)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/clusters", response_model=EmailClusterResponse)
async def get_email_clusters(
    n_clusters: int = Query(5, ge=2, le=20),
    db: Session = Depends(get_db)
):
    """Get email clusters for analysis"""
    try:
        clusters = email_service.get_email_clusters(db, n_clusters)
        return EmailClusterResponse(**clusters)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trends")
async def get_email_trends(
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db)
):
    """Get email trends over time"""
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get emails in date range
        from ..models.email import Email
        emails = db.query(Email).filter(
            Email.date_received >= start_date,
            Email.date_received <= end_date
        ).order_by(Email.date_received).all()
        
        # Group by date
        daily_stats = {}
        for email in emails:
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories")
async def get_category_analytics(db: Session = Depends(get_db)):
    """Get detailed category analytics"""
    try:
        from ..models.email import Email
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
                "category": cat or "other",
                "count": count,
                "avg_sentiment": float(avg_sentiment) if avg_sentiment else 0,
                "avg_priority": float(avg_priority) if avg_priority else 0
            })
        
        return {"categories": categories}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/senders")
async def get_sender_analytics(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get sender analytics"""
    try:
        from ..models.email import Email
        from sqlalchemy import func
        
        # Get top senders with stats
        sender_stats = db.query(
            Email.sender,
            func.count(Email.id).label('count'),
            func.avg(Email.sentiment_score).label('avg_sentiment'),
            func.avg(Email.priority_score).label('avg_priority'),
            func.sum(func.cast(Email.is_read, func.Integer)).label('read_count')
        ).group_by(Email.sender).order_by(
            func.count(Email.id).desc()
        ).limit(limit).all()
        
        senders = []
        for sender, count, avg_sentiment, avg_priority, read_count in sender_stats:
            if sender:  # Skip None senders
                senders.append({
                    "sender": sender,
                    "count": count,
                    "avg_sentiment": float(avg_sentiment) if avg_sentiment is not None else 0,
                    "avg_priority": float(avg_priority) if avg_priority is not None else 0,
                    "read_count": read_count or 0,
                    "unread_count": count - (read_count or 0),
                    "read_rate": (read_count / count * 100) if count > 0 else 0
                })
        
        return {"senders": senders}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sentiment")
async def get_sentiment_analytics(db: Session = Depends(get_db)):
    """Get sentiment analysis insights"""
    try:
        from ..models.email import Email
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/priority")
async def get_priority_analytics(db: Session = Depends(get_db)):
    """Get priority analysis insights"""
    try:
        from ..models.email import Email
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
            
            if priority >= 8:
                priority_data["high_priority"] += count
            elif priority >= 4:
                priority_data["medium_priority"] += count
            else:
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/activity")
async def get_activity_analytics(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """Get email activity patterns"""
    try:
        from ..models.email import Email
        from sqlalchemy import func, extract
        
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
        for i in range(7):
            daily_activity[i] = 0
        
        for email in emails:
            if email.date_received:
                day = email.date_received.weekday()
                daily_activity[day] += 1
        
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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
async def get_performance_metrics(db: Session = Depends(get_db)):
    """Get system performance metrics"""
    try:
        from ..models.email import Email, EmailAttachment
        from sqlalchemy import func
        
        # Get basic counts
        total_emails = db.query(Email).count()
        total_attachments = db.query(EmailAttachment).count()
        
        # Get storage usage
        attachment_sizes = db.query(
            func.sum(EmailAttachment.size).label('total_size')
        ).first()
        
        total_size_bytes = attachment_sizes[0] or 0
        total_size_mb = total_size_bytes / (1024 * 1024)
        
        # Get average email size
        avg_email_size = db.query(
            func.avg(func.length(Email.body_plain) + func.length(Email.body_html or ''))
        ).scalar() or 0
        
        # Get processing stats
        processed_emails = db.query(Email).filter(
            Email.sentiment_score.isnot(None)
        ).count()
        
        processing_rate = (processed_emails / total_emails * 100) if total_emails > 0 else 0
        
        return {
            "total_emails": total_emails,
            "total_attachments": total_attachments,
            "total_storage_mb": round(total_size_mb, 2),
            "avg_email_size_chars": round(avg_email_size, 0),
            "processed_emails": processed_emails,
            "processing_rate_percent": round(processing_rate, 2),
            "unprocessed_emails": total_emails - processed_emails
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/insights")
async def get_email_insights(db: Session = Depends(get_db)):
    """Get AI-generated insights about email patterns"""
    try:
        from ..models.email import Email
        from sqlalchemy import func
        
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
                    "severity": "info"
                })
        
        # Analyze unread email patterns
        unread_emails = [e for e in recent_emails if not e.is_read]
        if len(unread_emails) > len(recent_emails) * 0.3:
            insights.append({
                "type": "high_unread",
                "title": "High Unread Email Rate",
                "description": f"{len(unread_emails)} out of {len(recent_emails)} recent emails are unread",
                "severity": "warning"
            })
        
        # Analyze sentiment trends
        positive_emails = [e for e in recent_emails if e.sentiment_score == 1]
        negative_emails = [e for e in recent_emails if e.sentiment_score == -1]
        
        if len(negative_emails) > len(positive_emails):
            insights.append({
                "type": "negative_trend",
                "title": "Negative Sentiment Trend",
                "description": "More negative emails than positive emails in recent period",
                "severity": "warning"
            })
        
        # Analyze priority distribution
        high_priority = [e for e in recent_emails if e.priority_score and e.priority_score >= 8]
        if len(high_priority) > len(recent_emails) * 0.2:
            insights.append({
                "type": "high_priority",
                "title": "High Priority Email Volume",
                "description": f"{len(high_priority)} high priority emails detected",
                "severity": "info"
            })
        
        return {"insights": insights}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
