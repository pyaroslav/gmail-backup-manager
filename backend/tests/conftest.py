import pytest
import tempfile
import shutil
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Add the parent directory to the path so we can import the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import Base, get_db
from main import app
from app.models.user import User
from app.models.email import Email, EmailAttachment, EmailLabel

# Use PostgreSQL for testing to match production environment
SQLALCHEMY_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", 
    "postgresql://gmail_user:gmail_password@localhost:5432/gmail_backup_test"
)

# Create test engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    connect_args={
        "application_name": "gmail_backup_test",
        "options": "-c timezone=utc"
    }
)

# Create test session
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def db_engine():
    """Create database engine for testing."""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    yield engine
    # Clean up - drop all tables
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(db_engine):
    """Create a fresh database session for each test."""
    # Create a new session
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client(db_session):
    """Create a test client with database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        gmail_id="test_gmail_id",
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_expires_at=None
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def sample_emails(db_session, test_user):
    """Create sample emails for testing."""
    emails = []
    
    # Create test emails
    test_emails = [
        {
            "gmail_id": "test_email_1",
            "thread_id": "thread_1",
            "subject": "Test Email 1",
            "sender": "sender1@example.com",
            "recipients": ["test@example.com"],
            "body_plain": "This is a test email body",
            "body_html": "<p>This is a test email body</p>",
            "is_read": True,
            "is_starred": False,
            "is_important": False,
            "category": "primary",
            "sentiment_score": 1,
            "priority_score": 7
        },
        {
            "gmail_id": "test_email_2",
            "thread_id": "thread_1",
            "subject": "Test Email 2",
            "sender": "sender2@example.com",
            "recipients": ["test@example.com"],
            "body_plain": "This is another test email body",
            "body_html": "<p>This is another test email body</p>",
            "is_read": False,
            "is_starred": True,
            "is_important": True,
            "category": "personal",
            "sentiment_score": -1,
            "priority_score": 5
        },
        {
            "gmail_id": "test_email_3",
            "thread_id": "thread_2",
            "subject": "Newsletter",
            "sender": "newsletter@example.com",
            "recipients": ["test@example.com"],
            "body_plain": "Weekly newsletter content",
            "body_html": "<p>Weekly newsletter content</p>",
            "is_read": False,
            "is_starred": False,
            "is_important": False,
            "category": "newsletter",
            "sentiment_score": 0,
            "priority_score": 3
        }
    ]
    
    for email_data in test_emails:
        email = Email(**email_data)
        db_session.add(email)
        emails.append(email)
    
    db_session.commit()
    
    # Refresh emails to get IDs
    for email in emails:
        db_session.refresh(email)
    
    return emails

@pytest.fixture
def sample_attachments(db_session, sample_emails):
    """Create sample attachments for testing."""
    attachments = []
    
    # Create test attachments
    test_attachments = [
        {
            "email_id": sample_emails[0].id,
            "filename": "test_document.pdf",
            "content_type": "application/pdf",
            "size": 1024,
            "is_inline": False
        },
        {
            "email_id": sample_emails[1].id,
            "filename": "image.jpg",
            "content_type": "image/jpeg",
            "size": 2048,
            "is_inline": True
        }
    ]
    
    for attachment_data in test_attachments:
        attachment = EmailAttachment(**attachment_data)
        db_session.add(attachment)
        attachments.append(attachment)
    
    db_session.commit()
    
    # Refresh attachments to get IDs
    for attachment in attachments:
        db_session.refresh(attachment)
    
    return attachments

@pytest.fixture
def temp_attachments_dir():
    """Create a temporary directory for attachments."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

# Mock environment variables for testing
@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables for testing."""
    os.environ["DATABASE_URL"] = SQLALCHEMY_DATABASE_URL
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["GMAIL_CLIENT_ID"] = "test-client-id"
    os.environ["GMAIL_CLIENT_SECRET"] = "test-client-secret"
    os.environ["REDIS_URL"] = "redis://localhost:6379"
    yield
    # Clean up environment variables
    for key in ["DATABASE_URL", "SECRET_KEY", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "REDIS_URL"]:
        if key in os.environ:
            del os.environ[key]

@pytest.fixture(autouse=True)
def clear_sync_status():
    """Clear sync status before each test to ensure clean state."""
    # Remove the problematic import - sync_status doesn't exist in the current implementation
    yield
    # No cleanup needed
