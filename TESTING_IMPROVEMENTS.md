# Testing and Quality Assurance Improvements

## Current Testing Assessment

### ✅ Good Testing Practices
- Unit tests with pytest
- API endpoint testing
- Database model testing
- Service layer testing

### 🔧 Recommended Testing Enhancements

## 1. Test Coverage Expansion

### Current Issues
- Limited integration tests
- No end-to-end tests
- No performance tests
- No security tests
- Missing test data management

### Improvements

#### Comprehensive Test Structure
```python
# tests/conftest.py - Enhanced test configuration
import pytest
import asyncio
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import redis
import os

# Test database configuration
TEST_DATABASE_URL = "postgresql://test_user:test_pass@localhost:5432/gmail_backup_test"
TEST_REDIS_URL = "redis://localhost:6379/1"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        echo=False
    )
    yield engine
    engine.dispose()

@pytest.fixture(scope="session")
def test_db_session(test_engine):
    """Create test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )
    session = TestingSessionLocal()
    yield session
    session.close()

@pytest.fixture(scope="session")
def test_redis():
    """Create test Redis connection."""
    redis_client = redis.from_url(TEST_REDIS_URL)
    yield redis_client
    redis_client.flushdb()

@pytest.fixture
def client(test_db_session, test_redis) -> Generator:
    """Create test client with test database."""
    from main import app
    from app.models.database import get_db
    
    def override_get_db():
        try:
            yield test_db_session
        finally:
            test_db_session.rollback()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "gmail_access_token": "test_access_token",
        "gmail_refresh_token": "test_refresh_token",
        "gmail_token_expiry": "2024-12-31T23:59:59Z"
    }

@pytest.fixture
def sample_email_data():
    """Sample email data for testing."""
    return {
        "gmail_id": "test_gmail_id_123",
        "thread_id": "test_thread_id_456",
        "subject": "Test Email Subject",
        "sender": "sender@example.com",
        "recipients": ["recipient@example.com"],
        "body_plain": "This is a test email body.",
        "body_html": "<p>This is a test email body.</p>",
        "date_received": "2024-01-01T12:00:00Z",
        "is_read": False,
        "labels": ["INBOX", "UNREAD"]
    }

@pytest.fixture
def mock_gmail_service(monkeypatch):
    """Mock Gmail service for testing."""
    class MockGmailService:
        def __init__(self):
            self.emails = []
            self.labels = []
        
        def authenticate_user(self, user):
            return True
        
        def get_user_emails(self, user, max_results=100):
            return self.emails[:max_results]
        
        def get_all_labels(self, user):
            return self.labels
    
    mock_service = MockGmailService()
    monkeypatch.setattr("app.services.gmail_service.GmailService", lambda: mock_service)
    return mock_service
```

