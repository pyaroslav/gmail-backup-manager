"""
Optimized sync service for Gmail backup manager
This service provides high-performance email synchronization using:
- PostgreSQL with connection pooling
- BLOB storage for attachments
- Parallel processing
- Batch operations
- Optimized queries
"""

import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from sqlalchemy.exc import SQLAlchemyError

from ..models.database import SessionLocal, get_db
from ..models.email import Email, EmailAttachment, EmailLabel
from ..models.user import User
from .gmail_service import GmailService

logger = logging.getLogger(__name__)

class OptimizedSyncService:
    def __init__(self):
        self.gmail_service = GmailService()
        self.batch_size = 100
        self.max_workers = 10
        
    def sync_user_emails(self, user: User, max_emails: int = None) -> int:
        """
        Sync emails for a user with optimized database operations
        """
        if not self.gmail_service.authenticate_user(user):
            raise Exception("Failed to authenticate with Gmail")
        
        emails_synced = 0
        page_token = None
        api_batch_size = 100  # Reduced batch size to avoid memory issues
        
        try:
            # Get the last synced email to continue from where we left off
            # Use a separate session for this initial query
            with SessionLocal() as db:
                last_synced_email = db.query(Email).order_by(Email.date_received.desc()).first()
                last_sync_date = last_synced_email.date_received if last_synced_email else None
            
            if last_sync_date:
                logger.info(f"Continuing sync from last email date: {last_sync_date}")
                # Use Gmail query to get emails after the last synced date
                query = f"after:{int(last_sync_date.timestamp())}"
            else:
                logger.info("Starting fresh sync - no previous emails found")
                query = None
            
            while True:
                # Get batch of email IDs from Gmail
                batch_size = min(api_batch_size, max_emails - emails_synced) if max_emails else api_batch_size
                
                request_params = {
                    'userId': 'me',
                    'maxResults': batch_size
                }
                
                if page_token:
                    request_params['pageToken'] = page_token
                
                if query:
                    request_params['q'] = query
                
                logger.info(f"Requesting batch of {batch_size} emails (page_token: {bool(page_token)}, query: {query})")
                
                results = self.gmail_service.service.users().messages().list(**request_params).execute()
                messages = results.get('messages', [])
                
                if not messages:
                    logger.info("No more messages to process")
                    break
                
                logger.info(f"Processing batch of {len(messages)} emails (total synced: {emails_synced})")
                
                # Process emails sequentially to avoid memory issues
                batch_synced = 0
                batch_processed = 0
                for message in messages:
                    try:
                        batch_processed += 1
                        if self._process_single_email(user, message['id']):
                            emails_synced += 1
                            batch_synced += 1
                            
                            if emails_synced % 25 == 0:  # Log every 25 emails
                                logger.info(f"Progress: {emails_synced} emails synced")
                                
                    except Exception as e:
                        logger.error(f"Error processing email {message['id']}: {e}")
                        continue
                
                logger.info(f"Batch completed: {batch_synced} new emails synced out of {batch_processed} processed (total synced: {emails_synced})")
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    logger.info("No more pages available")
                    break
                
                if max_emails and emails_synced >= max_emails:
                    logger.info(f"Reached max emails limit: {max_emails}")
                    break
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error in email sync: {e}")
            raise
            
        logger.info(f"Sync completed: {emails_synced} emails synced")
        return emails_synced
    
    def sync_user_emails_from_date(self, user: User, start_date: str, max_emails: int = None) -> int:
        """
        Sync emails for a user from a specific date (format: YYYY/MM/DD)
        Example: sync_user_emails_from_date(user, "2011/01/01") will sync emails from 2011 onwards
        """
        if not self.gmail_service.authenticate_user(user):
            raise Exception("Failed to authenticate with Gmail")
        
        emails_synced = 0
        page_token = None
        api_batch_size = 100  # Reduced batch size to avoid memory issues
        
        try:
            logger.info(f"Starting sync from date: {start_date}")
            
            while True:
                # Get batch of email IDs from Gmail
                batch_size = min(api_batch_size, max_emails - emails_synced) if max_emails else api_batch_size
                
                request_params = {
                    'userId': 'me',
                    'maxResults': batch_size,
                    'q': f'after:{start_date}'  # Gmail query for date filtering
                }
                
                if page_token:
                    request_params['pageToken'] = page_token
                
                logger.info(f"Requesting batch of {batch_size} emails from {start_date} (page_token: {bool(page_token)})")
                
                results = self.gmail_service.service.users().messages().list(**request_params).execute()
                messages = results.get('messages', [])
                
                if not messages:
                    logger.info("No more messages to process")
                    break
                
                logger.info(f"Processing batch of {len(messages)} emails (total synced: {emails_synced})")
                
                # Process emails sequentially to avoid memory issues
                for message in messages:
                    try:
                        if self._process_single_email(user, message['id']):
                            emails_synced += 1
                            
                            if emails_synced % 25 == 0:  # Log every 25 emails
                                logger.info(f"Progress: {emails_synced} emails synced")
                                
                    except Exception as e:
                        logger.error(f"Error processing email {message['id']}: {e}")
                        continue
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    logger.info("No more pages available")
                    break
                
                if max_emails and emails_synced >= max_emails:
                    logger.info(f"Reached max emails limit: {max_emails}")
                    break
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error in date-based email sync: {e}")
            raise
            
        logger.info(f"Date-based sync completed: {emails_synced} emails synced from {start_date}")
        return emails_synced
    
    def sync_user_emails_full(self, user: User, max_emails: int = None) -> int:
        """
        Sync all emails for a user without date filtering (full sync)
        """
        if not self.gmail_service.authenticate_user(user):
            raise Exception("Failed to authenticate with Gmail")
        
        emails_synced = 0
        page_token = None
        api_batch_size = 100  # Reduced batch size to avoid memory issues
        
        try:
            logger.info("Starting full sync - fetching all available emails")
            
            while True:
                # Get batch of email IDs from Gmail
                batch_size = min(api_batch_size, max_emails - emails_synced) if max_emails else api_batch_size
                
                request_params = {
                    'userId': 'me',
                    'maxResults': batch_size
                }
                
                if page_token:
                    request_params['pageToken'] = page_token
                
                logger.info(f"Requesting batch of {batch_size} emails (page_token: {bool(page_token)})")
                
                results = self.gmail_service.service.users().messages().list(**request_params).execute()
                messages = results.get('messages', [])
                
                if not messages:
                    logger.info("No more messages to process")
                    break
                
                logger.info(f"Processing batch of {len(messages)} emails (total synced: {emails_synced})")
                
                # Process emails sequentially to avoid memory issues
                for message in messages:
                    try:
                        if self._process_single_email(user, message['id']):
                            emails_synced += 1
                            
                            if emails_synced % 25 == 0:  # Log every 25 emails
                                logger.info(f"Progress: {emails_synced} emails synced")
                                
                    except Exception as e:
                        logger.error(f"Error processing email {message['id']}: {e}")
                        continue
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    logger.info("No more pages available")
                    break
                
                if max_emails and emails_synced >= max_emails:
                    logger.info(f"Reached max emails limit: {max_emails}")
                    break
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error in full email sync: {e}")
            raise
            
        logger.info(f"Full sync completed: {emails_synced} emails synced")
        return emails_synced
    
    def _sync_emails_optimized(self, user: User, db: Session, max_emails: int = None) -> int:
        """
        Sync emails with optimized batch processing and parallel execution
        """
        emails_synced = 0
        page_token = None
        api_batch_size = 100  # Reduced batch size to avoid memory issues
        
        try:
            # Get current database stats
            total_existing = db.query(Email).count()
            logger.info(f"Starting email sync with pagination... Current database has {total_existing} emails")
            
            while True:
                # Get batch of email IDs from Gmail
                batch_size = min(api_batch_size, max_emails - emails_synced) if max_emails else api_batch_size
                
                request_params = {
                    'userId': 'me',
                    'maxResults': batch_size
                }
                
                if page_token:
                    request_params['pageToken'] = page_token
                
                logger.info(f"Requesting batch of {batch_size} emails (page_token: {bool(page_token)})")
                
                results = self.gmail_service.service.users().messages().list(**request_params).execute()
                messages = results.get('messages', [])
                
                if not messages:
                    logger.info("No more messages to process")
                    break
                
                logger.info(f"Processing batch of {len(messages)} emails (total synced: {emails_synced})")
                
                # Process emails sequentially to avoid memory issues
                for message in messages:
                    try:
                        if self._process_single_email(user, message['id']):
                            emails_synced += 1
                            
                            if emails_synced % 25 == 0:  # Log every 25 emails
                                logger.info(f"Progress: {emails_synced} emails synced")
                                
                    except Exception as e:
                        logger.error(f"Error processing email {message['id']}: {e}")
                        continue
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    logger.info("No more pages available")
                    break
                
                if max_emails and emails_synced >= max_emails:
                    logger.info(f"Reached max emails limit: {max_emails}")
                    break
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error in email sync: {e}")
            raise
            
        logger.info(f"Sync completed: {emails_synced} emails synced")
        return emails_synced
    
    def _process_single_email(self, user: User, message_id: str) -> bool:
        """
        Process a single email with optimized database operations
        """
        db = SessionLocal()
        try:
            # Check if email already exists
            existing_email = db.query(Email).filter(Email.gmail_id == message_id).first()
            if existing_email:
                return False  # Already synced
            
            # Fetch email details from Gmail
            email_data = self._fetch_email_data(message_id)
            if not email_data:
                return False
            
            # Extract attachments before creating Email object
            attachments = email_data.pop('attachments', [])
            
            # Clean up the data for Email model creation
            # Remove any fields that might cause SQLAlchemy issues
            email_model_data = {
                'gmail_id': email_data.get('gmail_id'),
                'thread_id': email_data.get('thread_id'),
                'subject': email_data.get('subject', ''),
                'sender': email_data.get('sender', ''),
                'recipients': email_data.get('recipients', []),
                'cc': email_data.get('cc', []),
                'bcc': email_data.get('bcc', []),
                'body_plain': email_data.get('body_plain', ''),
                'body_html': email_data.get('body_html', ''),
                'date_received': email_data.get('date_received'),
                'labels': email_data.get('labels', []),
                'is_read': email_data.get('is_read', False),
                'is_starred': email_data.get('is_starred', False),
                'is_important': email_data.get('is_important', False),
                'is_spam': email_data.get('is_spam', False),
                'is_trash': email_data.get('is_trash', False)
            }
            
            # Create email record
            email_obj = Email(**email_model_data)
            db.add(email_obj)
            db.flush()  # Get the ID without committing
            
            # Process attachments
            if attachments:
                self._process_attachments(db, email_obj.id, attachments)
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error processing email {message_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def _fetch_email_data(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch email data from Gmail API with retry logic
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                message = self.gmail_service.service.users().messages().get(
                    userId='me',
                    id=message_id,
                    format='full'
                ).execute()
                
                return self._parse_email_message(message)
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Retry {attempt + 1} for message {message_id}: {e}")
                    time.sleep(2 ** attempt)
                    continue
                else:
                    logger.error(f"Failed to fetch message {message_id} after {max_retries} attempts")
                    return None
    
    def _parse_email_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Gmail message into database format
        """
        headers = message['payload']['headers']
        
        # Extract headers
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
        
        # Extract content and attachments
        body_plain, body_html, attachments = self._extract_content_optimized(message['payload'], message['id'])
        
        # Get labels
        label_ids = message.get('labelIds', [])
        
        return {
            'gmail_id': message['id'],
            'thread_id': message.get('threadId'),
            'subject': subject,
            'sender': sender,
            'recipients': to_emails,
            'cc': cc_emails,
            'bcc': bcc_emails,
            'body_plain': body_plain,
            'body_html': body_html,
            'date_received': date_received,
            'labels': label_ids,
            'is_read': 'UNREAD' not in label_ids,
            'is_starred': 'STARRED' in label_ids,
            'is_important': 'IMPORTANT' in label_ids,
            'is_spam': 'SPAM' in label_ids,
            'is_trash': 'TRASH' in label_ids,
            'attachments': attachments
        }
    
    def _process_attachments(self, db: Session, email_id: int, attachments: List[Dict[str, Any]]):
        """
        Process attachments and store as BLOBs
        """
        for attachment_data in attachments:
            attachment = EmailAttachment(
                email_id=email_id,
                filename=attachment_data['filename'],
                content_type=attachment_data['content_type'],
                size=attachment_data['size'],
                content_id=attachment_data.get('content_id'),
                file_data=attachment_data['file_data'],
                file_path=attachment_data.get('file_path'),
                is_inline=attachment_data.get('is_inline', False),
                checksum=attachment_data.get('checksum')
            )
            db.add(attachment)
    
    def _extract_content_optimized(self, payload: Dict[str, Any], message_id: str) -> tuple:
        """
        Extract email content and attachments with BLOB storage
        """
        body_plain = ""
        body_html = ""
        attachments = []
        
        def process_part(part):
            nonlocal body_plain, body_html
            
            if part.get('mimeType') == 'text/plain':
                if 'data' in part['body']:
                    body_plain = self._decode_base64(part['body']['data'])
            elif part.get('mimeType') == 'text/html':
                if 'data' in part['body']:
                    body_html = self._decode_base64(part['body']['data'])
            elif part.get('filename'):
                attachment_data = self._download_attachment_as_blob(part, message_id)
                if attachment_data:
                    attachments.append(attachment_data)
            
            # Process nested parts
            if 'parts' in part:
                for subpart in part['parts']:
                    process_part(subpart)
        
        process_part(payload)
        return body_plain, body_html, attachments
    
    def _download_attachment_as_blob(self, part: Dict[str, Any], message_id: str) -> Optional[Dict[str, Any]]:
        """
        Download attachment and store as BLOB
        """
        try:
            attachment_id = part['body']['attachmentId']
            attachment = self.gmail_service.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            file_data = self._decode_base64_bytes(attachment['data'])
            filename = part['filename']
            
            # Calculate checksum
            import hashlib
            checksum = hashlib.sha256(file_data).hexdigest()
            
            return {
                'filename': filename,
                'content_type': part['mimeType'],
                'size': len(file_data),
                'content_id': part.get('body', {}).get('contentId'),
                'file_data': file_data,
                'file_path': f"attachments/{filename}",
                'is_inline': part.get('body', {}).get('contentId') is not None,
                'checksum': checksum
            }
            
        except Exception as e:
            logger.error(f"Error downloading attachment: {e}")
            return None
    
    def _decode_base64(self, data: str) -> str:
        """Decode base64 data to string"""
        import base64
        return base64.urlsafe_b64decode(data).decode('utf-8')
    
    def _decode_base64_bytes(self, data: str) -> bytes:
        """Decode base64 data to bytes"""
        import base64
        return base64.urlsafe_b64decode(data)
    
    def _parse_email_list(self, email_string: str) -> List[str]:
        """Parse email list from header value"""
        if not email_string:
            return []
        
        emails = []
        for email_part in email_string.split(','):
            email_part = email_part.strip()
            if '<' in email_part and '>' in email_part:
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
            import email.utils
            return email.utils.parsedate_to_datetime(date_string)
        except Exception as e:
            logger.warning(f"Could not parse date '{date_string}': {e}")
            return None
    
    def get_sync_stats(self, user: User) -> Dict[str, Any]:
        """
        Get synchronization statistics for a user
        """
        db = SessionLocal()
        try:
            # Get email counts
            total_emails = db.query(Email).filter(Email.sender == user.email).count()
            unread_emails = db.query(Email).filter(
                Email.sender == user.email,
                Email.is_read == False
            ).count()
            
            # Get attachment stats
            total_attachments = db.query(EmailAttachment).join(Email).filter(
                Email.sender == user.email
            ).count()
            
            total_attachment_size = db.query(func.sum(EmailAttachment.size)).join(Email).filter(
                Email.sender == user.email
            ).scalar() or 0
            
            # Get label stats
            total_labels = db.query(EmailLabel).count()
            
            return {
                "total_emails": total_emails,
                "unread_emails": unread_emails,
                "total_attachments": total_attachments,
                "total_attachment_size_bytes": total_attachment_size,
                "total_labels": total_labels,
                "last_sync": user.last_sync.isoformat() if user.last_sync else None
            }
            
        finally:
            db.close()
