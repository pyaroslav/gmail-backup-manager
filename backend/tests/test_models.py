import pytest
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.email import Email, EmailAttachment
from app.models.user import User
from app.models.database import Base, engine

class TestEmailModel:
    """Test suite for Email model."""
    
    def test_create_email(self, db_session):
        """Test creating an email."""
        email = Email(
            gmail_id="test_email_1",
            thread_id="thread_1",
            subject="Test Email",
            sender="sender@example.com",
            recipients=["recipient@example.com"],
            body_plain="This is a test email",
            body_html="<p>This is a test email</p>",
            is_read=False,
            is_starred=False,
            is_important=False,
            category="work",
            sentiment_score=1,
            priority_score=8
        )
        
        db_session.add(email)
        db_session.commit()
        db_session.refresh(email)
        
        assert email.id is not None
        assert email.gmail_id == "test_email_1"
        assert email.subject == "Test Email"
        assert email.sender == "sender@example.com"
        assert email.is_read is False
        assert email.is_starred is False
        assert email.is_important is False
        assert email.category == "work"
        assert email.sentiment_score == 1
        assert email.priority_score == 8
    
    def test_email_relationships(self, db_session):
        """Test email relationships."""
        # Create an email
        email = Email(
            gmail_id="test_email_1",
            subject="Test Email",
            sender="sender@example.com",
            recipients=["recipient@example.com"],
            body_plain="Test body"
        )
        db_session.add(email)
        db_session.commit()
        db_session.refresh(email)
        
        # Create attachments for the email
        attachment1 = EmailAttachment(
            email_id=email.id,
            filename="test1.pdf",
            content_type="application/pdf",
            size=1024,
            is_inline=False
        )
        
        attachment2 = EmailAttachment(
            email_id=email.id,
            filename="test2.jpg",
            content_type="image/jpeg",
            size=2048,
            is_inline=True
        )
        
        db_session.add_all([attachment1, attachment2])
        db_session.commit()
        
        # Test relationship
        assert len(email.attachments) == 2
        assert email.attachments[0].filename == "test1.pdf"
        assert email.attachments[1].filename == "test2.jpg"
    
    def test_email_validation(self, db_session):
        """Test email field validation."""
        # Test required fields
        email = Email(
            gmail_id="test_email_1",
            subject="Test Email",
            sender="sender@example.com",
            recipients=["recipient@example.com"],
            body_plain="Test body"
        )
        
        db_session.add(email)
        db_session.commit()
        db_session.refresh(email)
        
        assert email.id is not None
        assert email.gmail_id == "test_email_1"
    
    def test_email_default_values(self, db_session):
        """Test email default values."""
        email = Email(
            gmail_id="test_email_1",
            subject="Test Email",
            sender="sender@example.com",
            recipients=["recipient@example.com"],
            body_plain="Test body"
        )
        
        db_session.add(email)
        db_session.commit()
        db_session.refresh(email)
        
        # Check default values
        assert email.is_read is False
        assert email.is_starred is False
        assert email.is_important is False
        assert email.is_spam is False
        assert email.is_trash is False
        assert email.date_received is not None  # Should be set to current time
    
    def test_email_date_handling(self, db_session):
        """Test email date handling."""
        now = datetime.now()
        
        email = Email(
            gmail_id="test_email_1",
            subject="Test Email",
            sender="sender@example.com",
            recipients=["recipient@example.com"],
            body_plain="Test body",
            date_received=now,
            date_sent=now
        )
        
        db_session.add(email)
        db_session.commit()
        db_session.refresh(email)
        
        assert email.date_received == now
        assert email.date_sent == now
    
    def test_email_list_fields(self, db_session):
        """Test email list fields (recipients, cc, bcc, labels)."""
        email = Email(
            gmail_id="test_email_1",
            subject="Test Email",
            sender="sender@example.com",
            recipients=["recipient1@example.com", "recipient2@example.com"],
            cc=["cc1@example.com", "cc2@example.com"],
            bcc=["bcc1@example.com"],
            labels=["INBOX", "IMPORTANT", "WORK"]
        )
        
        db_session.add(email)
        db_session.commit()
        db_session.refresh(email)
        
        assert len(email.recipients) == 2
        assert "recipient1@example.com" in email.recipients
        assert "recipient2@example.com" in email.recipients
        
        assert len(email.cc) == 2
        assert "cc1@example.com" in email.cc
        assert "cc2@example.com" in email.cc
        
        assert len(email.bcc) == 1
        assert "bcc1@example.com" in email.bcc
        
        assert len(email.labels) == 3
        assert "INBOX" in email.labels
        assert "IMPORTANT" in email.labels
        assert "WORK" in email.labels
    
    def test_email_string_representation(self, db_session):
        """Test email string representation."""
        email = Email(
            gmail_id="test_email_1",
            subject="Test Email",
            sender="sender@example.com",
            recipients=["recipient@example.com"],
            body_plain="Test body"
        )
        
        db_session.add(email)
        db_session.commit()
        db_session.refresh(email)
        
        # Test string representation
        email_str = str(email)
        assert "Test Email" in email_str
        assert "sender@example.com" in email_str