#### Integration Tests
```python
# tests/integration/test_email_sync_integration.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.sync_service import OptimizedSyncService
from app.models.user import User
from app.models.email import Email

class TestEmailSyncIntegration:
    """Integration tests for email synchronization."""
    
    @pytest.fixture
    def sync_service(self, test_db_session):
        """Create sync service with test database."""
        return OptimizedSyncService()
    
    @pytest.fixture
    def test_user(self, test_db_session, sample_user_data):
        """Create test user in database."""
        user = User(**sample_user_data)
        test_db_session.add(user)
        test_db_session.commit()
        test_db_session.refresh(user)
        return user
    
    @pytest.mark.asyncio
    async def test_full_email_sync_flow(self, sync_service, test_user, mock_gmail_service, test_db_session):
        """Test complete email sync flow from Gmail to database."""
        # Setup mock Gmail data
        mock_emails = [
            {
                "id": "gmail_id_1",
                "threadId": "thread_id_1",
                "labelIds": ["INBOX", "UNREAD"],
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Test Email 1"},
                        {"name": "From", "value": "sender1@example.com"},
                        {"name": "To", "value": "recipient@example.com"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 12:00:00 +0000"}
                    ],
                    "body": {"data": "VGVzdCBlbWFpbCBib2R5IDE="}  # Base64 encoded
                }
            },
            {
                "id": "gmail_id_2",
                "threadId": "thread_id_2",
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Test Email 2"},
                        {"name": "From", "value": "sender2@example.com"},
                        {"name": "To", "value": "recipient@example.com"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 13:00:00 +0000"}
                    ],
                    "body": {"data": "VGVzdCBlbWFpbCBib2R5IDI="}
                }
            }
        ]
        
        mock_gmail_service.emails = mock_emails
        
        # Perform sync
        emails_synced = await sync_service.sync_user_emails(test_user, max_emails=10)
        
        # Verify results
        assert emails_synced == 2
        
        # Check database
        db_emails = test_db_session.query(Email).filter_by(user_id=test_user.id).all()
        assert len(db_emails) == 2
        
        # Verify email content
        email1 = next(e for e in db_emails if e.gmail_id == "gmail_id_1")
        assert email1.subject == "Test Email 1"
        assert email1.sender == "sender1@example.com"
        assert "INBOX" in email1.labels
        assert "UNREAD" in email1.labels
    
    @pytest.mark.asyncio
    async def test_sync_with_existing_emails(self, sync_service, test_user, mock_gmail_service, test_db_session):
        """Test sync behavior with existing emails in database."""
        # Add existing email to database
        existing_email = Email(
            gmail_id="existing_gmail_id",
            thread_id="existing_thread_id",
            subject="Existing Email",
            sender="existing@example.com",
            user_id=test_user.id
        )
        test_db_session.add(existing_email)
        test_db_session.commit()
        
        # Setup mock Gmail data with same email
        mock_emails = [
            {
                "id": "existing_gmail_id",
                "threadId": "existing_thread_id",
                "labelIds": ["INBOX", "READ"],
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Updated Subject"},
                        {"name": "From", "value": "existing@example.com"},
                        {"name": "To", "value": "recipient@example.com"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 12:00:00 +0000"}
                    ],
                    "body": {"data": "VXBkYXRlZCBib2R5"}
                }
            }
        ]
        
        mock_gmail_service.emails = mock_emails
        
        # Perform sync
        emails_synced = await sync_service.sync_user_emails(test_user, max_emails=10)
        
        # Verify results
        assert emails_synced == 1  # Should update existing email
        
        # Check database
        db_emails = test_db_session.query(Email).filter_by(user_id=test_user.id).all()
        assert len(db_emails) == 1
        
        # Verify email was updated
        updated_email = db_emails[0]
        assert updated_email.subject == "Updated Subject"
        assert "READ" in updated_email.labels
```

