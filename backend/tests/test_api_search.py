import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

class TestSearchAPI:
    """Test suite for search API endpoints."""
    
    def test_search_emails_basic(self, client: TestClient, sample_emails):
        """Test basic email search."""
        response = client.post("/api/v1/search/emails", json={
            "query": "test",
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert "emails" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert isinstance(data["emails"], list)
    
    def test_search_emails_by_sender(self, client: TestClient, sample_emails):
        """Test searching emails by sender."""
        response = client.post("/api/v1/search/emails", json={
            "sender": "sender1@example.com",
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) == 1
        assert data["emails"][0]["sender"] == "sender1@example.com"
    
    def test_search_emails_by_subject(self, client: TestClient, sample_emails):
        """Test searching emails by subject."""
        response = client.post("/api/v1/search/emails", json={
            "subject": "Newsletter",
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) == 1
        assert "Newsletter" in data["emails"][0]["subject"]
    
    def test_search_emails_by_category(self, client: TestClient, sample_emails):
        """Test searching emails by category."""
        response = client.post("/api/v1/search/emails", json={
            "category": "work",
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) == 1
        assert data["emails"][0]["category"] == "work"
    
    def test_search_emails_by_sentiment(self, client: TestClient, sample_emails):
        """Test searching emails by sentiment."""
        response = client.post("/api/v1/search/emails", json={
            "sentiment": 1,  # Positive sentiment
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) == 1
        assert data["emails"][0]["sentiment_score"] == 1
    
    def test_search_emails_by_priority(self, client: TestClient, sample_emails):
        """Test searching emails by priority range."""
        response = client.post("/api/v1/search/emails", json={
            "priority_min": 7,
            "priority_max": 10,
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) == 1
        assert data["emails"][0]["priority_score"] >= 7
    
    def test_search_emails_by_read_status(self, client: TestClient, sample_emails):
        """Test searching emails by read status."""
        response = client.post("/api/v1/search/emails", json={
            "is_read": False,
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) == 2  # Two unread emails
        for email in data["emails"]:
            assert email["is_read"] is False
    
    def test_search_emails_by_starred_status(self, client: TestClient, sample_emails):
        """Test searching emails by starred status."""
        response = client.post("/api/v1/search/emails", json={
            "is_starred": True,
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) == 1
        assert data["emails"][0]["is_starred"] is True
    
    def test_search_emails_by_important_status(self, client: TestClient, sample_emails):
        """Test searching emails by important status."""
        response = client.post("/api/v1/search/emails", json={
            "is_important": True,
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) == 1
        assert data["emails"][0]["is_important"] is True
    
    def test_search_emails_with_attachments(self, client: TestClient, sample_emails, sample_attachments):
        """Test searching emails with attachments."""
        response = client.post("/api/v1/search/emails", json={
            "has_attachments": True,
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) == 2  # Two emails have attachments
    
    def test_search_emails_sorting(self, client: TestClient, sample_emails):
        """Test email search with sorting."""
        response = client.post("/api/v1/search/emails", json={
            "sort_by": "subject",
            "sort_order": "asc",
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        subjects = [email["subject"] for email in data["emails"]]
        assert subjects == sorted(subjects)
    
    def test_search_emails_pagination(self, client: TestClient, sample_emails):
        """Test email search pagination."""
        response = client.post("/api/v1/search/emails", json={
            "page": 1,
            "page_size": 2
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["emails"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 2
    
    def test_get_search_suggestions(self, client: TestClient, sample_emails):
        """Test getting search suggestions."""
        response = client.get("/api/v1/search/suggestions?query=test&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
    
    def test_get_email_labels(self, client: TestClient, sample_emails):
        """Test getting email labels."""
        response = client.get("/api/v1/search/labels")
        assert response.status_code == 200
        
        data = response.json()
        assert "labels" in data
        assert isinstance(data["labels"], list)
    
    def test_get_email_categories(self, client: TestClient):
        """Test getting email categories."""
        response = client.get("/api/v1/search/categories")
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
        
        # Check that expected categories are present
        category_ids = [cat["id"] for cat in data["categories"]]
        expected_categories = ["work", "personal", "spam", "newsletter", "other"]
        for expected in expected_categories:
            assert expected in category_ids
    
    def test_get_email_statistics(self, client: TestClient, sample_emails):
        """Test getting email statistics."""
        response = client.get("/api/v1/search/statistics")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        # Check for expected statistics fields
        assert "total_emails" in data or "total_count" in data
    
    def test_get_email_threads(self, client: TestClient, sample_emails):
        """Test getting email threads."""
        response = client.get("/api/v1/search/threads")
        assert response.status_code == 200
        
        data = response.json()
        assert "threads" in data
        assert isinstance(data["threads"], list)
    
    def test_get_email_threads_by_id(self, client: TestClient, sample_emails):
        """Test getting email threads by specific thread ID."""
        response = client.get("/api/v1/search/threads?thread_id=thread_1")
        assert response.status_code == 200
        
        data = response.json()
        assert "threads" in data
        assert isinstance(data["threads"], list)
    
    def test_export_emails_json(self, client: TestClient, sample_emails):
        """Test exporting emails in JSON format."""
        email_ids = [sample_emails[0].id, sample_emails[1].id]
        
        response = client.post("/api/v1/search/export", json={
            "email_ids": email_ids,
            "format": "json"
        })
        assert response.status_code == 200
        assert "Content-Disposition" in response.headers
        assert "application/json" in response.headers["content-type"]
    
    def test_export_emails_csv(self, client: TestClient, sample_emails):
        """Test exporting emails in CSV format."""
        email_ids = [sample_emails[0].id, sample_emails[1].id]
        
        response = client.post("/api/v1/search/export", json={
            "email_ids": email_ids,
            "format": "csv"
        })
        assert response.status_code == 200
        assert "Content-Disposition" in response.headers
        assert "text/csv" in response.headers["content-type"]
    
    def test_export_emails_eml(self, client: TestClient, sample_emails):
        """Test exporting emails in EML format."""
        email_ids = [sample_emails[0].id, sample_emails[1].id]
        
        response = client.post("/api/v1/search/export", json={
            "email_ids": email_ids,
            "format": "eml"
        })
        assert response.status_code == 200
        assert "Content-Disposition" in response.headers
        assert "message/rfc822" in response.headers["content-type"]
    
    def test_export_emails_invalid_format(self, client: TestClient, sample_emails):
        """Test exporting emails with invalid format."""
        email_ids = [sample_emails[0].id]
        
        response = client.post("/api/v1/search/export", json={
            "email_ids": email_ids,
            "format": "invalid_format"
        })
        assert response.status_code == 400
        assert "unsupported export format" in response.json()["detail"]
    
    def test_get_email_clusters(self, client: TestClient, sample_emails):
        """Test getting email clusters."""
        response = client.get("/api/v1/search/clusters?n_clusters=3")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
    
    def test_quick_search_by_sender(self, client: TestClient, sample_emails):
        """Test quick search by sender."""
        response = client.get("/api/v1/search/quick/sender/sender1@example.com")
        assert response.status_code == 200
        
        data = response.json()
        assert "emails" in data
        assert len(data["emails"]) == 1
        assert data["emails"][0]["sender"] == "sender1@example.com"
    
    def test_quick_search_by_subject(self, client: TestClient, sample_emails):
        """Test quick search by subject."""
        response = client.get("/api/v1/search/quick/subject/Newsletter")
        assert response.status_code == 200
        
        data = response.json()
        assert "emails" in data
        assert len(data["emails"]) == 1
        assert "Newsletter" in data["emails"][0]["subject"]
    
    def test_quick_search_by_category(self, client: TestClient, sample_emails):
        """Test quick search by category."""
        response = client.get("/api/v1/search/quick/category/work")
        assert response.status_code == 200
        
        data = response.json()
        assert "emails" in data
        assert len(data["emails"]) == 1
        assert data["emails"][0]["category"] == "work"
    
    def test_quick_search_unread(self, client: TestClient, sample_emails):
        """Test quick search for unread emails."""
        response = client.get("/api/v1/search/quick/unread")
        assert response.status_code == 200
        
        data = response.json()
        assert "emails" in data
        assert len(data["emails"]) == 2  # Two unread emails
        for email in data["emails"]:
            assert email["is_read"] is False
    
    def test_quick_search_starred(self, client: TestClient, sample_emails):
        """Test quick search for starred emails."""
        response = client.get("/api/v1/search/quick/starred")
        assert response.status_code == 200
        
        data = response.json()
        assert "emails" in data
        assert len(data["emails"]) == 1
        assert data["emails"][0]["is_starred"] is True
    
    def test_quick_search_important(self, client: TestClient, sample_emails):
        """Test quick search for important emails."""
        response = client.get("/api/v1/search/quick/important")
        assert response.status_code == 200
        
        data = response.json()
        assert "emails" in data
        assert len(data["emails"]) == 1
        assert data["emails"][0]["is_important"] is True
    
    def test_quick_search_attachments(self, client: TestClient, sample_emails, sample_attachments):
        """Test quick search for emails with attachments."""
        response = client.get("/api/v1/search/quick/attachments")
        assert response.status_code == 200
        
        data = response.json()
        assert "emails" in data
        assert len(data["emails"]) == 2  # Two emails have attachments
    
    def test_search_with_date_range(self, client: TestClient, sample_emails):
        """Test searching emails with date range."""
        from datetime import datetime, timedelta
        
        # Create date range for the last 30 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        response = client.post("/api/v1/search/emails", json={
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert "emails" in data
        assert isinstance(data["emails"], list)
    
    def test_search_with_multiple_filters(self, client: TestClient, sample_emails):
        """Test searching emails with multiple filters."""
        response = client.post("/api/v1/search/emails", json={
            "category": "work",
            "is_read": False,
            "priority_min": 5,
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
        
        data = response.json()
        assert "emails" in data
        # Should find the work email that is unread and has priority >= 5
        assert len(data["emails"]) == 1
        email = data["emails"][0]
        assert email["category"] == "work"
        assert email["is_read"] is False
        assert email["priority_score"] >= 5
    
    def test_search_invalid_parameters(self, client: TestClient):
        """Test search with invalid parameters."""
        response = client.post("/api/v1/search/emails", json={
            "page": 0,  # Invalid page number
            "page_size": 0  # Invalid page size
        })
        assert response.status_code == 422  # Validation error
    
    def test_search_suggestions_invalid_query(self, client: TestClient):
        """Test search suggestions with invalid query."""
        response = client.get("/api/v1/search/suggestions?query=&limit=5")
        assert response.status_code == 422  # Validation error
    
    def test_search_suggestions_invalid_limit(self, client: TestClient):
        """Test search suggestions with invalid limit."""
        response = client.get("/api/v1/search/suggestions?query=test&limit=0")
        assert response.status_code == 422  # Validation error
