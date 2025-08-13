#!/usr/bin/env python3
"""
Gmail Authentication Script
This script helps you authenticate with Gmail and get access tokens
"""

import os
import sys
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.user import User
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config.settings import settings

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

def create_credentials_file():
    """Create a credentials.json file from environment variables"""
    client_id = settings.GMAIL_CLIENT_ID
    client_secret = settings.GMAIL_CLIENT_SECRET
    
    if not client_id or not client_secret:
        print("❌ Gmail credentials not found in environment variables")
        print("Please make sure GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET are set in your .env file")
        return False
    
    credentials_data = {
        "installed": {
            "client_id": client_id,
            "project_id": "gmail-backup-manager",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"]
        }
    }
    
    with open('credentials.json', 'w') as f:
        json.dump(credentials_data, f, indent=2)
    
    print("✅ Created credentials.json file")
    return True

def authenticate_gmail():
    """Authenticate with Gmail and get tokens"""
    print("🔐 Starting Gmail Authentication Process")
    print("=" * 50)
    
    # Create credentials file
    if not create_credentials_file():
        return None
    
    creds = None
    
    # Check if we have valid credentials
    if os.path.exists('token.json'):
        print("📄 Found existing token.json, checking if valid...")
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"❌ Failed to refresh token: {e}")
                creds = None
        
        if not creds:
            print("🔑 Starting OAuth2 authentication flow...")
            print("📱 A browser window will open for you to authenticate with Google")
            print("📋 Please follow the authentication steps in your browser")
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
                
                print("✅ Authentication successful! Token saved to token.json")
                
            except Exception as e:
                print(f"❌ Authentication failed: {e}")
                return None
    
    return creds

def update_user_tokens(creds):
    """Update the user in the database with the new tokens"""
    print("\n💾 Updating user tokens in database...")
    
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
        
        # Update user with new tokens
        user.gmail_access_token = creds.token
        user.gmail_refresh_token = creds.refresh_token
        user.gmail_token_expiry = creds.expiry
        
        db.commit()
        print(f"✅ Updated user {user.email} with new Gmail tokens")
        return True
        
    except Exception as e:
        print(f"❌ Error updating user: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def test_gmail_access(creds):
    """Test if we can access Gmail with the new tokens"""
    print("\n🧪 Testing Gmail access...")
    
    try:
        from googleapiclient.discovery import build
        
        service = build('gmail', 'v1', credentials=creds)
        
        # Try to get user profile
        profile = service.users().getProfile(userId='me').execute()
        email = profile['emailAddress']
        
        print(f"✅ Successfully authenticated as: {email}")
        
        # Try to get a few emails
        results = service.users().messages().list(userId='me', maxResults=5).execute()
        messages = results.get('messages', [])
        
        print(f"✅ Successfully accessed Gmail - found {len(messages)} recent messages")
        return True
        
    except Exception as e:
        print(f"❌ Gmail access test failed: {e}")
        return False

def main():
    """Main authentication process"""
    print("🚀 Gmail Authentication Setup")
    print("=" * 50)
    
    # Step 1: Authenticate with Gmail
    creds = authenticate_gmail()
    if not creds:
        print("❌ Authentication failed")
        return
    
    # Step 2: Test Gmail access
    if not test_gmail_access(creds):
        print("❌ Gmail access test failed")
        return
    
    # Step 3: Update user in database
    if not update_user_tokens(creds):
        print("❌ Failed to update user tokens")
        return
    
    print("\n🎉 Gmail Authentication Complete!")
    print("=" * 50)
    print("✅ You can now start syncing your emails")
    print("📧 Run: curl -X POST http://127.0.0.1:8000/api/v1/sync/start")
    print("📊 Check status: curl http://127.0.0.1:8000/api/v1/sync/status")

if __name__ == "__main__":
    main()