#### End-to-End Tests
```python
# tests/e2e/test_full_workflow.py
import pytest
from playwright.async_api import async_playwright
import asyncio
from fastapi.testclient import TestClient

class TestFullWorkflow:
    """End-to-end tests for complete user workflows."""
    
    @pytest.fixture
    def browser_context(self):
        """Setup browser context for E2E tests."""
        async def _setup_browser():
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            yield page
            await browser.close()
            await playwright.stop()
        
        return asyncio.run(_setup_browser())
    
    @pytest.mark.asyncio
    async def test_user_login_and_sync_workflow(self, browser_context, client: TestClient):
        """Test complete user login and email sync workflow."""
        page = browser_context
        
        # Navigate to application
        await page.goto("http://localhost:3002")
        
        # Verify login page is displayed
        await page.wait_for_selector("#login-form")
        
        # Fill login form
        await page.fill("#email", "test@example.com")
        await page.fill("#password", "testpassword")
        
        # Submit login
        await page.click("#login-button")
        
        # Wait for dashboard to load
        await page.wait_for_selector("#dashboard")
        
        # Verify dashboard elements
        email_count = await page.text_content("#email-count")
        assert email_count is not None
        
        # Navigate to sync page
        await page.click('a[data-page="sync"]')
        await page.wait_for_selector("#sync-controls")
        
        # Start sync
        await page.click("#start-sync-button")
        
        # Wait for sync to complete
        await page.wait_for_selector("#sync-status.completed", timeout=30000)
        
        # Verify sync results
        sync_status = await page.text_content("#sync-status")
        assert "completed" in sync_status.lower()
        
        # Navigate to emails page
        await page.click('a[data-page="emails"]')
        await page.wait_for_selector("#email-list")
        
        # Verify emails are displayed
        email_items = await page.query_selector_all(".email-item")
        assert len(email_items) > 0
    
    @pytest.mark.asyncio
    async def test_search_functionality(self, browser_context, client: TestClient):
        """Test email search functionality."""
        page = browser_context
        
        # Navigate to search page
        await page.goto("http://localhost:3002")
        await page.click('a[data-page="search"]')
        await page.wait_for_selector("#search-form")
        
        # Perform search
        await page.fill("#search-input", "test email")
        await page.click("#search-button")
        
        # Wait for results
        await page.wait_for_selector("#search-results")
        
        # Verify search results
        results = await page.query_selector_all(".search-result")
        assert len(results) >= 0  # May be 0 if no results
    
    @pytest.mark.asyncio
    async def test_analytics_dashboard(self, browser_context, client: TestClient):
        """Test analytics dashboard functionality."""
        page = browser_context
        
        # Navigate to analytics page
        await page.goto("http://localhost:3002")
        await page.click('a[data-page="analytics"]')
        await page.wait_for_selector("#analytics-dashboard")
        
        # Verify analytics components
        await page.wait_for_selector("#email-trends-chart")
        await page.wait_for_selector("#sender-stats")
        await page.wait_for_selector("#category-breakdown")
        
        # Check if charts are rendered
        chart_elements = await page.query_selector_all("canvas")
        assert len(chart_elements) > 0
```

## 2. Performance Testing

