#!/bin/bash

# Gmail Backup & Management System Setup Script
# This script helps you set up the application for the first time

set -e

echo "Gmail Backup & Management System Setup"
echo "=========================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
 echo "ERROR: Docker is not installed. Please install Docker first."
 exit 1
fi

if ! command -v docker-compose &> /dev/null; then
 echo "ERROR: Docker Compose is not installed. Please install Docker Compose first."
 exit 1
fi

echo "Docker and Docker Compose are installed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
 echo "Creating .env file..."
 cat > .env << EOF
# Gmail API Configuration
GMAIL_CLIENT_ID=your-gmail-client-id-here
GMAIL_CLIENT_SECRET=your-gmail-client-secret-here

# Security
SECRET_KEY=$(openssl rand -hex 32)

# Environment
ENVIRONMENT=development

# Database (PostgreSQL)
DATABASE_URL=postgresql://gmail_user:gmail_password@localhost:5432/gmail_backup

# Redis
REDIS_URL=redis://localhost:6379
EOF
 echo "Created .env file"
else
 echo ".env file already exists"
fi

# Create config directory if it doesn't exist
mkdir -p config

# Create credentials.json template
if [ ! -f config/credentials.json ]; then
 echo "Creating Gmail API credentials template..."
 cat > config/credentials.json << EOF
{
 "installed": {
 "client_id": "your-gmail-client-id-here",
 "project_id": "your-project-id",
 "auth_uri": "https://accounts.google.com/o/oauth2/auth",
 "token_uri": "https://oauth2.googleapis.com/token",
 "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
 "client_secret": "your-gmail-client-secret-here",
 "redirect_uris": ["http://localhost"]
 }
}
EOF
 echo "Created Gmail API credentials template"
else
 echo "Gmail API credentials already exist"
fi

# Create nginx configuration
mkdir -p nginx
if [ ! -f nginx/nginx.conf ]; then
 echo "Creating Nginx configuration..."
 cat > nginx/nginx.conf << EOF
events {
 worker_connections 1024;
}

http {
 upstream backend {
 server backend:8000;
 }

 upstream frontend {
 server frontend:3002;
 }

 server {
 listen 80;
 server_name localhost;

 # Frontend
 location / {
 proxy_pass http://frontend;
 proxy_set_header Host \$host;
 proxy_set_header X-Real-IP \$remote_addr;
 proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
 proxy_set_header X-Forwarded-Proto \$scheme;
 }

 # Backend API
 location /api/ {
 proxy_pass http://backend;
 proxy_set_header Host \$host;
 proxy_set_header X-Real-IP \$remote_addr;
 proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
 proxy_set_header X-Forwarded-Proto \$scheme;
 }

 # Health check
 location /health {
 proxy_pass http://backend;
 }
 }
}
EOF
 echo "Created Nginx configuration"
else
 echo "Nginx configuration already exists"
fi

# Create database initialization script
mkdir -p database
if [ ! -f database/init.sql ]; then
 echo "Creating database initialization script..."
 cat > database/init.sql << EOF
-- Database initialization script
-- This script runs when the PostgreSQL container starts for the first time

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- The actual tables will be created by SQLAlchemy
-- This file can be used for any additional database setup
EOF
 echo "Created database initialization script"
else
 echo "Database initialization script already exists"
fi

echo ""
echo "Setup Instructions:"
echo "====================="
echo ""
echo "1. Configure Gmail API:"
echo " - Go to https://console.cloud.google.com/"
echo " - Create a new project or select existing one"
echo " - Enable Gmail API"
echo " - Create OAuth 2.0 credentials"
echo " - Download credentials and save as config/credentials.json"
echo " - Update GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env"
echo ""
echo "2. Start the application:"
echo " docker-compose up -d"
echo ""
echo "3. Access the application:"
echo " - Frontend: http://localhost:3002"
echo " - Backend API: http://localhost:8000"
echo " - API Documentation: http://localhost:8000/docs"
echo ""
echo "4. First-time setup:"
echo " - Go to the Sync page to connect your Gmail account"
echo " - Start a full sync to download all emails"
echo " - Wait for AI analysis to complete"
echo ""
echo "Configuration files created:"
echo " - .env (environment variables)"
echo " - config/credentials.json (Gmail API credentials template)"
echo " - nginx/nginx.conf (reverse proxy configuration)"
echo " - database/init.sql (database initialization)"
echo ""
echo "WARNING: Important:"
echo " - Update the Gmail API credentials before starting"
echo " - Change the SECRET_KEY in production"
echo " - Review and adjust settings in .env as needed"
echo ""
echo "Setup complete! Follow the instructions above to get started."
