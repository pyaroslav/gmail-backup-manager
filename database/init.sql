-- Database initialization script for Gmail Backup Manager
-- This script runs when the PostgreSQL container starts for the first time

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The actual tables will be created by SQLAlchemy/Alembic
-- This file can be used for any additional database setup

-- Create the database user if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'gmail_user') THEN
        CREATE ROLE gmail_user WITH LOGIN PASSWORD 'gmail_password';
    END IF;
END
$$;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE gmail_backup TO gmail_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gmail_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gmail_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO gmail_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO gmail_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO gmail_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO gmail_user;
