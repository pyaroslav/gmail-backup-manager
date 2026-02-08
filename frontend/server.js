const express = require('express');
const { Client, Pool } = require('pg');
const path = require('path');
const cors = require('cors');
const fetch = require('node-fetch');

// Global sync control state
let syncControlState = {
    isActive: false,
    sessionId: null,
    startTime: null,
    syncType: null,
    maxEmails: null
};

const app = express();
const port = 3002;
const API_KEY = process.env.API_KEY || '';

// Helper: headers to send when proxying to the backend API
function backendHeaders(extra) {
    const h = {};
    if (API_KEY) h['X-API-Key'] = API_KEY;
    return Object.assign(h, extra);
}

// Enable CORS
app.use(cors());

// Parse JSON bodies
app.use(express.json());

// Serve static files with no caching
app.use(express.static(path.join(__dirname), {
    setHeaders: (res, path) => {
        res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
        res.setHeader('Pragma', 'no-cache');
        res.setHeader('Expires', '0');
    }
}));

// Database configuration
const dbConfig = {
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || 'gmail_backup',
    user: process.env.DB_USER || 'gmail_user',
    password: process.env.DB_PASSWORD || 'gmail_password',
    connectionTimeoutMillis: 5000,
    statement_timeout: 60000,
    query_timeout: 60000,
    max: 10
};

// Use pool for all queries — it handles connection recovery automatically.
// The single Client would permanently break after a timeout.
const pool = new Pool(dbConfig);
// Keep client as an alias so existing code continues to work.
const client = pool;

// Connect to database (pool connects lazily, just verify connectivity)
async function connectDB(retries = 5) {
    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            await pool.query('SELECT 1');
            console.log('Connected to PostgreSQL database via pool');
            return;
        } catch (error) {
            const delay = Math.min(1000 * Math.pow(2, attempt), 32000);
            console.error(`Database connection attempt ${attempt}/${retries} failed: ${error.message}`);
            if (attempt < retries) {
                console.log(`Retrying in ${delay / 1000}s...`);
                await new Promise(r => setTimeout(r, delay));
            } else {
                console.error('All database connection attempts failed');
            }
        }
    }
}

// Email count endpoint
// Fast approximate row count using PostgreSQL statistics (avoids full table scan)
async function fastEmailCount() {
    const result = await pool.query(
        "SELECT reltuples::bigint AS count FROM pg_class WHERE relname = 'emails'"
    );
    return parseInt(result.rows[0].count) || 0;
}

app.get('/api/db/email-count', async (req, res) => {
    try {
        const totalEmails = await fastEmailCount();
        res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
        res.setHeader('Pragma', 'no-cache');
        res.setHeader('Expires', '0');
        res.json({
            total_emails: totalEmails,
            timestamp: new Date().toISOString(),
            method: 'direct_nodejs'
        });
    } catch (error) {
        console.error('Email count error:', error);
        res.status(500).json({
            error: error.message,
            total_emails: 0,
            timestamp: new Date().toISOString()
        });
    }
});

// Dashboard data endpoint - comprehensive data for dashboard display
app.get('/api/db/dashboard', async (req, res) => {
    try {
        // Get total email count (fast estimate)
        const totalEmails = await fastEmailCount();
        
        // Get database size
        const sizeResult = await client.query(`
            SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                   pg_database_size(current_database()) as size_bytes
        `);
        const dbSizeBytes = parseInt(sizeResult.rows[0].size_bytes);
        const dbSizeGB = (dbSizeBytes / (1024 * 1024 * 1024)).toFixed(2);
        
        // Get latest email date
        const latestEmailResult = await client.query('SELECT MAX(date_received) FROM emails');
        const latestEmailDate = latestEmailResult.rows[0].max;
        
        // Get unread email count (use estimate for speed on large tables)
        let unreadEmails = 0;
        try {
            const unreadResult = await pool.query(
                'SELECT COUNT(*) FROM emails WHERE is_read = false'
            );
            unreadEmails = parseInt(unreadResult.rows[0].count);
        } catch (unreadErr) {
            console.log('Unread count slow, using 0:', unreadErr.message);
        }
        
        // Get recent emails (last 10)
        const recentEmailsResult = await client.query(`
            SELECT id, subject, sender, date_received, is_read
            FROM emails 
            ORDER BY date_received DESC 
            LIMIT 10
        `);
        
        const recentEmails = recentEmailsResult.rows.map(row => ({
            id: row.id,
            subject: row.subject || 'No Subject',
            sender: row.sender || 'Unknown',
            date_received: row.date_received ? row.date_received.toISOString() : null,
            is_read: row.is_read
        }));
        
        // Check for active sync sessions
        let syncStatus = 'ready';
        let lastSyncTime = null;
        let syncInProgress = false;
        
        try {
            // Check if sync_sessions table exists
            const tableExistsResult = await client.query(`
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'sync_sessions'
                );
            `);
            
            if (tableExistsResult.rows[0].exists) {
                // Get the most recent sync session
                const syncResult = await client.query(`
                    SELECT status, started_at, completed_at, emails_synced
                    FROM sync_sessions 
                    ORDER BY started_at DESC 
                    LIMIT 1
                `);
                
                if (syncResult.rows.length > 0) {
                    const sync = syncResult.rows[0];
                    syncStatus = sync.status;
                    syncInProgress = sync.status === 'started' || sync.status === 'running';
                    lastSyncTime = sync.completed_at || sync.started_at;
                }
            }
        } catch (syncError) {
            console.log('Sync sessions table not available:', syncError.message);
        }
        
        res.json({
            total_emails: totalEmails,
            unread_emails: unreadEmails,
            database_size_gb: parseFloat(dbSizeGB),
            database_size_pretty: sizeResult.rows[0].size,
            latest_email_date: latestEmailDate ? latestEmailDate.toISOString() : null,
            last_sync_time: lastSyncTime ? lastSyncTime.toISOString() : null,
            sync_status: syncStatus,
            sync_in_progress: syncInProgress,
            recent_emails: recentEmails,
            timestamp: new Date().toISOString(),
            method: 'direct_nodejs_dashboard'
        });
    } catch (error) {
        console.error('Dashboard data error:', error);
        res.status(500).json({
            error: error.message,
            total_emails: 0,
            unread_emails: 0,
            database_size_gb: 0,
            database_size_pretty: '0 MB',
            latest_email_date: null,
            last_sync_time: null,
            sync_status: 'error',
            sync_in_progress: false,
            recent_emails: [],
            timestamp: new Date().toISOString()
        });
    }
});

// Emails endpoint
app.get('/api/db/emails', async (req, res) => {
    try {
        const page = parseInt(req.query.page) || 1;
        const pageSize = parseInt(req.query.page_size) || 25;
        const offset = (page - 1) * pageSize;
        
        // Get total count (fast estimate)
        const totalCount = await fastEmailCount();
        
        // Keep list payload small: do NOT return full body_html/body_plain here.
        const emailsResult = await pool.query(`
            SELECT id, subject, sender, date_received, is_read, is_starred, 
                   thread_id, gmail_id, labels,
                   LEFT(COALESCE(body_plain, ''), 500) as body_preview
            FROM emails 
            ORDER BY date_received DESC 
            LIMIT $1 OFFSET $2
        `, [pageSize, offset]);
        
        const emails = emailsResult.rows.map(row => ({
            id: row.id,
            subject: row.subject || 'No Subject',
            sender: row.sender || 'Unknown',
            date_received: row.date_received ? row.date_received.toISOString() : null,
            is_read: row.is_read,
            is_starred: row.is_starred,
            thread_id: row.thread_id,
            gmail_id: row.gmail_id,
            labels: row.labels,
            body_preview: row.body_preview
        }));
        
        res.json({
            emails: emails,
            total_count: totalCount,
            page: page,
            page_size: pageSize,
            total_pages: Math.ceil(totalCount / pageSize),
            method: 'direct_nodejs'
        });
    } catch (error) {
        console.error('Emails error:', error);
        res.status(500).json({
            error: error.message,
            emails: [],
            total_count: 0
        });
    }
});