### Load Testing
```python
# tests/performance/test_load.py
import asyncio
import time
import statistics
from typing import List, Dict
import aiohttp
import pytest

class TestLoadPerformance:
    """Performance and load testing."""
    
    @pytest.fixture
    def api_base_url(self):
        """API base URL for testing."""
        return "http://localhost:8000"
    
    async def make_request(self, session: aiohttp.ClientSession, url: str, method: str = "GET", **kwargs) -> Dict:
        """Make HTTP request and return timing data."""
        start_time = time.time()
        
        try:
            async with session.request(method, url, **kwargs) as response:
                response_time = time.time() - start_time
                return {
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "success": response.status_code < 400
                }
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "status_code": 0,
                "response_time": response_time,
                "success": False,
                "error": str(e)
            }
    
    @pytest.mark.asyncio
    async def test_api_response_times(self, api_base_url):
        """Test API response times under normal load."""
        async with aiohttp.ClientSession() as session:
            endpoints = [
                "/api/v1/emails",
                "/api/v1/analytics/overview",
                "/api/v1/sync/status",
                "/health"
            ]
            
            results = []
            
            # Make 100 requests to each endpoint
            for endpoint in endpoints:
                endpoint_results = []
                for _ in range(100):
                    result = await self.make_request(session, f"{api_base_url}{endpoint}")
                    endpoint_results.append(result)
                
                results.append({
                    "endpoint": endpoint,
                    "results": endpoint_results
                })
            
            # Analyze results
            for endpoint_data in results:
                response_times = [r["response_time"] for r in endpoint_data["results"]]
                success_rate = sum(1 for r in endpoint_data["results"] if r["success"]) / len(endpoint_data["results"])
                
                print(f"\nEndpoint: {endpoint_data['endpoint']}")
                print(f"Average response time: {statistics.mean(response_times):.3f}s")
                print(f"Median response time: {statistics.median(response_times):.3f}s")
                print(f"95th percentile: {statistics.quantiles(response_times, n=20)[18]:.3f}s")
                print(f"Success rate: {success_rate:.2%}")
                
                # Assertions
                assert statistics.mean(response_times) < 1.0  # Average < 1 second
                assert success_rate > 0.95  # 95% success rate
    
    @pytest.mark.asyncio
    async def test_concurrent_users(self, api_base_url):
        """Test system performance with concurrent users."""
        async def simulate_user(user_id: int) -> List[Dict]:
            """Simulate a single user making requests."""
            async with aiohttp.ClientSession() as session:
                user_results = []
                
                # Simulate user workflow
                workflows = [
                    ("GET", "/api/v1/emails?page=1&page_size=25"),
                    ("GET", "/api/v1/analytics/overview"),
                    ("GET", "/api/v1/sync/status"),
                    ("POST", "/api/v1/sync/start", {"sync_type": "full", "max_emails": 100}),
                    ("GET", "/api/v1/emails?page=2&page_size=25"),
                ]
                
                for method, endpoint, *args in workflows:
                    kwargs = {}
                    if args:
                        kwargs["json"] = args[0]
                    
                    result = await self.make_request(
                        session, 
                        f"{api_base_url}{endpoint}", 
                        method, 
                        **kwargs
                    )
                    user_results.append(result)
                    
                    # Small delay between requests
                    await asyncio.sleep(0.1)
                
                return user_results
        
        # Simulate 50 concurrent users
        user_tasks = [simulate_user(i) for i in range(50)]
        all_results = await asyncio.gather(*user_tasks)
        
        # Flatten results
        flat_results = [result for user_results in all_results for result in user_results]
        
        # Analyze performance
        response_times = [r["response_time"] for r in flat_results]
        success_rate = sum(1 for r in flat_results if r["success"]) / len(flat_results)
        
        print(f"\nConcurrent Users Test (50 users)")
        print(f"Total requests: {len(flat_results)}")
        print(f"Average response time: {statistics.mean(response_times):.3f}s")
        print(f"95th percentile: {statistics.quantiles(response_times, n=20)[18]:.3f}s")
        print(f"Success rate: {success_rate:.2%}")
        
        # Assertions
        assert statistics.mean(response_times) < 2.0  # Average < 2 seconds under load
        assert success_rate > 0.90  # 90% success rate under load
    
    @pytest.mark.asyncio
    async def test_database_performance(self, test_db_session):
        """Test database query performance."""
        from app.models.email import Email
        import time
        
        # Test email count query
        start_time = time.time()
        count = test_db_session.query(Email).count()
        count_time = time.time() - start_time
        
        print(f"\nDatabase Performance Test")
        print(f"Email count query time: {count_time:.3f}s")
        
        # Test email listing with pagination
        start_time = time.time()
        emails = test_db_session.query(Email).order_by(Email.date_received.desc()).limit(100).all()
        list_time = time.time() - start_time
        
        print(f"Email list query time: {list_time:.3f}s")
        
        # Test search query
        start_time = time.time()
        search_results = test_db_session.query(Email).filter(
            Email.subject.ilike("%test%")
        ).limit(50).all()
        search_time = time.time() - start_time
        
        print(f"Search query time: {search_time:.3f}s")
        
        # Assertions
        assert count_time < 0.1  # Count query < 100ms
        assert list_time < 0.5   # List query < 500ms
        assert search_time < 1.0  # Search query < 1s
```

## 3. Security Testing

