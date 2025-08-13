# Gmail Background Sync Service

## Overview

The Gmail Background Sync Service is a continuous email synchronization system that automatically keeps your email database updated with the latest emails from Gmail. It runs in the background and syncs emails at regular intervals without manual intervention.

## Features

- **Automatic Sync**: Continuously syncs emails every 5 minutes (configurable)
- **Smart Scheduling**: Only syncs users who haven't been synced in the last hour
- **Error Handling**: Robust error handling with automatic retry logic
- **Logging**: Comprehensive logging with file and console output
- **Graceful Shutdown**: Handles shutdown signals properly
- **Status Monitoring**: Real-time status monitoring via API
- **Resource Efficient**: Processes emails in batches to avoid memory issues

## Quick Start

### 1. Start the Background Sync Service

```bash
# Start the service
./manage_background_sync.sh start

# Check status
./manage_background_sync.sh status

# View logs
./manage_background_sync.sh logs
```

### 2. Monitor the Service

```bash
# Follow logs in real-time
./manage_background_sync.sh logs-follow

# Check API status
curl -s "http://localhost:8000/api/v1/test/background-sync/status" | jq .
```

### 3. Stop the Service

```bash
# Stop the service
./manage_background_sync.sh stop
```

## Management Commands

| Command | Description |
|---------|-------------|
| `start` | Start the background sync service |
| `stop` | Stop the background sync service |
| `restart` | Restart the background sync service |
| `status` | Show service status and recent logs |
| `logs` | Show recent log entries |
| `logs-follow` | Follow log entries in real-time |
| `help` | Show help message |

## API Endpoints

### Start Background Sync
```bash
curl -X POST "http://localhost:8000/api/v1/test/background-sync/start?interval_minutes=5"
```

### Stop Background Sync
```bash
curl -X POST "http://localhost:8000/api/v1/test/background-sync/stop"
```

### Get Sync Status
```bash
curl -s "http://localhost:8000/api/v1/test/background-sync/status" | jq .
```

## Configuration

### Sync Interval
The default sync interval is 5 minutes. You can change this by:

1. **Via API**: Set the `interval_minutes` parameter when starting
2. **Via Script**: Modify the `interval_minutes` parameter in `start_background_sync.py`

### Batch Size
The service processes emails in batches of 1000 emails per sync cycle. This can be modified in the `BackgroundSyncService` class.

### Sync Conditions
A user will be synced if:
- They have never been synced before, OR
- Their last sync was more than 1 hour ago

## Logging

### Log Files
- **Main Log**: `background_sync.log` - Contains all sync activity
- **Backend Log**: `backend/backend.log` - Contains backend API logs

### Log Levels
- **INFO**: Normal sync operations
- **WARNING**: Non-critical issues
- **ERROR**: Sync failures and errors

### Sample Log Output
```
2025-08-13 08:15:00 - app.services.background_sync_service - INFO - Starting sync cycle...
2025-08-13 08:15:01 - app.services.background_sync_service - INFO - Syncing user: yaroslavp2010@gmail.com
2025-08-13 08:15:45 - app.services.background_sync_service - INFO - Sync completed for yaroslavp2010@gmail.com: 1000 emails
2025-08-13 08:15:46 - app.services.background_sync_service - INFO - Sync cycle completed in 45.23s
```

## Performance

### Sync Performance
- **Rate**: ~2 emails per second
- **Batch Size**: 1000 emails per cycle
- **Memory Usage**: Optimized for low memory footprint
- **CPU Usage**: Minimal impact on system performance

### Scalability
- **Multiple Users**: Supports multiple Gmail accounts
- **Large Mailboxes**: Handles mailboxes with millions of emails
- **Concurrent Syncs**: Processes users sequentially to avoid conflicts

## Troubleshooting

### Common Issues

#### 1. Service Won't Start
```bash
# Check if backend is running
curl -s "http://localhost:8000/health"

# Check log file
tail -f background_sync.log
```

#### 2. Sync Errors
```bash
# Check sync status
curl -s "http://localhost:8000/api/v1/test/background-sync/status" | jq .

# Check recent logs
./manage_background_sync.sh logs
```

#### 3. High Memory Usage
- The service uses sequential processing to minimize memory usage
- If you experience memory issues, reduce the batch size in the sync service

### Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Backend server is not running` | Backend API not available | Start the backend server first |
| `Service is already running` | Multiple instances | Stop existing service first |
| `'dict' object has no attribute '_sa_instance_state'` | Database model issue | This is a known issue with some emails, sync continues |

## Monitoring

### Health Checks
```bash
# Check service health
./manage_background_sync.sh status

# Check API health
curl -s "http://localhost:8000/health"
```

### Metrics
The service provides the following metrics:
- Total sync cycles completed
- Total emails synced
- Last sync duration
- Error count
- Service uptime

### Alerts
Monitor the log file for:
- Sync failures
- High error rates
- Long sync durations
- Service restarts

## Security

### Authentication
- Uses existing Gmail OAuth tokens
- No additional authentication required
- Tokens are automatically refreshed

### Data Protection
- Emails are stored locally in PostgreSQL
- No data is sent to external services
- All communication is over HTTPS

## Integration

### With Frontend
The frontend can display sync status by calling:
```javascript
fetch('/api/v1/test/background-sync/status')
  .then(response => response.json())
  .then(data => {
    // Display sync status
    console.log(data.sync_status);
  });
```

### With Monitoring Systems
The service provides JSON endpoints that can be integrated with:
- Prometheus
- Grafana
- Nagios
- Custom monitoring solutions

## Development

### Adding New Features
1. Modify `BackgroundSyncService` class
2. Add new API endpoints in `test.py`
3. Update management script if needed
4. Test thoroughly before deployment

### Testing
```bash
# Test API endpoints
curl -s "http://localhost:8000/api/v1/test/background-sync/status"

# Test service management
./manage_background_sync.sh start
./manage_background_sync.sh status
./manage_background_sync.sh stop
```

## Support

For issues and questions:
1. Check the log files first
2. Review this documentation
3. Check the main project README
4. Create an issue in the project repository

## License

This background sync service is part of the Gmail Backup Manager project and follows the same license terms.