// Search endpoint
app.get('/api/db/search', async (req, res) => {
    try {
        const query = req.query.q;
        const page = parseInt(req.query.page) || 1;
        const pageSize = parseInt(req.query.page_size) || 50;
        const offset = (page - 1) * pageSize;
        const filter = (req.query.filter || 'all').toString();
        const dateFrom = (req.query.date_from || '').toString();
        const dateTo = (req.query.date_to || '').toString();
        
        if (!query) {
            return res.status(400).json({ error: 'Query parameter required' });
        }
        
        const searchTerm = `%${query}%`;

        // Build WHERE clause (server-side filtering is much faster than pulling everything and filtering client-side)
        const whereParts = [];
        const params = [];
        let idx = 1;

        if (filter === 'subject') {
            whereParts.push(`subject ILIKE $${idx++}`);
            params.push(searchTerm);
        } else if (filter === 'sender') {
            whereParts.push(`sender ILIKE $${idx++}`);
            params.push(searchTerm);
        } else if (filter === 'body') {
            whereParts.push(`body_plain ILIKE $${idx++}`);
            params.push(searchTerm);
        } else {
            whereParts.push(`(subject ILIKE $${idx} OR sender ILIKE $${idx} OR body_plain ILIKE $${idx})`);
            params.push(searchTerm);
            idx++;
        }

        if (dateFrom) {
            whereParts.push(`date_received >= $${idx++}`);
            params.push(dateFrom);
        }
        if (dateTo) {
            // dateTo is YYYY-MM-DD; include full day
            whereParts.push(`date_received < ($${idx++}::date + INTERVAL '1 day')`);
            params.push(dateTo);
        }

        const whereSql = whereParts.length ? `WHERE ${whereParts.join(' AND ')}` : '';
        
        // Get total count
        const countResult = await pool.query(
            `SELECT COUNT(*) FROM emails ${whereSql}`,
            params
        );
        const totalCount = parseInt(countResult.rows[0].count);
        
        // Keep search payload small: do NOT return full body_html/body_plain here.
        // Use /api/db/email/:id when the user opens an email.
        const searchParams = [...params, pageSize, offset];
        const searchResult = await pool.query(
            `
            SELECT id, subject, sender, date_received, is_read, is_starred,
                   thread_id, gmail_id, labels,
                   LEFT(COALESCE(body_plain, ''), 500) as body_preview
            FROM emails
            ${whereSql}
            ORDER BY date_received DESC
            LIMIT $${idx} OFFSET $${idx + 1}
            `,
            searchParams
        );
        
        const emails = searchResult.rows.map(row => ({
            id: row.id,
            subject: row.subject || 'No Subject',
            sender: row.sender || 'Unknown',
            date_received: row.date_received ? row.date_received.toISOString() : null,
            is_read: row.is_read,
            is_starred: row.is_starred,
            thread_id: row.thread_id,
            gmail_id: row.gmail_id,
            labels: row.labels,
            body_preview: row.body_preview
        }));
        
        res.json({
            emails: emails,
            total_count: totalCount,
            page: page,
            page_size: pageSize,
            total_pages: Math.ceil(totalCount / pageSize),
            search_term: query,
            method: 'direct_nodejs'
        });
    } catch (error) {
        console.error('Search error:', error);
        res.status(500).json({
            error: error.message,
            emails: [],
            total_count: 0
        });
    }
});

