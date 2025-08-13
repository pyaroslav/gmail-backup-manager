#!/usr/bin/env python3
"""
Script to fix Gmail API scope issues by updating stored tokens
"""

import os
import sys
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.database import get_db
from app.models.user import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

def fix_gmail_scopes():
    """Fix Gmail API scope issues by re-authenticating with correct scopes"""
    
    print("🔧 Fixing Gmail API Scope Issues...")
    print("=" * 50)
    
    # Get database session
    db = next(get_db())
    
    try:
        # Get user from database
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            print("❌ User not found in database")
            return False
        
        print(f"👤 User: {user.email}")
        
        # Check if credentials file exists
        credentials_path = "credentials.json"
        if not os.path.exists(credentials_path):
            print(f"❌ Credentials file not found: {credentials_path}")
            return False
        
        print("📁 Credentials file found")
        
        # Create OAuth flow with correct scopes
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_path, 
            SCOPES
        )
        
        print("🔄 Starting OAuth flow...")
        print("📋 Requested scopes:")
        for scope in SCOPES:
            print(f"   - {scope}")
        
        # Run the OAuth flow
        creds = flow.run_local_server(port=0)
        
        print("✅ OAuth flow completed successfully")
        
        # Test the new credentials
        print("\n🧪 Testing new credentials...")
        service = build('gmail', 'v1', credentials=creds)
        
        # Test basic API call
        try:
            profile = service.users().getProfile(userId='me').execute()
            print(f"✅ Profile test passed: {profile['emailAddress']}")
        except HttpError as error:
            print(f"❌ Profile test failed: {error}")
            return False
        
        # Test labels API call
        try:
            labels = service.users().labels().list(userId='me').execute()
            label_count = len(labels.get('labels', []))
            print(f"✅ Labels test passed: {label_count} labels found")
        except HttpError as error:
            print(f"❌ Labels test failed: {error}")
            return False
        
        # Test messages API call
        try:
            messages = service.users().messages().list(userId='me', maxResults=1).execute()
            message_count = messages.get('resultSizeEstimate', 0)
            print(f"✅ Messages test passed: {message_count} messages estimated")
        except HttpError as error:
            print(f"❌ Messages test failed: {error}")
            return False
        
        # Update user tokens in database
        print("\n💾 Updating tokens in database...")
        user.gmail_access_token = creds.token
        user.gmail_refresh_token = creds.refresh_token
        user.gmail_token_expiry = creds.expiry
        db.commit()
        
        print("✅ Tokens updated successfully")
        print(f"🔑 New token expiry: {creds.expiry}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing Gmail scopes: {e}")
        return False
    
    finally:
        db.close()

def test_fixed_credentials():
    """Test the fixed credentials"""
    
    print("\n🧪 Testing Fixed Credentials...")
    print("=" * 50)
    
    # Get database session
    db = next(get_db())
    
    try:
        # Get user from database
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            print("❌ User not found in database")
            return False
        
        # Create credentials from updated tokens
        creds = Credentials(
            token=user.gmail_access_token,
            refresh_token=user.gmail_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GMAIL_CLIENT_ID"),
            client_secret=os.getenv("GMAIL_CLIENT_SECRET"),
            scopes=SCOPES
        )
        
        # Build Gmail service
        service = build('gmail', 'v1', credentials=creds)
        
        # Test all API endpoints
        tests = [
            ("Profile", lambda: service.users().getProfile(userId='me').execute()),
            ("Labels", lambda: service.users().labels().list(userId='me').execute()),
            ("Messages", lambda: service.users().messages().list(userId='me', maxResults=1).execute()),
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            try:
                result = test_func()
                if test_name == "Profile":
                    print(f"✅ {test_name}: {result['emailAddress']}")
                elif test_name == "Labels":
                    print(f"✅ {test_name}: {len(result.get('labels', []))} labels")
                elif test_name == "Messages":
                    print(f"✅ {test_name}: {result.get('resultSizeEstimate', 0)} messages")
            except HttpError as error:
                print(f"❌ {test_name}: {error}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Error testing fixed credentials: {e}")
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Gmail Scope Fix Script")
    print("=" * 50)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Fix the scopes
    if fix_gmail_scopes():
        print("\n🎉 Gmail scopes fixed successfully!")
        
        # Test the fixed credentials
        if test_fixed_credentials():
            print("\n🎉 All tests passed! Gmail API is now working correctly.")
            print("\n📋 Next steps:")
            print("1. Run the sync validation script: ./test_sync_validation.sh")
            print("2. Start a full sync to download all emails")
            print("3. Monitor the sync progress in the web interface")
        else:
            print("\n❌ Some tests failed. Please check the error messages above.")
    else:
        print("\n❌ Failed to fix Gmail scopes. Please check the error messages above.")
        sys.exit(1)
