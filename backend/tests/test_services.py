import pytest
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Import services
from app.services.email_service import EmailService
from app.services.gmail_service import GmailService
from app.services.search_service import SearchService
from app.services.ai_service import AIService

class TestEmailService:
    """Test suite for EmailService."""
    
    def test_search_emails_basic(self, db_session, sample_emails):
        """Test basic email search functionality."""
        service = EmailService()
        
        result = service.search_emails(
            db=db_session,
            page=1,
            page_size=10
        )
        
        assert "emails" in result
        assert "total_count" in result
        assert "page" in result
        assert "page_size" in result
        assert "total_pages" in result
        assert len(result["emails"]) == 3  # We have 3 sample emails
    
    def test_search_emails_with_filters(self, db_session, sample_emails):
        """Test email search with various filters."""
        service = EmailService()
        
        # Test search by sender
        result = service.search_emails(
            db=db_session,
            sender="sender1@example.com",
            page=1,
            page_size=10
        )
        assert len(result["emails"]) == 1
        assert result["emails"][0].sender == "sender1@example.com"
        
        # Test search by category
        result = service.search_emails(
            db=db_session,
            category="work",
            page=1,
            page_size=10
        )
        assert len(result["emails"]) == 1
        assert result["emails"][0].category == "work"
        
        # Test search by read status
        result = service.search_emails(
            db=db_session,
            is_read=False,
            page=1,
            page_size=10
        )
        assert len(result["emails"]) == 2  # Two unread emails
    
    def test_get_email_by_id(self, db_session, sample_emails):
        """Test getting email by ID."""
        service = EmailService()
        email_id = sample_emails[0].id
        
        email = service.get_email_by_id(email_id, db_session)
        assert email is not None
        assert email.id == email_id
        assert email.subject == "Test Email 1"
    
    def test_get_email_by_id_not_found(self, db_session):
        """Test getting non-existent email by ID."""
        service = EmailService()
        
        email = service.get_email_by_id(99999, db_session)
        assert email is None
    
    def test_get_email_attachments(self, db_session, sample_emails, sample_attachments):
        """Test getting email attachments."""
        service = EmailService()
        email_id = sample_emails[0].id
        
        attachments = service.get_email_attachments(email_id, db_session)
        assert len(attachments) == 1
        assert attachments[0].filename == "test_document.pdf"
    
    def test_mark_email_as_read(self, db_session, sample_emails):
        """Test marking email as read."""
        service = EmailService()
        email_id = sample_emails[0].id  # This email is initially unread
        
        success = service.mark_email_as_read(email_id, db_session)
        assert success is True
        
        # Verify the email is now marked as read
        email = service.get_email_by_id(email_id, db_session)
        assert email.is_read is True
    
    def test_mark_email_as_unread(self, db_session, sample_emails):
        """Test marking email as unread."""
        service = EmailService()
        email_id = sample_emails[1].id  # This email is initially read
        
        success = service.mark_email_as_unread(email_id, db_session)
        assert success is True
        
        # Verify the email is now marked as unread
        email = service.get_email_by_id(email_id, db_session)
        assert email.is_read is False
    
    def test_star_email(self, db_session, sample_emails):
        """Test starring an email."""
        service = EmailService()
        email_id = sample_emails[0].id  # This email is initially not starred
        
        success = service.star_email(email_id, db_session)
        assert success is True
        
        # Verify the email is now starred
        email = service.get_email_by_id(email_id, db_session)
        assert email.is_starred is True
    
    def test_mark_as_important(self, db_session, sample_emails):
        """Test marking email as important."""
        service = EmailService()
        email_id = sample_emails[0].id  # This email is initially not important
        
        success = service.mark_as_important(email_id, db_session)
        assert success is True
        
        # Verify the email is now marked as important
        email = service.get_email_by_id(email_id, db_session)
        assert email.is_important is True
    
    def test_delete_email(self, db_session, sample_emails):
        """Test deleting an email."""
        service = EmailService()
        email_id = sample_emails[2].id  # Delete the newsletter email
        
        success = service.delete_email(email_id, db_session)
        assert success is True
        
        # Verify the email is deleted
        email = service.get_email_by_id(email_id, db_session)
        assert email is None
    
    def test_bulk_update_emails(self, db_session, sample_emails):
        """Test bulk updating emails."""
        service = EmailService()
        email_ids = [sample_emails[0].id, sample_emails[1].id]
        
        updated_count = service.bulk_update_emails(
            email_ids, db_session, is_read=True, is_starred=True
        )
        assert updated_count == 2
        
        # Verify the emails are updated
        for email_id in email_ids:
            email = service.get_email_by_id(email_id, db_session)
            assert email.is_read is True
            assert email.is_starred is True
    
    def test_get_email_thread(self, db_session, sample_emails):
        """Test getting email thread."""
        service = EmailService()
        thread_id = "thread_1"
        
        thread_emails = service.get_email_thread(thread_id, db_session)
        assert len(thread_emails) == 2  # Two emails in thread_1
    
    def test_get_similar_emails(self, db_session, sample_emails):
        """Test getting similar emails."""
        service = EmailService()
        email_id = sample_emails[0].id
        
        similar_emails = service.get_similar_emails(email_id, db_session, limit=5)
        assert isinstance(similar_emails, list)
    
    def test_get_email_summary(self, db_session, sample_emails):
        """Test getting email summary."""
        service = EmailService()
        email_id = sample_emails[0].id
        
        summary = service.get_email_summary(email_id, db_session)
        assert isinstance(summary, str) or summary is None
    
    def test_get_email_suggestions(self, db_session, sample_emails):
        """Test getting email suggestions."""
        service = EmailService()
        
        suggestions = service.get_email_suggestions("test", db_session, limit=5)
        assert isinstance(suggestions, list)
    
    def test_get_email_labels(self, db_session, sample_emails):
        """Test getting email labels."""
        service = EmailService()
        
        labels = service.get_email_labels(db_session)
        assert isinstance(labels, list)
    
    def test_get_email_statistics(self, db_session, sample_emails):
        """Test getting email statistics."""
        service = EmailService()
        
        stats = service.get_email_statistics(db_session)
        assert isinstance(stats, dict)
    
    def test_get_email_analytics(self, db_session, sample_emails):
        """Test getting email analytics."""
        service = EmailService()
        
        analytics = service.get_email_analytics(db_session, days=30)
        assert isinstance(analytics, dict)
        assert "total_emails" in analytics
        assert "read_emails" in analytics
        assert "unread_emails" in analytics
    
    def test_get_email_clusters(self, db_session, sample_emails):
        """Test getting email clusters."""
        service = EmailService()
        
        clusters = service.get_email_clusters(db_session, n_clusters=3)
        assert isinstance(clusters, dict)
        assert "clusters" in clusters
        assert "centroids" in clusters
    
    def test_export_emails(self, db_session, sample_emails):
        """Test exporting emails."""
        service = EmailService()
        email_ids = [sample_emails[0].id, sample_emails[1].id]
        
        # Test JSON export
        json_data = service.export_emails(email_ids, db_session, "json")
        assert isinstance(json_data, str)
        
        # Test CSV export
        csv_data = service.export_emails(email_ids, db_session, "csv")
        assert isinstance(csv_data, str)
        
        # Test EML export
        eml_data = service.export_emails(email_ids, db_session, "eml")
        assert isinstance(eml_data, str)
    
    @patch('app.services.email_service.GmailService')
    def test_sync_user_emails(self, mock_gmail_service, db_session, sample_user):
        """Test syncing user emails."""
        service = EmailService()
        
        # Mock Gmail service
        mock_service = MagicMock()
        mock_service.get_user_emails.return_value = []
        mock_gmail_service.return_value = mock_service
        
        result = service.sync_user_emails(sample_user, db_session, full_sync=False)
        assert isinstance(result, dict)
        assert "success" in result
        assert "sync_type" in result
        assert "emails_synced" in result
        assert "emails_analyzed" in result
        assert "timestamp" in result


