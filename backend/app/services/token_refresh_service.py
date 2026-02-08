"""
Proactive Token Refresh Service
Automatically refreshes Gmail OAuth tokens before they expire
"""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
import os

from ..models.database import SessionLocal
from ..models.user import User

logger = logging.getLogger(__name__)

class TokenRefreshService:
    """
    Service to proactively refresh OAuth tokens before they expire
    """
    
    def __init__(self):
        self.is_running = False
        self.check_interval = 900  # Check every 15 minutes
        self.refresh_threshold = 600  # Refresh if expiring in next 10 minutes
        
    async def start_token_refresh_service(self):
        """
        Start the background token refresh service
        """
        if self.is_running:
            logger.warning("Token refresh service is already running")
            return
        
        self.is_running = True
        logger.info("Starting token refresh service (checks every 15 minutes)")

        while self.is_running:
            try:
                await self._check_and_refresh_tokens()
            except asyncio.CancelledError:
                logger.info("Token refresh service cancelled")
                self.is_running = False
                raise
            except Exception as e:
                logger.error(f"Token refresh service error (will retry next cycle): {e}")
                await asyncio.sleep(30)
                continue
            await asyncio.sleep(self.check_interval)
    
    def stop_token_refresh_service(self):
        """Stop the token refresh service"""
        logger.info("Stopping token refresh service")
        self.is_running = False
    
    async def _check_and_refresh_tokens(self):
        """
        Check all users and refresh tokens if needed
        """
        db = SessionLocal()
        try:
            users = db.query(User).filter(User.gmail_access_token.isnot(None)).all()
            
            for user in users:
                try:
                    await self._refresh_user_token_if_needed(user, db)
                except Exception as e:
                    logger.error(f"Error refreshing token for {user.email}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in token refresh cycle: {e}")
        finally:
            db.close()
    
    async def _refresh_user_token_if_needed(self, user: User, db: Session):
        """
        Check if user's token needs refresh and refresh it
        """
        # Check if token will expire soon
        if not user.gmail_token_expiry:
            logger.debug(f"No expiry set for {user.email}, skipping proactive refresh")
            return
        
        now = datetime.now(timezone.utc)
        time_until_expiry = user.gmail_token_expiry - now
        
        # If token expires in less than refresh_threshold seconds, refresh it
        if time_until_expiry.total_seconds() < self.refresh_threshold:
            logger.info(f"⏰ Token expiring soon for {user.email} (in {time_until_expiry.total_seconds():.0f}s), refreshing...")
            
            try:
                # Create credentials object
                creds = Credentials(
                    token=user.gmail_access_token,
                    refresh_token=user.gmail_refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.getenv("GMAIL_CLIENT_ID"),
                    client_secret=os.getenv("GMAIL_CLIENT_SECRET")
                )
                
                # Refresh the token
                creds.refresh(Request())
                
                # Update database with new tokens
                user.gmail_access_token = creds.token
                if creds.refresh_token:  # Refresh token might not change
                    user.gmail_refresh_token = creds.refresh_token
                user.gmail_token_expiry = creds.expiry
                
                db.commit()
                
                logger.info(f"✅ Token refreshed successfully for {user.email}")
                logger.info(f"   New expiry: {creds.expiry}")
                
            except RefreshError as e:
                logger.error(f"❌ Token refresh failed for {user.email}: {e}")
                logger.error(f"   Token may have been revoked")
                logger.error(f"   ⚠️ MANUAL RE-AUTHENTICATION REQUIRED!")
                logger.error(f"   Run: cd backend && python gmail_auth.py")
                
                # Don't raise - allow other users to be processed
                
            except Exception as e:
                logger.error(f"❌ Unexpected error refreshing token for {user.email}: {e}")
        else:
            logger.debug(f"Token for {user.email} still valid for {time_until_expiry.total_seconds()/3600:.1f}h")
    
    def refresh_user_token_now(self, user: User, db: Session) -> bool:
        """
        Immediately refresh a user's token (synchronous)
        """
        try:
            logger.info(f"🔄 Force-refreshing token for {user.email}...")
            
            creds = Credentials(
                token=user.gmail_access_token,
                refresh_token=user.gmail_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GMAIL_CLIENT_ID"),
                client_secret=os.getenv("GMAIL_CLIENT_SECRET")
            )
            
            creds.refresh(Request())
            
            # Update database
            user.gmail_access_token = creds.token
            if creds.refresh_token:
                user.gmail_refresh_token = creds.refresh_token
            user.gmail_token_expiry = creds.expiry
            
            db.commit()
            
            logger.info(f"✅ Token refreshed for {user.email}")
            return True
            
        except RefreshError as e:
            logger.error(f"❌ Token refresh failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False

# Global instance
token_refresh_service = TokenRefreshService()

