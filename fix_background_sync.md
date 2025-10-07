# Fix Background Sync Issues

## Problem
The background sync service is failing with the error:
```
No module named 'aiohttp'
```

## Root Cause
1. **Missing Dependencies**: The `aiohttp` and `httpx` packages are not installed
2. **Incorrect API Endpoint**: The service is calling the wrong sync endpoint
3. **Poor Error Handling**: Limited error information for debugging

## Solution

### Step 1: Install Missing Dependencies

Run the fix script:
```bash
./fix_dependencies.sh
```

Or manually install the dependencies:
```bash
cd backend
pip install aiohttp==3.9.1 httpx==0.25.2
```

### Step 2: Verify Installation

Check that the packages are installed:
```bash
python -c "import aiohttp; import httpx; print('✅ Dependencies installed successfully')"
```

### Step 3: Restart Background Sync Service

```bash
# Stop the current service
./manage_background_sync.sh stop

# Start it again
./manage_background_sync.sh start

# Check status
./manage_background_sync.sh status
```

### Step 4: Monitor Logs

Watch the logs for any remaining issues:
```bash
./manage_background_sync.sh logs-follow
```

## Changes Made

### 1. Updated requirements.txt
Added missing HTTP client dependencies:
```
# HTTP client for background sync
aiohttp==3.9.1
httpx==0.25.2
```

### 2. Fixed API Endpoint
Changed from:
```python
f"http://localhost:8000/api/v1/test/sync/start?max_emails=1000"
```

To:
```python
f"http://localhost:8000/api/v1/sync/start",
json={"max_emails": 1000}
```

### 3. Enhanced Error Logging
Added more detailed error information:
```python
logger.error(f"Error type: {type(e).__name__}")
logger.error(f"Error details: {str(e)}")
```

## Verification

After applying the fixes, you should see:

1. **No more import errors** in the logs
2. **Successful sync operations** with proper API calls
3. **Better error messages** if issues occur

## Troubleshooting

### If you still see errors:

1. **Check if backend is running**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Verify API endpoint exists**:
   ```bash
   curl http://localhost:8000/docs
   ```

3. **Check database connection**:
   ```bash
   docker logs gmail-backup-postgres
   ```

4. **Monitor background sync logs**:
   ```bash
   tail -f background_sync.log
   ```

### Common Issues:

1. **Backend not running**: Start the backend first
2. **Database connection issues**: Check PostgreSQL container
3. **Network connectivity**: Ensure containers can communicate
4. **Permission issues**: Check file permissions

## Prevention

To prevent similar issues in the future:

1. **Always update requirements.txt** when adding new imports
2. **Test dependencies** in a clean environment
3. **Use dependency management tools** like pip-tools
4. **Add dependency checks** to startup scripts

## Next Steps

After fixing the background sync:

1. **Monitor performance** and adjust sync intervals
2. **Set up alerts** for sync failures
3. **Implement retry logic** for failed syncs
4. **Add metrics** for sync success rates
