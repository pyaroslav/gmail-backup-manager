# Gmail Backup Manager

A comprehensive Gmail backup and management system with real-time synchronization, analytics, and a modern web interface.

## 🚀 Features

- **Real-time Gmail Synchronization**: Automatic backup of emails with progress tracking
- **Modern Web Interface**: Responsive dashboard with dark mode support
- **Email Analytics**: Detailed statistics and insights about your email data
- **Advanced Search**: Full-text search across all backed-up emails
- **Database Management**: PostgreSQL backend with efficient data storage
- **Sync Monitoring**: Real-time sync status and progress tracking
- **Settings Management**: Configurable sync intervals and preferences

## 📁 Project Structure

```
gmail-backup-manager/
├── backend/                 # Python FastAPI backend
│   ├── app/                # Main application code
│   │   ├── api/           # API endpoints
│   │   ├── models/        # Database models
│   │   ├── services/      # Business logic
│   │   └── utils/         # Utility functions
│   ├── config/            # Configuration files
│   ├── tests/             # Test files
│   ├── main.py            # FastAPI application entry point
│   ├── requirements.txt   # Python dependencies
│   └── Dockerfile         # Backend container
├── frontend/              # Node.js frontend server
│   ├── index.html         # Main web interface
│   ├── script.js          # Frontend JavaScript
│   ├── styles.css         # Styling
│   ├── server.js          # Node.js server
│   ├── package.json       # Node.js dependencies
│   └── Dockerfile.node    # Frontend container
├── database/              # Database configuration
│   ├── init.sql          # Database initialization
│   └── postgresql.conf   # PostgreSQL configuration
├── nginx/                 # Nginx configuration
├── config/                # Application configuration
├── docker-compose.yml     # Docker orchestration
├── setup.sh              # Setup script
└── README.md             # This file
```

## 🛠️ Setup Instructions

### Prerequisites

- Docker and Docker Compose
- Python 3.8+
- Node.js 16+
- PostgreSQL (or use Docker)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd gmail-backup-manager
   ```

2. **Set up environment variables**
   ```bash
   cp backend/env.example backend/.env
   # Edit backend/.env with your Gmail API credentials
   ```

3. **Start the application**
   ```bash
   # Using Docker (recommended)
   docker-compose up -d
   
   # Or manually
   ./setup.sh
   ```

4. **Access the application**
   - Frontend: http://localhost:3002
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Manual Setup

1. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```

2. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   node server.js
   ```

3. **Database Setup**
   ```bash
   # Start PostgreSQL
   docker run -d --name postgres \
     -e POSTGRES_PASSWORD=password \
     -e POSTGRES_DB=gmail_backup \
     -p 5432:5432 \
     postgres:13
   
   # Initialize database
   psql -h localhost -U postgres -d gmail_backup -f database/init.sql
   ```

## 🔧 Configuration

### Gmail API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Gmail API
4. Create OAuth 2.0 credentials
5. Download credentials and save as `backend/credentials.json`
6. Update `backend/.env` with your credentials

### Environment Variables

Key environment variables in `backend/.env`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/gmail_backup
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_REDIRECT_URI=http://localhost:8000/auth/callback
```

## 📊 Features Overview

### Dashboard
- Email count statistics
- Sync status monitoring
- Recent email preview
- Quick actions

### Email Management
- Browse all backed-up emails
- Search functionality
- Email categorization
- Read/unread status

### Analytics
- Email activity trends
- Sender statistics
- Storage usage
- Processing status

### Sync Management
- Manual sync initiation
- Sync progress tracking
- Error monitoring
- Configuration options

## 🔒 Security

- OAuth 2.0 authentication with Gmail
- Secure token storage
- Environment-based configuration
- No email deletion (read-only access)

## 🐳 Docker Deployment

The application includes Docker support for easy deployment:

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📝 API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the documentation
2. Review existing issues
3. Create a new issue with detailed information

---

**Note**: This application only reads emails and does not delete any emails from Gmail accounts.
