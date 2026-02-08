"""
Authentication service for the Gmail Backup Manager
"""

import os
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..models.database import get_db
from ..models.user import User
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()

# ---------------------------------------------------------------------------
# Simple API-key authentication for local deployment
# ---------------------------------------------------------------------------

_API_KEY: str = os.getenv("API_KEY", "")


def verify_api_key(x_api_key: str = Header(default="")) -> str:
    """FastAPI dependency that checks the X-API-Key header.

    When API_KEY is not configured (empty string) authentication is
    disabled so the app works out of the box for local development.
    """
    if not _API_KEY:
        # No key configured – auth disabled
        return ""
    if x_api_key != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key

# For testing purposes - create a test user
def create_test_user(db: Session):
    """Create a test user for development/testing"""
    try:
        # Check if test user already exists
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            test_user = User(
                email="test@example.com",
                gmail_id="test_gmail_id",
                access_token="test_access_token",
                refresh_token="test_refresh_token",
                token_expires_at=None
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            logger.info("Test user created successfully")
        return test_user
    except Exception as e:
        logger.error(f"Error creating test user: {e}")
        db.rollback()
        return None

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    try:
        token = credentials.credentials
        
        # For testing purposes, accept a simple test token
        if token == "test_token":
            # Return test user
            test_user = create_test_user(db)
            if test_user:
                return test_user
        
        # Try to find user by token (in a real app, you'd validate JWT)
        user = db.query(User).filter(User.access_token == token).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current user (optional - for endpoints that can work without auth)"""
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        # Return None if authentication fails
        return None

# For development/testing - bypass authentication
def get_test_user(db: Session = Depends(get_db)) -> User:
    """Get test user for development (bypasses authentication)"""
    return create_test_user(db)