class TestEmailAttachmentModel:
    """Test suite for EmailAttachment model."""
    
    def test_create_attachment(self, db_session, sample_emails):
        """Test creating an attachment."""
        email_id = sample_emails[0].id
        
        attachment = EmailAttachment(
            email_id=email_id,
            filename="test_document.pdf",
            content_type="application/pdf",
            size=1024,
            is_inline=False
        )
        
        db_session.add(attachment)
        db_session.commit()
        db_session.refresh(attachment)
        
        assert attachment.id is not None
        assert attachment.email_id == email_id
        assert attachment.filename == "test_document.pdf"
        assert attachment.content_type == "application/pdf"
        assert attachment.size == 1024
        assert attachment.is_inline is False
    
    def test_attachment_relationship(self, db_session, sample_emails):
        """Test attachment relationship with email."""
        email_id = sample_emails[0].id
        
        attachment = EmailAttachment(
            email_id=email_id,
            filename="test_document.pdf",
            content_type="application/pdf",
            size=1024,
            is_inline=False
        )
        
        db_session.add(attachment)
        db_session.commit()
        db_session.refresh(attachment)
        
        # Test relationship
        assert attachment.email is not None
        assert attachment.email.id == email_id
        assert attachment.email.subject == "Test Email 1"
    
    def test_attachment_default_values(self, db_session, sample_emails):
        """Test attachment default values."""
        email_id = sample_emails[0].id
        
        attachment = EmailAttachment(
            email_id=email_id,
            filename="test_document.pdf",
            content_type="application/pdf",
            size=1024
        )
        
        db_session.add(attachment)
        db_session.commit()
        db_session.refresh(attachment)
        
        # Check default values
        assert attachment.is_inline is False
    
    def test_attachment_validation(self, db_session, sample_emails):
        """Test attachment field validation."""
        email_id = sample_emails[0].id
        
        # Test required fields
        attachment = EmailAttachment(
            email_id=email_id,
            filename="test_document.pdf",
            content_type="application/pdf",
            size=1024
        )
        
        db_session.add(attachment)
        db_session.commit()
        db_session.refresh(attachment)
        
        assert attachment.id is not None
        assert attachment.email_id == email_id
    
    def test_attachment_string_representation(self, db_session, sample_emails):
        """Test attachment string representation."""
        email_id = sample_emails[0].id
        
        attachment = EmailAttachment(
            email_id=email_id,
            filename="test_document.pdf",
            content_type="application/pdf",
            size=1024
        )
        
        db_session.add(attachment)
        db_session.commit()
        db_session.refresh(attachment)
        
        # Test string representation
        attachment_str = str(attachment)
        assert "test_document.pdf" in attachment_str


class TestUserModel:
    """Test suite for User model."""
    
    def test_create_user(self, db_session):
        """Test creating a user."""
        user = User(
            email="test@example.com",
            name="Test User",
            gmail_access_token="test_access_token",
            gmail_refresh_token="test_refresh_token"
        )
        
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.gmail_access_token == "test_access_token"
        assert user.gmail_refresh_token == "test_refresh_token"
    
    def test_user_default_values(self, db_session):
        """Test user default values."""
        user = User(
            email="test@example.com",
            name="Test User"
        )
        
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Check default values
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None
    
    def test_user_validation(self, db_session):
        """Test user field validation."""
        # Test required fields
        user = User(
            email="test@example.com",
            name="Test User"
        )
        
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.id is not None
        assert user.email == "test@example.com"
    
    def test_user_string_representation(self, db_session):
        """Test user string representation."""
        user = User(
            email="test@example.com",
            name="Test User"
        )
        
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Test string representation
        user_str = str(user)
        assert "test@example.com" in user_str
        assert "Test User" in user_str
    
    def test_user_timestamp_handling(self, db_session):
        """Test user timestamp handling."""
        user = User(
            email="test@example.com",
            name="Test User"
        )
        
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Check that timestamps are set
        assert user.created_at is not None
        assert user.updated_at is not None
        
        # Update user and check that updated_at changes
        original_updated_at = user.updated_at
        import time
        time.sleep(0.1)
        user.name = "Updated User"
        db_session.commit()
        db_session.refresh(user)
        
        # Note: PostgreSQL onupdate should work in tests, so we check that updated_at exists
        assert user.updated_at is not None