// Email actions endpoints
app.post('/api/db/emails/:id/read', async (req, res) => {
    try {
        const emailId = parseInt(req.params.id);
        const result = await pool.query(
            'UPDATE emails SET is_read = true WHERE id = $1',
            [emailId]
        );
        
        if (result.rowCount === 0) {
            return res.status(404).json({ error: 'Email not found' });
        }
        
        res.json({ success: true, message: 'Email marked as read' });
    } catch (error) {
        console.error('Error marking email as read:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

app.post('/api/db/emails/:id/unread', async (req, res) => {
    try {
        const emailId = parseInt(req.params.id);
        const result = await pool.query(
            'UPDATE emails SET is_read = false WHERE id = $1',
            [emailId]
        );
        
        if (result.rowCount === 0) {
            return res.status(404).json({ error: 'Email not found' });
        }
        
        res.json({ success: true, message: 'Email marked as unread' });
    } catch (error) {
        console.error('Error marking email as unread:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

app.post('/api/db/emails/:id/star', async (req, res) => {
    try {
        const emailId = parseInt(req.params.id);
        const result = await pool.query(
            'UPDATE emails SET is_starred = NOT is_starred WHERE id = $1 RETURNING is_starred',
            [emailId]
        );
        
        if (result.rowCount === 0) {
            return res.status(404).json({ error: 'Email not found' });
        }
        
        const isStarred = result.rows[0].is_starred;
        res.json({ 
            success: true, 
            message: `Email ${isStarred ? 'starred' : 'unstarred'}`,
            is_starred: isStarred
        });
    } catch (error) {
        console.error('Error toggling star:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

app.delete('/api/db/emails/:id', async (req, res) => {
    try {
        const emailId = parseInt(req.params.id);
        const result = await pool.query(
            'DELETE FROM emails WHERE id = $1',
            [emailId]
        );
        
        if (result.rowCount === 0) {
            return res.status(404).json({ error: 'Email not found' });
        }
        
        res.json({ success: true, message: 'Email deleted' });
    } catch (error) {
        console.error('Error deleting email:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

// Global variable to track email count changes
let lastEmailCount = 0;
let emailCountHistory = [];
let lastCountCheck = Date.now();
let syncStartTime = null; // Track actual sync start time
let syncDetected = false; // Track if sync has been detected

// Sync status endpoint
app.get('/api/db/sync-status', async (req, res) => {
    try {
        // Get basic database stats (fast estimate)
        const totalEmails = await fastEmailCount();
        const currentTime = Date.now();
        
        // Track email count changes
        if (lastEmailCount > 0) {
            const countChange = totalEmails - lastEmailCount;
            const timeDiff = (currentTime - lastCountCheck) / 1000; // seconds
            
            if (countChange > 0) {
                emailCountHistory.push({
                    timestamp: currentTime,
                    count: totalEmails,
                    change: countChange,
                    timeDiff: timeDiff
                });
                
                // Keep only last 10 entries
                if (emailCountHistory.length > 10) {
                    emailCountHistory.shift();
                }
            }

        } else {
            // First time running, initialize with current count
            // Don't add to history yet, just set the baseline
        }
        
        lastEmailCount = totalEmails;
        lastCountCheck = currentTime;
        
        // Get latest email timestamp
        const latestResult = await client.query('SELECT MAX(date_received) FROM emails');
        const latestEmailDate = latestResult.rows[0].max;
        
        // Get database size in GB
        const sizeResult = await client.query(`
            SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                   pg_database_size(current_database()) as size_bytes
        `);
        const dbSize = sizeResult.rows[0].size;
        const dbSizeBytes = parseInt(sizeResult.rows[0].size_bytes);
        const dbSizeGB = (dbSizeBytes / (1024 * 1024 * 1024)).toFixed(2);
        
        // Check for recent email activity (emails added in last 5 minutes)
        const recentEmailsResult = await client.query(`
            SELECT COUNT(*) FROM emails 
            WHERE date_received > NOW() - INTERVAL '5 minutes'
        `);
        const recentEmails = parseInt(recentEmailsResult.rows[0].count);
        
        // Check for emails added in last 1 minute
        const veryRecentEmailsResult = await client.query(`
            SELECT COUNT(*) FROM emails 
            WHERE date_received > NOW() - INTERVAL '1 minute'
        `);
        const veryRecentEmails = parseInt(veryRecentEmailsResult.rows[0].count);
        
        // Check for emails added in the last 30 seconds by comparing with a previous count
        // This is a more reliable way to detect recent additions
        const recentCountResult = await client.query(`
            SELECT COUNT(*) FROM emails 
            WHERE id > (SELECT MAX(id) FROM emails) - 100
        `);
        const recentCount = parseInt(recentCountResult.rows[0].count);
        
        // Detect sync activity based on email count changes
        let syncInProgress = false;
        let syncStatus = 'ready';
        let lastSyncTime = null;
        let syncDetails = null;
        
        // Check if emails are being added recently (last 30 seconds)
        const recentChanges = emailCountHistory.filter(entry => 
            (currentTime - entry.timestamp) < 30000 // 30 seconds
        );
        
        const hasRecentCountChanges = recentChanges.length > 0;
        const totalRecentChanges = recentChanges.reduce((sum, entry) => sum + entry.change, 0);
        
        // Track sync start time when first detected
        if (hasRecentCountChanges && !syncDetected) {
            syncInProgress = true;
            syncStatus = 'syncing';
            syncDetected = true;
            syncStartTime = currentTime;
            // Reset email count history to only track changes from this sync session
            emailCountHistory = emailCountHistory.filter(entry => entry.timestamp >= currentTime - 30000); // Keep only last 30 seconds
        } else if (hasRecentCountChanges) {
            syncInProgress = true;
            syncStatus = 'syncing';
        } else if (!hasRecentCountChanges && syncDetected) {
            // No recent activity, but sync was detected before - keep it active for a bit longer
            const timeSinceLastActivity = currentTime - (emailCountHistory.length > 0 ? emailCountHistory[emailCountHistory.length - 1].timestamp : currentTime);
            if (timeSinceLastActivity < 60000) { // Keep active for 1 minute after last activity
                syncInProgress = true;
                syncStatus = 'syncing';
            } else {
                // Reset sync detection after 1 minute of no activity
                syncDetected = false;
                syncStartTime = null;
                syncInProgress = false;
                syncStatus = 'ready';
                // Clear email count history when sync ends
                emailCountHistory = [];
            }
        }
        
        // Get sync status from background sync service (if available)
        let backendTimeout = false;
        try {
            // Try to get background sync status from backend
            const backendResponse = await fetch('http://gmail-backup-backend:8000/api/v1/test/background-sync/status', {
                headers: backendHeaders(),
                signal: AbortSignal.timeout(2000) // 2 second timeout
            });
            
            if (backendResponse.ok) {
                const backendData = await backendResponse.json();
                const syncData = backendData.sync_status || {};
                
                // Use backend sync status as the primary source of truth
                syncInProgress = syncData.sync_in_progress || false;
                syncStatus = syncInProgress ? 'syncing' : 'ready';
                
                // Reset frontend sync detection when backend says no sync
                if (!syncInProgress) {
                    syncDetected = false;
                    syncStartTime = null;
                }
                
                if (syncData.stats && syncData.stats.last_sync_start) {
                    lastSyncTime = syncData.stats.last_sync_start;
                } else if (syncData.last_sync_time) {
                    lastSyncTime = syncData.last_sync_time;
                }
                
                // Get detailed sync information
                if (syncInProgress) {
                    try {
                        const monitoringResponse = await fetch('http://gmail-backup-backend:8000/api/v1/test/sync/real-time-status', {
                            headers: backendHeaders(),
                            signal: AbortSignal.timeout(500)
                        });
                        
                        if (monitoringResponse.ok) {
                            const monitoringData = await monitoringResponse.json();
                            syncDetails = monitoringData.sync_progress || {};
                        }
                    } catch (monitoringError) {
                        console.log('Sync monitoring details unavailable:', monitoringError.message);
                    }
                }
            }
        } catch (backendError) {
            // Backend might be busy, try alternative sync detection
            console.log('Backend sync status unavailable:', backendError.message);
            backendTimeout = true;
            
            // If backend is unavailable, reset sync state to avoid stuck states
            if (backendError.name === 'AbortError' || backendError.message.includes('aborted')) {
                syncDetected = false;
                syncStartTime = null;
                syncInProgress = false;
                syncStatus = 'ready';
            }
            
            // Try to detect sync by checking if there's an active sync process
            try {
                const syncProcessResponse = await fetch('http://gmail-backup-backend:8000/api/v1/test/sync/status', {
                    headers: backendHeaders(),
                    signal: AbortSignal.timeout(300) // Quick timeout
                });
                
                if (syncProcessResponse.ok) {
                    const syncProcessData = await syncProcessResponse.json();
                    if (syncProcessData.status === 'syncing' || syncProcessData.sync_in_progress) {
                        syncInProgress = true;
                        syncStatus = 'syncing';
                    }
                }
            } catch (syncProcessError) {
                console.log('Sync process check failed:', syncProcessError.message);
            }
        }
        
        // Additional sync detection: Check if there's any active sync process
        if (!syncInProgress) {
            try {
                // Try to check if there's an active sync by looking at the sync progress endpoint
                const progressResponse = await fetch('http://gmail-backup-backend:8000/api/v1/test/sync/progress', {
                    headers: backendHeaders(),
                    signal: AbortSignal.timeout(1000)
                });
                
                if (progressResponse.ok) {
                    const progressData = await progressResponse.json();
                    if (progressData.status === 'syncing' || progressData.is_running) {
                        syncInProgress = true;
                        syncStatus = 'syncing';
                        
                        // Create basic sync details from progress data
                        if (!syncDetails) {
                            syncDetails = {
                                sync_type: 'detected_from_backend',
                                start_time: progressData.start_time || new Date().toISOString(),
                                elapsed_time: progressData.elapsed_time || 'unknown',
                                progress_percentage: progressData.progress || 0,
                                emails_processed: progressData.emails_processed || 0,
                                emails_per_minute: progressData.emails_per_minute || 0,
                                current_batch: progressData.current_batch || 1,
                                total_batches: progressData.total_batches || 1
                            };
                        }
                    }
                }
            } catch (progressError) {
                console.log('Progress check failed:', progressError.message);
            }
        }
        
        // If backend is timing out consistently, it might be busy with sync
        if (!syncInProgress && backendTimeout) {
            // If backend is consistently timing out, assume it's busy with sync
            syncInProgress = true;
            syncStatus = 'syncing';
            syncDetails = {
                sync_type: 'detected_from_timeouts',
                start_time: new Date().toISOString(),
                elapsed_time: 'unknown',
                progress_percentage: 0,
                emails_processed: 0,
                emails_per_minute: 0,
                current_batch: 1,
                total_batches: 1,
                note: 'Backend is busy with sync operations'
            };
        }
        
        // If we detected activity but no backend details, create basic sync details
        if (syncInProgress && !syncDetails) {
            // Only count actual new emails added during this sync session
            // Use the recent changes that happened after sync start time
            const syncSessionChanges = recentChanges.filter(entry => 
                entry.timestamp >= syncStartTime
            );
            const actualNewEmails = syncSessionChanges.reduce((sum, entry) => sum + entry.change, 0);
            
            const avgChange = syncSessionChanges.length > 0 ? actualNewEmails / syncSessionChanges.length : 0;
            const emailsPerMinute = Math.round(avgChange * 60 / 30); // Assuming 30-second intervals
            
            // Calculate elapsed time from actual start time
            const elapsedMs = currentTime - syncStartTime;
            const elapsedMinutes = Math.floor(elapsedMs / 60000);
            const elapsedSeconds = Math.floor((elapsedMs % 60000) / 1000);
            const elapsedTime = `${elapsedMinutes}:${elapsedSeconds.toString().padStart(2, '0')}`;
            
            syncDetails = {
                sync_type: 'detected',
                start_time: new Date(syncStartTime).toISOString(),
                elapsed_time: elapsedTime,
                progress_percentage: 0,
                emails_processed: actualNewEmails, // Only new emails in this session
                emails_per_minute: emailsPerMinute,
                current_batch: 1,
                total_batches: 1
            };
        }
        
        // Add a note about backend processing if we see backend activity but no database changes
        let syncNote = null;
        if (!syncInProgress && hasRecentCountChanges === false) {
            // Check if backend is processing but not saving to database
            syncNote = "Backend may be processing emails but not saving to database";
        }
        
        res.json({
            status: syncStatus,
            sync_in_progress: syncInProgress,
            total_emails: totalEmails,
            database_size_gb: parseFloat(dbSizeGB),
            database_size_pretty: dbSize,
            latest_email_date: latestEmailDate ? latestEmailDate.toISOString() : null,
            last_sync_time: lastSyncTime,
            sync_details: syncDetails,
            sync_note: syncNote,
            activity_detection: {
                recent_emails_5min: recentEmails,
                recent_emails_1min: veryRecentEmails,
                has_recent_activity: hasRecentCountChanges,
                total_recent_changes: totalRecentChanges,
                recent_changes_count: recentChanges.length,
                count_history_length: emailCountHistory.length
            },
            timestamp: new Date().toISOString(),
            method: 'direct_nodejs'
        });
    } catch (error) {
        console.error('Sync status error:', error);
        res.status(500).json({
            error: error.message,
            status: 'error',
            timestamp: new Date().toISOString()
        });
    }
});

// Real-time sync monitoring endpoint (database-first approach)
app.get('/api/db/sync-monitoring', async (req, res) => {
    // Add cache-busting headers
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
    
    try {
        const currentTime = Date.now();
        
        // Get basic database stats (fast estimate)
        const totalEmails = await fastEmailCount();
        
        const sizeResult = await pool.query(`
            SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                   pg_database_size(current_database()) as size_bytes
        `);
        const dbSizeBytes = parseInt(sizeResult.rows[0].size_bytes);
        const dbSizeGB = (dbSizeBytes / (1024 * 1024 * 1024)).toFixed(2);
        
        const latestEmailResult = await pool.query('SELECT MAX(date_received) FROM emails');
        const latestEmailDate = latestEmailResult.rows[0].max;
        
        let syncProgress = {
            is_active: false,
            start_time: null,
            elapsed_time: null,
            emails_processed: 0,
            emails_per_minute: 0,
            progress_percentage: 0,
            estimated_completion: null,
            current_batch: 1,
            total_batches: 1,
            sync_type: 'unknown',
            status: 'ready',
            actual_synced: 0,
            backend_status: 'unknown'
        };
        
        let recentActivity = {
            recent_emails_5min: 0,
            recent_emails_1min: 0,
            has_recent_activity: false
        };
        
        // Primary: Try to get sync data from sync_sessions table
        try {
            // Check if sync_sessions table exists
            const tableExistsResult = await pool.query(`
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'sync_sessions'
                );
            `);
            
            if (tableExistsResult.rows[0].exists) {
                // Get the most recent active sync session
                const activeSyncResult = await pool.query(`
                    SELECT 
                        id, user_id, sync_type, sync_source, max_emails, start_date, end_date,
                        query_filter, status, started_at, completed_at, last_activity_at,
                        emails_processed, emails_synced, emails_updated, emails_skipped,
                        batches_processed, total_api_calls, avg_batch_time_ms, 
                        total_duration_seconds, error_count, last_error_message,
                        sync_metadata, notes, created_at, updated_at
                    FROM sync_sessions 
                    WHERE status IN ('started', 'running')
                    ORDER BY started_at DESC 
                    LIMIT 1
                `);
                
                if (activeSyncResult.rows.length > 0) {
                    const session = activeSyncResult.rows[0];
                    const startTime = new Date(session.started_at).getTime();
                    const elapsedMs = currentTime - startTime;
                    const elapsedMinutes = elapsedMs / (1000 * 60);
                    const elapsedHours = elapsedMinutes / 60;
                    
                    // Check if sync session is stale (running for more than 2 hours without progress)
                    const isStale = elapsedHours > 2;
                    
                    // Use the actual sync session data instead of calculating from total emails
                    const actualEmailsSynced = session.emails_synced || 0;
                    
                    if (isStale) {
                        // Mark stale session as inactive
                        syncProgress = {
                            is_active: false,
                            start_time: session.started_at,
                            elapsed_time: formatElapsedTime(elapsedMs),
                            emails_processed: actualEmailsSynced,
                            emails_per_minute: 0,
                            progress_percentage: 100,
                            estimated_completion: null,
                            current_batch: session.batches_processed || 1,
                            total_batches: session.batches_processed || 1,
                            sync_type: session.sync_type || 'unknown',
                            status: 'stale',
                            actual_synced: actualEmailsSynced,
                            backend_status: 'stale',
                            session_id: session.id,
                            sync_source: session.sync_source,
                            query_filter: session.query_filter,
                            start_date: session.start_date,
                            max_emails: session.max_emails,
                            error_count: session.error_count || 0,
                            last_error: session.last_error_message || 'Session became stale after 2+ hours'
                        };
                    } else {
                        syncProgress = {
                            is_active: true,
                            start_time: session.started_at,
                            elapsed_time: formatElapsedTime(elapsedMs),
                            emails_processed: actualEmailsSynced,
                            emails_per_minute: elapsedMinutes > 0 ? Math.round(actualEmailsSynced / elapsedMinutes) : 0,
                            progress_percentage: session.max_emails ? Math.min((actualEmailsSynced / session.max_emails) * 100, 95) : 0,
                            estimated_completion: null,
                            current_batch: session.batches_processed || 1,
                            total_batches: session.batches_processed || 1,
                            sync_type: session.sync_type || 'unknown',
                            status: 'syncing',
                            actual_synced: actualEmailsSynced,
                            backend_status: 'active',
                            session_id: session.id,
                            sync_source: session.sync_source,
                            query_filter: session.query_filter,
                            start_date: session.start_date,
                            max_emails: session.max_emails,
                            error_count: session.error_count || 0,
                            last_error: session.last_error_message
                        };
                    }
                    
                    // Calculate estimated completion if we have enough data
                    if (syncProgress.emails_per_minute > 0 && session.max_emails) {
                        const remainingEmails = session.max_emails - (session.emails_processed || 0);
                        const minutesRemaining = remainingEmails / syncProgress.emails_per_minute;
                        syncProgress.estimated_completion = new Date(currentTime + (minutesRemaining * 60 * 1000)).toISOString();
                    }
                    
                    // Calculate recent activity based on actual email count changes
                    // Since we're actively syncing, estimate recent activity based on sync progress
                    const emailsPerMinute = elapsedMinutes > 0 ? Math.round(actualEmailsSynced / elapsedMinutes) : 0;
                    
                    if (emailsPerMinute > 0) {
                        recentActivity.has_recent_activity = true;
                        recentActivity.recent_emails_5min = Math.min(emailsPerMinute * 5, actualEmailsSynced);
                        recentActivity.recent_emails_1min = Math.min(emailsPerMinute, actualEmailsSynced);
                    }
                    
                } else {
                    // No active sync, check for the most recent completed sync
                    const recentSyncResult = await pool.query(`
                        SELECT 
                            id, sync_type, status, started_at, completed_at,
                            emails_synced, total_duration_seconds
                        FROM sync_sessions 
                        ORDER BY started_at DESC 
                        LIMIT 1
                    `);
                    
                    if (recentSyncResult.rows.length > 0) {
                        const lastSync = recentSyncResult.rows[0];
                        syncProgress.sync_type = lastSync.sync_type || 'unknown';
                        syncProgress.status = lastSync.status === 'completed' ? 'ready' : 'ready';
                        syncProgress.actual_synced = lastSync.emails_synced || 0;
                        syncProgress.backend_status = 'ready';
                    }
                }
            } else {
                console.log('sync_sessions table does not exist, falling back to log parsing');
                throw new Error('sync_sessions table not found');
            }
            
        } catch (dbError) {
            console.log('Could not read sync sessions from database:', dbError.message);
            
            // Fallback: Try to get sync data from backend logs
            try {
                const { exec } = require('child_process');
                const util = require('util');
                const execAsync = util.promisify(exec);
                
                const { stdout: logs } = await execAsync('docker logs gmail-backup-backend --tail 100 2>&1', { timeout: 5000, maxBuffer: 1024 * 1024 * 5 });
                
                const logLines = logs.split('\n');
                let totalSynced = 0;
                let isBackendSyncing = false;
                
                // Look for the most recent sync activity in logs
                for (let i = logLines.length - 1; i >= 0; i--) {
                    const line = logLines[i];
                    if (line.includes('total synced:')) {
                        const match = line.match(/total synced: (\d+)/);
                        if (match) {
                            totalSynced = parseInt(match[1]);
                            isBackendSyncing = true;
                            break; // Use the most recent entry, not the highest
                        }
                    }
                }
                
                if (isBackendSyncing && totalSynced > 0) {
                    syncProgress.is_active = true;
                    syncProgress.status = 'syncing';
                    syncProgress.sync_type = 'fallback_logs';
                    syncProgress.actual_synced = totalSynced;
                    syncProgress.emails_processed = totalSynced;
                    syncProgress.backend_status = 'active';
                    
                    // Estimate recent activity from log parsing
                    const recentBatches = logLines.filter(line => 
                        line.includes('Processing batch') && 
                        line.includes(new Date().toISOString().split('T')[0]) // Today's logs
                    ).length;
                    
                    if (recentBatches > 0) {
                        recentActivity.has_recent_activity = true;
                        recentActivity.recent_emails_5min = recentBatches * 100;
                        recentActivity.recent_emails_1min = Math.min(recentBatches * 100, 100); // Conservative estimate
                    }
                }
                
            } catch (logError) {
                console.log('Could not read backend logs:', logError.message);
                // Use default values - no active sync detected
            }
        }

        res.json({
            sync_progress: syncProgress,
            database_stats: {
                total_emails: totalEmails,
                database_size_gb: parseFloat(dbSizeGB),
                database_size_pretty: sizeResult.rows[0].size,
                latest_email_date: latestEmailDate
            },
            activity_stats: recentActivity,
            timestamp: new Date().toISOString(),
            data_source: syncProgress.session_id ? 'database' : 'logs_fallback'
        });
        
    } catch (error) {
        console.error('Error in sync monitoring:', error);
        res.status(500).json({ 
            error: 'Internal server error',
            timestamp: new Date().toISOString()
        });
    }
});

// Helper function to format elapsed time
function formatElapsedTime(milliseconds) {
    const seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${seconds % 60}s`;
    } else {
        return `${seconds}s`;
    }
}

// Sync control endpoints
app.post('/api/sync/start', async (req, res) => {
    try {
        const { sync_type = 'full', max_emails = 100, start_date, resume_mode = false } = req.body;
        
        console.log(`Sync start request: ${sync_type} sync with max_emails=${max_emails}${start_date ? `, start_date=${start_date}` : ''}`);
        
        // Check if sync is already active (unless this is a resume request)
        if (syncControlState.isActive && !resume_mode) {
            console.log('Sync already active, rejecting new request');
            return res.status(409).json({
                success: false,
                message: 'Sync already in progress',
                error: 'Another sync process is currently running',
                current_sync: {
                    type: syncControlState.syncType,
                    started: syncControlState.startTime,
                    session_id: syncControlState.sessionId
                },
                timestamp: new Date().toISOString()
            });
        }
        
        // Check database for active sync sessions
        try {
            const activeSyncResult = await client.query(`
                SELECT id, sync_type, started_at, status 
                FROM sync_sessions 
                WHERE status IN ('started', 'running')
                ORDER BY started_at DESC 
                LIMIT 1
            `);
            
            if (activeSyncResult.rows.length > 0) {
                const activeSync = activeSyncResult.rows[0];
                console.log('Active sync found in database:', activeSync);
                
                // Check if the active sync is recent (within last 5 minutes)
                const syncStartTime = new Date(activeSync.started_at).getTime();
                const currentTime = Date.now();
                const timeDiff = currentTime - syncStartTime;
                const fiveMinutes = 5 * 60 * 1000;
                
                if (timeDiff < fiveMinutes && !resume_mode) {
                    // Recent sync, reject the request (unless resuming)
                    return res.status(409).json({
                        success: false,
                        message: 'Sync already in progress',
                        error: 'Active sync session found in database',
                        current_sync: {
                            session_id: activeSync.id,
                            type: activeSync.sync_type,
                            started: activeSync.started_at,
                            status: activeSync.status
                        },
                        timestamp: new Date().toISOString()
                    });
                } else {
                    // Old stuck sync, clean it up automatically
                    console.log('Found old stuck sync, cleaning up automatically');
                    await client.query(`
                        UPDATE sync_sessions 
                        SET status = 'stopped', 
                            completed_at = NOW(),
                            notes = CONCAT(COALESCE(notes, ''), ' - Cleaned up for resume')
                        WHERE id = $1
                    `, [activeSync.id]);
                    console.log(`Cleaned up stuck sync session ${activeSync.id}`);
                }
            }
        } catch (dbError) {
            console.log('Database check failed, proceeding with sync start:', dbError.message);
        }
        
        // Update sync control state
        syncControlState.isActive = true;
        syncControlState.startTime = new Date().toISOString();
        syncControlState.syncType = sync_type;
        syncControlState.maxEmails = max_emails;
        
        console.log('Sync control state updated:', syncControlState);
        
        // Determine the correct backend endpoint based on sync type
        let backendUrl = `http://gmail-backup-backend:8000/api/v1/test/sync/start-${sync_type}?max_emails=${max_emails}`;
        
        if (sync_type === 'date-range' && start_date) {
            backendUrl = `http://gmail-backup-backend:8000/api/v1/test/sync/start-from-date?start_date=${start_date}&max_emails=${max_emails}`;
        }
        
        console.log('Calling backend endpoint:', backendUrl);
        
        // Call the backend sync endpoint with enhanced timeout and retry logic
        let response;
        let retryCount = 0;
        const maxRetries = 3;
        
        while (retryCount < maxRetries) {
            try {
                response = await fetch(backendUrl, {
                    method: 'POST',
                    headers: backendHeaders(),
                    signal: AbortSignal.timeout(30000) // 30 second timeout
                });
                break; // Success, exit retry loop
            } catch (fetchError) {
                retryCount++;
                console.log(`Backend sync attempt ${retryCount} failed:`, fetchError.message);
                
                if (retryCount >= maxRetries) {
                    throw new Error(`Backend sync failed after ${maxRetries} attempts. Last error: ${fetchError.message}`);
                }
                
                // Wait before retry (exponential backoff)
                const waitTime = Math.min(1000 * Math.pow(2, retryCount - 1), 5000);
                console.log(`Waiting ${waitTime}ms before retry...`);
                await new Promise(resolve => setTimeout(resolve, waitTime));
            }
        }
        
        if (response.ok) {
            const data = await response.json();
            console.log('Backend sync started successfully:', data);
            
            // Update session ID if provided by backend
            if (data.session_id) {
                syncControlState.sessionId = data.session_id;
            }
            
            const successMessage = resume_mode ? 
                `${sync_type} sync resumed successfully from where it left off` : 
                `${sync_type} sync started successfully`;
            
            res.json({
                success: true,
                message: successMessage,
                data: data,
                sync_control_state: syncControlState,
                resume_mode: resume_mode,
                timestamp: new Date().toISOString()
            });
        } else {
            // Reset sync control state on failure
            syncControlState.isActive = false;
            syncControlState.startTime = null;
            syncControlState.syncType = null;
            syncControlState.maxEmails = null;
            
            const errorData = await response.json();
            console.error('Backend sync start failed:', errorData);
            res.status(500).json({
                success: false,
                message: `Failed to start ${sync_type} sync`,
                error: errorData.error || 'Unknown error',
                timestamp: new Date().toISOString()
            });
        }
        
    } catch (error) {
        // Reset sync control state on error
        syncControlState.isActive = false;
        syncControlState.startTime = null;
        syncControlState.syncType = null;
        syncControlState.maxEmails = null;
        
        console.error('Error starting sync:', error);
        
        // If it's a timeout error, provide a more helpful message
        let errorMessage = error.message;
        if (error.name === 'AbortError' || error.message.includes('aborted')) {
            errorMessage = 'Backend is not responding. The sync service may be busy or unavailable.';
        }
        
        res.status(500).json({
            success: false,
            message: 'Error starting sync',
            error: errorMessage,
            error_type: error.name,
            timestamp: new Date().toISOString()
        });
    }
});

app.post('/api/sync/stop', async (req, res) => {
    try {
        console.log('Stopping sync...');
        
        // Reset sync control state
        const previousState = { ...syncControlState };
        syncControlState.isActive = false;
        syncControlState.startTime = null;
        syncControlState.syncType = null;
        syncControlState.maxEmails = null;
        syncControlState.sessionId = null;
        
        console.log('Sync control state reset. Previous state:', previousState);
        
        // Update database to mark sync sessions as inactive
        try {
            await client.query(`
                UPDATE sync_sessions 
                SET status = 'stopped', 
                    completed_at = NOW() 
                WHERE status IN ('started', 'running')
            `);
            console.log('Database sync sessions marked as inactive');
        } catch (dbError) {
            console.log('Database update failed:', dbError.message);
        }
        
        // First try the backend stop endpoint with timeout
        try {
            const response = await fetch('http://gmail-backup-backend:8000/api/v1/test/sync/stop', {
                method: 'POST',
                headers: backendHeaders(),
                signal: AbortSignal.timeout(3000) // 3 second timeout
            });
            
            if (response.ok) {
                const data = await response.json();
                return res.json({
                    success: true,
                    message: data.message || 'Sync stop requested',
                    data: data,
                    method: 'backend_api',
                    previous_state: previousState,
                    timestamp: new Date().toISOString()
                });
            }
        } catch (backendError) {
            console.log('Backend stop endpoint failed, trying container restart...');
        }
        
        // If backend is hanging, restart the container to force stop
        const { exec } = require('child_process');
        const util = require('util');
        const execAsync = util.promisify(exec);
        
        console.log('Restarting backend container to force stop sync...');
        
        try {
            // Restart the backend container
            const { stdout, stderr } = await execAsync('docker restart gmail-backup-backend', {
                timeout: 10000 // 10 second timeout
            });
            
            console.log('Container restart output:', stdout);
            if (stderr) console.log('Container restart stderr:', stderr);
            
            res.json({
                success: true,
                message: 'Sync stopped by restarting backend container',
                method: 'container_restart',
                container_output: stdout,
                previous_state: previousState,
                timestamp: new Date().toISOString()
            });
            
        } catch (restartError) {
            console.error('Error restarting container:', restartError);
            
            // Even if container restart fails, the sync has been stopped in the database
            // Check if sync is actually stopped
            try {
                const syncCheck = await client.query(`
                    SELECT COUNT(*) as active_count 
                    FROM sync_sessions 
                    WHERE status IN ('started', 'running')
                `);
                
                const activeCount = parseInt(syncCheck.rows[0].active_count);
                
                if (activeCount === 0) {
                    // Sync is actually stopped, return success
                    res.json({
                        success: true,
                        message: 'Sync stopped successfully (database cleanup completed)',
                        method: 'database_cleanup',
                        note: 'Container restart failed but sync was stopped via database',
                        previous_state: previousState,
                        timestamp: new Date().toISOString()
                    });
                } else {
                    // Sync is still active, return error
                    res.status(500).json({
                        success: false,
                        message: 'Failed to stop sync - container restart failed and sync still active',
                        error: restartError.message,
                        method: 'container_restart_failed',
                        active_syncs: activeCount,
                        previous_state: previousState,
                        timestamp: new Date().toISOString()
                    });
                }
            } catch (checkError) {
                // If we can't check, assume it failed
                res.status(500).json({
                    success: false,
                    message: 'Failed to stop sync - container restart failed',
                    error: restartError.message,
                    method: 'container_restart_failed',
                    previous_state: previousState,
                    timestamp: new Date().toISOString()
                });
            }
        }
        
    } catch (error) {
        console.error('Error stopping sync:', error);
        res.status(500).json({
            success: false,
            message: 'Error stopping sync',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

app.get('/api/sync/status', async (req, res) => {
    try {
        // Return the local sync control state
        res.json({
            success: true,
            data: {
                sync_control_state: syncControlState,
                is_active: syncControlState.isActive,
                session_id: syncControlState.sessionId,
                sync_type: syncControlState.syncType,
                start_time: syncControlState.startTime
            },
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('Error getting sync status:', error);
        res.status(500).json({
            success: false,
            message: 'Error getting sync status',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// New endpoint to get sync control state
app.get('/api/sync/control-state', async (req, res) => {
    try {
        res.json({
            success: true,
            sync_control_state: syncControlState,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        console.error('Error getting sync control state:', error);
        res.status(500).json({
            success: false,
            message: 'Error getting sync control state',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Cleanup endpoint to reset all sync sessions
app.post('/api/sync/cleanup', async (req, res) => {
    try {
        console.log('Cleaning up sync sessions...');
        
        // Reset sync control state
        syncControlState.isActive = false;
        syncControlState.startTime = null;
        syncControlState.syncType = null;
        syncControlState.maxEmails = null;
        syncControlState.sessionId = null;
        
        // Mark all active sync sessions as stopped
        const result = await client.query(`
            UPDATE sync_sessions 
            SET status = 'stopped', 
                completed_at = NOW() 
            WHERE status IN ('started', 'running')
        `);
        
        console.log(`Cleaned up ${result.rowCount} sync sessions`);
        
        res.json({
            success: true,
            message: `Cleaned up ${result.rowCount} sync sessions`,
            sync_control_state: syncControlState,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('Error cleaning up sync sessions:', error);
        res.status(500).json({
            success: false,
            message: 'Error cleaning up sync sessions',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Resume sync endpoint - handles graceful resumption from where it left off
app.post('/api/sync/resume', async (req, res) => {
    try {
        console.log('Resuming sync from where it left off...');
        
        // First, clean up any stale sessions
        const cleanupResult = await client.query(`
            UPDATE sync_sessions 
            SET status = 'stopped', 
                completed_at = NOW(),
                notes = CONCAT(COALESCE(notes, ''), ' - Auto-stopped due to inactivity')
            WHERE status IN ('started', 'running') 
            AND started_at < NOW() - INTERVAL '2 hours'
        `);
        
        if (cleanupResult.rowCount > 0) {
            console.log(`Cleaned up ${cleanupResult.rowCount} stale sync sessions`);
        }
        
        // Get the latest completed sync to determine resumption point
        const lastSyncResult = await client.query(`
            SELECT 
                id, sync_type, emails_synced, started_at, completed_at,
                max_emails, query_filter, start_date
            FROM sync_sessions 
            WHERE status = 'completed' OR status = 'stopped'
            ORDER BY completed_at DESC 
            LIMIT 1
        `);
        
        let resumeConfig = {
            sync_type: 'full',
            max_emails: 1000,
            start_date: null,
            resume_from_last: true
        };
        
        if (lastSyncResult.rows.length > 0) {
            const lastSync = lastSyncResult.rows[0];
            console.log('Found last sync session:', lastSync);
            
            // Use the same configuration as the last sync
            resumeConfig = {
                sync_type: lastSync.sync_type || 'full',
                max_emails: lastSync.max_emails || 1000,
                start_date: lastSync.start_date,
                query_filter: lastSync.query_filter,
                resume_from_last: true,
                last_sync_info: {
                    session_id: lastSync.id,
                    emails_synced: lastSync.emails_synced,
                    completed_at: lastSync.completed_at
                }
            };
        }
        
        // Get current email count to show progress
        const emailCountResult = { rows: [{ total_emails: await fastEmailCount() }] };
        const currentEmailCount = parseInt(emailCountResult.rows[0].total_emails);
        
        console.log('Resume configuration:', resumeConfig);
        console.log('Current email count:', currentEmailCount);
        
        // Start new sync with resume configuration
        const syncStartBody = {
            sync_type: resumeConfig.sync_type,
            max_emails: resumeConfig.max_emails,
            start_date: resumeConfig.start_date,
            resume_mode: true
        };
        
        // Call the sync start endpoint internally
        const startResponse = await fetch('http://localhost:3002/api/sync/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(syncStartBody)
        });
        
        if (startResponse.ok) {
            const startData = await startResponse.json();
            
            res.json({
                success: true,
                message: 'Sync resumed successfully from where it left off',
                resume_config: resumeConfig,
                current_email_count: currentEmailCount,
                sync_start_data: startData,
                timestamp: new Date().toISOString()
            });
        } else {
            const errorData = await startResponse.json();
            res.status(500).json({
                success: false,
                message: 'Failed to resume sync',
                error: errorData.error || 'Unknown error',
                resume_config: resumeConfig,
                timestamp: new Date().toISOString()
            });
        }
        
    } catch (error) {
        console.error('Error resuming sync:', error);
        res.status(500).json({
            success: false,
            message: 'Error resuming sync',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Enhanced sync status endpoint with resumption information
app.get('/api/sync/resume-info', async (req, res) => {
    try {
        // Get the latest sync session for resumption analysis
        const lastSyncResult = await client.query(`
            SELECT 
                id, sync_type, status, emails_synced, started_at, completed_at,
                max_emails, query_filter, start_date, notes
            FROM sync_sessions 
            ORDER BY started_at DESC 
            LIMIT 1
        `);
        
        // Get current email count
        const emailCountResult = { rows: [{ total_emails: await fastEmailCount() }] };
        const currentEmailCount = parseInt(emailCountResult.rows[0].total_emails);
        
        // Get latest email date
        const latestEmailResult = await client.query(`
            SELECT MAX(date_received) as latest_email_date 
            FROM emails
        `);
        const latestEmailDate = latestEmailResult.rows[0].latest_email_date;
        
        let resumeInfo = {
            can_resume: false,
            resume_reason: null,
            last_sync: null,
            current_state: {
                total_emails: currentEmailCount,
                latest_email_date: latestEmailDate
            },
            resume_config: null
        };
        
        if (lastSyncResult.rows.length > 0) {
            const lastSync = lastSyncResult.rows[0];
            
            // Determine if we can resume
            const isStale = lastSync.status === 'started' || lastSync.status === 'running';
            const isRecent = lastSync.completed_at && 
                (new Date() - new Date(lastSync.completed_at)) < (24 * 60 * 60 * 1000); // 24 hours
            
            resumeInfo.last_sync = {
                session_id: lastSync.id,
                sync_type: lastSync.sync_type,
                status: lastSync.status,
                emails_synced: lastSync.emails_synced,
                started_at: lastSync.started_at,
                completed_at: lastSync.completed_at,
                notes: lastSync.notes
            };
            
            if (isStale) {
                resumeInfo.can_resume = true;
                resumeInfo.resume_reason = 'stale_session';
                resumeInfo.resume_config = {
                    sync_type: lastSync.sync_type || 'full',
                    max_emails: lastSync.max_emails || 1000,
                    start_date: lastSync.start_date,
                    query_filter: lastSync.query_filter
                };
            } else if (isRecent) {
                resumeInfo.can_resume = true;
                resumeInfo.resume_reason = 'continue_from_last';
                resumeInfo.resume_config = {
                    sync_type: lastSync.sync_type || 'full',
                    max_emails: lastSync.max_emails || 1000,
                    start_date: lastSync.start_date,
                    query_filter: lastSync.query_filter
                };
            }
        }
        
        res.json({
            success: true,
            resume_info: resumeInfo,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('Error getting resume info:', error);
        res.status(500).json({
            success: false,
            message: 'Error getting resume information',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Get individual email details
app.get('/api/db/email/:id', async (req, res) => {
    try {
        const emailId = parseInt(req.params.id);
        
        if (isNaN(emailId)) {
            return res.status(400).json({
                success: false,
                message: 'Invalid email ID',
                timestamp: new Date().toISOString()
            });
        }
        
        const result = await client.query(`
            SELECT 
                id,
                subject,
                sender,
                recipients,
                date_received,
                is_read,
                is_starred,
                body_plain,
                body_html,
                thread_id,
                gmail_id
            FROM emails 
            WHERE id = $1
        `, [emailId]);
        
        if (result.rows.length === 0) {
            return res.status(404).json({
                success: false,
                message: 'Email not found',
                timestamp: new Date().toISOString()
            });
        }
        
        const email = result.rows[0];
        
        // Format the response
        res.json({
            success: true,
            email: {
                id: email.id,
                subject: email.subject || 'No Subject',
                sender: email.sender || 'Unknown',
                recipient: email.recipients || 'Unknown',
                date_received: email.date_received ? email.date_received.toISOString() : null,
                is_read: email.is_read,
                is_starred: email.is_starred,
                content: email.body_html || email.body_plain || 'No content available',
                thread_id: email.thread_id,
                gmail_id: email.gmail_id
            },
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('Error fetching email details:', error);
        res.status(500).json({
            success: false,
            message: 'Error fetching email details',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Comprehensive Analytics Endpoints

// Get analytics overview data
app.get('/api/analytics/overview', async (req, res) => {
    try {
        const timeRange = req.query.range || '30'; // days
        
        // Calculate date filter
        let dateFilter = '';
        let dateParams = [];
        if (timeRange !== 'all') {
            const daysAgo = new Date();
            daysAgo.setDate(daysAgo.getDate() - parseInt(timeRange));
            dateFilter = 'WHERE date_received >= $1';
            dateParams = [daysAgo.toISOString()];
        }
        
        // Get basic counts
        let countsQuery = `
            SELECT 
                COUNT(*) as total_emails,
                COUNT(CASE WHEN is_read = false THEN 1 END) as unread_emails,
                COUNT(CASE WHEN is_starred = true THEN 1 END) as starred_emails,
                COUNT(CASE WHEN is_important = true THEN 1 END) as important_emails,
                COUNT(CASE WHEN is_spam = true THEN 1 END) as spam_emails,
                COUNT(CASE WHEN is_trash = true THEN 1 END) as trash_emails
            FROM emails`;
        
        if (dateFilter) {
            countsQuery += ` ${dateFilter}`;
        }
        
        const countsResult = await client.query(countsQuery, dateParams);
        
        // Get date range
        let dateRangeQuery = `
            SELECT 
                MIN(date_received) as oldest_email,
                MAX(date_received) as newest_email
            FROM emails`;
        
        if (dateFilter) {
            dateRangeQuery += ` ${dateFilter}`;
        }
        
        const dateRangeResult = await client.query(dateRangeQuery, dateParams);
        
        // Get top senders
        let topSendersQuery = `
            SELECT 
                sender,
                COUNT(*) as email_count,
                COUNT(CASE WHEN is_read = false THEN 1 END) as unread_count
            FROM emails`;
        
        if (dateFilter) {
            topSendersQuery += ` ${dateFilter}`;
        }
        
        topSendersQuery += ` GROUP BY sender ORDER BY email_count DESC LIMIT 10`;
        const topSendersResult = await client.query(topSendersQuery, dateParams);
        
        // Get hourly distribution
        let hourlyQuery = `
            SELECT 
                EXTRACT(HOUR FROM date_received) as hour,
                COUNT(*) as email_count
            FROM emails`;
        
        if (dateFilter) {
            hourlyQuery += ` ${dateFilter}`;
        }
        
        hourlyQuery += ` GROUP BY EXTRACT(HOUR FROM date_received) ORDER BY hour`;
        const hourlyResult = await client.query(hourlyQuery, dateParams);
        
        // Get daily distribution
        let dailyQuery = `
            SELECT 
                EXTRACT(DOW FROM date_received) as day_of_week,
                COUNT(*) as email_count
            FROM emails`;
        
        if (dateFilter) {
            dailyQuery += ` ${dateFilter}`;
        }
        
        dailyQuery += ` GROUP BY EXTRACT(DOW FROM date_received) ORDER BY day_of_week`;
        const dailyResult = await client.query(dailyQuery, dateParams);
        
        // Get labels/categories - skip for now as labels is JSONB
        const labelsResult = { rows: [] };
        
        // Get email length distribution
        let lengthQuery = `
            SELECT 
                CASE 
                    WHEN LENGTH(body_plain) < 100 THEN 'Short (< 100 chars)'
                    WHEN LENGTH(body_plain) < 500 THEN 'Medium (100-500 chars)'
                    WHEN LENGTH(body_plain) < 1000 THEN 'Long (500-1000 chars)'
                    ELSE 'Very Long (> 1000 chars)'
                END as length_category,
                COUNT(*) as email_count
            FROM emails`;
        
        if (dateFilter) {
            lengthQuery += ` ${dateFilter}`;
        }
        
        lengthQuery += ` GROUP BY 
                CASE 
                    WHEN LENGTH(body_plain) < 100 THEN 'Short (< 100 chars)'
                    WHEN LENGTH(body_plain) < 500 THEN 'Medium (100-500 chars)'
                    WHEN LENGTH(body_plain) < 1000 THEN 'Long (500-1000 chars)'
                    ELSE 'Very Long (> 1000 chars)'
                END
            ORDER BY email_count DESC`;
        const lengthResult = await client.query(lengthQuery, dateParams);
        
        // Get subject line analysis
        let subjectQuery = `
            SELECT 
                CASE 
                    WHEN subject ILIKE '%urgent%' OR subject ILIKE '%important%' THEN 'Urgent/Important'
                    WHEN subject ILIKE '%meeting%' OR subject ILIKE '%call%' THEN 'Meetings/Calls'
                    WHEN subject ILIKE '%newsletter%' OR subject ILIKE '%update%' THEN 'Newsletters/Updates'
                    WHEN subject ILIKE '%promo%' OR subject ILIKE '%sale%' THEN 'Promotions/Sales'
                    WHEN subject ILIKE '%receipt%' OR subject ILIKE '%invoice%' THEN 'Receipts/Invoices'
                    WHEN subject ILIKE '%password%' OR subject ILIKE '%reset%' THEN 'Security/Password'
                    ELSE 'Other'
                END as subject_category,
                COUNT(*) as email_count
            FROM emails`;
        
        if (dateFilter) {
            subjectQuery += ` ${dateFilter}`;
        }
        
        subjectQuery += ` GROUP BY 
                CASE 
                    WHEN subject ILIKE '%urgent%' OR subject ILIKE '%important%' THEN 'Urgent/Important'
                    WHEN subject ILIKE '%meeting%' OR subject ILIKE '%call%' THEN 'Meetings/Calls'
                    WHEN subject ILIKE '%newsletter%' OR subject ILIKE '%update%' THEN 'Newsletters/Updates'
                    WHEN subject ILIKE '%promo%' OR subject ILIKE '%sale%' THEN 'Promotions/Sales'
                    WHEN subject ILIKE '%receipt%' OR subject ILIKE '%invoice%' THEN 'Receipts/Invoices'
                    WHEN subject ILIKE '%password%' OR subject ILIKE '%reset%' THEN 'Security/Password'
                    ELSE 'Other'
                END
            ORDER BY email_count DESC`;
        const subjectResult = await client.query(subjectQuery, dateParams);
        
        const counts = countsResult.rows[0];
        const dateRange = dateRangeResult.rows[0];
        
        res.json({
            success: true,
            data: {
                overview: {
                    total_emails: parseInt(counts.total_emails),
                    unread_emails: parseInt(counts.unread_emails),
                    starred_emails: parseInt(counts.starred_emails),
                    important_emails: parseInt(counts.important_emails),
                    spam_emails: parseInt(counts.spam_emails),
                    trash_emails: parseInt(counts.trash_emails),
                    read_rate: counts.total_emails > 0 ? ((counts.total_emails - counts.unread_emails) / counts.total_emails * 100).toFixed(1) : 0
                },
                date_range: {
                    oldest_email: dateRange.oldest_email,
                    newest_email: dateRange.newest_email
                },
                top_senders: topSendersResult.rows,
                hourly_distribution: hourlyResult.rows,
                daily_distribution: dailyResult.rows,
                labels: labelsResult.rows,
                email_lengths: lengthResult.rows,
                subject_categories: subjectResult.rows
            },
            time_range: timeRange,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('Error fetching analytics overview:', error);
        res.status(500).json({
            success: false,
            message: 'Error fetching analytics overview',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Get email activity trends
app.get('/api/analytics/trends', async (req, res) => {
    try {
        const timeRange = req.query.range || '30'; // days
        
        let dateFilter = '';
        let dateParams = [];
        
        if (timeRange === 'all') {
            // For "all time", don't use a date filter
            dateFilter = '';
            dateParams = [];
        } else {
            // Calculate date for specific time range
            const daysAgo = new Date();
            daysAgo.setDate(daysAgo.getDate() - parseInt(timeRange));
            dateFilter = 'WHERE date_received >= $1';
            dateParams = [daysAgo.toISOString()];
        }
        
        // Get daily email counts
        let trendsQuery = `
            SELECT 
                DATE(date_received) as date,
                COUNT(*) as email_count,
                COUNT(CASE WHEN is_read = false THEN 1 END) as unread_count
            FROM emails`;
        
        if (dateFilter) {
            trendsQuery += ` ${dateFilter}`;
        }
        
        trendsQuery += ` GROUP BY DATE(date_received) ORDER BY date`;
        
        const trendsResult = await client.query(trendsQuery, dateParams);
        
        res.json({
            success: true,
            data: trendsResult.rows,
            time_range: timeRange,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('Error fetching email trends:', error);
        res.status(500).json({
            success: false,
            message: 'Error fetching email trends',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Reset sync context endpoint
app.post('/api/db/reset-sync-context', (req, res) => {
    try {
        // Reset all sync tracking variables
        syncDetected = false;
        syncStartTime = null;
        emailCountHistory = [];
        lastEmailCount = 0;
        lastCountCheck = Date.now();
        
        res.json({
            success: true,
            message: 'Sync context reset successfully',
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        console.error('Error resetting sync context:', error);
        res.status(500).json({
            success: false,
            message: 'Error resetting sync context',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// Health check endpoint
app.get('/api/health', (req, res) => {
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        server: 'nodejs_direct'
    });
});

// Proxy /api/v1/test/* to backend (used by script.js instead of direct localhost:8000)
app.all('/api/v1/test/*', async (req, res) => {
    try {
        const backendUrl = `http://gmail-backup-backend:8000${req.originalUrl}`;
        const fetchOpts = {
            method: req.method,
            headers: backendHeaders({'Content-Type': 'application/json'}),
            signal: AbortSignal.timeout(30000),
        };
        if (['POST', 'PUT', 'PATCH'].includes(req.method) && req.body && Object.keys(req.body).length > 0) {
            fetchOpts.body = JSON.stringify(req.body);
        }
        const backendRes = await fetch(backendUrl, fetchOpts);
        const data = await backendRes.json();
        res.status(backendRes.status).json(data);
    } catch (error) {
        console.error(`Backend proxy error for ${req.originalUrl}:`, error.message);
        res.status(502).json({ error: 'Backend unavailable', detail: error.message });
    }
});

// Start server
async function startServer() {
    await connectDB();
    
    app.listen(port, () => {
        console.log(`Frontend server running on http://localhost:${port}`);
        console.log('Direct database access available');
    });
}

startServer().catch(console.error);