class TestGmailService:
    """Test suite for GmailService."""
    
    def test_authenticate_user(self, sample_user):
        """Test user authentication."""
        service = GmailService()
        
        # This would require actual Gmail API credentials
        # For now, we'll test the method exists and returns a boolean
        result = service.authenticate_user(sample_user)
        assert isinstance(result, bool)
    
    @patch('app.services.gmail_service.build')
    def test_get_user_emails(self, mock_build, sample_user):
        """Test getting user emails from Gmail."""
        service = GmailService()
        
        # Mock the Gmail API response
        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_messages.list.return_value.execute.return_value = {
            'messages': [{'id': 'test_id_1'}, {'id': 'test_id_2'}]
        }
        mock_service.users.return_value.messages.return_value = mock_messages
        mock_build.return_value = mock_service
        
        # Mock the get_all_emails method to return a list
        with patch.object(service, 'get_all_emails', return_value=[]):
            emails = service.get_user_emails(sample_user, max_results=10)
            assert isinstance(emails, list)
    
    def test_get_email_attachments(self, sample_user):
        """Test getting email attachments from Gmail."""
        service = GmailService()
        
        # This would require actual Gmail API credentials
        # For now, we'll test the method exists
        attachments = service.get_email_attachments(sample_user, "test_email_id")
        assert isinstance(attachments, list)