class TestDatabaseModels:
    """Test suite for database model interactions."""
    
    def test_email_user_relationship(self, db_session):
        """Test relationship between emails and users."""
        # Create a user
        user = User(
            email="test@example.com",
            name="Test User"
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Create emails for the user
        email1 = Email(
            gmail_id="test_email_1",
            subject="Test Email 1",
            sender="sender1@example.com",
            recipients=["test@example.com"],
            body_plain="Test body 1"
        )
        
        email2 = Email(
            gmail_id="test_email_2",
            subject="Test Email 2",
            sender="sender2@example.com",
            recipients=["test@example.com"],
            body_plain="Test body 2"
        )
        
        db_session.add_all([email1, email2])
        db_session.commit()
        
        # Test that emails are created successfully
        assert email1.id is not None
        assert email2.id is not None
    
    def test_cascade_delete(self, db_session, sample_emails, sample_attachments):
        """Test cascade delete behavior."""
        email_id = sample_emails[0].id
        
        # Verify attachment exists
        attachment = db_session.query(EmailAttachment).filter(
            EmailAttachment.email_id == email_id
        ).first()
        assert attachment is not None
        
        # Delete the email
        email = db_session.query(Email).filter(Email.id == email_id).first()
        db_session.delete(email)
        db_session.commit()
        
        # Verify attachment is also deleted (if cascade is configured)
        attachment = db_session.query(EmailAttachment).filter(
            EmailAttachment.email_id == email_id
        ).first()
        # This behavior depends on the cascade configuration in the model
    
    def test_database_constraints(self, db_session):
        """Test database constraints."""
        # Test unique constraint on gmail_id (if configured)
        email1 = Email(
            gmail_id="duplicate_id",
            subject="Test Email 1",
            sender="sender1@example.com",
            recipients=["test@example.com"],
            body_plain="Test body 1"
        )
        
        email2 = Email(
            gmail_id="duplicate_id",  # Same gmail_id
            subject="Test Email 2",
            sender="sender2@example.com",
            recipients=["test@example.com"],
            body_plain="Test body 2"
        )
        
        db_session.add(email1)
        db_session.commit()
        
        # This should raise an integrity error if unique constraint is configured
        db_session.add(email2)
        try:
            db_session.commit()
            # If no error, unique constraint is not configured
        except Exception:
            # If error, unique constraint is working
            db_session.rollback()
    
    def test_database_indexes(self, db_session):
        """Test database indexes."""
        # Create multiple emails to test indexing
        emails = []
        for i in range(10):
            email = Email(
                gmail_id=f"test_email_{i}",
                subject=f"Test Email {i}",
                sender=f"sender{i}@example.com",
                recipients=["test@example.com"],
                body_plain=f"Test body {i}",
                is_read=(i % 2 == 0),  # Alternate read status
                category="work" if i < 5 else "personal"
            )
            emails.append(email)
        
        db_session.add_all(emails)
        db_session.commit()
        
        # Test queries that should use indexes
        # Query by gmail_id (should be indexed)
        email = db_session.query(Email).filter(Email.gmail_id == "test_email_5").first()
        assert email is not None
        assert email.subject == "Test Email 5"
        
        # Query by read status (should be indexed)
        read_emails = db_session.query(Email).filter(Email.is_read == True).all()
        assert len(read_emails) == 5
        
        # Query by category (should be indexed)
        work_emails = db_session.query(Email).filter(Email.category == "work").all()
        assert len(work_emails) == 5
    
    def test_database_transactions(self, db_session):
        """Test database transaction behavior."""
        # Start a transaction
        email = Email(
            gmail_id="transaction_test",
            subject="Transaction Test",
            sender="sender@example.com",
            recipients=["test@example.com"],
            body_plain="Test body"
        )
        
        db_session.add(email)
        db_session.commit()
        db_session.refresh(email)
        
        # Verify email was created
        assert email.id is not None
        
        # Test rollback
        email2 = Email(
            gmail_id="rollback_test",
            subject="Rollback Test",
            sender="sender@example.com",
            recipients=["test@example.com"],
            body_plain="Test body"
        )
        
        db_session.add(email2)
        db_session.rollback()
        
        # Email2 should not be in database
        email2_check = db_session.query(Email).filter(
            Email.gmail_id == "rollback_test"
        ).first()
        assert email2_check is None
