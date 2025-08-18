#!/usr/bin/env python3
"""
Script to automatically update sync progress by monitoring backend logs
"""

import time
import subprocess
import re
import psycopg2
from datetime import datetime

# Database connection parameters
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'gmail_backup',
    'user': 'gmail_user',
    'password': 'gmail_password'
}

def get_latest_sync_progress():
    """Get the latest sync progress from backend logs"""
    try:
        # Get the last log line from the backend container
        result = subprocess.run([
            'docker', 'logs', 'gmail-backup-backend', '--tail', '1'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            log_line = result.stdout.strip()
            
            # Look for progress pattern: "Progress: X emails synced"
            progress_match = re.search(r'Progress: (\d+) emails synced', log_line)
            if progress_match:
                return int(progress_match.group(1))
            
            # Look for batch processing pattern: "total synced: X"
            batch_match = re.search(r'total synced: (\d+)', log_line)
            if batch_match:
                return int(batch_match.group(1))
        
        return None
    except Exception as e:
        print(f"Error getting sync progress: {e}")
        return None

def update_sync_session_progress(emails_synced):
    """Update the sync session with the latest progress"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Update the active sync session
        cursor.execute("""
            UPDATE sync_sessions 
            SET emails_synced = %s, emails_processed = %s, updated_at = NOW()
            WHERE status = 'started' OR status = 'running'
            ORDER BY id DESC 
            LIMIT 1
        """, (emails_synced, emails_synced))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"Updated sync progress to {emails_synced} emails at {datetime.now()}")
        return True
        
    except Exception as e:
        print(f"Error updating sync progress: {e}")
        return False

def main():
    """Main function to monitor and update sync progress"""
    print("Starting sync progress monitor...")
    last_progress = None
    
    while True:
        try:
            # Get current progress from logs
            current_progress = get_latest_sync_progress()
            
            if current_progress is not None and current_progress != last_progress:
                # Update database if progress has changed
                if update_sync_session_progress(current_progress):
                    last_progress = current_progress
            
            # Wait 5 seconds before next check
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\nStopping sync progress monitor...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
