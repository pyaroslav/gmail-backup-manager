#!/usr/bin/env python3
"""
Database initialization script for Gmail Backup Manager
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.database import Base
from app.models.user import User, UserSession
from app.models.email import Email, EmailAttachment
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config.settings import settings

def init_database():
    """Initialize the database with all tables"""
    print("Initializing database...")
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")
    
    # Create a test user
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if test user already exists
        existing_user = db.query(User).filter(User.email == "test@example.com").first()
        if not existing_user:
            # Create test user
            test_user = User(
                email="test@example.com",
                name="Test User",
                gmail_access_token="test_token",
                gmail_refresh_token="test_refresh_token",
                sync_enabled=True,
                is_active=True
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            print(f"✅ Test user created: {test_user.email}")
        else:
            print(f"✅ Test user already exists: {existing_user.email}")
            
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        db.rollback()
    finally:
        db.close()
    
    print("✅ Database initialization complete!")

if __name__ == "__main__":
    init_database()
