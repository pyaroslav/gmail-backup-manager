import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database configuration - PostgreSQL only
    DATABASE_URL: str = "postgresql://gmail_user:gmail_password@localhost:5432/gmail_backup"
    
    # Gmail API configuration
    GMAIL_CLIENT_ID: str = "your-gmail-client-id"
    GMAIL_CLIENT_SECRET: str = "your-gmail-client-secret"
    GMAIL_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    
    # JWT configuration
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Redis configuration (for background tasks)
    REDIS_URL: str = "redis://localhost:6379"
    
    # Sync configuration
    SYNC_BATCH_SIZE: int = 100
    SYNC_INTERVAL_MINUTES: int = 5
    
    # AI Analysis settings
    AI_ANALYSIS_ENABLED: bool = True
    BATCH_ANALYSIS_SIZE: int = 100
    SENTIMENT_ANALYSIS_ENABLED: bool = True
    CATEGORIZATION_ENABLED: bool = True
    SUMMARIZATION_ENABLED: bool = True
    PRIORITY_SCORING_ENABLED: bool = True
    
    # Search settings
    SEARCH_RESULTS_PER_PAGE: int = 50
    MAX_SEARCH_RESULTS: int = 1000
    ELASTICSEARCH_URL: Optional[str] = None
    
    # File storage settings
    ATTACHMENTS_DIR: str = "attachments"
    MAX_FILE_SIZE_MB: int = 50
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    
    # CORS settings
    CORS_ORIGINS: str = "*"
    CORS_ALLOW_CREDENTIALS: bool = True
    
    @property
    def cors_origins_list(self) -> list:
        """Convert CORS_ORIGINS string to list"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Background tasks
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Environment-specific overrides
if os.getenv("ENVIRONMENT") == "production":
    settings.DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)
    settings.SECRET_KEY = os.getenv("SECRET_KEY", settings.SECRET_KEY)
    settings.CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3002")
    settings.LOG_LEVEL = "WARNING"
elif os.getenv("ENVIRONMENT") == "development":
    settings.LOG_LEVEL = "DEBUG"
    settings.CORS_ORIGINS = "http://localhost:3002,http://127.0.0.1:3002"
