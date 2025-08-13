# Gmail Backup & Management System

A comprehensive application for backing up and managing Gmail emails with advanced search, filtering, and organization capabilities.

## Features

- **Email Backup**: Download all existing and future emails from Gmail
- **Database Storage**: Store emails in PostgreSQL with full metadata
- **Advanced GUI**: Modern web interface for browsing and managing emails
- **Search & Filter**: Search by sender, subject, content, date, and more
- **Email Organization**: Group, sort, and categorize emails
- **Real-time Sync**: Continuous monitoring for new emails
- **Export Capabilities**: Export emails in various formats

## Project Structure

```
gmail-backup-manager/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── models/         # Database models
│   │   ├── services/       # Business logic
│   │   ├── api/           # API endpoints
│   │   └── utils/         # Utilities
│   ├── requirements.txt
│   └── main.py
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/        # Page components
│   │   ├── services/     # API services
│   │   └── utils/        # Utilities
│   ├── package.json
│   └── public/
├── database/              # Database migrations and setup
├── config/               # Configuration files
└── docker-compose.yml    # Docker setup
```

## Quick Start

1. **Setup Environment**:
   ```bash
   # Backend
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   
   # Frontend
   cd frontend
   npm install
   ```

2. **Configure Gmail API**:
   - Create a Google Cloud Project
   - Enable Gmail API
   - Create OAuth 2.0 credentials
   - Download credentials to `config/credentials.json`

3. **Setup Database**:
   ```bash
   # Using Docker
   docker-compose up -d postgres
   
   # Or install PostgreSQL locally
   ```

4. **Run Application**:
   ```bash
   # Backend
   cd backend
   uvicorn main:app --reload
   
   # Frontend
   cd frontend
   npm start
   ```

## Configuration

Edit `config/settings.py` to configure:
- Database connection
- Gmail API settings
- Email sync intervals
- Search settings

## API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation.

## License

MIT License