class TestSearchService:
    """Test suite for SearchService."""
    
    def test_get_email_threads(self, db_session, sample_emails):
        """Test getting email threads."""
        service = SearchService()
        
        threads = service.get_email_threads(db_session)
        assert isinstance(threads, list)
        
        # Test with specific thread ID
        threads = service.get_email_threads(db_session, thread_id="thread_1")
        assert isinstance(threads, list)


class TestAIService:
    """Test suite for AIService."""
    
    def test_analyze_email_sentiment(self, sample_emails):
        """Test analyzing email sentiment."""
        service = AIService()
        
        email_text = sample_emails[0].body_plain
        sentiment = service.analyze_email_sentiment(email_text)
        assert isinstance(sentiment, int)
        assert sentiment in [-1, 0, 1]  # Negative, neutral, positive
    
    def test_analyze_email_priority(self, sample_emails):
        """Test analyzing email priority."""
        service = AIService()
        
        email_text = sample_emails[0].body_plain
        priority = service.analyze_email_priority(email_text)
        assert isinstance(priority, int)
        assert 1 <= priority <= 10  # Priority score between 1 and 10
    
    def test_categorize_email(self, sample_emails):
        """Test categorizing email."""
        service = AIService()
        
        email_text = sample_emails[0].body_plain
        category = service.categorize_email(email_text)
        assert isinstance(category, str)
        assert category in ["work", "personal", "spam", "newsletter", "other"]
    
    def test_generate_email_summary(self, sample_emails):
        """Test generating email summary."""
        service = AIService()
        
        email_text = sample_emails[0].body_plain
        summary = service.generate_email_summary(email_text)
        assert isinstance(summary, str)
        assert len(summary) > 0
    
    def test_find_similar_emails(self, db_session, sample_emails):
        """Test finding similar emails."""
        service = AIService()
        
        email_text = sample_emails[0].body_plain
        similar_emails = service.find_similar_emails(email_text, db_session, limit=5)
        assert isinstance(similar_emails, list)
    
    def test_cluster_emails(self, db_session, sample_emails):
        """Test clustering emails."""
        service = AIService()
        
        clusters = service.cluster_emails(db_session, n_clusters=3)
        assert isinstance(clusters, dict)
        assert "clusters" in clusters
        assert "centroids" in clusters
    
    def test_extract_keywords(self, sample_emails):
        """Test extracting keywords from email."""
        service = AIService()
        
        email_text = sample_emails[0].body_plain
        keywords = service.extract_keywords(email_text)
        assert isinstance(keywords, list)
    
    def test_detect_language(self, sample_emails):
        """Test detecting email language."""
        service = AIService()
        
        email_text = sample_emails[0].body_plain
        language = service.detect_language(email_text)
        assert isinstance(language, str)
    
    def test_analyze_email_complexity(self, sample_emails):
        """Test analyzing email complexity."""
        service = AIService()
        
        email_text = sample_emails[0].body_plain
        complexity = service.analyze_email_complexity(email_text)
        assert isinstance(complexity, dict)
        assert "readability_score" in complexity
        assert "word_count" in complexity
        assert "sentence_count" in complexity
    
    def test_extract_entities(self, sample_emails):
        """Test extracting entities from email."""
        service = AIService()
        
        email_text = sample_emails[0].body_plain
        entities = service.extract_entities(email_text)
        assert isinstance(entities, dict)
        assert "people" in entities
        assert "organizations" in entities
        assert "locations" in entities