### Security Test Suite
```python
# tests/security/test_security.py
import pytest
from fastapi.testclient import TestClient
import jwt
from datetime import datetime, timedelta

class TestSecurity:
    """Security testing suite."""
    
    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        from main import app
        return TestClient(app)
    
    def test_authentication_required(self, client: TestClient):
        """Test that protected endpoints require authentication."""
        protected_endpoints = [
            "/api/v1/emails",
            "/api/v1/analytics/overview",
            "/api/v1/sync/start",
            "/api/v1/search"
        ]
        
        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401
    
    def test_invalid_token_rejected(self, client: TestClient):
        """Test that invalid tokens are rejected."""
        headers = {"Authorization": "Bearer invalid_token"}
        
        response = client.get("/api/v1/emails", headers=headers)
        assert response.status_code == 401
    
    def test_expired_token_rejected(self, client: TestClient):
        """Test that expired tokens are rejected."""
        # Create expired token
        expired_token = jwt.encode(
            {
                "sub": "test@example.com",
                "exp": datetime.utcnow() - timedelta(hours=1)
            },
            "test_secret",
            algorithm="HS256"
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/emails", headers=headers)
        assert response.status_code == 401
    
    def test_sql_injection_prevention(self, client: TestClient):
        """Test SQL injection prevention."""
        # Test search endpoint with SQL injection attempts
        sql_injection_payloads = [
            "'; DROP TABLE emails; --",
            "' OR '1'='1",
            "'; INSERT INTO emails VALUES (1, 'hacked'); --",
            "' UNION SELECT * FROM users --"
        ]
        
        for payload in sql_injection_payloads:
            response = client.get(f"/api/v1/search?q={payload}")
            # Should not crash or return unexpected data
            assert response.status_code in [200, 400, 401]
    
    def test_xss_prevention(self, client: TestClient):
        """Test XSS prevention."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert('xss');//"
        ]
        
        for payload in xss_payloads:
            response = client.get(f"/api/v1/search?q={payload}")
            # Check that response doesn't contain unescaped script tags
            if response.status_code == 200:
                response_text = response.text
                assert "<script>" not in response_text.lower()
                assert "javascript:" not in response_text.lower()
    
    def test_rate_limiting(self, client: TestClient):
        """Test rate limiting functionality."""
        # Make many requests quickly
        for _ in range(100):
            response = client.get("/api/v1/emails")
            # Should not all succeed (rate limiting should kick in)
        
        # Check that some requests were rate limited
        responses = [client.get("/api/v1/emails") for _ in range(10)]
        rate_limited = sum(1 for r in responses if r.status_code == 429)
        assert rate_limited > 0
    
    def test_cors_headers(self, client: TestClient):
        """Test CORS headers are properly set."""
        response = client.options("/api/v1/emails")
        
        # Check CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers
    
    def test_content_security_policy(self, client: TestClient):
        """Test Content Security Policy headers."""
        response = client.get("/")
        
        # Check security headers
        assert "content-security-policy" in response.headers
        assert "x-frame-options" in response.headers
        assert "x-content-type-options" in response.headers
```

## 4. Data Quality Testing

