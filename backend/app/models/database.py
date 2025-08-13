from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL - PostgreSQL only
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://gmail_user:gmail_password@localhost:5432/gmail_backup"
)

# Ensure we're using PostgreSQL
if not DATABASE_URL.startswith("postgresql"):
    raise ValueError("Only PostgreSQL is supported. Please set DATABASE_URL to a PostgreSQL connection string.")

# Create engine with optimized settings for PostgreSQL
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=30,  # Increased from 20 to handle sync operations
    max_overflow=50,  # Increased from 30 to handle peak load during sync
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=1800,  # Recycle connections after 30 minutes (reduced from 1 hour)
    pool_timeout=30,  # Timeout for getting connection from pool
    echo=False,  # Set to True for SQL debugging
    # PostgreSQL-specific optimizations
    connect_args={
        "application_name": "gmail_backup_manager",
        "options": "-c timezone=utc -c statement_timeout=600000"  # 10 minutes timeout (increased from 5)
    }
)

# Create SessionLocal class with optimized settings
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    expire_on_commit=False  # Keep objects loaded after commit
)

# Create Base class
Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create all tables
def create_tables():
    Base.metadata.create_all(bind=engine)

# Function to drop all tables (use with caution)
def drop_tables():
    Base.metadata.drop_all(bind=engine)
