#!/usr/bin/env python3
"""
Update user with new Gmail authentication tokens
"""

import os
import sys
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from google.oauth2.credentials import Credentials

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.user import User
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config.settings import settings

def update_user_with_tokens():
    """Update the user in database with new Gmail tokens"""
    print("💾 Updating user with new Gmail tokens...")
    
    # Check if token.json exists
    if not os.path.exists('token.json'):
        print("❌ token.json not found. Please run authentication first.")
        return False
    
    try:
        # Load credentials from token.json
        with open('token.json', 'r') as f:
            token_data = json.load(f)
        
        # Create engine
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Get the test user
        user = db.query(User).filter(User.email == "test@example.com").first()
        
        if not user:
            print("❌ Test user not found")
            return False
        
        # Update user with new tokens
        user.gmail_access_token = token_data.get('token')
        user.gmail_refresh_token = token_data.get('refresh_token')
        
        # Convert expiry timestamp
        if token_data.get('expiry'):
            from datetime import datetime
            expiry = datetime.fromisoformat(token_data['expiry'].replace('Z', '+00:00'))
            user.gmail_token_expiry = expiry
        
        # Update email to match authenticated account
        user.email = "yaroslavp2010@gmail.com"
        
        db.commit()
        print(f"✅ Updated user {user.email} with new Gmail tokens")
        print(f"📧 Email: {user.email}")
        print(f"🔑 Access token: {'✅ Set' if user.gmail_access_token else '❌ Missing'}")
        print(f"🔄 Refresh token: {'✅ Set' if user.gmail_refresh_token else '❌ Missing'}")
        print(f"⏰ Token expiry: {user.gmail_token_expiry}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating user: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    update_user_with_tokens()
