#!/usr/bin/env python3
"""
Simple Gmail Authentication Script
This script provides a simpler approach to Gmail authentication with better error handling
"""

import os
import sys
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
load_dotenv()

# Gmail API scopes (minimal for testing)
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly'
]

def check_credentials():
    """Check if we have valid credentials"""
    print("🔍 Checking for existing credentials...")
    
    if os.path.exists('token.json'):
        print("✅ Found token.json")
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            if creds and creds.valid:
                print("✅ Existing token is valid")
                return creds
            elif creds and creds.expired and creds.refresh_token:
                print("🔄 Token expired, attempting to refresh...")
                try:
                    creds.refresh(Request())
                    print("✅ Token refreshed successfully")
                    return creds
                except Exception as e:
                    print(f"❌ Failed to refresh token: {e}")
        except Exception as e:
            print(f"❌ Error reading token.json: {e}")
    
    return None

def create_credentials_file():
    """Create credentials.json from environment variables"""
    print("📝 Creating credentials file...")
    
    # Try to get credentials from environment
    client_id = os.getenv('GMAIL_CLIENT_ID')
    client_secret = os.getenv('GMAIL_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("❌ Gmail credentials not found in environment")
        print("Please set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in your .env file")
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
    
    print("✅ Created credentials.json")
    return True

def authenticate_gmail():
    """Authenticate with Gmail"""
    print("\n🔐 Starting Gmail Authentication")
    print("=" * 50)
    
    # Check existing credentials
    creds = check_credentials()
    if creds:
        return creds
    
    # Create credentials file
    if not create_credentials_file():
        return None
    
    print("\n📋 IMPORTANT: Before proceeding, please ensure:")
    print("1. You've added your email as a test user in Google Cloud Console")
    print("2. Your Gmail API project is in 'Testing' mode")
    print("3. You're using the correct Gmail account")
    
    input("\nPress Enter to continue with authentication...")
    
    try:
        print("\n🔑 Starting OAuth2 flow...")
        print("📱 A browser window will open for authentication")
        print("⚠️  If you get an 'access_denied' error, you need to add your email as a test user")
        
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Save credentials
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        
        print("✅ Authentication successful!")
        return creds
        
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        
        if "access_denied" in str(e).lower():
            print("\n🔧 SOLUTION: You need to add your email as a test user")
            print("1. Go to https://console.cloud.google.com/")
            print("2. Select your project")
            print("3. Go to APIs & Services > OAuth consent screen")
            print("4. Add your email to 'Test users'")
            print("5. Try again")
        
        return None

def test_gmail_access(creds):
    """Test Gmail access"""
    print("\n🧪 Testing Gmail access...")
    
    try:
        from googleapiclient.discovery import build
        
        service = build('gmail', 'v1', credentials=creds)
        
        # Get user profile
        profile = service.users().getProfile(userId='me').execute()
        email = profile['emailAddress']
        
        print(f"✅ Authenticated as: {email}")
        
        # Try to get messages
        results = service.users().messages().list(userId='me', maxResults=3).execute()
        messages = results.get('messages', [])
        
        print(f"✅ Successfully accessed Gmail - found {len(messages)} recent messages")
        return True, email
        
    except Exception as e:
        print(f"❌ Gmail access test failed: {e}")
        return False, None

def main():
    """Main function"""
    print("🚀 Simple Gmail Authentication")
    print("=" * 50)
    
    # Authenticate
    creds = authenticate_gmail()
    if not creds:
        print("\n❌ Authentication failed. Please check the error messages above.")
        return
    
    # Test access
    success, email = test_gmail_access(creds)
    if not success:
        print("\n❌ Gmail access test failed.")
        return
    
    print(f"\n🎉 SUCCESS! You're authenticated as: {email}")
    print("=" * 50)
    print("✅ You can now use the Gmail backup manager")
    print("📧 Run: curl -X POST http://127.0.0.1:8000/api/v1/sync/start")
    print("📊 Check status: curl http://127.0.0.1:8000/api/v1/sync/status")

if __name__ == "__main__":
    main()
