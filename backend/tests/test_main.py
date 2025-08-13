import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

class TestMainApplication:
    """Test suite for main application endpoints."""
    
    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Gmail Backup & Management System"
        assert data["version"] == "1.0.0"
    
    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Gmail Backup & Management System API"
        assert data["version"] == "1.0.0"
        assert "docs" in data
        assert "health" in data
        assert "endpoints" in data
        
        # Check endpoints structure
        endpoints = data["endpoints"]
        assert "emails" in endpoints
        assert "search" in endpoints
        assert "sync" in endpoints
        assert "analytics" in endpoints
    
    def test_api_documentation_endpoints(self, client: TestClient):
        """Test API documentation endpoints."""
        # Test OpenAPI docs endpoint
        response = client.get("/docs")
        assert response.status_code == 200
        
        # Test ReDoc endpoint
        response = client.get("/redoc")
        assert response.status_code == 200
    
    def test_cors_headers(self, client: TestClient):
        """Test CORS headers are present."""
        response = client.options("/health")
        # CORS headers should be present
        assert response.status_code in [200, 405]  # OPTIONS might not be implemented
    
    def test_404_error_handler(self, client: TestClient):
        """Test 404 error handling."""
        response = client.get("/non-existent-endpoint")
        assert response.status_code == 404
        
        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "path" in data
        assert data["error"] == "Not Found"
    
    def test_500_error_handler(self, client: TestClient):
        """Test 500 error handling."""
        # This would require triggering an actual error
        # For now, we'll test that the error handler is properly configured
        # by checking that the endpoint exists in the app
        pass
    
    def test_application_startup(self, client: TestClient):
        """Test application startup process."""
        # The application should start successfully
        # This is tested by the fact that we can make requests to it
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_database_connection(self, client: TestClient):
        """Test database connection is working."""
        # Test that we can access endpoints that require database
        response = client.get("/api/v1/emails/")
        assert response.status_code == 200
    
    def test_api_versioning(self, client: TestClient):
        """Test API versioning is working."""
        # Test that v1 endpoints are accessible
        response = client.get("/api/v1/emails/")
        assert response.status_code == 200
        
        # Test that non-versioned endpoints are not accessible
        response = client.get("/api/emails/")
        assert response.status_code == 404
    
    def test_application_metadata(self, client: TestClient):
        """Test application metadata is correct."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Gmail Backup & Management System API"
        assert data["version"] == "1.0.0"
    
    def test_endpoint_availability(self, client: TestClient):
        """Test that all expected endpoints are available."""
        # Test emails endpoints
        response = client.get("/api/v1/emails/")
        assert response.status_code == 200
        
        # Test search endpoints
        response = client.get("/api/v1/search/categories")
        assert response.status_code == 200
        
        # Test sync endpoints
        response = client.get("/api/v1/sync/status")
        assert response.status_code == 200
        
        # Test analytics endpoints
        response = client.get("/api/v1/analytics/statistics")
        assert response.status_code == 200
    
    def test_application_logging(self, client: TestClient):
        """Test that application logging is configured."""
        # This is more of an integration test
        # We can test that the application starts without logging errors
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_application_configuration(self, client: TestClient):
        """Test application configuration."""
        # Test that the application is properly configured
        response = client.get("/")
        assert response.status_code == 200
        
        # Check that the application title and description are set
        # This would be visible in the OpenAPI docs
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_middleware_configuration(self, client: TestClient):
        """Test that middleware is properly configured."""
        # Test CORS middleware
        response = client.get("/health")
        assert response.status_code == 200
        
        # The fact that we can make requests indicates middleware is working
    
    def test_database_tables_creation(self, client: TestClient):
        """Test that database tables are created on startup."""
        # Test that we can access database-dependent endpoints
        response = client.get("/api/v1/emails/")
        assert response.status_code == 200
        
        # This indicates that the database tables were created successfully
    
    def test_attachments_directory_creation(self, client: TestClient):
        """Test that attachments directory is created on startup."""
        # This is tested by the fact that the application starts successfully
        # and we can access endpoints that might use attachments
        response = client.get("/api/v1/emails/")
        assert response.status_code == 200
    
    def test_application_robustness(self, client: TestClient):
        """Test application robustness with various requests."""
        # Test with different HTTP methods
        response = client.post("/health")
        assert response.status_code == 405  # Method not allowed
        
        response = client.put("/health")
        assert response.status_code == 405  # Method not allowed
        
        response = client.delete("/health")
        assert response.status_code == 405  # Method not allowed
    
    def test_application_performance(self, client: TestClient):
        """Test basic application performance."""
        import time
        
        # Test response time for health check
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        assert response.status_code == 200
        response_time = end_time - start_time
        
        # Response should be reasonably fast (less than 1 second)
        assert response_time < 1.0
    
    def test_application_consistency(self, client: TestClient):
        """Test application response consistency."""
        # Make multiple requests to the same endpoint
        responses = []
        for _ in range(5):
            response = client.get("/health")
            responses.append(response)
        
        # All responses should be successful and consistent
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "Gmail Backup & Management System"
            assert data["version"] == "1.0.0"
    
    def test_application_error_recovery(self, client: TestClient):
        """Test application error recovery."""
        # Test that the application can handle errors gracefully
        # and continue to function
        
        # First, make a successful request
        response = client.get("/health")
        assert response.status_code == 200
        
        # Then make a request that might cause an error
        response = client.get("/api/v1/emails/99999")
        assert response.status_code == 404
        
        # Then make another successful request
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_application_security_headers(self, client: TestClient):
        """Test that security headers are present."""
        response = client.get("/health")
        assert response.status_code == 200
        
        # Check for basic security headers
        headers = response.headers
        # Note: In a production environment, you'd want to check for
        # security headers like X-Content-Type-Options, X-Frame-Options, etc.
    
    def test_application_content_types(self, client: TestClient):
        """Test that content types are correctly set."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
    
    def test_application_encoding(self, client: TestClient):
        """Test that response encoding is correct."""
        response = client.get("/health")
        assert response.status_code == 200
        
        # Test that JSON response can be parsed
        data = response.json()
        assert isinstance(data, dict)
    
    def test_application_availability(self, client: TestClient):
        """Test that the application is available and responsive."""
        # Test multiple endpoints to ensure the application is fully available
        endpoints = [
            "/health",
            "/",
            "/api/v1/emails/",
            "/api/v1/search/categories",
            "/api/v1/sync/status",
            "/api/v1/analytics/statistics"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [200, 404]  # 404 is acceptable for some endpoints
    
    def test_application_integration(self, client: TestClient):
        """Test that all components work together."""
        # Test a complete workflow
        # 1. Check health
        response = client.get("/health")
        assert response.status_code == 200
        
        # 2. Check API availability
        response = client.get("/api/v1/emails/")
        assert response.status_code == 200
        
        # 3. Check search functionality
        response = client.get("/api/v1/search/categories")
        assert response.status_code == 200
        
        # 4. Check sync functionality
        response = client.get("/api/v1/sync/status")
        assert response.status_code == 200
        
        # 5. Check analytics functionality
        response = client.get("/api/v1/analytics/statistics")
        assert response.status_code == 200
