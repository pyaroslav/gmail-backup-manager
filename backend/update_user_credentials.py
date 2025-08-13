#!/usr/bin/env python3
"""
Script to update test user with fresh Gmail credentials
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.database import Base
from app.models.user import User
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config.settings import settings

def update_user_credentials():
    """Update test user with fresh Gmail credentials"""
    print("Updating test user credentials...")
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Get the test user
        user = db.query(User).filter(User.email == "test@example.com").first()
        
        if not user:
            print("❌ Test user not found")
            return False
        
        print(f"📧 Found user: {user.email}")
        
        # Clear old tokens (they're expired)
        user.gmail_access_token = None
        user.gmail_refresh_token = None
        user.gmail_token_expiry = None
        
        # Update user settings
        user.sync_enabled = True
        user.is_active = True
        
        db.commit()
        print("✅ User credentials cleared successfully")
        print("ℹ️  Note: You'll need to authenticate with Gmail on first sync")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating user: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    update_user_credentials()
