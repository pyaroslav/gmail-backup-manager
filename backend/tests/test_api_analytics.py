import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

class TestAnalyticsAPI:
    """Test suite for analytics API endpoints."""
    
    def test_get_email_analytics_overview(self, client: TestClient, sample_emails):
        """Test getting email analytics overview."""
        response = client.get("/api/v1/analytics/overview?days=30")
        assert response.status_code == 200
        
        data = response.json()
        assert "period_days" in data
        assert "total_emails" in data
        assert "read_emails" in data
        assert "unread_emails" in data
        assert "starred_emails" in data
        assert "important_emails" in data
        assert "category_distribution" in data
        assert "sentiment_distribution" in data
        assert "top_senders" in data
        
        # Check data types
        assert isinstance(data["period_days"], int)
        assert isinstance(data["total_emails"], int)
        assert isinstance(data["read_emails"], int)
        assert isinstance(data["unread_emails"], int)
        assert isinstance(data["starred_emails"], int)
        assert isinstance(data["important_emails"], int)
        assert isinstance(data["category_distribution"], dict)
        assert isinstance(data["sentiment_distribution"], dict)
        assert isinstance(data["top_senders"], list)
    
    def test_get_email_analytics_different_periods(self, client: TestClient, sample_emails):
        """Test getting email analytics for different time periods."""
        periods = [7, 30, 90, 365]
        
        for days in periods:
            response = client.get(f"/api/v1/analytics/overview?days={days}")
            assert response.status_code == 200
            
            data = response.json()
            assert data["period_days"] == days
    
    def test_get_email_analytics_invalid_period(self, client: TestClient):
        """Test getting email analytics with invalid period."""
        response = client.get("/api/v1/analytics/overview?days=0")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/v1/analytics/overview?days=366")
        assert response.status_code == 422  # Validation error
    
    def test_get_email_statistics(self, client: TestClient, sample_emails):
        """Test getting comprehensive email statistics."""
        response = client.get("/api/v1/analytics/statistics")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        
        # Check for expected statistics fields
        expected_fields = [
            "total_emails", "total_attachments", "total_storage_mb",
            "avg_email_size_chars", "processed_emails", "processing_rate_percent"
        ]
        
        for field in expected_fields:
            assert field in data
    
    def test_get_email_clusters(self, client: TestClient, sample_emails):
        """Test getting email clusters."""
        response = client.get("/api/v1/analytics/clusters?n_clusters=3")
        assert response.status_code == 200
        
        data = response.json()
        assert "clusters" in data
        assert "centroids" in data
        assert isinstance(data["clusters"], list)
        assert isinstance(data["centroids"], list)
    
    def test_get_email_clusters_invalid_count(self, client: TestClient):
        """Test getting email clusters with invalid cluster count."""
        response = client.get("/api/v1/analytics/clusters?n_clusters=1")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/v1/analytics/clusters?n_clusters=21")
        assert response.status_code == 422  # Validation error
    
    def test_get_email_trends(self, client: TestClient, sample_emails):
        """Test getting email trends over time."""
        response = client.get("/api/v1/analytics/trends?days=30")
        assert response.status_code == 200
        
        data = response.json()
        assert "trends" in data
        assert isinstance(data["trends"], list)
        
        if data["trends"]:
            trend_item = data["trends"][0]
            assert "date" in trend_item
            assert "total" in trend_item
            assert "read" in trend_item
            assert "unread" in trend_item
            assert "starred" in trend_item
            assert "important" in trend_item
    
    def test_get_email_trends_invalid_period(self, client: TestClient):
        """Test getting email trends with invalid period."""
        response = client.get("/api/v1/analytics/trends?days=6")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/v1/analytics/trends?days=366")
        assert response.status_code == 422  # Validation error
    
    def test_get_category_analytics(self, client: TestClient, sample_emails):
        """Test getting detailed category analytics."""
        response = client.get("/api/v1/analytics/categories")
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
        
        if data["categories"]:
            category_item = data["categories"][0]
            assert "category" in category_item
            assert "count" in category_item
            assert "avg_sentiment" in category_item
            assert "avg_priority" in category_item
    
    def test_get_sender_analytics(self, client: TestClient, sample_emails):
        """Test getting sender analytics."""
        response = client.get("/api/v1/analytics/senders?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "senders" in data
        assert isinstance(data["senders"], list)
        
        if data["senders"]:
            sender_item = data["senders"][0]
            assert "sender" in sender_item
            assert "count" in sender_item
            assert "avg_sentiment" in sender_item
            assert "avg_priority" in sender_item
            assert "read_count" in sender_item
            assert "unread_count" in sender_item
            assert "read_rate" in sender_item
    
    def test_get_sender_analytics_invalid_limit(self, client: TestClient):
        """Test getting sender analytics with invalid limit."""
        response = client.get("/api/v1/analytics/senders?limit=0")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/v1/analytics/senders?limit=101")
        assert response.status_code == 422  # Validation error
    
    def test_get_sentiment_analytics(self, client: TestClient, sample_emails):
        """Test getting sentiment analysis insights."""
        response = client.get("/api/v1/analytics/sentiment")
        assert response.status_code == 200
        
        data = response.json()
        assert "sentiment" in data
        sentiment_data = data["sentiment"]
        
        assert "positive" in sentiment_data
        assert "neutral" in sentiment_data
        assert "negative" in sentiment_data
        assert "total" in sentiment_data
        assert "positive_percent" in sentiment_data
        assert "neutral_percent" in sentiment_data
        assert "negative_percent" in sentiment_data
        
        # Check that percentages add up to approximately 100%
        total_percent = (
            sentiment_data["positive_percent"] +
            sentiment_data["neutral_percent"] +
            sentiment_data["negative_percent"]
        )
        assert abs(total_percent - 100) < 1  # Allow for rounding errors
    
    def test_get_priority_analytics(self, client: TestClient, sample_emails):
        """Test getting priority analysis insights."""
        response = client.get("/api/v1/analytics/priority")
        assert response.status_code == 200
        
        data = response.json()
        assert "priority" in data
        priority_data = data["priority"]
        
        assert "high_priority" in priority_data
        assert "medium_priority" in priority_data
        assert "low_priority" in priority_data
        assert "total" in priority_data
        assert "distribution" in priority_data
        assert "high_priority_percent" in priority_data
        assert "medium_priority_percent" in priority_data
        assert "low_priority_percent" in priority_data
        
        # Check that percentages add up to approximately 100%
        total_percent = (
            priority_data["high_priority_percent"] +
            priority_data["medium_priority_percent"] +
            priority_data["low_priority_percent"]
        )
        assert abs(total_percent - 100) < 1  # Allow for rounding errors
    
    def test_get_activity_analytics(self, client: TestClient, sample_emails):
        """Test getting email activity patterns."""
        response = client.get("/api/v1/analytics/activity?days=7")
        assert response.status_code == 200
        
        data = response.json()
        assert "hourly_activity" in data
        assert "daily_activity" in data
        assert "most_active_hours" in data
        assert "most_active_days" in data
        
        # Check hourly activity structure
        hourly_activity = data["hourly_activity"]
        assert isinstance(hourly_activity, list)
        assert len(hourly_activity) == 24  # 24 hours
        
        if hourly_activity:
            hour_item = hourly_activity[0]
            assert "hour" in hour_item
            assert "count" in hour_item
        
        # Check daily activity structure
        daily_activity = data["daily_activity"]
        assert isinstance(daily_activity, list)
        assert len(daily_activity) == 7  # 7 days
        
        if daily_activity:
            day_item = daily_activity[0]
            assert "day" in day_item
            assert "count" in day_item
    
    def test_get_activity_analytics_invalid_period(self, client: TestClient):
        """Test getting activity analytics with invalid period."""
        response = client.get("/api/v1/analytics/activity?days=0")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/v1/analytics/activity?days=31")
        assert response.status_code == 422  # Validation error
    
    def test_get_performance_metrics(self, client: TestClient, sample_emails, sample_attachments):
        """Test getting system performance metrics."""
        response = client.get("/api/v1/analytics/performance")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_emails" in data
        assert "total_attachments" in data
        assert "total_storage_mb" in data
        assert "avg_email_size_chars" in data
        assert "processed_emails" in data
        assert "processing_rate_percent" in data
        assert "unprocessed_emails" in data
        
        # Check data types
        assert isinstance(data["total_emails"], int)
        assert isinstance(data["total_attachments"], int)
        assert isinstance(data["total_storage_mb"], (int, float))
        assert isinstance(data["avg_email_size_chars"], (int, float))
        assert isinstance(data["processed_emails"], int)
        assert isinstance(data["processing_rate_percent"], (int, float))
        assert isinstance(data["unprocessed_emails"], int)
    
    def test_get_email_insights(self, client: TestClient, sample_emails):
        """Test getting AI-generated insights about email patterns."""
        response = client.get("/api/v1/analytics/insights")
        assert response.status_code == 200
        
        data = response.json()
        assert "insights" in data
        assert isinstance(data["insights"], list)
        
        if data["insights"]:
            insight_item = data["insights"][0]
            assert "type" in insight_item
            assert "title" in insight_item
            assert "description" in insight_item
            assert "severity" in insight_item
            
            # Check severity values
            assert insight_item["severity"] in ["info", "warning", "error"]
    
    def test_analytics_data_consistency(self, client: TestClient, sample_emails):
        """Test that analytics data is consistent across calls."""
        # Get analytics multiple times
        response1 = client.get("/api/v1/analytics/overview?days=30")
        response2 = client.get("/api/v1/analytics/overview?days=30")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Data should be consistent
        assert data1["total_emails"] == data2["total_emails"]
        assert data1["read_emails"] == data2["read_emails"]
        assert data1["unread_emails"] == data2["unread_emails"]
    
    def test_analytics_with_empty_data(self, client: TestClient):
        """Test analytics endpoints with no email data."""
        # Test with empty database
        response = client.get("/api/v1/analytics/overview?days=30")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_emails"] == 0
        assert data["read_emails"] == 0
        assert data["unread_emails"] == 0
    
    def test_analytics_date_range_validation(self, client: TestClient, sample_emails):
        """Test analytics date range validation."""
        # Test with very large date range
        response = client.get("/api/v1/analytics/trends?days=365")
        assert response.status_code == 200
        
        # Test with minimum valid range
        response = client.get("/api/v1/analytics/trends?days=7")
        assert response.status_code == 200
    
    def test_analytics_cluster_validation(self, client: TestClient, sample_emails):
        """Test analytics cluster validation."""
        # Test with minimum valid clusters
        response = client.get("/api/v1/analytics/clusters?n_clusters=2")
        assert response.status_code == 200
        
        # Test with maximum valid clusters
        response = client.get("/api/v1/analytics/clusters?n_clusters=20")
        assert response.status_code == 200
    
    def test_analytics_sender_limit_validation(self, client: TestClient, sample_emails):
        """Test analytics sender limit validation."""
        # Test with minimum valid limit
        response = client.get("/api/v1/analytics/senders?limit=1")
        assert response.status_code == 200
        
        # Test with maximum valid limit
        response = client.get("/api/v1/analytics/senders?limit=100")
        assert response.status_code == 200
    
    def test_analytics_percentage_calculations(self, client: TestClient, sample_emails):
        """Test that percentage calculations are mathematically correct."""
        # Test sentiment percentages
        response = client.get("/api/v1/analytics/sentiment")
        assert response.status_code == 200
        
        data = response.json()
        sentiment_data = data["sentiment"]
        
        if sentiment_data["total"] > 0:
            # Check that percentages are calculated correctly
            expected_positive_percent = (sentiment_data["positive"] / sentiment_data["total"]) * 100
            expected_neutral_percent = (sentiment_data["neutral"] / sentiment_data["total"]) * 100
            expected_negative_percent = (sentiment_data["negative"] / sentiment_data["total"]) * 100
            
            assert abs(sentiment_data["positive_percent"] - expected_positive_percent) < 0.1
            assert abs(sentiment_data["neutral_percent"] - expected_neutral_percent) < 0.1
            assert abs(sentiment_data["negative_percent"] - expected_negative_percent) < 0.1
    
    def test_analytics_data_types(self, client: TestClient, sample_emails):
        """Test that analytics data has correct types."""
        response = client.get("/api/v1/analytics/overview?days=30")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check integer fields
        integer_fields = ["period_days", "total_emails", "read_emails", "unread_emails", 
                         "starred_emails", "important_emails"]
        for field in integer_fields:
            assert isinstance(data[field], int)
        
        # Check dictionary fields
        dict_fields = ["category_distribution", "sentiment_distribution"]
        for field in dict_fields:
            assert isinstance(data[field], dict)
        
        # Check list fields
        list_fields = ["top_senders"]
        for field in list_fields:
            assert isinstance(data[field], list)
    
    def test_analytics_error_handling(self, client: TestClient):
        """Test analytics error handling."""
        # Test with invalid query parameters
        response = client.get("/api/v1/analytics/overview?days=invalid")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/v1/analytics/clusters?n_clusters=invalid")
        assert response.status_code == 422  # Validation error
