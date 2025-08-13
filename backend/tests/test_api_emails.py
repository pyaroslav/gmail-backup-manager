import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

class TestEmailsAPI:
    """Test suite for emails API endpoints."""
    
    def test_get_emails(self, client: TestClient, sample_emails):
        """Test getting paginated list of emails."""
        response = client.get("/api/v1/emails/")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3  # We have 3 sample emails
        
        # Check email structure
        email = data[0]
        assert "id" in email
        assert "gmail_id" in email
        assert "subject" in email
        assert "sender" in email
        assert "is_read" in email
        assert "is_starred" in email
        assert "is_important" in email
    
    def test_get_emails_pagination(self, client: TestClient, sample_emails):
        """Test email pagination."""
        response = client.get("/api/v1/emails/?page=1&page_size=2")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 2
        
        response = client.get("/api/v1/emails/?page=2&page_size=2")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
    
    def test_get_email_by_id(self, client: TestClient, sample_emails):
        """Test getting a specific email by ID."""
        email_id = sample_emails[0].id
        response = client.get(f"/api/v1/emails/{email_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == email_id
        assert data["subject"] == "Test Email 1"
        assert data["sender"] == "sender1@example.com"
        assert "attachments" in data
    
    def test_get_email_not_found(self, client: TestClient):
        """Test getting a non-existent email."""
        response = client.get("/api/v1/emails/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_get_email_attachments(self, client: TestClient, sample_emails, sample_attachments):
        """Test getting email attachments."""
        email_id = sample_emails[0].id
        response = client.get(f"/api/v1/emails/{email_id}/attachments")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1  # One attachment for this email
        
        attachment = data[0]
        assert "id" in attachment
        assert "filename" in attachment
        assert "content_type" in attachment
        assert "size" in attachment
        assert "is_inline" in attachment
    
    def test_download_attachment(self, client: TestClient, sample_emails, sample_attachments):
        """Test downloading an attachment."""
        email_id = sample_emails[0].id
        attachment_id = sample_attachments[0].id
        
        response = client.get(f"/api/v1/emails/{email_id}/attachment/{attachment_id}")
        assert response.status_code == 200
        assert "Content-Disposition" in response.headers
    
    def test_download_attachment_not_found(self, client: TestClient, sample_emails):
        """Test downloading a non-existent attachment."""
        email_id = sample_emails[0].id
        response = client.get(f"/api/v1/emails/{email_id}/attachment/99999")
        assert response.status_code == 404
    
    def test_get_email_thread(self, client: TestClient, sample_emails):
        """Test getting email thread."""
        email_id = sample_emails[0].id  # This email has thread_id "thread_1"
        response = client.get(f"/api/v1/emails/{email_id}/thread")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2  # Two emails in thread_1
    
    def test_get_similar_emails(self, client: TestClient, sample_emails):
        """Test getting similar emails."""
        email_id = sample_emails[0].id
        response = client.get(f"/api/v1/emails/{email_id}/similar?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_email_summary(self, client: TestClient, sample_emails):
        """Test getting email summary."""
        email_id = sample_emails[0].id
        response = client.get(f"/api/v1/emails/{email_id}/summary")
        assert response.status_code == 200
        
        data = response.json()
        assert "summary" in data
    
    def test_mark_email_as_read(self, client: TestClient, sample_emails):
        """Test marking email as read."""
        email_id = sample_emails[0].id  # This email is initially unread
        
        response = client.patch(f"/api/v1/emails/{email_id}/read")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        
        # Verify the email is now marked as read
        response = client.get(f"/api/v1/emails/{email_id}")
        assert response.status_code == 200
        assert response.json()["is_read"] is True
    
    def test_mark_email_as_unread(self, client: TestClient, sample_emails):
        """Test marking email as unread."""
        email_id = sample_emails[1].id  # This email is initially read
        
        response = client.patch(f"/api/v1/emails/{email_id}/unread")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        
        # Verify the email is now marked as unread
        response = client.get(f"/api/v1/emails/{email_id}")
        assert response.status_code == 200
        assert response.json()["is_read"] is False
    
    def test_toggle_star(self, client: TestClient, sample_emails):
        """Test toggling star status."""
        email_id = sample_emails[0].id  # This email is initially not starred
        
        response = client.patch(f"/api/v1/emails/{email_id}/star")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        
        # Verify the email is now starred
        response = client.get(f"/api/v1/emails/{email_id}")
        assert response.status_code == 200
        assert response.json()["is_starred"] is True
    
    def test_toggle_important(self, client: TestClient, sample_emails):
        """Test toggling important status."""
        email_id = sample_emails[0].id  # This email is initially not important
        
        response = client.patch(f"/api/v1/emails/{email_id}/important")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        
        # Verify the email is now marked as important
        response = client.get(f"/api/v1/emails/{email_id}")
        assert response.status_code == 200
        assert response.json()["is_important"] is True
    
    def test_delete_email(self, client: TestClient, sample_emails):
        """Test deleting an email."""
        email_id = sample_emails[2].id  # Delete the newsletter email
        
        response = client.delete(f"/api/v1/emails/{email_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        
        # Verify the email is deleted
        response = client.get(f"/api/v1/emails/{email_id}")
        assert response.status_code == 404
    
    def test_bulk_update_emails(self, client: TestClient, sample_emails):
        """Test bulk updating emails."""
        email_ids = [sample_emails[0].id, sample_emails[1].id]
        
        response = client.patch("/api/v1/emails/bulk/update", json={
            "email_ids": email_ids,
            "is_read": True,
            "is_starred": True
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["updated_count"] == 2
        
        # Verify the emails are updated
        for email_id in email_ids:
            response = client.get(f"/api/v1/emails/{email_id}")
            assert response.status_code == 200
            email_data = response.json()
            assert email_data["is_read"] is True
            assert email_data["is_starred"] is True
    
    def test_bulk_delete_emails(self, client: TestClient, sample_emails):
        """Test bulk deleting emails."""
        email_ids = [sample_emails[0].id, sample_emails[1].id]
        email_ids_str = ",".join(map(str, email_ids))
        
        response = client.delete(f"/api/v1/emails/bulk/delete?email_ids={email_ids_str}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 2
        
        # Verify the emails are deleted
        for email_id in email_ids:
            response = client.get(f"/api/v1/emails/{email_id}")
            assert response.status_code == 404
    
    def test_invalid_email_id(self, client: TestClient):
        """Test handling of invalid email IDs."""
        response = client.get("/api/v1/emails/invalid")
        assert response.status_code == 422  # Validation error
    
    def test_invalid_pagination_params(self, client: TestClient):
        """Test handling of invalid pagination parameters."""
        response = client.get("/api/v1/emails/?page=0&page_size=0")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/v1/emails/?page_size=101")
        assert response.status_code == 422  # Validation error
