from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..models.database import get_db
from ..models.email import Email
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(tags=["test_analytics"])


@router.get("/analytics/overview")
async def get_test_analytics_overview(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get test analytics overview (no authentication required)"""
    try:
        from sqlalchemy import func
        from datetime import datetime, timedelta

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get emails in date range
        emails_in_period = db.query(Email).filter(
            Email.date_received >= start_date,
            Email.date_received <= end_date
        ).count()

        # Get total emails
        total_emails = db.query(Email).count()

        # Get read/unread counts
        read_emails = db.query(Email).filter(Email.is_read == True).count()
        unread_emails = db.query(Email).filter(Email.is_read == False).count()

        # Get starred/important counts
        starred_emails = db.query(Email).filter(Email.is_starred == True).count()
        important_emails = db.query(Email).filter(Email.is_important == True).count()

        # Get category distribution
        category_stats = db.query(
            Email.category,
            func.count(Email.id).label('count')
        ).group_by(Email.category).all()

        category_distribution = {}
        for category, count in category_stats:
            cat_name = category or "uncategorized"
            category_distribution[cat_name] = count

        # Get sentiment distribution
        sentiment_stats = db.query(
            Email.sentiment_score,
            func.count(Email.id).label('count')
        ).group_by(Email.sentiment_score).all()

        sentiment_distribution = {"positive": 0, "neutral": 0, "negative": 0}
        for sentiment, count in sentiment_stats:
            if sentiment == 1:
                sentiment_distribution["positive"] = count
            elif sentiment == -1:
                sentiment_distribution["negative"] = count
            else:
                sentiment_distribution["neutral"] = count

        # Get top senders
        sender_stats = db.query(
            Email.sender,
            func.count(Email.id).label('count')
        ).group_by(Email.sender).order_by(
            func.count(Email.id).desc()
        ).limit(10).all()

        top_senders = []
        for sender, count in sender_stats:
            if sender:  # Skip None senders
                top_senders.append({
                    "sender": sender,
                    "count": count
                })

        return {
            "period_days": days,
            "total_emails": total_emails,
            "emails_in_period": emails_in_period,
            "read_emails": read_emails,
            "unread_emails": unread_emails,
            "starred_emails": starred_emails,
            "important_emails": important_emails,
            "category_distribution": category_distribution,
            "sentiment_distribution": sentiment_distribution,
            "top_senders": top_senders
        }

    except Exception as e:
        logger.error(f"Error getting test analytics overview: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/statistics")
async def get_test_statistics(db: Session = Depends(get_db)):
    """Get comprehensive test statistics (no authentication required)"""
    try:
        from sqlalchemy import func
        from datetime import datetime, timedelta

        # Basic counts
        total_emails = db.query(Email).count()
        read_emails = db.query(Email).filter(Email.is_read == True).count()
        unread_emails = db.query(Email).filter(Email.is_read == False).count()
        starred_emails = db.query(Email).filter(Email.is_starred == True).count()
        important_emails = db.query(Email).filter(Email.is_important == True).count()

        # Date range analysis
        oldest_email = db.query(Email.date_received).order_by(Email.date_received.asc()).first()
        newest_email = db.query(Email.date_received).order_by(Email.date_received.desc()).first()

        # Yearly breakdown
        yearly_counts = db.query(
            func.extract('year', Email.date_received).label('year'),
            func.count(Email.id).label('count')
        ).filter(
            Email.date_received.isnot(None)
        ).group_by(
            func.extract('year', Email.date_received)
        ).order_by(
            func.extract('year', Email.date_received)
        ).all()

        # Monthly breakdown (last 12 months)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)

        monthly_counts = db.query(
            func.extract('year', Email.date_received).label('year'),
            func.extract('month', Email.date_received).label('month'),
            func.count(Email.id).label('count')
        ).filter(
            Email.date_received >= start_date,
            Email.date_received <= end_date
        ).group_by(
            func.extract('year', Email.date_received),
            func.extract('month', Email.date_received)
        ).order_by(
            func.extract('year', Email.date_received),
            func.extract('month', Email.date_received)
        ).all()

        # Sender analysis
        unique_senders = db.query(func.count(func.distinct(Email.sender))).scalar()
        top_senders = db.query(
            Email.sender,
            func.count(Email.id).label('count')
        ).group_by(Email.sender).order_by(
            func.count(Email.id).desc()
        ).limit(20).all()

        # Category analysis
        categories = db.query(
            Email.category,
            func.count(Email.id).label('count')
        ).group_by(Email.category).order_by(
            func.count(Email.id).desc()
        ).all()

        # Sentiment analysis
        sentiment_breakdown = db.query(
            Email.sentiment_score,
            func.count(Email.id).label('count')
        ).group_by(Email.sentiment_score).all()

        # Priority analysis
        priority_breakdown = db.query(
            Email.priority_score,
            func.count(Email.id).label('count')
        ).group_by(Email.priority_score).order_by(Email.priority_score).all()

        return {
            "total_emails": total_emails,
            "read_emails": read_emails,
            "unread_emails": unread_emails,
            "starred_emails": starred_emails,
            "important_emails": important_emails,
            "read_rate": (read_emails / total_emails * 100) if total_emails > 0 else 0,
            "date_range": {
                "oldest_email": oldest_email[0].isoformat() if oldest_email and oldest_email[0] else None,
                "newest_email": newest_email[0].isoformat() if newest_email and newest_email[0] else None
            },
            "yearly_breakdown": [
                {"year": int(year), "count": count}
                for year, count in yearly_counts
            ],
            "monthly_breakdown": [
                {"year": int(year), "month": int(month), "count": count}
                for year, month, count in monthly_counts
            ],
            "sender_analysis": {
                "unique_senders": unique_senders,
                "top_senders": [
                    {"sender": sender, "count": count}
                    for sender, count in top_senders if sender
                ]
            },
            "categories": [
                {"category": category or "uncategorized", "count": count}
                for category, count in categories
            ],
            "sentiment_breakdown": [
                {"sentiment": sentiment, "count": count}
                for sentiment, count in sentiment_breakdown
            ],
            "priority_breakdown": [
                {"priority": priority, "count": count}
                for priority, count in priority_breakdown
            ]
        }

    except Exception as e:
        logger.error(f"Error getting test statistics: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/trends")
async def get_test_trends(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get email trends over time (no authentication required)"""
    try:
        from datetime import datetime, timedelta

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get emails in date range
        emails = db.query(Email).filter(
            Email.date_received >= start_date,
            Email.date_received <= end_date
        ).order_by(Email.date_received).all()

        # Group by date
        daily_stats = {}
        for email in emails:
            if email.date_received:
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
        logger.error(f"Error getting test trends: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/activity")
async def get_test_activity(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Get email activity patterns (no authentication required)"""
    try:
        from datetime import datetime, timedelta

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
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for i in range(7):
            daily_activity[day_names[i]] = 0

        for email in emails:
            if email.date_received:
                day = email.date_received.weekday()
                daily_activity[day_names[day]] += 1

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
        logger.error(f"Error getting test activity: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/performance")
async def get_test_performance(db: Session = Depends(get_db)):
    """Get system performance metrics (no authentication required)"""
    try:
        from sqlalchemy import func

        # Get basic counts
        total_emails = db.query(Email).count()

        # Get emails with sentiment analysis
        processed_emails = db.query(Email).filter(
            Email.sentiment_score.isnot(None)
        ).count()

        # Get emails with priority scores
        priority_processed = db.query(Email).filter(
            Email.priority_score.isnot(None)
        ).count()

        # Get emails with categories
        categorized_emails = db.query(Email).filter(
            Email.category.isnot(None)
        ).count()

        # Calculate processing rates
        sentiment_rate = (processed_emails / total_emails * 100) if total_emails > 0 else 0
        priority_rate = (priority_processed / total_emails * 100) if total_emails > 0 else 0
        categorization_rate = (categorized_emails / total_emails * 100) if total_emails > 0 else 0

        # Get average email size (character count)
        avg_email_size = db.query(
            func.avg(func.length(Email.body_plain) + func.length(Email.body_html or ''))
        ).scalar() or 0

        # Get emails by year for storage estimation
        yearly_counts = db.query(
            func.extract('year', Email.date_received).label('year'),
            func.count(Email.id).label('count')
        ).filter(
            Email.date_received.isnot(None)
        ).group_by(
            func.extract('year', Email.date_received)
        ).order_by(
            func.extract('year', Email.date_received)
        ).all()

        return {
            "total_emails": total_emails,
            "processed_emails": {
                "sentiment_analysis": processed_emails,
                "priority_scoring": priority_processed,
                "categorization": categorized_emails
            },
            "processing_rates": {
                "sentiment_analysis": round(sentiment_rate, 2),
                "priority_scoring": round(priority_rate, 2),
                "categorization": round(categorization_rate, 2)
            },
            "avg_email_size_chars": round(avg_email_size, 0),
            "yearly_distribution": [
                {"year": int(year), "count": count}
                for year, count in yearly_counts
            ]
        }

    except Exception as e:
        logger.error(f"Error getting test performance: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/insights")
async def get_test_insights(db: Session = Depends(get_db)):
    """Get AI-generated insights about email patterns (no authentication required)"""
    try:
        from datetime import datetime, timedelta

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
                    "severity": "info",
                    "icon": "\U0001f4c8"
                })

        # Analyze unread email patterns
        unread_emails = [e for e in recent_emails if not e.is_read]
        unread_percentage = (len(unread_emails) / len(recent_emails)) * 100
        if unread_percentage > 30:
            insights.append({
                "type": "high_unread",
                "title": "High Unread Email Rate",
                "description": f"{unread_percentage:.1f}% of recent emails are unread ({len(unread_emails)} emails)",
                "severity": "warning",
                "icon": "\U0001f4ec"
            })

        # Analyze sender patterns
        sender_counts = {}
        for email in recent_emails:
            sender = email.sender.split('<')[0].strip() if email.sender else "Unknown"
            sender_counts[sender] = sender_counts.get(sender, 0) + 1

        top_sender = max(sender_counts.items(), key=lambda x: x[1])
        if top_sender[1] > len(recent_emails) * 0.3:
            insights.append({
                "type": "dominant_sender",
                "title": "Dominant Sender",
                "description": f"{top_sender[0]} accounts for {round((top_sender[1]/len(recent_emails))*100)}% of recent emails",
                "severity": "info",
                "icon": "\U0001f464"
            })

        # Analyze time patterns
        hourly_counts = {}
        for email in recent_emails:
            if email.date_received:
                hour = email.date_received.hour
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1

        if hourly_counts:
            peak_hour = max(hourly_counts.items(), key=lambda x: x[1])
            insights.append({
                "type": "peak_activity",
                "title": "Peak Email Activity",
                "description": f"Most emails arrive at {peak_hour[0]}:00 ({peak_hour[1]} emails in recent period)",
                "severity": "info",
                "icon": "\u23f0"
            })

        # Analyze important emails
        important_emails = [e for e in recent_emails if e.is_important]
        if important_emails:
            important_percentage = (len(important_emails) / len(recent_emails)) * 100
            insights.append({
                "type": "important_emails",
                "title": "Important Email Volume",
                "description": f"{important_percentage:.1f}% of recent emails are marked as important",
                "severity": "info",
                "icon": "\u2b50"
            })

        # Analyze date range
        if recent_emails:
            oldest_recent = min(e.date_received for e in recent_emails if e.date_received)
            newest_recent = max(e.date_received for e in recent_emails if e.date_received)
            if oldest_recent and newest_recent:
                days_span = (newest_recent - oldest_recent).days
                insights.append({
                    "type": "date_span",
                    "title": "Email Time Span",
                    "description": f"Recent emails span {days_span} days ({oldest_recent.strftime('%Y-%m-%d')} to {newest_recent.strftime('%Y-%m-%d')})",
                    "severity": "info",
                    "icon": "\U0001f4c5"
                })

        return {"insights": insights}

    except Exception as e:
        logger.error(f"Error getting test insights: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/domains")
async def get_test_domain_analysis(db: Session = Depends(get_db)):
    """Get domain analysis for emails (no authentication required)"""
    try:
        from sqlalchemy import func
        import re

        # Get all senders
        senders = db.query(Email.sender).filter(Email.sender.isnot(None)).all()

        # Extract domains
        domain_counts = {}
        domain_emails = {}

        for (sender,) in senders:
            # Extract domain from email address
            domain_match = re.search(r'@([^>]+)', sender)
            if domain_match:
                domain = domain_match.group(1).lower()
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

                if domain not in domain_emails:
                    domain_emails[domain] = []
                domain_emails[domain].append(sender)

        # Get top domains
        top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:20]

        # Analyze domain types
        domain_types = {
            "social_media": ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "facebook.com", "twitter.com"],
            "shopping": ["amazon.com", "ebay.com", "etsy.com", "shopify.com", "walmart.com", "target.com"],
            "finance": ["chase.com", "bankofamerica.com", "wellsfargo.com", "capitalone.com", "usbank.com"],
            "news": ["cnn.com", "bbc.com", "nytimes.com", "washingtonpost.com", "reuters.com"],
            "tech": ["google.com", "microsoft.com", "apple.com", "github.com", "stackoverflow.com"]
        }

        domain_categories = {}
        for domain, count in domain_counts.items():
            category = "other"
            for cat, domains in domain_types.items():
                if any(d in domain for d in domains):
                    category = cat
                    break
            domain_categories[category] = domain_categories.get(category, 0) + count

        # Get domain statistics
        domain_stats = []
        for domain, count in top_domains:
            # Get read rate for this domain
            domain_emails_list = domain_emails[domain]
            read_count = db.query(Email).filter(
                Email.sender.in_(domain_emails_list),
                Email.is_read == True
            ).count()
            read_rate = (read_count / count * 100) if count > 0 else 0

            domain_stats.append({
                "domain": domain,
                "count": count,
                "read_rate": round(read_rate, 1),
                "percentage": round((count / sum(domain_counts.values())) * 100, 1)
            })

        return {
            "total_domains": len(domain_counts),
            "top_domains": domain_stats,
            "domain_categories": [
                {"category": cat, "count": count}
                for cat, count in domain_categories.items()
            ]
        }

    except Exception as e:
        logger.error(f"Error getting test domain analysis: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/trends-detailed")
async def get_test_detailed_trends(
    days: int = 90,
    db: Session = Depends(get_db)
):
    """Get detailed email trends analysis (no authentication required)"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get emails in date range
        emails = db.query(Email).filter(
            Email.date_received >= start_date,
            Email.date_received <= end_date
        ).order_by(Email.date_received).all()

        # Weekly trends
        weekly_stats = {}
        for email in emails:
            if email.date_received:
                week_start = email.date_received - timedelta(days=email.date_received.weekday())
                week_key = week_start.strftime('%Y-%W')

                if week_key not in weekly_stats:
                    weekly_stats[week_key] = {
                        "week_start": week_start,
                        "total": 0,
                        "read": 0,
                        "unread": 0,
                        "important": 0,
                        "starred": 0
                    }

                weekly_stats[week_key]["total"] += 1
                if email.is_read:
                    weekly_stats[week_key]["read"] += 1
                else:
                    weekly_stats[week_key]["unread"] += 1

                if email.is_important:
                    weekly_stats[week_key]["important"] += 1

                if email.is_starred:
                    weekly_stats[week_key]["starred"] += 1

        # Convert to list and sort
        weekly_trends = []
        for week_key, stats in sorted(weekly_stats.items()):
            weekly_trends.append({
                "week": week_key,
                "week_start": stats["week_start"].strftime('%Y-%m-%d'),
                **stats
            })

        # Monthly trends
        monthly_stats = {}
        for email in emails:
            if email.date_received:
                month_key = email.date_received.strftime('%Y-%m')

                if month_key not in monthly_stats:
                    monthly_stats[month_key] = {
                        "total": 0,
                        "read": 0,
                        "unread": 0,
                        "important": 0,
                        "starred": 0
                    }

                monthly_stats[month_key]["total"] += 1
                if email.is_read:
                    monthly_stats[month_key]["read"] += 1
                else:
                    monthly_stats[month_key]["unread"] += 1

                if email.is_important:
                    monthly_stats[month_key]["important"] += 1

                if email.is_starred:
                    monthly_stats[month_key]["starred"] += 1

        # Convert to list and sort
        monthly_trends = []
        for month_key, stats in sorted(monthly_stats.items()):
            monthly_trends.append({
                "month": month_key,
                **stats
            })

        # Calculate growth rates
        if len(weekly_trends) >= 2:
            recent_week = weekly_trends[-1]["total"]
            previous_week = weekly_trends[-2]["total"]
            weekly_growth = ((recent_week - previous_week) / previous_week * 100) if previous_week > 0 else 0
        else:
            weekly_growth = 0

        if len(monthly_trends) >= 2:
            recent_month = monthly_trends[-1]["total"]
            previous_month = monthly_trends[-2]["total"]
            monthly_growth = ((recent_month - previous_month) / previous_month * 100) if previous_month > 0 else 0
        else:
            monthly_growth = 0

        return {
            "period_days": days,
            "total_emails_in_period": len(emails),
            "weekly_trends": weekly_trends,
            "monthly_trends": monthly_trends,
            "growth_rates": {
                "weekly_growth": round(weekly_growth, 1),
                "monthly_growth": round(monthly_growth, 1)
            }
        }

    except Exception as e:
        logger.error(f"Error getting test detailed trends: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/categories")
async def get_test_categories(db: Session = Depends(get_db)):
    """Get email categories analytics (no authentication required)"""
    try:
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
                "category": cat or "uncategorized",
                "count": count,
                "avg_sentiment": float(avg_sentiment) if avg_sentiment else 0,
                "avg_priority": float(avg_priority) if avg_priority else 0
            })

        return {"categories": categories}

    except Exception as e:
        logger.error(f"Error getting test categories: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/senders")