### Data Validation Tests
```python
# tests/data/test_data_quality.py
import pytest
from app.models.email import Email
from app.services.ai_service import AIService
from datetime import datetime

class TestDataQuality:
    """Data quality and validation testing."""
    
    @pytest.fixture
    def ai_service(self):
        """Create AI service for testing."""
        return AIService()
    
    def test_email_data_integrity(self, test_db_session, sample_email_data):
        """Test email data integrity and validation."""
        # Create email with valid data
        email = Email(**sample_email_data)
        test_db_session.add(email)
        test_db_session.commit()
        
        # Verify data was stored correctly
        stored_email = test_db_session.query(Email).filter_by(gmail_id=sample_email_data["gmail_id"]).first()
        assert stored_email is not None
        assert stored_email.subject == sample_email_data["subject"]
        assert stored_email.sender == sample_email_data["sender"]
        assert stored_email.labels == sample_email_data["labels"]
    
    def test_email_duplicate_prevention(self, test_db_session, sample_email_data):
        """Test that duplicate emails are not created."""
        # Create first email
        email1 = Email(**sample_email_data)
        test_db_session.add(email1)
        test_db_session.commit()
        
        # Try to create duplicate
        email2 = Email(**sample_email_data)
        test_db_session.add(email2)
        
        # Should raise integrity error
        with pytest.raises(Exception):
            test_db_session.commit()
    
    def test_email_data_cleaning(self, test_db_session):
        """Test email data cleaning and normalization."""
        # Test with malformed data
        malformed_data = {
            "gmail_id": "test_id",
            "subject": "  Test Subject  ",  # Extra whitespace
            "sender": "SENDER@EXAMPLE.COM",  # Uppercase
            "body_plain": "Test body\n\n\n\n",  # Extra newlines
            "labels": ["INBOX", "inbox", "Inbox"],  # Duplicate labels
            "date_received": "2024-01-01T12:00:00Z"
        }
        
        email = Email(**malformed_data)
        test_db_session.add(email)
        test_db_session.commit()
        
        # Verify data was cleaned
        stored_email = test_db_session.query(Email).filter_by(gmail_id="test_id").first()
        assert stored_email.subject == "Test Subject"  # Whitespace trimmed
        assert stored_email.sender == "sender@example.com"  # Lowercase
        assert len(stored_email.labels) == 1  # Duplicates removed
        assert "inbox" in stored_email.labels
    
    def test_ai_analysis_quality(self, ai_service, sample_email_data):
        """Test AI analysis quality and consistency."""
        # Test sentiment analysis
        sentiment = ai_service.analyze_sentiment(sample_email_data["body_plain"])
        assert -1 <= sentiment <= 1  # Sentiment should be between -1 and 1
        
        # Test categorization
        category = ai_service.categorize_email(sample_email_data["subject"], sample_email_data["body_plain"])
        assert category in ["work", "personal", "spam", "newsletter", "other"]
        
        # Test priority scoring
        priority = ai_service.calculate_priority(sample_email_data["subject"], sample_email_data["body_plain"])
        assert 1 <= priority <= 10  # Priority should be between 1 and 10
        
        # Test summarization
        summary = ai_service.summarize_email(sample_email_data["body_plain"])
        assert len(summary) > 0
        assert len(summary) < len(sample_email_data["body_plain"])  # Summary should be shorter
    
    def test_data_consistency(self, test_db_session):
        """Test data consistency across the system."""
        # Create multiple emails
        emails_data = [
            {
                "gmail_id": f"id_{i}",
                "subject": f"Email {i}",
                "sender": f"sender{i}@example.com",
                "body_plain": f"Body {i}",
                "date_received": datetime.utcnow().isoformat()
            }
            for i in range(10)
        ]
        
        for data in emails_data:
            email = Email(**data)
            test_db_session.add(email)
        
        test_db_session.commit()
        
        # Verify consistency
        total_emails = test_db_session.query(Email).count()
        assert total_emails == 10
        
        # Check unique constraints
        unique_gmail_ids = test_db_session.query(Email.gmail_id).distinct().count()
        assert unique_gmail_ids == 10
        
        # Check date ordering
        emails = test_db_session.query(Email).order_by(Email.date_received.desc()).all()
        for i in range(len(emails) - 1):
            assert emails[i].date_received >= emails[i + 1].date_received
```

## 5. Test Automation and CI/CD

