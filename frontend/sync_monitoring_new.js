// New database-first sync monitoring endpoint content
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
                        metadata, notes, created_at, updated_at
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
                    
                    syncProgress = {
                        is_active: true,
                        start_time: session.started_at,
                        elapsed_time: formatElapsedTime(elapsedMs),
                        emails_processed: session.emails_processed || 0,
                        emails_per_minute: elapsedMinutes > 0 ? Math.round((session.emails_processed || 0) / elapsedMinutes) : 0,
                        progress_percentage: session.max_emails ? Math.min(((session.emails_processed || 0) / session.max_emails) * 100, 95) : 0,
                        estimated_completion: null,
                        current_batch: session.batches_processed || 1,
                        total_batches: session.batches_processed || 1,
                        sync_type: session.sync_type || 'unknown',
                        status: 'syncing',
                        actual_synced: session.emails_synced || 0,
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
                    
                    // Calculate recent activity from sync session data
                    const lastActivityTime = new Date(session.last_activity_at || session.started_at).getTime();
                    const timeSinceLastActivity = currentTime - lastActivityTime;
                    
                    // Consider it recent activity if updated within last 5 minutes
                    if (timeSinceLastActivity < 5 * 60 * 1000) {
                        recentActivity.has_recent_activity = true;
                        // For recent activity, use estimated emails processed in batches
                        const estimatedBatchEmails = (session.batches_processed || 0) * 100;
                        recentActivity.recent_emails_5min = Math.max(estimatedBatchEmails, session.emails_processed || 0);
                        
                        // Consider it very recent if within last minute
                        if (timeSinceLastActivity < 60 * 1000) {
                            recentActivity.recent_emails_1min = Math.max(estimatedBatchEmails, session.emails_processed || 0);
                        }
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
