import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import func

from ..models.database import SessionLocal
from ..models.user import User
from ..models.email import Email

logger = logging.getLogger(__name__)

class BackgroundSyncService:
    """
    Background service for continuous email synchronization
    """
    
    def __init__(self):
        self.is_running = False
        self.sync_interval = 300  # 5 minutes default
        self.last_sync_time = None
        self.sync_in_progress = False  # Lock to prevent overlapping syncs
        self.sync_stats = {
            "total_syncs": 0,
            "total_emails_synced": 0,
            "last_sync_duration": 0,
            "last_sync_time": None,
            "errors": 0,
            "start_time": None,
            "sync_in_progress": False
        }
    
    async def start_background_sync(self, sync_interval_minutes: int = 5):
        """
        Start the background sync service
        """
        if self.is_running:
            logger.warning("Background sync is already running")
            return
        
        self.sync_interval = sync_interval_minutes * 60  # Convert to seconds
        self.is_running = True
        self.sync_stats["start_time"] = datetime.now(timezone.utc)
        
        logger.info(f"Starting background sync service (interval: {sync_interval_minutes} minutes)")
        
        try:
            while self.is_running:
                # Check if a sync is already in progress
                if not self.sync_in_progress:
                    await self._perform_sync_cycle()
                else:
                    logger.info("Previous sync still in progress, skipping this cycle")
                
                await asyncio.sleep(self.sync_interval)
        except Exception as e:
            logger.error(f"Background sync service error: {e}")
            self.is_running = False
            raise
    
    def stop_background_sync(self):
        """
        Stop the background sync service
        """
        logger.info("Stopping background sync service")
        self.is_running = False
    
    async def _perform_sync_cycle(self):
        """
        Perform a single sync cycle
        """
        # Check if sync is already in progress
        if self.sync_in_progress:
            logger.warning("Sync already in progress, skipping this cycle")
            return
        
        # Set sync lock
        self.sync_in_progress = True
        self.sync_stats["sync_in_progress"] = True
        
        start_time = time.time()
        logger.info("Starting sync cycle...")
        
        try:
            # Get users that need syncing
            db = SessionLocal()
            try:
                users = db.query(User).filter(User.gmail_access_token.isnot(None)).all()
            except Exception as db_error:
                logger.error(f"Database error fetching users: {db_error}")
                db.rollback()
                return
            
            if not users:
                logger.info("No users found for syncing")
                return
            
            for user in users:
                try:
                    # Check if user needs syncing (last sync > 10 minutes ago or never synced)
                    current_time = datetime.now(timezone.utc)
                    time_since_last_sync = current_time - user.last_sync if user.last_sync else timedelta(hours=999)
                    needs_sync = (
                        user.last_sync is None or 
                        time_since_last_sync > timedelta(minutes=10)
                    )
                    
                    logger.info(f"User {user.email}: last_sync={user.last_sync}, current_time={current_time}, time_since_last_sync={time_since_last_sync}, needs_sync={needs_sync}")
                    
                    if needs_sync:
                        logger.info(f"Syncing user: {user.email}")
                        
                        # Use the API endpoint to trigger sync with timeout
                        import aiohttp
                        timeout = aiohttp.ClientTimeout(total=1800)  # 30 minutes timeout
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            async with session.post(
                                f"http://localhost:8000/api/v1/test/sync/start",
                                json={"max_emails": 1000}
                            ) as response:
                                result = await response.json()
                                
                                if result.get("status") == "completed":
                                    self.sync_stats["total_syncs"] += 1
                                    emails_synced = result.get("result", {}).get("emails_synced", 0)
                                    self.sync_stats["total_emails_synced"] += emails_synced
                                    logger.info(f"Sync completed for {user.email}: {emails_synced} emails")
                                    
                                    # Update user's last_sync time to prevent immediate re-sync
                                    try:
                                        user.last_sync = datetime.now(timezone.utc)
                                        db.commit()
                                        logger.info(f"Updated last_sync for {user.email} to {user.last_sync}")
                                    except Exception as db_error:
                                        logger.error(f"Database error updating last_sync for {user.email}: {db_error}")
                                        db.rollback()
                                        # Try to refresh the session
                                        try:
                                            db.refresh(user)
                                        except:
                                            pass
                                else:
                                    self.sync_stats["errors"] += 1
                                    logger.error(f"Sync failed for {user.email}: {result.get('error', 'Unknown error')}")
                    else:
                        logger.info(f"User {user.email} doesn't need syncing (last sync: {user.last_sync})")
                        
                except asyncio.TimeoutError:
                    self.sync_stats["errors"] += 1
                    logger.error(f"Sync timeout for user {user.email}")
                    continue
                except Exception as e:
                    self.sync_stats["errors"] += 1
                    logger.error(f"Error syncing user {user.email}: {e}")
                    logger.error(f"Error type: {type(e).__name__}")
                    logger.error(f"Error details: {str(e)}")
                    continue
            
            # Update sync stats
            sync_duration = time.time() - start_time
            self.sync_stats["last_sync_duration"] = sync_duration
            self.sync_stats["last_sync_time"] = datetime.now(timezone.utc)
            self.last_sync_time = datetime.now(timezone.utc)
            
            logger.info(f"Sync cycle completed in {sync_duration:.2f}s")
            
        except Exception as e:
            self.sync_stats["errors"] += 1
            logger.error(f"Error in sync cycle: {e}")
        finally:
            # Release sync lock
            self.sync_in_progress = False
            self.sync_stats["sync_in_progress"] = False
            db.close()
    
    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current background sync status
        """
        logger.info(f"Getting sync status: is_running={self.is_running}, sync_in_progress={self.sync_in_progress}, last_sync_time={self.last_sync_time}")
        
        # Ensure proper serialization
        last_sync_time_str = None
        if self.last_sync_time:
            if hasattr(self.last_sync_time, 'isoformat'):
                last_sync_time_str = self.last_sync_time.isoformat()
            else:
                last_sync_time_str = str(self.last_sync_time)
        
        return {
            "is_running": bool(self.is_running),
            "sync_interval_seconds": int(self.sync_interval),
            "last_sync_time": last_sync_time_str,
            "sync_in_progress": bool(self.sync_in_progress),
            "stats": self.sync_stats.copy()
        }
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics
        """
        db = SessionLocal()
        try:
            total_emails = db.query(Email).count()
            total_users = db.query(User).count()
            
            # Get emails by year
            yearly_stats = db.query(
                func.extract('year', Email.date_received).label('year'),
                func.count(Email.id).label('count')
            ).group_by('year').order_by('year').all()
            
            # Get recent activity
            recent_emails = db.query(Email).order_by(Email.date_received.desc()).limit(10).all()
            
            return {
                "total_emails": total_emails,
                "total_users": total_users,
                "yearly_breakdown": [
                    {"year": int(stat.year), "count": stat.count} 
                    for stat in yearly_stats
                ],
                "recent_emails": [
                    {
                        "id": email.id,
                        "subject": email.subject,
                        "sender": email.sender,
                        "date_received": email.date_received.isoformat() if email.date_received else None
                    }
                    for email in recent_emails
                ]
            }
        finally:
            db.close()

# Global instance
background_sync_service = BackgroundSyncService()