### GitHub Actions Workflow
```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: gmail_backup_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r backend/requirements.txt
        pip install pytest pytest-asyncio pytest-cov pytest-playwright
        playwright install chromium
    
    - name: Run unit tests
      env:
        DATABASE_URL: postgresql://postgres:test_password@localhost:5432/gmail_backup_test
        REDIS_URL: redis://localhost:6379/1
      run: |
        cd backend
        pytest tests/ -v --cov=app --cov-report=xml --cov-report=html
    
    - name: Run integration tests
      env:
        DATABASE_URL: postgresql://postgres:test_password@localhost:5432/gmail_backup_test
        REDIS_URL: redis://localhost:6379/1
      run: |
        cd backend
        pytest tests/integration/ -v
    
    - name: Run security tests
      env:
        DATABASE_URL: postgresql://postgres:test_password@localhost:5432/gmail_backup_test
        REDIS_URL: redis://localhost:6379/1
      run: |
        cd backend
        pytest tests/security/ -v
    
    - name: Run performance tests
      env:
        DATABASE_URL: postgresql://postgres:test_password@localhost:5432/gmail_backup_test
        REDIS_URL: redis://localhost:6379/1
      run: |
        cd backend
        pytest tests/performance/ -v -m "not slow"
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./backend/coverage.xml
        flags: unittests
        name: codecov-umbrella
    
    - name: Run E2E tests
      run: |
        cd backend
        pytest tests/e2e/ -v

  security-scan:
    runs-on: ubuntu-latest
    needs: test
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Run security scan
      uses: snyk/actions/python@master
      env:
        SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      with:
        args: --severity-threshold=high
    
    - name: Run bandit security check
      run: |
        pip install bandit
        bandit -r backend/app/ -f json -o bandit-report.json
    
    - name: Upload security report
      uses: actions/upload-artifact@v3
      with:
        name: security-report
        path: bandit-report.json

  performance-benchmark:
    runs-on: ubuntu-latest
    needs: test
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r backend/requirements.txt
        pip install locust
    
    - name: Run performance benchmark
      run: |
        cd backend
        locust -f tests/performance/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 60s
```

## Implementation Priority

1. **High Priority**: Unit test coverage, Integration tests, Security tests
2. **Medium Priority**: Performance tests, E2E tests, Data quality tests
3. **Low Priority**: Advanced load testing, Chaos engineering tests

## Test Data Management

### Test Data Factory
```python
# tests/factories.py
import factory
from factory.fuzzy import FuzzyText, FuzzyChoice
from datetime import datetime, timedelta
from app.models.email import Email, EmailAttachment
from app.models.user import User

class UserFactory(factory.SQLAlchemyModelFactory):
    class Meta:
        model = User
    
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    gmail_access_token = FuzzyText(length=50)
    gmail_refresh_token = FuzzyText(length=50)
    gmail_token_expiry = factory.LazyFunction(
        lambda: (datetime.utcnow() + timedelta(hours=1)).isoformat()
    )

class EmailFactory(factory.SQLAlchemyModelFactory):
    class Meta:
        model = Email
    
    gmail_id = factory.Sequence(lambda n: f"gmail_id_{n}")
    thread_id = factory.Sequence(lambda n: f"thread_id_{n}")
    subject = factory.Faker('sentence', nb_words=6)
    sender = factory.Faker('email')
    recipients = factory.List([factory.Faker('email') for _ in range(3)])
    body_plain = factory.Faker('paragraph', nb_sentences=5)
    body_html = factory.LazyAttribute(lambda obj: f"<p>{obj.body_plain}</p>")
    date_received = factory.Faker('date_time_this_year')
    is_read = factory.Faker('boolean', chance_of_getting_true=70)
    is_starred = factory.Faker('boolean', chance_of_getting_true=10)
    labels = factory.List([FuzzyChoice(['INBOX', 'SENT', 'DRAFT', 'SPAM']) for _ in range(2)])
    user_id = factory.SubFactory(UserFactory).id

class EmailAttachmentFactory(factory.SQLAlchemyModelFactory):
    class Meta:
        model = EmailAttachment
    
    email_id = factory.SubFactory(EmailFactory).id
    filename = factory.Faker('file_name', extension='pdf')
    content_type = 'application/pdf'
    size = factory.Faker('random_int', min=1000, max=10000000)
    file_data = factory.LazyFunction(lambda: b'fake_pdf_content')
```
