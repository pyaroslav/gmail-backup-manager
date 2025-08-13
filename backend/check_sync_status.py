#!/usr/bin/env python3
"""
Check sync status and display results
"""

import requests
import json
from datetime import datetime

def check_sync_status():
    """Check the current sync status and display results"""
    base_url = "http://127.0.0.1:8000"
    
    print("📊 Gmail Backup Manager - Sync Status Check")
    print("=" * 50)
    print(f"📅 Check time: {datetime.now()}")
    
    # Check sync progress
    try:
        response = requests.get(f"{base_url}/api/v1/sync/progress")
        if response.status_code == 200:
            progress = response.json()
            print(f"\n🔄 Sync Progress:")
            print(f"   Status: {progress['status']}")
            print(f"   Progress: {progress['progress']}%")
            print(f"   Current Operation: {progress['current_operation']}")
            print(f"   Emails Processed: {progress['emails_processed']}")
            print(f"   Total Emails: {progress['total_emails']}")
        else:
            print(f"❌ Failed to get sync progress: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting sync progress: {e}")
    
    # Check sync status
    try:
        response = requests.get(f"{base_url}/api/v1/sync/status")
        if response.status_code == 200:
            status = response.json()
            print(f"\n📈 Sync Status:")
            print(f"   Status: {status['status']}")
            print(f"   Error: {status['error']}")
            print(f"   Timestamp: {status['timestamp']}")
            print(f"   Emails Synced: {status['emails_synced']}")
            print(f"   Emails Analyzed: {status['emails_analyzed']}")
        else:
            print(f"❌ Failed to get sync status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting sync status: {e}")
    
    # Check Gmail connection
    try:
        response = requests.post(f"{base_url}/api/v1/sync/test-connection")
        if response.status_code == 200:
            connection = response.json()
            print(f"\n🔗 Gmail Connection:")
            print(f"   Success: {connection['success']}")
            print(f"   Message: {connection['message']}")
            print(f"   User Email: {connection['user_email']}")
        else:
            print(f"❌ Failed to test connection: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing connection: {e}")
    
    # Check sync settings
    try:
        response = requests.get(f"{base_url}/api/v1/sync/settings")
        if response.status_code == 200:
            settings = response.json()
            print(f"\n⚙️  Sync Settings:")
            for key, value in settings['settings'].items():
                print(f"   {key}: {value}")
        else:
            print(f"❌ Failed to get sync settings: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting sync settings: {e}")
    
    print(f"\n📅 Check completed at: {datetime.now()}")

if __name__ == "__main__":
    check_sync_status()
