# Security Improvements for Gmail Backup Manager

## Current Security Assessment

### ✅ Good Security Practices
- OAuth 2.0 authentication with Gmail
- Read-only Gmail access (no email deletion)
- Environment-based configuration
- Docker containerization with non-root users

### 🔧 Recommended Security Enhancements

## 1. Environment Variables & Secrets Management

### Current Issues
- Hardcoded secrets in docker-compose.yml
- Default secret keys in settings
- Credentials stored in plain text

### Improvements
```yaml
# docker-compose.yml - Use Docker secrets or external secrets
services:
  backend:
    environment:
      - SECRET_KEY_FILE=/run/secrets/secret_key
      - GMAIL_CLIENT_ID_FILE=/run/secrets/gmail_client_id
      - GMAIL_CLIENT_SECRET_FILE=/run/secrets/gmail_client_secret
    secrets:
      - secret_key
      - gmail_client_id
      - gmail_client_secret

secrets:
  secret_key:
    external: true
  gmail_client_id:
    external: true
  gmail_client_secret:
    external: true
```

## 2. Database Security

### Current Issues
- Plain text database passwords
- No SSL/TLS for database connections
- Default PostgreSQL configuration

### Improvements
```python
# backend/app/models/database.py
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://gmail_user:gmail_password@localhost:5432/gmail_backup?sslmode=require"
)

# Add connection encryption
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "sslmode": "require",
        "application_name": "gmail_backup_manager",
        "options": "-c timezone=utc -c statement_timeout=600000"
    }
)
```

## 3. API Security

### Current Issues
- No rate limiting implementation
- CORS too permissive
- No input validation on some endpoints

### Improvements
```python
# backend/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add rate limiting to endpoints
@app.get("/api/v1/emails")
@limiter.limit("100/minute")
async def get_emails(request: Request):
    # Implementation
    pass
```

## 4. Frontend Security

### Current Issues
- Direct database access from frontend
- No CSRF protection
- No content security policy

### Improvements
```javascript
// frontend/server.js - Add security headers
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'", "https://cdnjs.cloudflare.com"],
            scriptSrc: ["'self'", "https://cdn.jsdelivr.net"],
            imgSrc: ["'self'", "data:", "https:"],
        },
    },
    hsts: {
        maxAge: 31536000,
        includeSubDomains: true,
        preload: true
    }
}));

// Add CSRF protection
app.use(csrf());
```

## 5. Container Security

### Current Issues
- Running as root in some containers
- No security scanning
- No resource limits

### Improvements
```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Set resource limits
USER appuser

# Add security scanning
RUN pip install safety && \
    safety check

# Add health checks
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

## 6. Network Security

### Current Issues
- No network segmentation
- HTTP traffic (no HTTPS)
- No firewall rules

### Improvements
```yaml
# docker-compose.yml
networks:
  gmail-backup-network:
    driver: bridge
    internal: true  # Isolate from external networks
  frontend-network:
    driver: bridge
    internal: false  # Allow external access only to frontend

services:
  backend:
    networks:
      - gmail-backup-network
  frontend:
    networks:
      - gmail-backup-network
      - frontend-network
```

## 7. Logging & Monitoring Security

### Current Issues
- Sensitive data in logs
- No log encryption
- No audit trail

### Improvements
```python
# backend/app/utils/logging.py
import logging
import json
from datetime import datetime

class SecureLogger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def log_email_access(self, user_id: int, email_id: int, action: str):
        """Log email access for audit trail"""
        audit_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "email_id": email_id,
            "action": action,
            "ip_address": "REDACTED",  # Add IP tracking
            "user_agent": "REDACTED"   # Add user agent tracking
        }
        self.logger.info(f"AUDIT: {json.dumps(audit_log)}")
    
    def sanitize_log_data(self, data: dict) -> dict:
        """Remove sensitive data from logs"""
        sensitive_fields = ['password', 'token', 'secret', 'credential']
        sanitized = data.copy()
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = '***REDACTED***'
        return sanitized
```

## 8. Data Encryption

### Current Issues
- No encryption at rest
- No encryption in transit for internal communication
- Plain text email storage

### Improvements
```python
# backend/app/utils/encryption.py
from cryptography.fernet import Fernet
import base64

class EmailEncryption:
    def __init__(self, key: str):
        self.cipher = Fernet(key)
    
    def encrypt_email_content(self, content: str) -> str:
        """Encrypt email content before storage"""
        return self.cipher.encrypt(content.encode()).decode()
    
    def decrypt_email_content(self, encrypted_content: str) -> str:
        """Decrypt email content for display"""
        return self.cipher.decrypt(encrypted_content.encode()).decode()
```

## 9. Authentication & Authorization

### Current Issues
- No session management
- No role-based access control
- No multi-factor authentication

### Improvements
```python
# backend/app/services/auth_service.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

class AuthService:
    def __init__(self):
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
    
    async def verify_user_permissions(self, user_id: int, resource: str, action: str) -> bool:
        """Verify user has permission to perform action on resource"""
        # Implement RBAC logic
        pass
    
    async def require_mfa(self, user_id: int) -> bool:
        """Check if user needs MFA for sensitive operations"""
        # Implement MFA logic
        pass
```

## 10. Security Headers & HTTPS

### Current Issues
- No HTTPS in development
- Missing security headers
- No HSTS

### Improvements
```nginx
# nginx/nginx.conf
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
}
```

## Implementation Priority

1. **High Priority**: Environment variables, database SSL, rate limiting
2. **Medium Priority**: Container security, logging improvements, HTTPS
3. **Low Priority**: MFA, advanced encryption, network segmentation

## Security Testing

```bash
# Run security scans
docker run --rm -v $(pwd):/app owasp/zap2docker-stable zap-baseline.py -t http://localhost:3002

# Check for vulnerabilities
safety check

# Audit dependencies
pip-audit

# Container security scan
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image gmail-backup-backend:latest
```
