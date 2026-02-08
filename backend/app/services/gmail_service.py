import os
import base64
import email
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..models.email import Email, EmailAttachment, EmailLabel
from ..models.user import User
from ..models.database import SessionLocal
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

class GmailService:
    def __init__(self, credentials_path: str = "config/credentials.json"):
        self.credentials_path = credentials_path
        self.service = None
        self._lock = threading.Lock()
        
    def authenticate_user(self, user: User) -> bool:
        """Authenticate user with Gmail API using stored tokens"""
        try:
            from google.auth.exceptions import RefreshError
            
            # Google's Credentials internally compares expiry against a
            # naive UTC datetime, so strip tzinfo to avoid
            # "can't compare offset-naive and offset-aware datetimes".
            token_expiry = user.gmail_token_expiry
            if token_expiry is not None and token_expiry.tzinfo is not None:
                token_expiry = token_expiry.replace(tzinfo=None)

            creds = Credentials(
                token=user.gmail_access_token,
                refresh_token=user.gmail_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GMAIL_CLIENT_ID"),
                client_secret=os.getenv("GMAIL_CLIENT_SECRET"),
                scopes=SCOPES,
                expiry=token_expiry
            )
            
            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                try:
                    logger.info(f"Token expired for {user.email}, attempting refresh...")
                    creds.refresh(Request())
                    
                    # Update user tokens in database
                    user.gmail_access_token = creds.token
                    if creds.refresh_token:  # Refresh token might not change
                        user.gmail_refresh_token = creds.refresh_token
                    user.gmail_token_expiry = creds.expiry
                    
                    # Save to database immediately using a new session
                    from ..models.database import SessionLocal
                    db = SessionLocal()
                    try:
                        db_user = db.query(User).filter(User.id == user.id).first()
                        if db_user:
                            db_user.gmail_access_token = creds.token
                            if creds.refresh_token:
                                db_user.gmail_refresh_token = creds.refresh_token
                            db_user.gmail_token_expiry = creds.expiry
                            db.commit()
                            logger.info(f"Token refreshed and saved to database for {user.email}")
                            logger.info(f"   New expiry: {creds.expiry}")
                    finally:
                        db.close()
                        
                except RefreshError as refresh_error:
                    logger.error(f"Token refresh failed for {user.email}: {refresh_error}")
                    logger.error("MANUAL RE-AUTHENTICATION REQUIRED!")
                    logger.error(f"   Run: cd backend && python gmail_auth.py")
                    return False
                
            self.service = build('gmail', 'v1', credentials=creds)
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed for {user.email}: {e}")
            if "invalid_grant" in str(e).lower() or "revoked" in str(e).lower():
                logger.error("Token has been revoked or expired!")
                logger.error("MANUAL RE-AUTHENTICATION REQUIRED!")
                logger.error(f"   Run: cd backend && python gmail_auth.py")
            return False
    
    def get_all_labels(self, user: User) -> List[Dict[str, Any]]:
        """Get all Gmail labels for the user"""
        if not self.authenticate_user(user):
            raise Exception("Failed to authenticate with Gmail")
        
        try:
            labels = []
            page_token = None
            
            while True:
                # Build the request
                request = self.service.users().labels().list(userId='me')
                if page_token:
                    request = request.pageToken(page_token)
                
                results = request.execute()
                
                labels.extend(results.get('labels', []))
                page_token = results.get('nextPageToken')
                
                if not page_token:
                    break
            
            logger.info(f"Retrieved {len(labels)} labels from Gmail")
            return labels
            
        except HttpError as error:
            logger.error(f"Error fetching labels: {error}")
            raise
    
    def sync_labels_to_database(self, user: User, db: Session) -> int:
        """Sync Gmail labels to local database"""
        try:
            gmail_labels = self.get_all_labels(user)
            synced_count = 0
            
            for label_data in gmail_labels:
                label_id = label_data['id']
                
                # Check if label already exists
                existing_label = db.query(EmailLabel).filter(
                    EmailLabel.gmail_label_id == label_id
                ).first()
                
                if existing_label:
                    # Update existing label
                    existing_label.name = label_data['name']
                    existing_label.label_type = label_data.get('type', 'user')
                    existing_label.color = label_data.get('backgroundColor', {})
                else:
                    # Create new label
                    new_label = EmailLabel(
                        gmail_label_id=label_id,
                        name=label_data['name'],
                        label_type=label_data.get('type', 'user'),
                        color=label_data.get('backgroundColor', {})
                    )
                    db.add(new_label)
                
                synced_count += 1
            
            db.commit()
            logger.info(f"Synced {synced_count} labels to database")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing labels: {e}")
            db.rollback()
            raise
    
    def get_all_emails(self, user: User, db: Session, max_results: int = None) -> List[Email]:
        """Get all emails from Gmail with optimized batch processing"""
        if not self.authenticate_user(user):
            raise Exception("Failed to authenticate with Gmail")
            
        emails = []
        page_token = None
        total_processed = 0
        api_batch_size = 500  # Increased batch size for better performance
        
        try:
            # First, sync all labels
            logger.info("Starting label synchronization...")
            self.sync_labels_to_database(user, db)
            
            logger.info("Starting email synchronization...")
            
            # Use a query to get emails from 2011 onwards to ensure we get all history
            # Gmail API query format: after:YYYY/MM/DD
            query = "after:2011/01/01"
            
            while True:
                # Get email list with optimized batch size
                batch_size = min(api_batch_size, max_results - total_processed) if max_results else api_batch_size
                
                # Build the request with explicit date range
                request_params = {
                    'userId': 'me', 
                    'maxResults': batch_size,
                    'q': query
                }
                
                if page_token:
                    request_params['pageToken'] = page_token
                
                request = self.service.users().messages().list(**request_params)
                results = request.execute()
                
                messages = results.get('messages', [])
                if not messages:
                    break
                
                logger.info(f"Processing batch of {len(messages)} emails (total processed: {total_processed})")
                
                # Process emails in parallel for better performance
                with ThreadPoolExecutor(max_workers=10) as executor:
                    # Submit all email processing tasks
                    future_to_message = {
                        executor.submit(self._fetch_email_details_optimized, message['id']): message['id']
                        for message in messages
                    }
                    
                    # Collect results as they complete
                    for future in as_completed(future_to_message):
                        message_id = future_to_message[future]
                        try:
                            email_obj = future.result()
                            if email_obj:
                                emails.append(email_obj)
                                total_processed += 1
                                
                                # Log progress every 100 emails
                                if total_processed % 100 == 0:
                                    logger.info(f"Progress: {total_processed} emails processed")
                                    
                        except Exception as e:
                            logger.error(f"Error processing email {message_id}: {e}")
                            continue
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                
                # Check if we've reached the max_results limit
                if max_results and total_processed >= max_results:
                    break
                    
        except HttpError as error:
            logger.error(f"Error fetching emails: {error}")
            raise
            
        logger.info(f"Successfully synced {len(emails)} emails")
        return emails
    
    def _fetch_email_details_optimized(self, message_id: str) -> Optional[Email]:
        """Fetch detailed email information with optimized database operations"""
        db = SessionLocal()
        try:
            # Check if email already exists using raw SQL for better performance
            existing_email = db.query(Email).filter(Email.gmail_id == message_id).first()
            if existing_email:
                return existing_email
            
            # Get full message with retry logic
            message = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    message = self.service.users().messages().get(
                        userId='me',
                        id=message_id,
                        format='full'
                    ).execute()
                    break
                except HttpError as e:
                    if e.resp.status == 500 and attempt < max_retries - 1:
                        logger.warning(f"Gmail API error for {message_id}, retrying... (attempt {attempt + 1})")
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        raise
            
            if not message:
                return None
            
            # Parse email headers
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            # Parse recipients
            to_emails = self._parse_email_list(
                next((h['value'] for h in headers if h['name'] == 'To'), '')
            )
            cc_emails = self._parse_email_list(
                next((h['value'] for h in headers if h['name'] == 'Cc'), '')
            )
            bcc_emails = self._parse_email_list(
                next((h['value'] for h in headers if h['name'] == 'Bcc'), '')
            )
            
            # Parse date
            date_received = self._parse_date(date_str)
            
            # Extract body and attachments with BLOB storage
            body_plain, body_html, attachments = self._extract_content_optimized(message['payload'], message_id)
            
            # Get label IDs and names
            label_ids = message.get('labelIds', [])
            
            # Create email object
            email_obj = Email(
                gmail_id=message_id,
                thread_id=message.get('threadId'),
                subject=subject,
                sender=sender,
                recipients=to_emails,
                cc=cc_emails,
                bcc=bcc_emails,
                body_plain=body_plain,
                body_html=body_html,
                date_received=date_received,
                labels=label_ids,  # Store all label IDs
                is_read='UNREAD' not in label_ids,
                is_starred='STARRED' in label_ids,
                is_important='IMPORTANT' in label_ids,
                is_spam='SPAM' in label_ids,
                is_trash='TRASH' in label_ids
            )
            
            # Save to database
            db.add(email_obj)
            db.commit()
            db.refresh(email_obj)
            
            # Save attachments as BLOBs
            for attachment_data in attachments:
                attachment = EmailAttachment(
                    email_id=email_obj.id,
                    filename=attachment_data['filename'],
                    content_type=attachment_data['content_type'],
                    size=attachment_data['size'],
                    content_id=attachment_data.get('content_id'),
                    file_data=attachment_data['file_data'],  # Store as BLOB
                    file_path=attachment_data.get('file_path'),  # Keep for backward compatibility
                    is_inline=attachment_data.get('is_inline', False),
                    checksum=attachment_data.get('checksum')
                )
                db.add(attachment)
            
            db.commit()
            return email_obj
            
        except Exception as e:
            logger.error(f"Error fetching email {message_id}: {e}")
            db.rollback()
            return None
        finally:
            db.close()
    
    def get_emails_by_label(self, user: User, db: Session, label_id: str, max_results: int = None) -> List[Email]:
        """Get emails for a specific label"""
        if not self.authenticate_user(user):
            raise Exception("Failed to authenticate with Gmail")
            
        emails = []
        page_token = None
        total_processed = 0
        
        try:
            while True:
                batch_size = min(500, max_results - total_processed) if max_results else 500
                
                # Build the request
                request = self.service.users().messages().list(
                    userId='me',
                    labelIds=[label_id],
                    maxResults=batch_size
                )
                if page_token:
                    request = request.pageToken(page_token)
                
                results = request.execute()
                
                messages = results.get('messages', [])
                if not messages:
                    break
                
                logger.info(f"Processing {len(messages)} emails for label {label_id}")
                
                for message in messages:
                    email_obj = self._fetch_email_details(message['id'], db)
                    if email_obj:
                        emails.append(email_obj)
                        total_processed += 1
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                
                if max_results and total_processed >= max_results:
                    break
                    
        except HttpError as error:
            logger.error(f"Error fetching emails for label {label_id}: {error}")
            raise
            
        return emails
    
    def _fetch_email_details(self, message_id: str, db: Session) -> Optional[Email]:
        """Fetch detailed email information"""
        try:
            # Check if email already exists
            existing_email = db.query(Email).filter(Email.gmail_id == message_id).first()
            if existing_email:
                return existing_email
            
            # Get full message
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Parse email headers
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            # Parse recipients
            to_emails = self._parse_email_list(
                next((h['value'] for h in headers if h['name'] == 'To'), '')
            )
            cc_emails = self._parse_email_list(
                next((h['value'] for h in headers if h['name'] == 'Cc'), '')
            )
            bcc_emails = self._parse_email_list(
                next((h['value'] for h in headers if h['name'] == 'Bcc'), '')
            )
            
            # Parse date
            date_received = self._parse_date(date_str)
            
            # Extract body and attachments
            body_plain, body_html, attachments = self._extract_content(message['payload'], message_id)
            
            # Get label IDs and names
            label_ids = message.get('labelIds', [])
            
            # Create email object
            email_obj = Email(
                gmail_id=message_id,
                thread_id=message.get('threadId'),
                subject=subject,
                sender=sender,
                recipients=to_emails,
                cc=cc_emails,
                bcc=bcc_emails,
                body_plain=body_plain,
                body_html=body_html,
                date_received=date_received,
                labels=label_ids,  # Store all label IDs
                is_read='UNREAD' not in label_ids,
                is_starred='STARRED' in label_ids,
                is_important='IMPORTANT' in label_ids,
                is_spam='SPAM' in label_ids,
                is_trash='TRASH' in label_ids
            )
            
            # Add to database (don't commit yet - will be committed in batch)
            db.add(email_obj)
            db.flush()  # Flush to get the ID without committing
            
            # Save attachments
            for attachment_data in attachments:
                attachment = EmailAttachment(
                    email_id=email_obj.id,
                    filename=attachment_data['filename'],
                    content_type=attachment_data['content_type'],
                    size=attachment_data['size'],
                    content_id=attachment_data.get('content_id'),
                    file_path=attachment_data['file_path'],
                    is_inline=attachment_data.get('is_inline', False)
                )
                db.add(attachment)
            
            return email_obj
            
        except Exception as e:
            logger.error(f"Error fetching email {message_id}: {e}")
            return None
    
    def _parse_email_list(self, email_string: str) -> List[str]:
        """Parse email list from header value"""
        if not email_string:
            return []
        
        emails = []
        # Simple parsing - can be enhanced
        for email_part in email_string.split(','):
            email_part = email_part.strip()
            if '<' in email_part and '>' in email_part:
                # Extract email from "Name <email@domain.com>" format
                start = email_part.find('<') + 1
                end = email_part.find('>')
                emails.append(email_part[start:end])
            elif '@' in email_part:
                emails.append(email_part)
        
        return emails
    
    def _parse_date(self, date_string: str) -> Optional[datetime]:
        """Parse email date string"""
        if not date_string:
            return None
        
        try:
            # Try to parse the date string
            parsed_date = email.utils.parsedate_to_datetime(date_string)
            return parsed_date
        except Exception as e:
            logger.warning(f"Could not parse date '{date_string}': {e}")
            return None
    
    def _extract_content_optimized(self, payload: Dict, message_id: str) -> tuple:
        """Extract email content and attachments with BLOB storage"""
        body_plain = ""
        body_html = ""
        attachments = []
        
        def process_part(part):
            nonlocal body_plain, body_html
            
            if part.get('mimeType') == 'text/plain':
                if 'data' in part['body']:
                    body_plain = base64.urlsafe_b64decode(
                        part['body']['data']
                    ).decode('utf-8')
            elif part.get('mimeType') == 'text/html':
                if 'data' in part['body']:
                    body_html = base64.urlsafe_b64decode(
                        part['body']['data']
                    ).decode('utf-8')
            elif part.get('filename'):
                # Handle attachment with BLOB storage
                attachment_data = self._download_attachment_as_blob(part, message_id)
                if attachment_data:
                    attachments.append(attachment_data)
            
            # Process nested parts
            if 'parts' in part:
                for subpart in part['parts']:
                    process_part(subpart)
        
        process_part(payload)
        return body_plain, body_html, attachments
    
    def _extract_content(self, payload: Dict, message_id: str) -> tuple:
        """Extract email content and attachments"""
        body_plain = ""
        body_html = ""
        attachments = []
        
        def process_part(part):
            nonlocal body_plain, body_html
            
            if part.get('mimeType') == 'text/plain':
                if 'data' in part['body']:
                    body_plain = base64.urlsafe_b64decode(
                        part['body']['data']
                    ).decode('utf-8')
            elif part.get('mimeType') == 'text/html':
                if 'data' in part['body']:
                    body_html = base64.urlsafe_b64decode(
                        part['body']['data']
                    ).decode('utf-8')
            elif part.get('filename'):
                # Handle attachment
                attachment_data = self._download_attachment(part, message_id)
                if attachment_data:
                    attachments.append(attachment_data)
            
            # Process nested parts
            if 'parts' in part:
                for subpart in part['parts']:
                    process_part(subpart)
        
        process_part(payload)
        return body_plain, body_html, attachments
    
    def _download_attachment_as_blob(self, part: Dict, message_id: str) -> Optional[Dict]:
        """Download attachment and store as BLOB in database"""
        try:
            attachment_id = part['body']['attachmentId']
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            # Get file data as bytes
            file_data = base64.urlsafe_b64decode(attachment['data'])
            filename = part['filename']
            
            # Calculate checksum for deduplication
            checksum = hashlib.sha256(file_data).hexdigest()
            
            return {
                'filename': filename,
                'content_type': part['mimeType'],
                'size': len(file_data),
                'content_id': part.get('body', {}).get('contentId'),
                'file_data': file_data,  # Store as BLOB
                'file_path': f"attachments/{filename}",  # Keep for backward compatibility
                'is_inline': part.get('body', {}).get('contentId') is not None,
                'checksum': checksum
            }
            
        except Exception as e:
            logger.error(f"Error downloading attachment: {e}")
            return None
    
    def _download_attachment(self, part: Dict, message_id: str) -> Optional[Dict]:
        """Download and save attachment to file system"""
        try:
            attachment_id = part['body']['attachmentId']
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            # Save attachment to file
            file_data = base64.urlsafe_b64decode(attachment['data'])
            filename = part['filename']
            file_path = f"attachments/{filename}"
            
            # Ensure directory exists
            os.makedirs("attachments", exist_ok=True)
            
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            return {
                'filename': filename,
                'content_type': part['mimeType'],
                'size': len(file_data),
                'content_id': part.get('body', {}).get('contentId'),
                'file_path': file_path,
                'is_inline': part.get('body', {}).get('contentId') is not None
            }
            
        except Exception as e:
            logger.error(f"Error downloading attachment: {e}")
            return None
    
    def sync_new_emails(self, user: User, db: Session) -> int:
        """Sync only new emails since last sync"""
        if not self.authenticate_user(user):
            raise Exception("Failed to authenticate with Gmail")
        
        # Get last sync time
        last_sync = user.last_sync or datetime(1970, 1, 1, tzinfo=timezone.utc)
        
        try:
            # Query for emails after last sync
            query = f"after:{int(last_sync.timestamp())}"
            
            results = self.service.users().messages().list(
                userId='me',
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            synced_count = 0
            
            for message in messages:
                email_obj = self._fetch_email_details(message['id'], db)
                if email_obj:
                    synced_count += 1
            
            # Update last sync time
            user.last_sync = datetime.now(timezone.utc)
            db.commit()
            
            return synced_count
            
        except HttpError as error:
            logger.error(f"Error syncing new emails: {error}")
            raise
    
    def get_email_attachments(self, user: User, email_id: str) -> List[dict]:
        """Get attachments for a specific email"""
        # Placeholder implementation
        return []
    
    def get_user_emails(self, user: User, max_results: int = None) -> List[Email]:
        """Wrapper method for backward compatibility"""
        return self.get_all_emails(user, None, max_results)
    
    def get_email_count_by_label(self, user: User, label_id: str) -> int:
        """Get the count of emails for a specific label"""
        if not self.authenticate_user(user):
            raise Exception("Failed to authenticate with Gmail")
        
        try:
            results = self.service.users().messages().list(
                userId='me',
                labelIds=[label_id],
                maxResults=1
            ).execute()
            
            return results.get('resultSizeEstimate', 0)
            
        except HttpError as error:
            logger.error(f"Error getting email count for label {label_id}: {error}")
            return 0

    def get_total_email_count(self, user: User) -> int:
        """Get total email count from Gmail profile"""
        if not self.authenticate_user(user):
            raise Exception("Failed to authenticate with Gmail")
        
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile.get('messagesTotal', 0)
        except HttpError as error:
            logger.error(f"Error getting total email count: {error}")
            return 0
