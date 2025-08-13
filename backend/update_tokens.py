#!/usr/bin/env python3
"""
Script to update user tokens with the new ones from the OAuth flow
"""

import os
import sys
import json
from datetime import datetime, timezone

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.database import get_db
from app.models.user import User

def update_user_tokens():
    """Update user tokens with the new ones from token.json"""
    
    print("🔄 Updating user tokens...")
    
    # Check if token.json exists
    token_file = "token.json"
    if not os.path.exists(token_file):
        print(f"❌ Token file not found: {token_file}")
        return False
    
    try:
        # Read the token file
        with open(token_file, 'r') as f:
            token_data = json.load(f)
        
        print("📁 Token file loaded successfully")
        
        # Extract token information
        access_token = token_data.get('token')
        refresh_token = token_data.get('refresh_token')
        
        if not access_token:
            print("❌ No access token found in token file")
            return False
        
        print("🔑 Access token found")
        if refresh_token:
            print("🔄 Refresh token found")
        else:
            print("⚠️  No refresh token found")
        
        # Get database session
        db = next(get_db())
        
        try:
            # Get user from database
            user = db.query(User).filter(User.id == 1).first()
            if not user:
                print("❌ User not found in database")
                return False
            
            print(f"👤 Updating tokens for user: {user.email}")
            
            # Update user tokens
            user.gmail_access_token = access_token
            if refresh_token:
                user.gmail_refresh_token = refresh_token
            
            # Set expiry to a reasonable time (1 hour from now)
            user.gmail_token_expiry = datetime.now(timezone.utc)
            
            db.commit()
            
            print("✅ User tokens updated successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error updating user tokens: {e}")
            db.rollback()
            return False
        
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Error reading token file: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Token Update Script")
    print("=" * 50)
    
    if update_user_tokens():
        print("\n🎉 Tokens updated successfully!")
        print("\n📋 Next steps:")
        print("1. Test the Gmail connection")
        print("2. Run the sync validation script")
        print("3. Start a full sync to download all emails")
    else:
        print("\n❌ Failed to update tokens")
        sys.exit(1)