async def get_test_senders(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get sender analytics (no authentication required)"""
    try:
        from sqlalchemy import func

        # Get top senders with basic stats
        sender_stats = db.query(
            Email.sender,
            func.count(Email.id).label('count')
        ).group_by(Email.sender).order_by(
            func.count(Email.id).desc()
        ).limit(limit).all()

        senders = []
        for sender, count in sender_stats:
            if sender and sender.strip():  # Skip None and empty senders
                # Get read count for this sender
                read_count = db.query(Email).filter(
                    Email.sender == sender,
                    Email.is_read == True
                ).count()

                senders.append({
                    "sender": sender,
                    "count": count,
                    "avg_sentiment": 0,  # Placeholder
                    "avg_priority": 0,   # Placeholder
                    "read_count": read_count,
                    "unread_count": count - read_count,
                    "read_rate": (read_count / count * 100) if count > 0 else 0
                })

        return {"senders": senders}

    except Exception as e:
        logger.error(f"Error getting test senders: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/sentiment")
async def get_test_sentiment(db: Session = Depends(get_db)):
    """Get sentiment analysis insights (no authentication required)"""
    try:
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
        logger.error(f"Error getting test sentiment: {e}")
        return {
            "error": str(e),
            "status": "error"
        }


@router.get("/analytics/priority")
async def get_test_priority(db: Session = Depends(get_db)):
    """Get priority analysis insights (no authentication required)"""
    try:
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

            if priority is not None:
                if priority >= 8:
                    priority_data["high_priority"] += count
                elif priority >= 4:
                    priority_data["medium_priority"] += count
                else:
                    priority_data["low_priority"] += count
            else:
                # Handle emails without priority scores
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
        logger.error(f"Error getting test priority: {e}")
        return {
            "error": str(e),
            "status": "error"
        }
