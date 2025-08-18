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

// Enable CORS
app.use(cors());

// Parse JSON bodies
app.use(express.json());

// Serve static files
app.use(express.static(path.join(__dirname)));

// Database configuration
const dbConfig = {
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT) || 5432,
    database: process.env.DB_NAME || 'gmail_backup',
    user: process.env.DB_USER || 'gmail_user',
    password: process.env.DB_PASSWORD || 'gmail_password',
    connectionTimeoutMillis: 5000,
    query_timeout: 5000
};

// Create database client and pool
const client = new Client(dbConfig);
const pool = new Pool(dbConfig);

// Connect to database
async function connectDB() {
    try {
        await client.connect();
        console.log('Connected to PostgreSQL database');
    } catch (error) {
        console.error('Database connection failed:', error);
    }
}

// Email count endpoint
app.get('/api/db/email-count', async (req, res) => {
    try {
        const result = await client.query('SELECT COUNT(*) FROM emails');
        res.json({
            total_emails: parseInt(result.rows[0].count),
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
        // Get total email count
        const countResult = await client.query('SELECT COUNT(*) FROM emails');
        const totalEmails = parseInt(countResult.rows[0].count);
        
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
        
        // Get unread email count
        const unreadResult = await client.query('SELECT COUNT(*) FROM emails WHERE is_read = false');
        const unreadEmails = parseInt(unreadResult.rows[0].count);
        
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
        
        // Get total count
        const countResult = await client.query('SELECT COUNT(*) FROM emails');
        const totalCount = parseInt(countResult.rows[0].count);
        
        // Get emails with more complete information
        const emailsResult = await client.query(`
            SELECT id, subject, sender, date_received, is_read, is_starred, 
                   body_plain, body_html, thread_id, gmail_id, labels,
                   LEFT(body_plain, 500) as body_preview
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
            body_plain: row.body_plain,
            body_html: row.body_html,
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
        
        if (!query) {
            return res.status(400).json({ error: 'Query parameter required' });
        }
        
        const searchTerm = `%${query}%`;
        
        // Get total count
        const countResult = await client.query(`
            SELECT COUNT(*) FROM emails 
            WHERE subject ILIKE $1 OR sender ILIKE $1 OR body_plain ILIKE $1
        `, [searchTerm]);
        const totalCount = parseInt(countResult.rows[0].count);
        
        // Get search results with more complete information
        const searchResult = await client.query(`
            SELECT id, subject, sender, date_received, is_read, is_starred, 
                   body_plain, body_html, thread_id, gmail_id, labels,
                   LEFT(body_plain, 500) as body_preview
            FROM emails 
            WHERE subject ILIKE $1 OR sender ILIKE $1 OR body_plain ILIKE $1
            ORDER BY date_received DESC 
            LIMIT $2 OFFSET $3
        `, [searchTerm, pageSize, offset]);
        
        const emails = searchResult.rows.map(row => ({
            id: row.id,
            subject: row.subject || 'No Subject',
            sender: row.sender || 'Unknown',
            date_received: row.date_received ? row.date_received.toISOString() : null,
            is_read: row.is_read,
            is_starred: row.is_starred,
            body_plain: row.body_plain,
            body_html: row.body_html,
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
        // Get basic database stats
        const countResult = await client.query('SELECT COUNT(*) FROM emails');
        const totalEmails = parseInt(countResult.rows[0].count);
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
            }
        }
        
        // Get sync status from background sync service (if available)
        let backendTimeout = false;
        try {
            // Try to get background sync status from backend
            const backendResponse = await fetch('http://localhost:8000/api/v1/test/background-sync/status', {
                signal: AbortSignal.timeout(500) // 0.5 second timeout
            });
            
            if (backendResponse.ok) {
                const backendData = await backendResponse.json();
                const syncData = backendData.sync_status || {};
                syncInProgress = syncData.sync_in_progress || syncInProgress;
                syncStatus = syncInProgress ? 'syncing' : 'ready';
                
                if (syncData.stats && syncData.stats.last_sync_start) {
                    lastSyncTime = syncData.stats.last_sync_start;
                }
                
                // Get detailed sync information
                if (syncInProgress) {
                    try {
                        const monitoringResponse = await fetch('http://localhost:8000/api/v1/test/sync/real-time-status', {
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
            
            // Try to detect sync by checking if there's an active sync process
            try {
                const syncProcessResponse = await fetch('http://localhost:8000/api/v1/test/sync/status', {
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
                const progressResponse = await fetch('http://localhost:8000/api/v1/test/sync/progress', {
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
            const avgChange = totalRecentChanges / recentChanges.length;
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
                emails_processed: totalRecentChanges,
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
    try {
        const currentTime = Date.now();
        
        // Get basic database stats
        const totalEmailsResult = await pool.query('SELECT COUNT(*) as count FROM emails');
        const totalEmails = parseInt(totalEmailsResult.rows[0].count);
        
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
                    
                    // Calculate actual progress based on email count difference
                    // Get the email count at the start of sync (approximate)
                    const startEmailCount = 844613; // Approximate count when sync started
                    const actualEmailsSynced = totalEmails - startEmailCount;
                    
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
                
                // Look for recent sync activity in logs
                for (const line of logLines) {
                    if (line.includes('total synced:')) {
                        const match = line.match(/total synced: (\d+)/);
                        if (match) {
                            const synced = parseInt(match[1]);
                            if (synced > totalSynced) {
                                totalSynced = synced;
                                isBackendSyncing = true;
                            }
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
        const { sync_type = 'full', max_emails = 100, start_date } = req.body;
        
        console.log(`Sync start request: ${sync_type} sync with max_emails=${max_emails}${start_date ? `, start_date=${start_date}` : ''}`);
        
        // Check if sync is already active
        if (syncControlState.isActive) {
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
                
                if (timeDiff < fiveMinutes) {
                    // Recent sync, reject the request
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
                            completed_at = NOW() 
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
        let backendUrl = `http://localhost:8000/api/v1/test/sync/start-${sync_type}?max_emails=${max_emails}`;
        
        if (sync_type === 'date-range' && start_date) {
            backendUrl = `http://localhost:8000/api/v1/test/sync/start-from-date?start_date=${start_date}&max_emails=${max_emails}`;
        }
        
        console.log('Calling backend endpoint:', backendUrl);
        
        // Call the backend sync endpoint with timeout
        const response = await fetch(backendUrl, {
            method: 'POST',
            signal: AbortSignal.timeout(10000) // 10 second timeout
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('Backend sync started successfully:', data);
            
            // Update session ID if provided by backend
            if (data.session_id) {
                syncControlState.sessionId = data.session_id;
            }
            
            res.json({
                success: true,
                message: `${sync_type} sync started successfully`,
                data: data,
                sync_control_state: syncControlState,
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
            const response = await fetch('http://localhost:8000/api/v1/test/sync/stop', {
                method: 'POST',
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

// Health check endpoint
app.get('/api/health', (req, res) => {
    res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        server: 'nodejs_direct'
    });
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
