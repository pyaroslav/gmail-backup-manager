// Global state
console.debug('[init] Script loading started');
let currentPage = 1;
let pageSize = 25;
let totalEmails = 0;
let emails = [];
let selectedEmails = new Set();
let selectedEmail = null;
let showEmailDetail = false;
let sortOrder = 'desc';

// Global variable to store current search results
let currentSearchResults = [];

// Search pagination variables
let searchCurrentPage = 1;
let searchPageSize = 25;
let searchTotalResults = 0;
let currentSearchTerm = '';
let currentSearchFilter = 'all';
let currentDateFrom = '';
let currentDateTo = '';

// DOM elements
const emailInterface = document.getElementById('emailInterface');
const dashboard = document.getElementById('dashboard');
const emailList = document.getElementById('emailList');
const emailDetailPanel = document.getElementById('emailDetailPanel');
const emailListPanel = document.getElementById('emailListPanel');
const detailContent = document.getElementById('detailContent');
const emailCount = document.getElementById('emailCount');
const selectAllCheckbox = document.getElementById('selectAll');
const bulkActions = document.getElementById('bulkActions');
const selectedCount = document.getElementById('selectedCount');
const loadingOverlay = document.getElementById('loadingOverlay');

// Navigation will be initialized in DOMContentLoaded

// Show page function
function showPage(page) {
    console.log('showPage called with:', page);
    
    // Hide all pages first
    document.getElementById('dashboard').style.display = 'none';
    document.getElementById('emailInterface').style.display = 'none';
    document.getElementById('searchPage').style.display = 'none';
    document.getElementById('syncPage').style.display = 'none';
    document.getElementById('analyticsPage').style.display = 'none';
    document.getElementById('settingsPage').style.display = 'none';
    
    // Show the selected page
    switch (page) {
        case 'dashboard':
            console.log('Showing dashboard page');
            document.getElementById('dashboard').style.display = 'block';
            stopSyncStatusRefresh(); // Stop sync refresh when leaving sync page
            loadDashboard();
            break;
        case 'emails':
            console.log('Showing emails page');
            document.getElementById('emailInterface').style.display = 'flex';
            stopSyncStatusRefresh(); // Stop sync refresh when leaving sync page
            loadEmails();
            break;
        case 'search':
            console.log('Showing search page');
            document.getElementById('searchPage').style.display = 'block';
            stopSyncStatusRefresh(); // Stop sync refresh when leaving sync page
            initializeSearch();
            break;
        case 'sync':
            console.log('Showing sync page');
            document.getElementById('syncPage').style.display = 'block';
            loadSyncPage();
            initializeSync();
            break;
        case 'analytics':
            console.log('Showing analytics page');
            document.getElementById('analyticsPage').style.display = 'block';
            console.log('Analytics page element:', document.getElementById('analyticsPage'));
            stopSyncStatusRefresh(); // Stop sync refresh when leaving sync page
            loadAnalytics();
            break;
        case 'settings':
            console.log('Showing settings page');
            document.getElementById('settingsPage').style.display = 'block';
            loadSettings();
            break;
        default:
            console.log('Unknown page, showing dashboard');
            document.getElementById('dashboard').style.display = 'block';
            loadDashboard();
    }
}

// Initialize navigation
function initializeNavigation() {
    console.log('Initializing navigation...');
    
    // Add click handlers to navigation items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.getAttribute('data-page');
            console.log('Navigation clicked:', page);
            
            // Update active state
            document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            // Show page
            showPage(page);
        });
    });
    
    console.log('Navigation initialized');
}

// Health check function
async function checkBackendHealth() {
    try {
        const response = await fetch('/api/db/health');
        if (response.ok) {
            console.log('Backend is healthy');
            return true;
        } else {
            console.error('Backend health check failed:', response.status);
            return false;
        }
    } catch (error) {
        console.error('Backend health check error:', error);
        return false;
    }
}

async function loadEmails(page = 1) {
    try {
        // Show loading state first
        document.getElementById('emailList').innerHTML = '<div class="loading">Loading emails...</div>';
        
        // Try Node.js endpoints first, avoid hanging backend calls
        const endpoints = [
            `/api/db/emails?page=${page}&page_size=25`,  // Node.js direct server
            `/api/db/email-count`  // Fallback to just count if emails fail
        ];
        
        let response = null;
        let usedEndpoint = '';
        
        for (const endpoint of endpoints) {
            try {
                response = await Promise.race([
                    fetch(endpoint),
                    new Promise((_, reject) => 
                        setTimeout(() => reject(new Error('Timeout')), 5000)
                    )
                ]);
                
                if (response.ok) {
                    usedEndpoint = endpoint;
                    break;
                }
            } catch (error) {
                console.log(`Endpoint ${endpoint} failed: ${error.message}`);
                continue;
            }
        }
        
        if (!response || !response.ok) {
            throw new Error('All endpoints failed');
        }
        
        const data = await response.json();
        
        // Update global variables
        totalEmails = data.total_count || 0;
        emails = data.emails || [];
        currentPage = data.page || 1;
        
        // Update email count display
        updateEmailCount();
        
        if (data.emails.length === 0) {
            document.getElementById('emailList').innerHTML = '<div class="no-emails">No emails found</div>';
            return;
        }
        
        // Use renderEmailList to display emails consistently
        renderEmailList();
        
        // Update pagination
        showPagination();
        
        // Show endpoint notice
        console.log(`Emails loaded using: ${usedEndpoint}`);
        
    } catch (error) {
        console.error('Error loading emails:', error);
        document.getElementById('emailList').innerHTML = `
            <div class="error-message">
                <h3>Error Loading Emails</h3>
                <p>${error.message}</p>
                <button class="btn btn-primary" onclick="loadEmails(currentPage)">Retry</button>
            </div>
        `;
    }
}

// Fallback email loading method
async function loadEmailsFallback(page = 1) {
    console.log('Using fallback email loading method...');
    
    // Try a simpler endpoint with smaller page size
    const response = await Promise.race([
        fetch(`/api/v1/test/emails/?page=${page}&page_size=10`),
        new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Fallback timeout')), 15000)
        )
    ]);
    
    if (!response.ok) {
        throw new Error(`Fallback HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Update global variables
    totalEmails = data.total_count || 0;
    emails = data.emails || [];
    currentPage = data.page || 1;
    
    // Update email count display
    updateEmailCount();
    
    if (data.emails.length === 0) {
        document.getElementById('emailList').innerHTML = `
            <div class="no-emails">
                <i class="fas fa-inbox"></i>
                <h3>No Emails Found</h3>
                <p>No emails were found in the database.</p>
            </div>
        `;
        return;
    }
    
    // Use renderEmailList to display emails consistently
    renderEmailList();
    
    // Update pagination
    showPagination();
    
    // Show fallback notice
    const notice = document.createElement('div');
    notice.className = 'fallback-notice';
    notice.innerHTML = `
        <div class="alert alert-info">
            <i class="fas fa-info-circle"></i>
            <strong>Note:</strong> Using fallback loading mode due to sync operations. 
            Showing ${data.emails.length} emails per page.
        </div>
    `;
    document.getElementById('emailList').insertBefore(notice, document.getElementById('emailList').firstChild);
}

// Render email list
function renderEmailList() {
    emailList.innerHTML = '';
    
    if (emails.length === 0) {
        emailList.innerHTML = `
            <div class="text-center" style="padding: 2rem;">
                <i class="fas fa-envelope" style="font-size: 3rem; color: #d1d5db; margin-bottom: 1rem;"></i>
                <p class="text-muted">No emails found</p>
            </div>
        `;
        return;
    }
    
    emails.forEach(email => {
        const emailElement = createEmailElement(email);
        emailList.appendChild(emailElement);
    });
}

// Create email element
function createEmailElement(email) {
    const div = document.createElement('div');
    div.className = `email-item ${email.is_read ? '' : 'unread'} ${selectedEmail?.id === email.id ? 'selected' : ''}`;
    div.dataset.emailId = email.id;
    
    const date = email.date_received ? new Date(email.date_received).toLocaleDateString() : '';
    const preview = email.body_plain ? email.body_plain.substring(0, 100) + '...' : 'No preview available';
    
    div.innerHTML = `
        <div class="email-checkbox">
            <label class="checkbox-container">
                <input type="checkbox" ${selectedEmails.has(email.id) ? 'checked' : ''}>
                <span class="checkmark"></span>
            </label>
        </div>
        <div class="email-star ${email.is_starred ? 'starred' : ''}" onclick="toggleStar('${email.id}', event)">
            <i class="fas fa-star"></i>
        </div>
        <div class="email-content" onclick="selectEmail('${email.id}')">
            <div class="email-header">
                <span class="email-sender">${email.sender || 'Unknown'}</span>
                <span class="email-date">${date}</span>
            </div>
            <div class="email-subject">${email.subject || 'No subject'}</div>
            <div class="email-preview">${preview}</div>
        </div>
    `;
    
    // Add event listeners
    const checkbox = div.querySelector('input[type="checkbox"]');
    checkbox.addEventListener('change', (e) => {
        e.stopPropagation();
        toggleEmailSelection(email.id);
    });
    
    return div;
}

// Select email (for emails page)
function selectEmail(emailId) {
    console.log('selectEmail called with emailId:', emailId, 'type:', typeof emailId);
    console.log('emails array length:', emails.length);
    
    // Convert emailId to number for comparison since API returns numeric IDs
    const numericEmailId = parseInt(emailId);
    console.log('Converted emailId to number:', numericEmailId);
    
    const email = emails.find(e => e.id === numericEmailId);
    console.log('Found email:', email);
    
    if (!email) {
        console.error('Email not found in emails array');
        console.log('Available email IDs:', emails.map(e => e.id).slice(0, 5));
        return;
    }
    
    selectedEmail = email;
    showEmailDetail = true;
    
    // Update UI - remove selected state from all email items
    document.querySelectorAll('.email-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    // Add selected state to clicked item
    const selectedElement = document.querySelector(`[data-email-id="${emailId}"]`);
    if (selectedElement) {
        selectedElement.classList.add('selected');
        console.log('Added selected class to email item');
    } else {
        console.error('Selected email element not found');
    }
    
    // Show emails page detail panel
    console.log('Detail panel elements:', {
        emailDetailPanel: emailDetailPanel,
        emailListPanel: emailListPanel,
        detailContent: detailContent
    });
    
    if (emailDetailPanel && emailListPanel && detailContent) {
        emailDetailPanel.style.display = 'flex';
        emailListPanel.classList.add('with-detail');
        
        // Load email detail
        loadEmailDetail(email);
        console.log('Emails page detail loaded for:', email.subject);
    } else {
        console.error('Emails detail panel elements not found');
    }
    
    // Mark as read if unread
    if (!email.is_read) {
        markAsRead(emailId);
    }
}

// Select search email (for search page)
function selectSearchEmail(emailId) {
    console.log('selectSearchEmail called with emailId:', emailId, 'type:', typeof emailId);
    console.log('currentSearchResults length:', currentSearchResults.length);
    
    // Convert emailId to number for comparison since API returns numeric IDs
    const numericEmailId = parseInt(emailId);
    console.log('Converted emailId to number:', numericEmailId);
    
    const email = currentSearchResults.find(e => e.id === numericEmailId);
    console.log('Found email:', email);
    
    if (!email) {
        console.error('Email not found in currentSearchResults');
        console.log('Available search result IDs:', currentSearchResults.map(e => e.id).slice(0, 5));
        return;
    }
    
    selectedEmail = email;
    showEmailDetail = true;
    
    // Update UI - remove selected state from all email items
    document.querySelectorAll('.email-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    // Add selected state to clicked item
    const selectedElement = document.querySelector(`[data-email-id="${emailId}"]`);
    if (selectedElement) {
        selectedElement.classList.add('selected');
    }
    
    // Show search page detail panel
    const searchDetailPanel = document.getElementById('searchEmailDetailPanel');
    const searchDetailContent = document.getElementById('searchDetailContent');
    const searchListPanel = document.querySelector('#searchPage .email-list-panel');
    
    console.log('Search detail panel elements:', {
        searchDetailPanel: searchDetailPanel,
        searchDetailContent: searchDetailContent,
        searchListPanel: searchListPanel
    });
    
    if (searchDetailPanel && searchDetailContent && searchListPanel) {
        searchDetailPanel.style.display = 'flex';
        searchListPanel.classList.add('with-detail');
        
        // Load email detail in search panel
        loadSearchEmailDetail(email, searchDetailContent);
        console.log('Search email detail loaded for:', email.subject);
    } else {
        console.error('Search detail panel elements not found');
    }
    
    // Mark as read if unread
    if (!email.is_read) {
        markAsRead(emailId); // markAsRead already handles string to number conversion
    }
}

// Render email detail HTML into a target element
function renderEmailDetail(email, bodyContent, targetElement) {
    const date = email.date_received ? new Date(email.date_received).toLocaleString() : '';
    const emailDetailHtml = `
        <div class="email-detail-subject">${email.subject || 'No subject'}</div>
        <div class="email-detail-meta">
            <div class="email-detail-meta-item">
                <i class="fas fa-user"></i>
                <span>${email.sender || 'Unknown'}</span>
            </div>
            <div class="email-detail-meta-item">
                <i class="fas fa-calendar"></i>
                <span>${date}</span>
            </div>
        </div>
        <div class="email-detail-body">
            ${bodyContent}
        </div>
        <div class="email-detail-actions">
            <button class="btn-detail-action primary" onclick="toggleReadStatus(${email.id})">
                <i class="fas fa-${email.is_read ? 'eye-slash' : 'eye'}"></i>
                ${email.is_read ? 'Mark Unread' : 'Mark Read'}
            </button>
            <button class="btn-detail-action secondary" onclick="toggleStar(${email.id})">
                <i class="fas fa-${email.is_starred ? 'star' : 'star'}"></i>
                ${email.is_starred ? 'Unstar' : 'Star'}
            </button>
            <button class="btn-detail-action danger" onclick="deleteEmail(${email.id})">
                <i class="fas fa-trash"></i>
                Delete
            </button>
        </div>
    `;
    targetElement.innerHTML = emailDetailHtml;
}

// Fetch full email content from API then render
function fetchAndRenderEmailDetail(email, targetElement) {
    // Show loading state immediately with preview text
    renderEmailDetail(email, '<div class="loading">Loading full content...</div>', targetElement);

    fetch(`/api/db/email/${email.id}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.email) {
                const body = data.email.content || email.body_preview || 'No content available';
                renderEmailDetail(email, body, targetElement);
            } else {
                renderEmailDetail(email, email.body_preview || 'No content available', targetElement);
            }
        })
        .catch(error => {
            console.error('Error fetching email content:', error);
            renderEmailDetail(email, email.body_preview || 'Failed to load content', targetElement);
        });
}

// Load email detail
function loadEmailDetail(email) {
    console.log('loadEmailDetail called with email:', email);
    if (detailContent) {
        fetchAndRenderEmailDetail(email, detailContent);
    } else {
        console.error('detailContent element not found');
    }
}

// Close email detail
function closeEmailDetail() {
    showEmailDetail = false;
    selectedEmail = null;
    emailDetailPanel.style.display = 'none';
    emailListPanel.classList.remove('with-detail');
    
    // Remove selected state from all emails
    document.querySelectorAll('.email-item').forEach(item => {
        item.classList.remove('selected');
    });
}

// Load search email detail
function loadSearchEmailDetail(email, targetElement) {
    console.log('Loading search email detail for:', email);
    if (targetElement) {
        fetchAndRenderEmailDetail(email, targetElement);
    } else {
        console.error('Detail content element is null or undefined');
    }
}

// Close search email detail
function closeSearchEmailDetail() {
    const searchDetailPanel = document.getElementById('searchEmailDetailPanel');
    const searchListPanel = document.querySelector('#searchPage .email-list-panel');
    
    searchDetailPanel.style.display = 'none';
    searchListPanel.classList.remove('with-detail');
    
    // Remove selected state from all search email items
    document.querySelectorAll('#searchPage .email-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    selectedEmail = null;
    showEmailDetail = false;
}

// Toggle email selection
function toggleEmailSelection(emailId) {
    if (selectedEmails.has(emailId)) {
        selectedEmails.delete(emailId);
    } else {
        selectedEmails.add(emailId);
    }
    
    updateBulkActions();
    updateSelectAllState();
}

// Update bulk actions visibility
function updateBulkActions() {
    if (selectedEmails.size > 0) {
        bulkActions.style.display = 'flex';
        selectedCount.textContent = `${selectedEmails.size} selected`;
    } else {
        bulkActions.style.display = 'none';
    }
}

// Update select all state
function updateSelectAllState() {
    const allSelected = emails.length > 0 && selectedEmails.size === emails.length;
    const someSelected = selectedEmails.size > 0 && selectedEmails.size < emails.length;
    
    selectAllCheckbox.checked = allSelected;
    selectAllCheckbox.indeterminate = someSelected;
}

// Select all emails
function selectAllEmails() {
    if (selectedEmails.size === emails.length) {
        selectedEmails.clear();
    } else {
        emails.forEach(email => selectedEmails.add(email.id));
    }
    
    renderEmailList();
    updateBulkActions();
    updateSelectAllState();
}

// Bulk actions
function performBulkAction(action) {
    selectedEmails.forEach(emailId => {
        switch (action) {
            case 'read':
                markAsRead(emailId);
                break;
            case 'unread':
                markAsUnread(emailId);
                break;
            case 'star':
                toggleStar(emailId);
                break;
            case 'delete':
                deleteEmail(emailId);
                break;
        }
    });
    
    selectedEmails.clear();
    updateBulkActions();
    updateSelectAllState();
}

// API functions
async function markAsRead(emailId) {
    // Convert emailId to number for comparison since API returns numeric IDs
    const numericEmailId = parseInt(emailId);
    
    try {
        await fetch(`/api/db/emails/${numericEmailId}/read`, { method: 'POST' });
        const email = emails.find(e => e.id === numericEmailId);
        if (email) email.is_read = true;
        renderEmailList();
    } catch (error) {
        console.error('Error marking as read:', error);
    }
}

async function markAsUnread(emailId) {
    // Convert emailId to number for comparison since API returns numeric IDs
    const numericEmailId = parseInt(emailId);
    
    try {
        await fetch(`/api/db/emails/${numericEmailId}/unread`, { method: 'POST' });
        const email = emails.find(e => e.id === numericEmailId);
        if (email) email.is_read = false;
        renderEmailList();
    } catch (error) {
        console.error('Error marking as unread:', error);
    }
}

async function toggleStar(emailId, event) {
    if (event) event.stopPropagation();
    
    // Convert emailId to number for comparison since API returns numeric IDs
    const numericEmailId = parseInt(emailId);
    
    try {
        await fetch(`/api/db/emails/${numericEmailId}/star`, { method: 'POST' });
        const email = emails.find(e => e.id === numericEmailId);
        if (email) email.is_starred = !email.is_starred;
        renderEmailList();
        
        // Update detail panel if this email is selected
        if (selectedEmail && selectedEmail.id === numericEmailId) {
            selectedEmail.is_starred = email.is_starred;
            loadEmailDetail(selectedEmail);
        }
    } catch (error) {
        console.error('Error toggling star:', error);
    }
}

async function deleteEmail(emailId) {
    if (!confirm('Are you sure you want to delete this email?')) return;
    
    // Convert emailId to number for comparison since API returns numeric IDs
    const numericEmailId = parseInt(emailId);
    
    try {
        await fetch(`/api/db/emails/${numericEmailId}`, { method: 'DELETE' });
        
        // Remove from emails array
        emails = emails.filter(e => e.id !== numericEmailId);
        
        // Remove from selected emails
        selectedEmails.delete(numericEmailId);
        
        // Close detail if this email was selected
        if (selectedEmail && selectedEmail.id === numericEmailId) {
            closeEmailDetail();
        }
        
        renderEmailList();
        updateEmailCount();
        updateBulkActions();
    } catch (error) {
        console.error('Error deleting email:', error);
    }
}

// Toggle read status
function toggleReadStatus(emailId) {
    // Convert emailId to number for comparison since API returns numeric IDs
    const numericEmailId = parseInt(emailId);
    
    const email = emails.find(e => e.id === numericEmailId);
    if (email) {
        if (email.is_read) {
            markAsUnread(emailId);
        } else {
            markAsRead(emailId);
        }
    }
}

// Update email count
function updateEmailCount() {
    emailCount.textContent = `${totalEmails.toLocaleString()} emails`;
}

// Show pagination
function showPagination() {
    const pagination = document.getElementById('pagination');
    const totalPages = Math.ceil(totalEmails / pageSize);
    
    if (totalPages > 1) {
        pagination.style.display = 'flex';
        document.getElementById('pageInfo').textContent = `Page ${currentPage} of ${totalPages}`;
        document.getElementById('prevPage').disabled = currentPage === 1;
        document.getElementById('nextPage').disabled = currentPage === totalPages;
    } else {
        pagination.style.display = 'none';
    }
}

// Pagination handlers
document.getElementById('prevPage').addEventListener('click', () => {
    if (currentPage > 1) {
        currentPage--;
        loadEmails(currentPage);
    }
});

document.getElementById('nextPage').addEventListener('click', () => {
    const totalPages = Math.ceil(totalEmails / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        loadEmails(currentPage);
    }
});

// Search pagination handlers
document.getElementById('searchPrevPage').addEventListener('click', () => {
    if (searchCurrentPage > 1) {
        searchCurrentPage--;
        performSearch(searchCurrentPage);
    }
});

document.getElementById('searchNextPage').addEventListener('click', () => {
    const totalPages = Math.ceil(searchTotalResults / searchPageSize);
    if (searchCurrentPage < totalPages) {
        searchCurrentPage++;
        performSearch(searchCurrentPage);
    }
});

// Sort handler
document.getElementById('sortBtn').addEventListener('click', () => {
    sortOrder = sortOrder === 'desc' ? 'asc' : 'desc';
    loadEmails(currentPage);
});

// Select all handler
selectAllCheckbox.addEventListener('change', selectAllEmails);

// Bulk action handlers
document.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', () => {
        performBulkAction(btn.dataset.action);
    });
});

// Close detail handler
document.getElementById('closeDetail').addEventListener('click', closeEmailDetail);

// Load dashboard
function loadDashboard() {
    console.debug('[dashboard] Loading data...');
    
    // Use the comprehensive dashboard endpoint
    const dashboardEndpoint = '/api/db/dashboard';
    
    Promise.race([
        fetch(dashboardEndpoint),
        new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Dashboard timeout')), 5000)
        )
    ])
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.debug('[dashboard] Data received:', data);

        // Debug: Check if elements exist
        const totalEmailsElement = document.getElementById('totalEmails');
        const unreadEmailsElement = document.getElementById('unreadEmails');
        const lastSyncElement = document.getElementById('lastSync');
        const starredEmailsElement = document.getElementById('starredEmails');
        const databaseSizeElement = document.getElementById('databaseSize');

        console.debug('[dashboard] Element check:', {
            totalEmails: !!totalEmailsElement,
            unreadEmails: !!unreadEmailsElement,
            lastSync: !!lastSyncElement,
            starredEmails: !!starredEmailsElement,
            databaseSize: !!databaseSizeElement
        });
        
        // Update total emails
        const totalEmails = data.total_emails || 0;
        if (totalEmailsElement) {
            totalEmailsElement.textContent = totalEmails.toLocaleString();
            console.debug('[ok] Updated totalEmails element');
        } else {
            console.debug('[error] totalEmails element not found!');
        }
        
        // Update unread emails
        const unreadEmails = data.unread_emails || 0;
        if (unreadEmailsElement) {
            unreadEmailsElement.textContent = unreadEmails.toLocaleString();
            console.debug('[ok] Updated unreadEmails element');
        } else {
            console.debug('[error] unreadEmails element not found!');
        }
        
        // Update last sync time
        let lastSyncDisplay = 'Never';
        if (data.last_sync_time) {
            const lastSync = new Date(data.last_sync_time);
            lastSyncDisplay = lastSync.toLocaleString();
        } else if (data.latest_email_date) {
            const latestEmail = new Date(data.latest_email_date);
            lastSyncDisplay = latestEmail.toLocaleString();
        }
        if (lastSyncElement) {
            lastSyncElement.textContent = lastSyncDisplay;
            console.debug('[ok] Updated lastSync element');
        } else {
            console.debug('[error] lastSync element not found!');
        }
        
        // Update starred emails (placeholder for now)
        if (starredEmailsElement) {
            starredEmailsElement.textContent = '0'; // TODO: Get actual starred count
            console.debug('[ok] Updated starredEmails element');
        } else {
            console.debug('[error] starredEmails element not found!');
        }
        
        // Update database size
        if (databaseSizeElement) {
            if (data.database_size_gb !== undefined) {
                databaseSizeElement.textContent = `${data.database_size_gb} GB`;
            } else if (data.database_size_pretty) {
                databaseSizeElement.textContent = data.database_size_pretty;
            } else {
                databaseSizeElement.textContent = `${totalEmails.toLocaleString()} emails`;
            }
            console.debug('[ok] Updated databaseSize element');
        } else {
            console.debug('[error] databaseSize element not found!');
        }
        
        // Update recent emails section if it exists
        console.debug('[email] Recent emails data check:', {
            has_recent_emails: !!data.recent_emails,
            recent_emails_length: data.recent_emails ? data.recent_emails.length : 0,
            recent_emails: data.recent_emails ? data.recent_emails.slice(0, 2) : null // Show first 2 for debugging
        });
        
        if (data.recent_emails && data.recent_emails.length > 0) {
            updateRecentEmailsSection(data.recent_emails);
        } else {
            console.debug('[warn] No recent emails data available');
        }
        
        console.debug('[ok] Dashboard updated successfully');
        console.debug(`[data] Total emails: ${totalEmails.toLocaleString()}`);
        console.debug(`[sync] Sync status: ${syncStatus}`);
        console.debug(`[time] Last sync: ${lastSyncDisplay}`);
    })
    .catch(error => {
        console.debug('[error] Dashboard loading failed:', error);
        
        // Fallback to simple email count
        fetch('/api/db/email-count')
            .then(response => response.json())
            .then(data => {
                const totalEmails = data.total_emails || 0;
                const totalEmailsElement = document.getElementById('totalEmails');
                const unreadEmailsElement = document.getElementById('unreadEmails');
                const lastSyncElement = document.getElementById('lastSync');
                const starredEmailsElement = document.getElementById('starredEmails');
                
                if (totalEmailsElement) {
                    totalEmailsElement.textContent = totalEmails.toLocaleString();
                }
                if (unreadEmailsElement) {
                    unreadEmailsElement.textContent = '0';
                }
                if (lastSyncElement) {
                    lastSyncElement.textContent = 'Recent';
                }
                if (starredEmailsElement) {
                    starredEmailsElement.textContent = '0';
                }
                console.debug('[ok] Dashboard updated with fallback data');
            })
            .catch(fallbackError => {
                console.debug('[error] Fallback also failed:', fallbackError);
                const totalEmailsElement = document.getElementById('totalEmails');
                const unreadEmailsElement = document.getElementById('unreadEmails');
                const lastSyncElement = document.getElementById('lastSync');
                const starredEmailsElement = document.getElementById('starredEmails');
                
                if (totalEmailsElement) totalEmailsElement.textContent = 'Loading...';
                if (unreadEmailsElement) unreadEmailsElement.textContent = 'Loading...';
                if (lastSyncElement) lastSyncElement.textContent = 'Unknown';
                if (starredEmailsElement) starredEmailsElement.textContent = 'Loading...';
            });
    });
}

// Load sync page data
function loadSyncPage() {
    console.debug('[sync] Loading sync page data...');
    
    // Use the comprehensive dashboard endpoint
    const dashboardEndpoint = '/api/db/dashboard';
    
    Promise.race([
        fetch(dashboardEndpoint),
        new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Sync page timeout')), 5000)
        )
    ])
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.debug('[data] Sync page data received:', data);
        
        // Debug: Check if sync page elements exist
        const syncStatusElement = document.getElementById('syncStatus');
        const lastSyncTimeElement = document.getElementById('lastSyncTime');
        const totalSyncedElement = document.getElementById('totalSynced');
        const syncDatabaseSizeElement = document.getElementById('syncDatabaseSize');
        
        console.debug('[debug] Sync page element check:', {
            syncStatus: !!syncStatusElement,
            lastSyncTime: !!lastSyncTimeElement,
            totalSynced: !!totalSyncedElement,
            syncDatabaseSize: !!syncDatabaseSizeElement
        });
        
        // Update sync status
        const syncStatus = data.sync_in_progress ? 'Sync in progress' : 'Ready to sync';
        if (syncStatusElement) {
            syncStatusElement.textContent = syncStatus;
            console.debug('[ok] Updated syncStatus element');
        } else {
            console.debug('[error] syncStatus element not found!');
        }
        
        // Update last sync time
        let lastSyncDisplay = 'Never';
        if (data.last_sync_time) {
            const lastSync = new Date(data.last_sync_time);
            lastSyncDisplay = lastSync.toLocaleString();
        } else if (data.latest_email_date) {
            const latestEmail = new Date(data.latest_email_date);
            lastSyncDisplay = latestEmail.toLocaleString();
        }
        if (lastSyncTimeElement) {
            lastSyncTimeElement.textContent = lastSyncDisplay;
            console.debug('[ok] Updated lastSyncTime element');
        } else {
            console.debug('[error] lastSyncTime element not found!');
        }
        
        // Update total synced
        const totalEmails = data.total_emails || 0;
        if (totalSyncedElement) {
            totalSyncedElement.textContent = `${totalEmails.toLocaleString()} emails`;
            console.debug('[ok] Updated totalSynced element');
        } else {
            console.debug('[error] totalSynced element not found!');
        }
        
        // Update sync database size
        if (syncDatabaseSizeElement) {
            if (data.database_size_gb !== undefined) {
                syncDatabaseSizeElement.textContent = `${data.database_size_gb} GB`;
            } else if (data.database_size_pretty) {
                syncDatabaseSizeElement.textContent = data.database_size_pretty;
            } else {
                syncDatabaseSizeElement.textContent = `${totalEmails.toLocaleString()} emails`;
            }
            console.debug('[ok] Updated syncDatabaseSize element');
        } else {
            console.debug('[error] syncDatabaseSize element not found!');
        }
        
        console.debug('[ok] Sync page updated successfully');
        console.debug(`[data] Total emails: ${totalEmails.toLocaleString()}`);
        console.debug(`[sync] Sync status: ${syncStatus}`);
        console.debug(`[time] Last sync: ${lastSyncDisplay}`);
    })
    .catch(error => {
        console.debug('[error] Sync page loading failed:', error);
        
        // Fallback to simple email count
        fetch('/api/db/email-count')
            .then(response => response.json())
            .then(data => {
                const totalEmails = data.total_emails || 0;
                const syncStatusElement = document.getElementById('syncStatus');
                const lastSyncTimeElement = document.getElementById('lastSyncTime');
                const totalSyncedElement = document.getElementById('totalSynced');
                const syncDatabaseSizeElement = document.getElementById('syncDatabaseSize');
                
                if (syncStatusElement) syncStatusElement.textContent = 'Ready to sync';
                if (lastSyncTimeElement) lastSyncTimeElement.textContent = 'Recent';
                if (totalSyncedElement) totalSyncedElement.textContent = `${totalEmails.toLocaleString()} emails`;
                if (syncDatabaseSizeElement) syncDatabaseSizeElement.textContent = `${totalEmails.toLocaleString()} emails`;
                
                console.debug('[ok] Sync page updated with fallback data');
            })
            .catch(fallbackError => {
                console.debug('[error] Sync page fallback also failed:', fallbackError);
                const syncStatusElement = document.getElementById('syncStatus');
                const lastSyncTimeElement = document.getElementById('lastSyncTime');
                const totalSyncedElement = document.getElementById('totalSynced');
                const syncDatabaseSizeElement = document.getElementById('syncDatabaseSize');
                
                if (syncStatusElement) syncStatusElement.textContent = 'Status unavailable';
                if (lastSyncTimeElement) lastSyncTimeElement.textContent = 'Unknown';
                if (totalSyncedElement) totalSyncedElement.textContent = 'Loading...';
                if (syncDatabaseSizeElement) syncDatabaseSizeElement.textContent = 'Loading...';
            });
    });
}

// Update recent emails section
function updateRecentEmailsSection(recentEmails) {
    console.debug('[email] Updating recent emails section with:', recentEmails.length, 'emails');
    
    const recentEmailsContainer = document.querySelector('.recent-emails-list');
    if (!recentEmailsContainer) {
        console.debug('[error] Recent emails container not found!');
        return;
    }
    
    console.debug('[ok] Found recent emails container, updating with', recentEmails.length, 'emails');
    
    const emailsHTML = recentEmails.map(email => `
        <div class="recent-email-item ${email.is_read ? 'read' : 'unread'}" data-email-id="${email.id}">
            <div class="recent-email-sender">${email.sender}</div>
            <div class="recent-email-subject">${email.subject}</div>
            <div class="recent-email-date">${email.date_received ? new Date(email.date_received).toLocaleDateString() : 'Unknown'}</div>
        </div>
    `).join('');
    
    recentEmailsContainer.innerHTML = emailsHTML;
    
    // Add click event listeners to each email item
    const emailItems = recentEmailsContainer.querySelectorAll('.recent-email-item');
    emailItems.forEach(item => {
        item.addEventListener('click', function() {
            const emailId = this.getAttribute('data-email-id');
            if (emailId) {
                showEmailModal(emailId);
            }
        });
    });
    
    console.debug('[ok] Recent emails section updated successfully with click handlers');
}

// Show email modal with email details
function showEmailModal(emailId) {
    console.debug('[email] Opening email modal for ID:', emailId);
    
    const modal = document.getElementById('emailModal');
    if (!modal) {
        console.debug('[error] Email modal not found!');
        return;
    }
    
    // Show loading state
    modal.style.display = 'block';
    document.getElementById('modalEmailSubject').textContent = 'Loading...';
    document.getElementById('modalEmailSender').textContent = 'Loading...';
    document.getElementById('modalEmailDate').textContent = 'Loading...';
    document.getElementById('modalEmailStatus').textContent = 'Loading...';
    document.getElementById('modalEmailContent').textContent = 'Loading email content...';
    
    // Fetch email details
    fetch(`/api/db/email/${emailId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.email) {
                const email = data.email;
                
                // Update modal content
                document.getElementById('modalEmailSubject').textContent = email.subject;
                document.getElementById('modalEmailSender').textContent = email.sender;
                document.getElementById('modalEmailDate').textContent = email.date_received ? 
                    new Date(email.date_received).toLocaleString() : 'Unknown';
                document.getElementById('modalEmailStatus').textContent = email.is_read ? 'Read' : 'Unread';
                
                // Render HTML content properly
                const contentElement = document.getElementById('modalEmailContent');
                if (email.content && email.content.trim()) {
                    // Sanitize and render HTML content
                    const sanitizedContent = sanitizeHTML(email.content);
                    contentElement.innerHTML = sanitizedContent;
                } else {
                    contentElement.textContent = 'No content available';
                }
                
                console.debug('[ok] Email modal populated with data');
            } else {
                throw new Error('Invalid response format');
            }
        })
        .catch(error => {
            console.debug('[error] Error loading email details:', error);
            document.getElementById('modalEmailSubject').textContent = 'Error Loading Email';
            document.getElementById('modalEmailSender').textContent = 'Error';
            document.getElementById('modalEmailDate').textContent = 'Error';
            document.getElementById('modalEmailStatus').textContent = 'Error';
            document.getElementById('modalEmailContent').textContent = 'Failed to load email content. Please try again.';
        });
}

// Simple HTML sanitization function
function sanitizeHTML(html) {
    if (!html) return '';
    
    // Create a temporary div to parse and sanitize HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    
    // Remove potentially dangerous elements and attributes
    const dangerousElements = tempDiv.querySelectorAll('script, style, iframe, object, embed, form, input, button, select, textarea');
    dangerousElements.forEach(el => el.remove());
    
    // Remove potentially dangerous attributes
    const allElements = tempDiv.querySelectorAll('*');
    allElements.forEach(el => {
        const dangerousAttrs = ['onclick', 'onload', 'onerror', 'onmouseover', 'onfocus', 'onblur', 'onchange', 'onsubmit'];
        dangerousAttrs.forEach(attr => {
            if (el.hasAttribute(attr)) {
                el.removeAttribute(attr);
            }
        });
    });
    
    return tempDiv.innerHTML;
}

// Initialize email modal functionality
function initializeEmailModal() {
    const modal = document.getElementById('emailModal');
    const closeBtn = document.getElementById('closeEmailModal');
    
    if (!modal || !closeBtn) {
        console.debug('[error] Email modal elements not found!');
        return;
    }
    
    // Close modal when clicking the close button
    closeBtn.addEventListener('click', function() {
        modal.style.display = 'none';
    });
    
    // Close modal when clicking outside the modal content
    modal.addEventListener('click', function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
    
    // Close modal with Escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && modal.style.display === 'block') {
            modal.style.display = 'none';
        }
    });
    
    console.debug('[ok] Email modal functionality initialized');
}

// Search functionality
function initializeSearch() {
    const searchBtn = document.getElementById('searchBtn');
    const searchInput = document.getElementById('searchInput');
    
    searchBtn.addEventListener('click', () => {
        // Reset pagination for new search
        searchCurrentPage = 1;
        performSearch(1);
    });
    
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            // Reset pagination for new search
            searchCurrentPage = 1;
            performSearch(1);
        }
    });
}

function performSearch(page = 1) {
    const searchTerm = document.getElementById('searchInput').value.trim();
    const searchFilter = document.getElementById('searchFilter').value;
    const dateFrom = document.getElementById('dateFrom').value;
    const dateTo = document.getElementById('dateTo').value;
    
    // Store search parameters for pagination
    currentSearchTerm = searchTerm;
    currentSearchFilter = searchFilter;
    currentDateFrom = dateFrom;
    currentDateTo = dateTo;
    searchCurrentPage = page;
    
    if (!searchTerm) {
        showSearchResults([]);
        return;
    }
    
    showLoading(true);
    
    // Use Node.js search endpoint only to avoid hanging backend calls
    const searchEndpoints = [
        `/api/db/search?q=${encodeURIComponent(searchTerm)}&page=${page}&page_size=${searchPageSize}&filter=${encodeURIComponent(searchFilter)}&date_from=${encodeURIComponent(dateFrom)}&date_to=${encodeURIComponent(dateTo)}`  // Node.js direct server
    ];
    
    let searchPromise = null;
    
    // Try each endpoint until one works
    for (const endpoint of searchEndpoints) {
        searchPromise = Promise.race([
            fetch(endpoint),
            new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Search timeout')), 8000)
            )
        ])
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            let results = data.emails || [];
            searchTotalResults = data.total_count || 0;
            
            // Apply additional filters if specified (client-side filtering)
            if (searchFilter === 'subject') {
                results = results.filter(email => 
                    email.subject && email.subject.toLowerCase().includes(searchTerm.toLowerCase())
                );
            } else if (searchFilter === 'sender') {
                results = results.filter(email => 
                    email.sender && email.sender.toLowerCase().includes(searchTerm.toLowerCase())
                );
            }
            
            // Apply date filters if specified
            if (dateFrom) {
                const fromDate = new Date(dateFrom);
                results = results.filter(email => 
                    email.date_received && new Date(email.date_received) >= fromDate
                );
            }
            
            if (dateTo) {
                const toDate = new Date(dateTo);
                toDate.setHours(23, 59, 59); // End of day
                results = results.filter(email => 
                    email.date_received && new Date(email.date_received) <= toDate
                );
            }
            
            showSearchResults(results);
            showSearchPagination();
            console.log(`Search completed using: ${endpoint}`);
        })
        .catch(error => {
            console.log(`Search endpoint ${endpoint} failed: ${error.message}`);
            throw error; // Re-throw to try next endpoint
        });
        
        // If we get here without throwing, break the loop
        break;
    }
    
    searchPromise
        .catch(error => {
            console.error('All search endpoints failed:', error);
            
            // Show user-friendly error message
            const searchResults = document.getElementById('searchResults');
            searchResults.innerHTML = `
                <div class="error-message">
                    <h3>Search Error</h3>
                    <p>Unable to perform search. The service may be busy with sync operations.</p>
                    <button class="btn btn-primary" onclick="performSearch()">Try Again</button>
                </div>
            `;
        })
        .finally(() => {
            showLoading(false);
        });
}

function showSearchResults(results) {
    console.log('showSearchResults called with:', results);
    console.log('Results length:', results.length);
    
    const searchResults = document.getElementById('searchResults');
    
    // Store search results globally
    currentSearchResults = results;
    console.log('currentSearchResults stored:', currentSearchResults);
    
    // Update search result count
    document.getElementById('searchResultCount').textContent = `${searchTotalResults.toLocaleString()} results`;
    
    if (results.length === 0) {
        searchResults.innerHTML = `
            <div class="text-center text-muted" style="padding: 2rem;">
                <i class="fas fa-search" style="font-size: 3rem; color: #d1d5db; margin-bottom: 1rem;"></i>
                <p>No emails found matching your search criteria</p>
            </div>
        `;
        return;
    }
    
    const resultsHtml = results.map(email => `
        <div class="email-item" data-email-id="${email.id}" onclick="selectSearchEmail('${email.id}')">
            <div class="email-header">
                <span class="email-sender">${email.sender}</span>
                <span class="email-date">${new Date(email.date_received).toLocaleDateString()}</span>
            </div>
            <div class="email-subject">${email.subject}</div>
            <div class="email-preview">${(email.body_preview || email.body_plain || '').substring(0, 100)}...</div>
        </div>
    `).join('');
    
    console.log('Generated HTML for search results');
    
    searchResults.innerHTML = `
        <div class="email-list">
            ${resultsHtml}
        </div>
    `;
    
    console.log('Search results HTML updated');
}

// Show search pagination
function showSearchPagination() {
    const pagination = document.getElementById('searchPagination');
    const totalPages = Math.ceil(searchTotalResults / searchPageSize);
    
    if (totalPages > 1) {
        pagination.style.display = 'flex';
        document.getElementById('searchPageInfo').textContent = `Page ${searchCurrentPage} of ${totalPages}`;
        document.getElementById('searchPrevPage').disabled = searchCurrentPage === 1;
        document.getElementById('searchNextPage').disabled = searchCurrentPage === totalPages;
    } else {
        pagination.style.display = 'none';
    }
}

// Resume sync functionality
function resumeSync() {
    console.debug('[sync] Resuming sync from where it left off...');
    
    // Show loading state
    const resumeSyncBtn = document.getElementById('resumeSyncBtn');
    const originalText = resumeSyncBtn.innerHTML;
    resumeSyncBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Resuming...';
    resumeSyncBtn.disabled = true;
    
    fetch('/api/sync/resume', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        console.debug('[data] Resume sync response:', data);
        
        if (data.success) {
            console.debug('[ok] Sync resumed successfully!');
            
            // Show success message
            showNotification('Sync resumed successfully from where it left off!', 'success');
            
            // Update sync status
            loadSyncMonitoring();
            
            // Log the resume action
            addLogEntry('SYNC RESUMED', `Resumed sync with configuration: ${JSON.stringify(data.resume_config)}`);
            
        } else {
            console.debug('[error] Failed to resume sync:', data.error);
            showNotification(`Failed to resume sync: ${data.error}`, 'error');
            addLogEntry('SYNC RESUME FAILED', data.error, 'error');
        }
    })
    .catch(error => {
        console.debug('[error] Error resuming sync:', error);
        showNotification(`Error resuming sync: ${error.message}`, 'error');
        addLogEntry('SYNC RESUME ERROR', error.message, 'error');
    })
    .finally(() => {
        // Restore button state
        resumeSyncBtn.innerHTML = originalText;
        resumeSyncBtn.disabled = false;
    });
}

// Sync functionality
let syncInitialized = false;
function initializeSync() {
    if (syncInitialized) {
        // Already initialized, just refresh data
        loadSyncMonitoring();
        checkResumeAvailability();
        return;
    }
    syncInitialized = true;

    // Initialize all sync buttons
    const quickSyncBtn = document.getElementById('quickSyncBtn');
    const dateRangeSyncBtn = document.getElementById('dateRangeSyncBtn');
    const fullSyncBtn = document.getElementById('fullSyncBtn');
    const startBackgroundSyncBtn = document.getElementById('startBackgroundSyncBtn');
    const stopBackgroundSyncBtn = document.getElementById('stopBackgroundSyncBtn');
    const startSyncBtn = document.getElementById('startSync');
    const stopSyncBtn = document.getElementById('stopSync');
    const resumeSyncBtn = document.getElementById('resumeSyncBtn');
    const resetLastSyncBtn = document.getElementById('resetLastSyncBtn');
    const clearLogBtn = document.getElementById('clearLogBtn');
    const exportLogBtn = document.getElementById('exportLogBtn');

    // Add event listeners with null guards
    if (quickSyncBtn) quickSyncBtn.addEventListener('click', () => performQuickSync());
    if (dateRangeSyncBtn) dateRangeSyncBtn.addEventListener('click', () => performDateRangeSync());
    if (fullSyncBtn) fullSyncBtn.addEventListener('click', () => performFullSync());
    if (startBackgroundSyncBtn) startBackgroundSyncBtn.addEventListener('click', () => startBackgroundSync());
    if (stopBackgroundSyncBtn) stopBackgroundSyncBtn.addEventListener('click', () => stopBackgroundSync());
    if (startSyncBtn) startSyncBtn.addEventListener('click', () => startManualSync());
    if (resumeSyncBtn) resumeSyncBtn.addEventListener('click', () => resumeSync());
    if (stopSyncBtn) stopSyncBtn.addEventListener('click', () => stopSync());
    if (resetLastSyncBtn) resetLastSyncBtn.addEventListener('click', () => resetLastSync());
    if (clearLogBtn) clearLogBtn.addEventListener('click', () => clearLog());
    if (exportLogBtn) exportLogBtn.addEventListener('click', () => exportLog());

    // Load initial sync monitoring data
    loadSyncMonitoring();
    
    // Let the API data flow through naturally - no hardcoded values
    console.debug('[ok] Sync page monitoring initialized - will use API data');
    
    // Check resume availability
    checkResumeAvailability();
    
    // Start periodic sync monitoring refresh (every 5 seconds)
    startSyncMonitoringRefresh();
    
    // Simple approach is now handled in the initialization above
    
    // Set default dates for date range sync
    setDefaultDates();
}

function setDefaultDates() {
    const today = new Date();
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(today.getFullYear() - 1);
    
    document.getElementById('dateFromSync').value = oneYearAgo.toISOString().split('T')[0];
    document.getElementById('dateToSync').value = today.toISOString().split('T')[0];
}

// Load sync status with better error handling
function loadSyncStatus() {
    console.debug('[sync] loadSyncStatus called - this should not update total emails on sync page');
    // Use Node.js endpoints only to avoid hanging backend calls
    const endpoints = [
        '/api/db/sync-status',  // Node.js sync status
        '/api/db/email-count'   // Node.js direct server
    ];
    
    let currentEndpoint = 0;
    
    function tryEndpoint() {
        if (currentEndpoint >= endpoints.length) {
            const syncStatusElement = document.getElementById('syncStatus');
            const lastSyncTimeElement = document.getElementById('lastSyncTime');
            const totalSyncedElement = document.getElementById('totalSynced');
            const syncDatabaseSizeElement = document.getElementById('syncDatabaseSize');
            
            // Check if we're on the sync page before setting fallback values
            const syncPageElement = document.querySelector('#syncPage');
            const currentPage = syncPageElement && syncPageElement.style.display === 'block' ? 'sync' : 'other';
            
            if (syncStatusElement && currentPage !== 'sync') syncStatusElement.textContent = 'Status unavailable';
            if (lastSyncTimeElement && currentPage !== 'sync') lastSyncTimeElement.textContent = 'Unknown';
            if (totalSyncedElement && currentPage !== 'sync') totalSyncedElement.textContent = 'Loading...';
            if (syncDatabaseSizeElement && currentPage !== 'sync') syncDatabaseSizeElement.textContent = 'Loading...';
            return;
        }
        
        const endpoint = endpoints[currentEndpoint];
        
        Promise.race([
            fetch(endpoint),
            new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Sync status timeout')), 3000)
            )
        ])
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Sync status data received:', data);
            
            if (data.total_emails !== undefined) {
                // Use sync status endpoint data if available
                const syncStatusElement = document.getElementById('syncStatus');
                const lastSyncTimeElement = document.getElementById('lastSyncTime');
                const totalSyncedElement = document.getElementById('totalSynced');
                const syncDatabaseSizeElement = document.getElementById('syncDatabaseSize');
                
                // Check if we're on the sync page
                const syncPageElement = document.querySelector('#syncPage');
                const currentPage = syncPageElement && syncPageElement.style.display === 'block' ? 'sync' : 'other';
                console.debug('[debug] loadSyncStatus - currentPage:', currentPage, 'syncPage display:', syncPageElement?.style.display);
                
                // Only update sync status if we're not on the sync page (where loadSyncMonitoring handles it)
                if (currentPage !== 'sync') {
                    if (data.status) {
                        if (syncStatusElement) {
                            syncStatusElement.textContent = data.sync_in_progress ? 'Sync in progress' : 'Ready to sync';
                        }
                        
                        if (lastSyncTimeElement) {
                            if (data.last_sync_time) {
                                const lastSync = new Date(data.last_sync_time);
                                lastSyncTimeElement.textContent = lastSync.toLocaleString();
                            } else if (data.latest_email_date) {
                                const latestEmail = new Date(data.latest_email_date);
                                lastSyncTimeElement.textContent = latestEmail.toLocaleString();
                            } else {
                                lastSyncTimeElement.textContent = 'Recent';
                            }
                        }
                    } else {
                        if (syncStatusElement) syncStatusElement.textContent = 'Ready to sync';
                        if (lastSyncTimeElement) lastSyncTimeElement.textContent = 'Recent';
                    }
                }
                
                // Only update total emails if we're not on the sync page (where loadSyncMonitoring handles it)
                if (totalSyncedElement && currentPage !== 'sync') {
                    console.debug('[ok] loadSyncStatus updating total emails to:', data.total_emails);
                    totalSyncedElement.textContent = `${data.total_emails?.toLocaleString() || 0} emails`;
                } else {
                    console.log('🚫 loadSyncStatus skipping total emails update (on sync page)');
                }
                
                // Debug: Check if we're actually on the sync page
                console.debug('[debug] loadSyncStatus debug - syncPage display:', syncPageElement?.style.display, 'currentPage:', currentPage);
                
                // Display database size in GB if available
                console.log('Database size data:', { 
                    database_size_gb: data.database_size_gb, 
                    database_size_pretty: data.database_size_pretty 
                });
                
                // Only update database size if we're not on the sync page (where loadSyncMonitoring handles it)
                if (syncDatabaseSizeElement && currentPage !== 'sync') {
                    if (data.database_size_gb !== undefined) {
                        syncDatabaseSizeElement.textContent = `${data.database_size_gb} GB`;
                        console.log('Set sync database size to:', `${data.database_size_gb} GB`);
                    } else {
                        syncDatabaseSizeElement.textContent = `${data.total_emails?.toLocaleString() || 0} emails`;
                        console.log('Set sync database size to email count:', `${data.total_emails?.toLocaleString() || 0} emails`);
                    }
                }
                
                // Display sync details if available
                console.log('Sync details check:', { 
                    has_sync_details: !!data.sync_details, 
                    sync_in_progress: data.sync_in_progress,
                    sync_details: data.sync_details 
                });
                
                if (data.sync_details && data.sync_in_progress) {
                    console.log('Calling displaySyncDetails with:', data.sync_details);
                    displaySyncDetails(data.sync_details);
                    displayCurrentSyncProgress(data.sync_details);
                } else {
                    console.log('Calling hideSyncDetails');
                    hideSyncDetails();
                    hideCurrentSyncProgress();
                }
                
                console.log(`Sync status loaded using: ${endpoint}`);
            } else {
                throw new Error('Invalid response format');
            }
        })
        .catch(error => {
            console.debug(`[error] Endpoint ${endpoint} failed: ${error.message}`);
            currentEndpoint++;
            setTimeout(tryEndpoint, 500);
        });
    }
    
    tryEndpoint();
}

// Fallback function to get email count when API is slow
async function getEmailCountFallback() {
    try {
        // Try to get count from Node.js direct database endpoint
        const response = await Promise.race([
            fetch('/api/db/email-count'),
            new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Count timeout')), 3000)
            )
        ]);
        
        if (response.ok) {
            const data = await response.json();
            return data.total_emails || 0;
        }
    } catch (error) {
        console.log('Fallback count failed:', error.message);
    }
    return null;
}

function performQuickSync() {
    const count = document.getElementById('quickSyncCount').value;
    startSyncOperation('quick', { max_emails: parseInt(count) });
}

function performDateRangeSync() {
    const fromDate = document.getElementById('dateFromSync').value;
    const toDate = document.getElementById('dateToSync').value;
    const count = document.getElementById('dateSyncCount').value;
    
    if (!fromDate || !toDate) {
        showNotification('Please select both start and end dates', 'error');
        return;
    }
    
    // Convert dates to YYYY/MM/DD format for the API
    const formattedFromDate = fromDate.replace(/-/g, '/');
    startSyncOperation('date-range', { 
        start_date: formattedFromDate, 
        max_emails: parseInt(count) 
    });
}

function performFullSync() {
    const count = document.getElementById('fullSyncCount').value;
    if (confirm(`This will sync up to ${count} emails. This may take a long time. Continue?`)) {
        startSyncOperation('full', { max_emails: parseInt(count) });
    }
}

function startBackgroundSync() {
    const interval = document.getElementById('backgroundInterval').value;
    
    fetch('/api/v1/test/background-sync/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ interval_minutes: parseInt(interval) })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'started') {
            showNotification('Background sync started successfully', 'success');
            document.getElementById('startBackgroundSyncBtn').style.display = 'none';
            document.getElementById('stopBackgroundSyncBtn').style.display = 'inline-block';
            addLogEntry('Background Sync Started', `Interval: ${interval} minutes`);
        } else {
            showNotification('Failed to start background sync', 'error');
        }
    })
    .catch(error => {
        console.error('Error starting background sync:', error);
        showNotification('Error starting background sync', 'error');
    });
}

function stopBackgroundSync() {
    fetch('/api/v1/test/background-sync/stop', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'stopped') {
            showNotification('Background sync stopped', 'success');
            document.getElementById('startBackgroundSyncBtn').style.display = 'inline-block';
            document.getElementById('stopBackgroundSyncBtn').style.display = 'none';
            addLogEntry('Background Sync Stopped', 'User stopped background sync');
        } else {
            showNotification('Failed to stop background sync', 'error');
        }
    })
    .catch(error => {
        console.error('Error stopping background sync:', error);
        showNotification('Error stopping background sync', 'error');
    });
}

function startManualSync() {
    startSyncOperation('manual', { max_emails: 1000 });
}

function startSyncOperation(type, params) {
    const startBtn = document.getElementById('startSync');
    const stopBtn = document.getElementById('stopSync');
    const progress = document.getElementById('syncProgress');
    const monitoring = document.getElementById('syncMonitoring');
    
    // Check if sync is already running before starting (with retry)
    console.debug('[debug] Checking if sync is already running...');
    checkSyncStatusAndStart(type, params, startBtn, stopBtn, progress, monitoring);
}

function checkSyncStatusAndStart(type, params, startBtn, stopBtn, progress, monitoring, retryCount = 0) {
    console.debug('[debug] Starting sync status check (attempt ' + (retryCount + 1) + '/3)...');
    fetch('/api/db/sync-monitoring')
        .then(response => response.json())
        .then(data => {
            console.debug('[debug] Sync status check result (attempt ' + (retryCount + 1) + '):', data.sync_progress);
            if (data.sync_progress.is_active) {
                console.debug('[warn] Sync already running - switching to monitoring mode');
                addLogEntry('Sync Status', 'Sync already in progress - monitoring existing sync');
                showNotification('Sync already running - monitoring progress', 'info');
                
                // Update UI to show sync is running
                startBtn.disabled = true;
                stopBtn.disabled = false;
                progress.style.display = 'block';
                monitoring.style.display = 'block';
                
                // Start monitoring the existing sync
                startRealTimeMonitoring();
                console.debug('[stop] Returning early - not starting new sync');
                return;
            }
            
            // No active sync found, but let's double-check after a short delay
            if (retryCount < 2) {
                console.log('⏳ No active sync found on attempt ' + (retryCount + 1) + ', retrying in 1 second...');
                setTimeout(() => {
                    checkSyncStatusAndStart(type, params, startBtn, stopBtn, progress, monitoring, retryCount + 1);
                }, 1000);
                return;
            }
            
            // After retries, proceed with starting new sync
            console.debug('[ok] No active sync found after ' + (retryCount + 1) + ' checks - starting new sync');
            startNewSyncOperation(type, params, startBtn, stopBtn, progress, monitoring);
        })
        .catch(error => {
            console.error('Error checking sync status (attempt ' + (retryCount + 1) + '):', error);
            if (retryCount < 2) {
                console.log('⏳ Error on attempt ' + (retryCount + 1) + ', retrying in 1 second...');
                setTimeout(() => {
                    checkSyncStatusAndStart(type, params, startBtn, stopBtn, progress, monitoring, retryCount + 1);
                }, 1000);
                return;
            }
            // After retries, proceed with starting sync anyway
            console.debug('[warn] Proceeding with sync start after ' + (retryCount + 1) + ' failed attempts');
            startNewSyncOperation(type, params, startBtn, stopBtn, progress, monitoring);
        });
}

function startNewSyncOperation(type, params, startBtn, stopBtn, progress, monitoring) {
    console.debug('[init] startNewSyncOperation called with type:', type, 'params:', params);
    
    // Final safety check - make sure no sync is running before we start
    console.debug('[auth] Final safety check - verifying no active sync...');
    fetch('/api/db/sync-monitoring')
        .then(response => response.json())
        .then(data => {
            if (data.sync_progress.is_active) {
                console.log('🚨 SAFETY CHECK FAILED: Active sync detected during startNewSyncOperation!');
                console.debug('[sync] Switching to monitoring mode instead of starting new sync');
                addLogEntry('Sync Status', 'Active sync detected during startup - switching to monitoring');
                showNotification('Active sync detected - monitoring existing sync', 'info');
                
                // Update UI to show sync is running
                startBtn.disabled = true;
                stopBtn.disabled = false;
                progress.style.display = 'block';
                monitoring.style.display = 'block';
                
                // Start monitoring the existing sync
                startRealTimeMonitoring();
                return;
            }
            
            // No active sync, proceed with starting new sync
            console.debug('[ok] Safety check passed - no active sync, proceeding with new sync');
            proceedWithNewSync(type, params, startBtn, stopBtn, progress, monitoring);
        })
        .catch(error => {
            console.error('Error in final safety check:', error);
            console.debug('[warn] Proceeding with sync start despite safety check error');
            proceedWithNewSync(type, params, startBtn, stopBtn, progress, monitoring);
        });
}

function proceedWithNewSync(type, params, startBtn, stopBtn, progress, monitoring) {
    // Initialize progress tracking
    const syncStartTime = new Date();
    let emailsSynced = 0;
    let totalEmails = params.max_emails || 1000;
    let errorCount = 0;
    let batchCount = 0;
    
    // Reset progress displays
    updateProgressDisplay(0, totalEmails, 0, syncStartTime);
    updateMonitoringDisplay(0, 0, 0, 0);
    
    // Clear previous errors
    clearSyncErrors();
    
    // Use Node.js sync control endpoint to avoid hanging
    const endpoint = '/api/sync/start';
    const requestBody = {
        sync_type: type,
        max_emails: params.max_emails
    };
    
    // Add date range parameters if needed
    if (type === 'date-range' && params.start_date) {
        requestBody.start_date = params.start_date;
    }
    
    addLogEntry('Sync Started', `${type} sync initiated with ${params.max_emails} emails`);
    showNotification(`Starting ${type} sync...`, 'info');
    
    // Store sync state for real-time updates
    window.currentSync = {
        type,
        startTime: syncStartTime,
        totalEmails,
        emailsSynced: 0,
        errorCount: 0,
        batchCount: 0,
        isRunning: true,
        endpoint
    };
    
    // Start real-time monitoring
    startRealTimeMonitoring();
    
    // Start the sync using Node.js endpoint
    console.debug('[init] Starting sync operation with:', requestBody);
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
    })
    .then(response => {
        console.log('📡 Sync start response status:', response.status, response.statusText);
        console.log('📡 Response headers:', Object.fromEntries(response.headers.entries()));
        
        if (!response.ok) {
            if (response.status === 409) {
                // Sync already in progress
                console.debug('[warn] Sync already in progress (409) - parsing response...');
                return response.json().then(data => {
                    console.debug('[info] 409 response data:', data);
                    throw new Error(`Sync already in progress: ${data.error}`);
                }).catch(parseError => {
                    console.debug('[error] Error parsing 409 response:', parseError);
                    throw new Error(`Sync already in progress: Unable to parse response`);
                });
            }
            console.debug('[error] HTTP error - status:', response.status);
            // Try to get error details from response
            return response.text().then(text => {
                console.debug('[error] Error response body:', text);
                throw new Error(`HTTP error! status: ${response.status} - ${text}`);
            }).catch(textError => {
                console.debug('[error] Error reading error response:', textError);
                throw new Error(`HTTP error! status: ${response.status}`);
            });
        }
        console.debug('[ok] Sync start successful - parsing response...');
        return response.json();
    })
    .then(data => {
        if (data.success || data.status === 'success') {
            emailsSynced = data.data?.emails_synced || data.result?.emails_synced || 0;
            addLogEntry('Sync Completed', `Successfully synced ${emailsSynced} emails`);
            completeSyncOperation(emailsSynced, totalEmails, syncStartTime);
        } else {
            throw new Error(data.error || data.message || 'Sync failed');
        }
    })
    .catch(error => {
        console.error('Sync error:', error);
        errorCount++;
        
        // Check if this is a "sync already in progress" error
        if (error.message.includes('Sync already in progress')) {
            console.debug('[sync] Sync already running - switching to monitoring mode');
            addLogEntry('Sync Status', 'Sync already in progress - monitoring existing sync');
            showNotification('Sync already running - monitoring progress', 'info');
            
            // Don't complete the operation, let monitoring continue
            // The sync monitoring will show the existing sync progress
            return;
        }
        
        addLogEntry('Sync Error', error.message);
        displaySyncError(error.message, 'critical');
        showNotification('Sync failed: ' + error.message, 'error');
        completeSyncOperation(0, totalEmails, syncStartTime, true);
    });
}

function stopSync() {
    if (window.currentSync) {
        window.currentSync.isRunning = false;
    }
    
    // Stop real-time monitoring
    stopRealTimeMonitoring();
    
    const startBtn = document.getElementById('startSync');
    const stopBtn = document.getElementById('stopSync');
    const syncStatus = document.getElementById('syncStatus');
    
    startBtn.disabled = false;
    stopBtn.disabled = true;
    syncStatus.textContent = 'Sync stopped';
    
    addLogEntry('Sync Stopped', 'User stopped the sync process');
    showNotification('Sync stopped by user', 'info');
    
    // Try to stop the sync using Node.js endpoint
    fetch('/api/sync/stop', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Stop sync response:', data);
        if (data.success || data.status === 'success') {
            addLogEntry('Backend Sync Stopped', data.message || 'Sync process stopped on server');
            showNotification('Sync stopped successfully', 'success');
        } else {
            addLogEntry('Stop Error', data.error || data.message || 'Unknown error stopping sync');
            showNotification('Error stopping sync: ' + (data.error || data.message || 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        console.error('Error stopping sync on backend:', error);
        addLogEntry('Stop Error', 'Could not stop sync on server: ' + error.message);
        showNotification('Error stopping sync: ' + error.message, 'error');
    });
}

function completeSyncOperation(emailsSynced, totalEmails, startTime, isError = false) {
    const startBtn = document.getElementById('startSync');
    const stopBtn = document.getElementById('stopSync');
    const syncStatus = document.getElementById('syncStatus');
    const progress = document.getElementById('syncProgress');
    const monitoring = document.getElementById('syncMonitoring');
    
    const endTime = new Date();
    const elapsedTime = Math.round((endTime - startTime) / 1000);
    const elapsedMinutes = Math.floor(elapsedTime / 60);
    const elapsedSeconds = elapsedTime % 60;
    
    // Update UI
    startBtn.disabled = false;
    stopBtn.disabled = true;
    syncStatus.textContent = isError ? 'Sync failed' : 'Sync completed';
    
    // Update progress
    const progressPercent = totalEmails > 0 ? (emailsSynced / totalEmails) * 100 : 0;
    document.getElementById('progressFill').style.width = `${progressPercent}%`;
    document.getElementById('progressText').textContent = `${Math.round(progressPercent)}% complete`;
    document.getElementById('progressCount').textContent = `${emailsSynced} / ${totalEmails} emails`;
    document.getElementById('syncElapsedTime').textContent = `${elapsedMinutes}:${elapsedSeconds.toString().padStart(2, '0')}`;
    
    // Calculate speed
    const speed = elapsedTime > 0 ? Math.round((emailsSynced / elapsedTime) * 60) : 0;
    document.getElementById('progressSpeed').textContent = `${speed} emails/min`;
    
    // Add log entry
    const message = isError ? 
        `Sync failed after ${elapsedTime}s` : 
        `Successfully synced ${emailsSynced} emails in ${elapsedTime}s`;
    addLogEntry('Sync Completed', message);
    
    // Show notification
    if (!isError) {
        showNotification(`Sync completed: ${emailsSynced} emails synced`, 'success');
    }
    
    // Hide monitoring after a delay
    setTimeout(() => {
        monitoring.style.display = 'none';
    }, 5000);
    
    // Reload sync status
    loadSyncStatus();
}

function resetLastSync() {
    if (confirm('This will reset the last sync time and allow syncing all emails from the beginning. Continue?')) {
        fetch('/api/v1/test/sync/reset-last-sync', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showNotification('Last sync time reset successfully', 'success');
                addLogEntry('Reset Last Sync', 'Last sync time has been reset');
                loadSyncStatus();
            } else {
                showNotification('Failed to reset last sync time', 'error');
            }
        })
        .catch(error => {
            console.error('Error resetting last sync:', error);
            showNotification('Error resetting last sync time', 'error');
        });
    }
}

function clearLog() {
    const logEntries = document.getElementById('logEntries');
    logEntries.innerHTML = '<div class="log-entry"><span class="log-time">System ready</span><span class="log-message">Log cleared</span></div>';
    showNotification('Sync log cleared', 'info');
}

function exportLog() {
    const logEntries = document.getElementById('logEntries');
    const entries = Array.from(logEntries.children).map(entry => {
        const time = entry.querySelector('.log-time').textContent;
        const message = entry.querySelector('.log-message').textContent;
        return `${time}: ${message}`;
    }).join('\n');
    
    const blob = new Blob([entries], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sync-log-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showNotification('Sync log exported', 'success');
}

function addLogEntry(time, message, type = 'info') {
    const logEntries = document.getElementById('logEntries');
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    
    const timestamp = new Date().toLocaleTimeString();
    entry.innerHTML = `
        <span class="log-time">${timestamp}</span>
        <span class="log-message">${message}</span>
        <span class="log-type">${type.toUpperCase()}</span>
    `;
    
    logEntries.appendChild(entry);
    logEntries.scrollTop = logEntries.scrollHeight;
    
    // Keep only last 100 entries
    while (logEntries.children.length > 100) {
        logEntries.removeChild(logEntries.firstChild);
    }
}

// Real-time monitoring functions
let monitoringInterval = null;
let progressUpdateInterval = null;

function startRealTimeMonitoring() {
    console.debug('[sync] Starting real-time sync monitoring...');
    
    // Clear any existing intervals
    stopRealTimeMonitoring();
    
    // Start progress polling every 2 seconds
    progressUpdateInterval = setInterval(updateSyncProgress, 2000);
    
    // Start detailed monitoring every 5 seconds
    monitoringInterval = setInterval(fetchSyncStatus, 5000);
    
    addLogEntry('Monitoring Started', 'Real-time sync monitoring activated', 'info');
}

function stopRealTimeMonitoring() {
    if (progressUpdateInterval) {
        clearInterval(progressUpdateInterval);
        progressUpdateInterval = null;
    }
    
    if (monitoringInterval) {
        clearInterval(monitoringInterval);
        monitoringInterval = null;
    }
    
    console.log('⏹️ Real-time sync monitoring stopped');
}

function updateSyncProgress() {
    if (!window.currentSync || !window.currentSync.isRunning) {
        stopRealTimeMonitoring();
        return;
    }
    
    const now = new Date();
    const elapsed = Math.floor((now - window.currentSync.startTime) / 1000);
    const elapsedMinutes = Math.floor(elapsed / 60);
    const elapsedSeconds = elapsed % 60;
    
    // Update elapsed time
    document.getElementById('syncElapsedTime').textContent = 
        `${elapsedMinutes}:${elapsedSeconds.toString().padStart(2, '0')}`;
    
    // Calculate estimated time remaining
    if (window.currentSync.emailsSynced > 0) {
        const rate = window.currentSync.emailsSynced / elapsed;
        const remaining = window.currentSync.totalEmails - window.currentSync.emailsSynced;
        const estimatedSeconds = Math.floor(remaining / rate);
        const estimatedMinutes = Math.floor(estimatedSeconds / 60);
        const estimatedSecondsRemainder = estimatedSeconds % 60;
        
        document.getElementById('syncEstimatedTime').textContent = 
            `${estimatedMinutes}:${estimatedSecondsRemainder.toString().padStart(2, '0')}`;
        
        // Update speed
        const speed = Math.round(rate * 60); // emails per minute
        document.getElementById('progressSpeed').textContent = `${speed} emails/min`;
    }
}

function fetchSyncStatus() {
    if (!window.currentSync || !window.currentSync.isRunning) {
        return;
    }
    
    fetch('/api/v1/test/sync/status')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'syncing') {
                // Update progress from backend data
                const progress = data.progress || {};
                
                window.currentSync.emailsSynced = progress.emails_processed || progress.emails_synced || window.currentSync.emailsSynced;
                window.currentSync.errorCount = progress.errors || window.currentSync.errorCount;
                window.currentSync.batchCount = progress.current_batch || window.currentSync.batchCount;
                
                // Update displays
                updateProgressDisplay(
                    window.currentSync.emailsSynced,
                    window.currentSync.totalEmails,
                    window.currentSync.errorCount,
                    window.currentSync.startTime
                );
                
                updateMonitoringDisplay(
                    window.currentSync.batchCount,
                    progress.batch_progress || 0,
                    progress.new_emails || 0,
                    window.currentSync.errorCount
                );
                
                // Log progress updates
                if (progress.current_email) {
                    addLogEntry('Processing', `Email: ${progress.current_email.subject || 'No subject'}`, 'progress');
                }
                
                // Handle errors
                if (progress.errors && progress.last_error) {
                    displaySyncError(progress.last_error, 'warning');
                    addLogEntry('Sync Warning', progress.last_error, 'warning');
                }
                
            } else if (data.status === 'completed') {
                // Sync completed
                window.currentSync.isRunning = false;
                stopRealTimeMonitoring();
                completeSyncOperation(
                    data.emails_synced || window.currentSync.emailsSynced,
                    window.currentSync.totalEmails,
                    window.currentSync.startTime
                );
            } else if (data.status === 'error') {
                // Sync failed
                window.currentSync.isRunning = false;
                stopRealTimeMonitoring();
                displaySyncError(data.error || 'Unknown sync error', 'critical');
                completeSyncOperation(0, window.currentSync.totalEmails, window.currentSync.startTime, true);
            }
        })
        .catch(error => {
            console.error('Error fetching sync status:', error);
            addLogEntry('Status Error', `Could not fetch sync status: ${error.message}`, 'error');
        });
}

function updateProgressDisplay(emailsSynced, totalEmails, errorCount, startTime) {
    const progressPercent = totalEmails > 0 ? (emailsSynced / totalEmails) * 100 : 0;
    
    // Update progress bar
    document.getElementById('progressFill').style.width = `${progressPercent}%`;
    document.getElementById('progressText').textContent = `${Math.round(progressPercent)}% complete`;
    document.getElementById('progressCount').textContent = `${emailsSynced.toLocaleString()} / ${totalEmails.toLocaleString()} emails`;
    
    // Update sync status
    document.getElementById('syncStatus').textContent = 
        `Syncing... ${emailsSynced}/${totalEmails} emails (${errorCount} errors)`;
}

function updateMonitoringDisplay(batchCount, batchProgress, newEmails, errorCount) {
    document.getElementById('currentBatch').textContent = `Batch ${batchCount}`;
    document.getElementById('batchProgress').textContent = `${batchProgress}%`;
    document.getElementById('newEmailsCount').textContent = newEmails.toLocaleString();
    document.getElementById('errorCount').textContent = errorCount.toLocaleString();
}

function displaySyncError(errorMessage, severity = 'error') {
    // Create error display if it doesn't exist
    let errorContainer = document.getElementById('syncErrors');
    if (!errorContainer) {
        errorContainer = document.createElement('div');
        errorContainer.id = 'syncErrors';
        errorContainer.className = 'sync-errors';
        errorContainer.innerHTML = '<h3>Sync Errors</h3><div class="error-list" id="errorList"></div>';
        
        // Insert after sync monitoring
        const monitoring = document.getElementById('syncMonitoring');
        monitoring.parentNode.insertBefore(errorContainer, monitoring.nextSibling);
    }
    
    const errorList = document.getElementById('errorList');
    const errorItem = document.createElement('div');
    errorItem.className = `error-item error-${severity}`;
    errorItem.innerHTML = `
        <div class="error-time">${new Date().toLocaleTimeString()}</div>
        <div class="error-message">${errorMessage}</div>
        <div class="error-severity">${severity.toUpperCase()}</div>
    `;
    
    errorList.appendChild(errorItem);
    errorContainer.style.display = 'block';
    
    // Keep only last 20 errors
    while (errorList.children.length > 20) {
        errorList.removeChild(errorList.firstChild);
    }
}

function clearSyncErrors() {
    const errorContainer = document.getElementById('syncErrors');
    if (errorContainer) {
        errorContainer.style.display = 'none';
        const errorList = document.getElementById('errorList');
        if (errorList) {
            errorList.innerHTML = '';
        }
    }
}

// Global chart instances to track and destroy
let chartInstances = {};

// Analytics functionality
function loadAnalytics() {
    console.debug('[sync] Loading comprehensive analytics...');
    
    const analyticsPage = document.getElementById('analyticsPage');
    const loadingElement = document.getElementById('analyticsLoading');
    const contentElement = document.getElementById('analyticsContent');
    const errorElement = document.getElementById('analyticsError');
    
    if (!analyticsPage) {
        console.debug('[error] Analytics page element not found!');
        return;
    }
    
    // Destroy existing charts before creating new ones
    destroyAllCharts();
    
    // Show loading state
    loadingElement.style.display = 'block';
    contentElement.style.display = 'none';
    errorElement.style.display = 'none';
    
    // Get time range from selector
    const timeRange = document.getElementById('analyticsTimeRange').value;
    
    // Fetch comprehensive analytics data
    Promise.all([
        fetch(`/api/analytics/overview?range=${timeRange}`),
        fetch(`/api/analytics/trends?range=${timeRange}`),
        fetch('/api/db/dashboard')
    ])
    .then(responses => {
        console.debug('[net] Analytics API responses received:', responses.map(r => r.status));
        return Promise.all(responses.map(r => r.json()));
    })
    .then(([overviewData, trendsData, dashboardData]) => {
        console.debug('[data] Comprehensive analytics data loaded successfully!');
        
        if (overviewData.success && trendsData.success) {
            displayComprehensiveAnalytics(overviewData.data, trendsData.data, dashboardData);
        } else {
            throw new Error('Analytics data not available');
        }
    })
    .catch(error => {
        console.debug('[error] Error loading analytics:', error);
        loadingElement.style.display = 'none';
        contentElement.style.display = 'none';
        errorElement.style.display = 'block';
        document.getElementById('analyticsErrorMessage').textContent = error.message;
    });
}

// Function to destroy all existing charts
function destroyAllCharts() {
    // Get all canvas elements and destroy any existing charts
    const canvasElements = document.querySelectorAll('canvas');
    canvasElements.forEach(canvas => {
        const existingChart = Chart.getChart(canvas);
        if (existingChart) {
            existingChart.destroy();
        }
    });
    
    // Clear our tracking object
    chartInstances = {};
}

function displayComprehensiveAnalytics(overviewData, trendsData, dashboardData) {
    console.log('🎨 Displaying comprehensive analytics...');
    
    const loadingElement = document.getElementById('analyticsLoading');
    const contentElement = document.getElementById('analyticsContent');
    
    // Hide loading, show content
    loadingElement.style.display = 'none';
    contentElement.style.display = 'block';
    
    // Display key metrics
    displayKeyMetrics(overviewData.overview, dashboardData);
    
    // Display charts
    displayEmailActivityChart(trendsData);
    displayTopSendersChart(overviewData.top_senders);
    displayLabelsChart(overviewData.labels);
    displayReadUnreadChart(overviewData.overview);
    displayHourlyChart(overviewData.hourly_distribution);
    displayWeeklyChart(overviewData.daily_distribution);
    displayEmailLengthChart(overviewData.email_lengths);
    
    // Display statistics
    displaySenderStats(overviewData.top_senders);
    displayCategoryBreakdown(overviewData.labels);
    displayReadStats(overviewData.overview);
    displayStorageMetrics(dashboardData);
    displayPerformanceMetrics(dashboardData);
    displaySubjectStats(overviewData.subject_categories);
    
    // Display insights
    displayAdvancedInsights(overviewData, trendsData, dashboardData);
    
    console.debug('[ok] Comprehensive analytics displayed successfully!');
}

function displayKeyMetrics(overview, dashboardData) {
    const metricsGrid = document.getElementById('keyMetricsGrid');
    
    const formatNumber = (num) => num.toLocaleString();
    const formatPercentage = (num) => {
        const numValue = parseFloat(num);
        return isNaN(numValue) ? '0.0%' : numValue.toFixed(1) + '%';
    };
    
    metricsGrid.innerHTML = `
        <div class="metric-card">
            <h3>Total Emails</h3>
            <div class="metric-value">${formatNumber(overview.total_emails)}</div>
            <div class="metric-subtitle">All time</div>
        </div>
        <div class="metric-card">
            <h3>Unread Emails</h3>
            <div class="metric-value">${formatNumber(overview.unread_emails)}</div>
            <div class="metric-subtitle">${formatPercentage(overview.read_rate)} read rate</div>
        </div>
        <div class="metric-card">
            <h3>Starred Emails</h3>
            <div class="metric-value">${formatNumber(overview.starred_emails)}</div>
            <div class="metric-subtitle">Important emails</div>
        </div>
        <div class="metric-card">
            <h3>Database Size</h3>
            <div class="metric-value">${dashboardData.database_size_pretty || 'Unknown'}</div>
            <div class="metric-subtitle">Storage used</div>
        </div>
        <div class="metric-card">
            <h3>Important Emails</h3>
            <div class="metric-value">${formatNumber(overview.important_emails)}</div>
            <div class="metric-subtitle">High priority</div>
        </div>
        <div class="metric-card">
            <h3>Spam Emails</h3>
            <div class="metric-value">${formatNumber(overview.spam_emails)}</div>
            <div class="metric-subtitle">Filtered out</div>
        </div>
    `;
}

function displayEmailActivityChart(trendsData) {
    const ctx = document.getElementById('emailActivityChart');
    if (!ctx) return;
    
    const labels = trendsData.map(item => new Date(item.date).toLocaleDateString());
    const emailCounts = trendsData.map(item => item.email_count);
    const unreadCounts = trendsData.map(item => item.unread_count);
    
    chartInstances['emailActivityChart'] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Total Emails',
                data: emailCounts,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.4
            }, {
                label: 'Unread Emails',
                data: unreadCounts,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Email Activity Over Time'
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function displayTopSendersChart(topSenders) {
    const ctx = document.getElementById('topSendersChart');
    if (!ctx) return;
    
    const labels = topSenders.slice(0, 8).map(sender => 
        sender.sender.length > 20 ? sender.sender.substring(0, 20) + '...' : sender.sender
    );
    const data = topSenders.slice(0, 8).map(sender => sender.email_count);
    const colors = [
        '#3b82f6', '#ef4444', '#10b981', '#f59e0b', 
        '#8b5cf6', '#06b6d4', '#84cc16', '#f97316'
    ];
    
    chartInstances['topSendersChart'] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Top Email Senders'
                },
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function displayLabelsChart(labels) {
    const ctx = document.getElementById('labelsChart');
    if (!ctx) return;
    
    const labelsData = labels.slice(0, 6);
    const labelNames = labelsData.map(label => label.label);
    const labelCounts = labelsData.map(label => label.email_count);
    const colors = [
        '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4'
    ];
    
    chartInstances['labelsChart'] = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labelNames,
            datasets: [{
                data: labelCounts,
                backgroundColor: colors,
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Email Labels Distribution'
                },
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function displayReadUnreadChart(overview) {
    const ctx = document.getElementById('readUnreadChart');
    if (!ctx) return;
    
    chartInstances['readUnreadChart'] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Read', 'Unread'],
            datasets: [{
                data: [overview.total_emails - overview.unread_emails, overview.unread_emails],
                backgroundColor: ['#10b981', '#ef4444'],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Read vs Unread Emails'
                },
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function displayHourlyChart(hourlyData) {
    const ctx = document.getElementById('hourlyChart');
    if (!ctx) return;
    
    const hours = Array.from({length: 24}, (_, i) => i);
    const emailCounts = hours.map(hour => {
        const data = hourlyData.find(item => item.hour == hour);
        return data ? data.email_count : 0;
    });
    
    chartInstances['hourlyChart'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: hours.map(h => `${h}:00`),
            datasets: [{
                label: 'Emails',
                data: emailCounts,
                backgroundColor: '#3b82f6',
                borderColor: '#2563eb',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function displayWeeklyChart(dailyData) {
    const ctx = document.getElementById('weeklyChart');
    if (!ctx) return;
    
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const emailCounts = days.map((_, index) => {
        const data = dailyData.find(item => item.day_of_week == index);
        return data ? data.email_count : 0;
    });
    
    chartInstances['weeklyChart'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: days,
            datasets: [{
                label: 'Emails',
                data: emailCounts,
                backgroundColor: '#10b981',
                borderColor: '#059669',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function displayEmailLengthChart(lengthData) {
    const ctx = document.getElementById('emailLengthChart');
    if (!ctx) return;
    
    const labels = lengthData.map(item => item.length_category);
    const counts = lengthData.map(item => item.email_count);
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];
    
    chartInstances['emailLengthChart'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Emails',
                data: counts,
                backgroundColor: colors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function displaySenderStats(topSenders) {
    const senderStats = document.getElementById('senderStats');
    
    senderStats.innerHTML = topSenders.slice(0, 5).map(sender => `
        <div class="sender-stat-item">
            <div class="sender-stat-label">${sender.sender}</div>
            <div class="sender-stat-value">${sender.email_count}</div>
        </div>
    `).join('');
}

function displayCategoryBreakdown(labels) {
    const categoryBreakdown = document.getElementById('categoryBreakdown');
    const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4'];
    
    categoryBreakdown.innerHTML = labels.slice(0, 6).map((label, index) => `
        <div class="category-item">
            <div class="category-name">
                <div class="category-color" style="background-color: ${colors[index]}"></div>
                ${label.label}
            </div>
            <div class="category-count">${label.email_count}</div>
        </div>
    `).join('');
}

function displayReadStats(overview) {
    const readStats = document.getElementById('readStats');
    
    const formatPercentage = (num) => {
        const numValue = parseFloat(num);
        return isNaN(numValue) ? '0.0%' : numValue.toFixed(1) + '%';
    };
    
    readStats.innerHTML = `
        <div class="read-stat-item">
            <div class="read-stat-label">Total Emails</div>
            <div class="read-stat-value">${overview.total_emails.toLocaleString()}</div>
        </div>
        <div class="read-stat-item">
            <div class="read-stat-label">Read Emails</div>
            <div class="read-stat-value">${(overview.total_emails - overview.unread_emails).toLocaleString()}</div>
        </div>
        <div class="read-stat-item">
            <div class="read-stat-label">Unread Emails</div>
            <div class="read-stat-value">${overview.unread_emails.toLocaleString()}</div>
        </div>
        <div class="read-stat-item">
            <div class="read-stat-label">Read Rate</div>
            <div class="read-stat-value">${formatPercentage(overview.read_rate)}</div>
        </div>
    `;
}

function displayStorageMetrics(dashboardData) {
    const storageMetrics = document.getElementById('storageMetrics');
    
    storageMetrics.innerHTML = `
        <div class="storage-metric-item">
            <div class="storage-metric-label">Database Size</div>
            <div class="storage-metric-value">${dashboardData.database_size_pretty || 'Unknown'}</div>
        </div>
        <div class="storage-metric-item">
            <div class="storage-metric-label">Total Emails</div>
            <div class="storage-metric-value">${dashboardData.total_emails?.toLocaleString() || 'Unknown'}</div>
        </div>
        <div class="storage-metric-item">
            <div class="storage-metric-label">Average Email Size</div>
            <div class="storage-metric-value">~35 KB</div>
        </div>
    `;
}

function displayPerformanceMetrics(dashboardData) {
    const performanceMetrics = document.getElementById('performanceMetrics');
    
    performanceMetrics.innerHTML = `
        <div class="performance-metric-item">
            <div class="performance-metric-label">Last Sync</div>
            <div class="performance-metric-value">${dashboardData.last_sync_time ? new Date(dashboardData.last_sync_time).toLocaleString() : 'Never'}</div>
        </div>
        <div class="performance-metric-item">
            <div class="performance-metric-label">Sync Status</div>
            <div class="performance-metric-value">${dashboardData.sync_status || 'Unknown'}</div>
        </div>
        <div class="performance-metric-item">
            <div class="performance-metric-label">Latest Email</div>
            <div class="performance-metric-value">${dashboardData.latest_email_date ? new Date(dashboardData.latest_email_date).toLocaleDateString() : 'Unknown'}</div>
        </div>
    `;
}

function displaySubjectStats(subjectCategories) {
    const subjectStats = document.getElementById('subjectStats');
    
    subjectStats.innerHTML = subjectCategories.map(category => `
        <div class="subject-stat-item">
            <div class="subject-stat-label">${category.subject_category}</div>
            <div class="subject-stat-value">${category.email_count}</div>
        </div>
    `).join('');
}

function displayAdvancedInsights(overviewData, trendsData, dashboardData) {
    const insightsGrid = document.getElementById('insightsGrid');
    
    const insights = [];
    
    // Email volume insight
    if (trendsData.length > 0) {
        const avgEmailsPerDay = trendsData.reduce((sum, day) => sum + day.email_count, 0) / trendsData.length;
        insights.push({
            title: 'Daily Email Volume',
            content: `You receive an average of ${avgEmailsPerDay.toFixed(1)} emails per day.`
        });
    }
    
    // Read rate insight
    const readRate = parseFloat(overviewData.overview.read_rate);
    if (readRate > 80) {
        insights.push({
            title: 'Excellent Read Rate',
            content: `You have a ${readRate.toFixed(1)}% read rate, which is excellent!`
        });
    } else if (readRate > 60) {
        insights.push({
            title: 'Good Read Rate',
            content: `You have a ${readRate.toFixed(1)}% read rate. Consider setting aside time to catch up on unread emails.`
        });
    } else {
        insights.push({
            title: 'Email Management',
            content: `You have a ${readRate.toFixed(1)}% read rate. Consider implementing email management strategies.`
        });
    }
    
    // Top sender insight
    if (overviewData.top_senders.length > 0) {
        const topSender = overviewData.top_senders[0];
        insights.push({
            title: 'Most Active Sender',
            content: `${topSender.sender} sends you the most emails (${topSender.email_count} emails).`
        });
    }
    
    // Storage insight
    if (dashboardData.database_size_gb > 10) {
        insights.push({
            title: 'Large Email Archive',
            content: `Your email archive is ${dashboardData.database_size_gb} GB. Consider archiving old emails to save space.`
        });
    }
    
    insightsGrid.innerHTML = insights.map(insight => `
        <div class="insight-card">
            <h4>${insight.title}</h4>
            <p>${insight.content}</p>
        </div>
    `).join('');
}

// Initialize analytics controls
function initializeAnalyticsControls() {
    const timeRangeSelect = document.getElementById('analyticsTimeRange');
    const refreshBtn = document.getElementById('refreshAnalytics');
    const exportBtn = document.getElementById('exportAnalytics');
    
    if (timeRangeSelect) {
        timeRangeSelect.addEventListener('change', loadAnalytics);
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadAnalytics);
    }
    
    if (exportBtn) {
        exportBtn.addEventListener('click', exportAnalyticsData);
    }
}

function exportAnalyticsData() {
    // Implementation for exporting analytics data
    console.debug('[data] Exporting analytics data...');
    alert('Export functionality will be implemented in the next version.');
}

// Settings functionality
function loadSettings() {
    // Load current settings
    loadCurrentSettings();
    
    // Add event listeners
    document.getElementById('saveSettings').addEventListener('click', saveSettings);
    document.getElementById('resetSettings').addEventListener('click', resetSettings);
    document.getElementById('clearData').addEventListener('click', clearData);
    document.getElementById('darkMode').addEventListener('change', toggleDarkMode);
}

function loadCurrentSettings() {
    // Load settings from localStorage or use defaults
    const settings = JSON.parse(localStorage.getItem('emailSettings')) || {
        emailAddress: 'user@example.com',
        displayName: 'John Doe',
        timezone: 'UTC',
        autoSync: true,
        syncInterval: '15',
        maxEmails: '1000',
        darkMode: false,
        emailsPerPage: '25',
        showPreview: true
    };
    
    // Apply settings to form
    document.getElementById('emailAddress').value = settings.emailAddress;
    document.getElementById('displayName').value = settings.displayName;
    document.getElementById('timezone').value = settings.timezone;
    document.getElementById('autoSync').checked = settings.autoSync;
    document.getElementById('syncInterval').value = settings.syncInterval;
    document.getElementById('maxEmails').value = settings.maxEmails;
    document.getElementById('darkMode').checked = settings.darkMode;
    document.getElementById('emailsPerPage').value = settings.emailsPerPage;
    document.getElementById('showPreview').checked = settings.showPreview;
    
    // Apply dark mode if enabled
    if (settings.darkMode) {
        document.body.classList.add('dark-theme');
    }
}

function saveSettings() {
    const settings = {
        emailAddress: document.getElementById('emailAddress').value,
        displayName: document.getElementById('displayName').value,
        timezone: document.getElementById('timezone').value,
        autoSync: document.getElementById('autoSync').checked,
        syncInterval: document.getElementById('syncInterval').value,
        maxEmails: document.getElementById('maxEmails').value,
        darkMode: document.getElementById('darkMode').checked,
        emailsPerPage: document.getElementById('emailsPerPage').value,
        showPreview: document.getElementById('showPreview').checked
    };
    
    localStorage.setItem('emailSettings', JSON.stringify(settings));
    
    // Show success message
    showNotification('Settings saved successfully!', 'success');
}

function resetSettings() {
    if (confirm('Are you sure you want to reset all settings to default?')) {
        localStorage.removeItem('emailSettings');
        loadCurrentSettings();
        showNotification('Settings reset to default!', 'info');
    }
}

function clearData() {
    if (confirm('Are you sure you want to clear all email data? This action cannot be undone.')) {
        // In a real app, this would call the backend to clear data
        showNotification('All data cleared!', 'warning');
    }
}

function toggleDarkMode() {
    const darkMode = document.getElementById('darkMode').checked;
    if (darkMode) {
        document.body.classList.add('dark-theme');
    } else {
        document.body.classList.remove('dark-theme');
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-message">${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Show/hide loading
function showLoading(show) {
    loadingOverlay.style.display = show ? 'flex' : 'none';
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing app...');
    
    try {
    
    // Immediately hide loading overlay
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
        console.log('Loading overlay hidden');
    }
    
    // Initialize navigation
    initializeNavigation();
    
    // Initialize email modal functionality
    initializeEmailModal();
    
    // Initialize analytics controls
    initializeAnalyticsControls();
    
    // Show dashboard by default
    showPage('dashboard');
    
    // Theme toggle
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            document.body.classList.toggle('dark-theme');
        });
    }
    
    // Logout handler
    const logoutBtn = document.querySelector('.btn-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            if (confirm('Are you sure you want to sign out?')) {
                // Handle logout
                console.log('User logged out');
            }
        });
    }
    
    // Search page close detail button
    const closeSearchDetailBtn = document.getElementById('closeSearchDetail');
    if (closeSearchDetailBtn) {
        closeSearchDetailBtn.addEventListener('click', closeSearchEmailDetail);
    }
    
    console.log('App initialization complete');
    
    } catch (error) {
        console.debug('[error] Error during app initialization:', error);
        console.debug('[error] Error stack:', error.stack);
    }
    
    // Start sync status refresh
    startSyncStatusRefresh();
});

// Global functions for onclick handlers
window.toggleStar = toggleStar;
window.selectEmail = selectEmail;
window.selectSearchEmail = selectSearchEmail;
window.toggleReadStatus = toggleReadStatus;
window.deleteEmail = deleteEmail;
window.closeSearchEmailDetail = closeSearchEmailDetail;

// Debug function for testing
window.testAnalytics = function() {
    console.debug('[test] TEST ANALYTICS CALLED');
    console.debug('[test] loadAnalytics function type:', typeof loadAnalytics);
    console.debug('[test] Calling loadAnalytics...');
    loadAnalytics();
};

console.debug('[init] Script loading completed - testAnalytics should be available');

// Function to clear all sync intervals and force refresh
window.clearAllSyncIntervals = function() {
    console.log('🧹 Clearing all sync intervals...');
    if (syncStatusInterval) {
        clearInterval(syncStatusInterval);
        syncStatusInterval = null;
        console.debug('[ok] Cleared syncStatusInterval');
    }
    if (window.progressUpdateInterval) {
        clearInterval(window.progressUpdateInterval);
        window.progressUpdateInterval = null;
        console.debug('[ok] Cleared progressUpdateInterval');
    }
    if (window.monitoringInterval) {
        clearInterval(window.monitoringInterval);
        window.monitoringInterval = null;
        console.debug('[ok] Cleared monitoringInterval');
    }
};

// Function to force refresh sync status
window.forceRefreshSyncStatus = function() {
    console.debug('[sync] Force refreshing sync status...');
    clearAllSyncIntervals();
    loadSyncMonitoring();
};

// Global error handler
window.addEventListener('error', (event) => {
    console.debug('[error] Global JavaScript Error:', event.error);
    console.debug('[error] Error message:', event.message);
    console.debug('[error] Error filename:', event.filename);
    console.debug('[error] Error line:', event.lineno);
    console.debug('[error] Error column:', event.colno);
});

// Unhandled promise rejection handler
window.addEventListener('unhandledrejection', (event) => {
    console.debug('[error] Unhandled Promise Rejection:', event.reason);
});

// Display sync details for currently running sync
function displaySyncDetails(syncDetails) {
    console.log('displaySyncDetails called with:', syncDetails);
    
    const syncInfoContainer = document.getElementById('syncInfoContainer');
    console.log('syncInfoContainer found:', !!syncInfoContainer);
    
    if (!syncInfoContainer) {
        console.error('syncInfoContainer not found!');
        return;
    }
    
    let detailsHTML = '<div class="sync-details-panel">';
    detailsHTML += '<h4>[sync] Current Sync Process</h4>';
    
    // Sync type and status
    if (syncDetails.sync_type) {
        const syncTypeDisplay = syncDetails.sync_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        detailsHTML += `<p><strong>Type:</strong> ${syncTypeDisplay}</p>`;
    }
    
    // Start time
    if (syncDetails.start_time) {
        const startTime = new Date(syncDetails.start_time);
        detailsHTML += `<p><strong>Started:</strong> ${startTime.toLocaleString()}</p>`;
    }
    
    // Elapsed time (with live update indicator)
    if (syncDetails.elapsed_time) {
        detailsHTML += `<p><strong>Running for:</strong> <span class="live-time">${syncDetails.elapsed_time}</span> ⏱️</p>`;
    }
    
    // Progress bar
    if (syncDetails.progress_percentage !== undefined) {
        const progressPercent = Math.min(syncDetails.progress_percentage, 100);
        detailsHTML += `
            <p><strong>Progress:</strong> ${progressPercent.toFixed(1)}%</p>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progressPercent}%"></div>
            </div>
        `;
    }
    
    // Emails processed (show actual synced emails prominently)
    if (syncDetails.emails_processed !== undefined) {
        const emailCount = syncDetails.emails_processed;
        let emailIcon = '[email]';
        if (emailCount > 1000) emailIcon = '📬';
        if (emailCount > 10000) emailIcon = '📭';
        
        detailsHTML += `<p><strong>Emails synced:</strong> <span class="live-count" style="color: #28a745; font-size: 1.1em;">${emailCount.toLocaleString()}</span> ${emailIcon}</p>`;
    }
    
    // Speed with trend indicator
    if (syncDetails.emails_per_minute !== undefined) {
        const speed = syncDetails.emails_per_minute;
        let speedIcon = '[data]';
        if (speed > 100) speedIcon = '[init]';
        else if (speed > 50) speedIcon = '[perf]';
        else if (speed > 10) speedIcon = '[data]';
        else speedIcon = '🐌';
        
        detailsHTML += `<p><strong>Speed:</strong> <span class="live-speed">${speed}</span> emails/min ${speedIcon}</p>`;
    }
    
    // Estimated completion
    if (syncDetails.estimated_completion) {
        const estimatedTime = new Date(syncDetails.estimated_completion);
        const now = new Date();
        const timeLeft = estimatedTime - now;
        
        if (timeLeft > 0) {
            const hoursLeft = Math.floor(timeLeft / (1000 * 60 * 60));
            const minutesLeft = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            
            let timeLeftText = '';
            if (hoursLeft > 0) {
                timeLeftText = `${hoursLeft}h ${minutesLeft}m remaining`;
            } else {
                timeLeftText = `${minutesLeft}m remaining`;
            }
            
            detailsHTML += `<p><strong>Estimated completion:</strong> ${estimatedTime.toLocaleString()} (${timeLeftText}) [time]</p>`;
        } else {
            detailsHTML += `<p><strong>Estimated completion:</strong> ${estimatedTime.toLocaleString()} (completing soon) [time]</p>`;
        }
    }
    
    // Current batch
    if (syncDetails.current_batch !== undefined && syncDetails.total_batches !== undefined) {
        detailsHTML += `<p><strong>Batch:</strong> ${syncDetails.current_batch} of ${syncDetails.total_batches}</p>`;
    }
    
    // Note
    if (syncDetails.note) {
        detailsHTML += `<p><strong>Activity:</strong> ${syncDetails.note} [data]</p>`;
    }
    
    // Auto-refresh indicator
    detailsHTML += '<p class="refresh-indicator">[sync] Auto-refreshing every 5 seconds</p>';
    
    detailsHTML += '</div>';
    
    console.log('Generated HTML:', detailsHTML);
    
    syncInfoContainer.innerHTML = detailsHTML;
    syncInfoContainer.style.display = 'block';
    
    console.log('Sync details displayed successfully');
}

// Hide sync details when no sync is running
function hideSyncDetails() {
    const syncInfoContainer = document.getElementById('syncInfoContainer');
    if (syncInfoContainer) {
        syncInfoContainer.style.display = 'none';
    }
}

// Display current sync progress in the dedicated section
function displayCurrentSyncProgress(syncDetails) {
    const progressContainer = document.getElementById('currentSyncProgress');
    if (!progressContainer) return;
    
    // Update the progress values
    const sessionEmailsElement = document.getElementById('currentSessionEmails');
    const emailsPerMinuteElement = document.getElementById('currentEmailsPerMinute');
    const elapsedTimeElement = document.getElementById('currentElapsedTime');
    
    if (sessionEmailsElement) {
        sessionEmailsElement.textContent = syncDetails.emails_processed?.toLocaleString() || '0';
    }
    
    if (emailsPerMinuteElement) {
        emailsPerMinuteElement.textContent = syncDetails.emails_per_minute?.toLocaleString() || '0';
    }
    
    if (elapsedTimeElement) {
        elapsedTimeElement.textContent = syncDetails.elapsed_time || '0:00';
    }
    
    progressContainer.style.display = 'block';
}

// Hide current sync progress when no sync is running
function hideCurrentSyncProgress() {
    const progressContainer = document.getElementById('currentSyncProgress');
    if (progressContainer) {
        progressContainer.style.display = 'none';
    }
}

// Periodic sync status refresh
let syncStatusInterval = null;

function startSyncStatusRefresh() {
    // Clear any existing interval
    if (syncStatusInterval) {
        clearInterval(syncStatusInterval);
    }
    
    // Refresh every 10 seconds
    syncStatusInterval = setInterval(() => {
        loadSyncStatus();
    }, 10000);
}

function stopSyncStatusRefresh() {
    if (syncStatusInterval) {
        clearInterval(syncStatusInterval);
        syncStatusInterval = null;
    }
}

// Check if sync can be resumed
function checkResumeAvailability() {
    console.debug('[debug] Checking resume availability...');
    
    fetch('/api/sync/resume-info')
        .then(response => response.json())
        .then(data => {
            console.debug('[data] Resume info:', data);
            
            const resumeSyncBtn = document.getElementById('resumeSyncBtn');
            
            if (data.success && data.resume_info.can_resume) {
                console.debug('[ok] Resume available:', data.resume_info.resume_reason);
                resumeSyncBtn.disabled = false;
                resumeSyncBtn.title = `Resume from ${data.resume_info.resume_reason}`;
                
                // Add visual indicator
                resumeSyncBtn.classList.add('btn-success');
                resumeSyncBtn.classList.remove('btn-secondary');
                
            } else {
                console.debug('[error] Resume not available');
                resumeSyncBtn.disabled = true;
                resumeSyncBtn.title = 'No sync to resume';
                
                // Add visual indicator
                resumeSyncBtn.classList.remove('btn-success');
                resumeSyncBtn.classList.add('btn-secondary');
            }
        })
        .catch(error => {
            console.debug('[error] Error checking resume availability:', error);
            const resumeSyncBtn = document.getElementById('resumeSyncBtn');
            resumeSyncBtn.disabled = true;
            resumeSyncBtn.title = 'Error checking resume availability';
        });
}

// Load real-time sync monitoring data
function loadSyncMonitoring() {
    console.debug('[sync] loadSyncMonitoring called - fetching latest sync status...');
    fetch('/api/db/sync-monitoring')
        .then(response => response.json())
        .then(data => {
            console.debug('[data] Sync monitoring data received:', data);
            
            const syncProgress = data.sync_progress;
            const dbStats = data.database_stats;
            const activityStats = data.activity_stats;
            
            // Update sync status and button states
            const startSyncBtn = document.getElementById('startSync');
            const stopSyncBtn = document.getElementById('stopSync');
            
            console.debug('[debug] Sync progress check - is_active:', syncProgress.is_active, 'status:', syncProgress.status);
            
            if (syncProgress.is_active && syncProgress.status !== 'stale') {
                console.log('🟡 Sync is ACTIVE - updating UI to show sync in progress');
                document.getElementById('syncStatus').textContent = 'Sync in progress';
                
                // Enable stop button, disable start button
                if (startSyncBtn) startSyncBtn.disabled = true;
                if (stopSyncBtn) stopSyncBtn.disabled = false;
                
                // Display sync details with real-time information
                const syncDetails = {
                    sync_type: syncProgress.sync_type,
                    start_time: syncProgress.start_time,
                    elapsed_time: syncProgress.elapsed_time,
                    progress_percentage: syncProgress.progress_percentage,
                    emails_processed: syncProgress.actual_synced || syncProgress.emails_processed,
                    emails_per_minute: syncProgress.emails_per_minute,
                    current_batch: syncProgress.current_batch,
                    total_batches: syncProgress.total_batches,
                    estimated_completion: syncProgress.estimated_completion,
                    note: `Backend status: ${syncProgress.backend_status}. Actual emails synced: ${syncProgress.actual_synced || 0}. Recent activity: ${activityStats.recent_emails_1min} emails in last minute, ${activityStats.recent_emails_5min} in last 5 minutes`
                };
                
                displaySyncDetails(syncDetails);
            } else if (syncProgress.status === 'stale') {
                console.log('🟠 Sync is STALE - updating UI to show stale status');
                document.getElementById('syncStatus').textContent = 'Sync stalled';
                
                // Enable start button, disable stop button
                if (startSyncBtn) startSyncBtn.disabled = false;
                if (stopSyncBtn) stopSyncBtn.disabled = true;
                
                // Display stale sync details
                const syncDetails = {
                    sync_type: syncProgress.sync_type,
                    start_time: syncProgress.start_time,
                    elapsed_time: syncProgress.elapsed_time,
                    progress_percentage: syncProgress.progress_percentage,
                    emails_processed: syncProgress.actual_synced || syncProgress.emails_processed,
                    emails_per_minute: 0, // Stale sessions have 0 speed
                    current_batch: syncProgress.current_batch,
                    total_batches: syncProgress.total_batches,
                    estimated_completion: 'Stalled',
                    note: `Session became stale after 2+ hours. Last synced: ${syncProgress.actual_synced || 0} emails. Error: ${syncProgress.last_error || 'Unknown'}`
                };
                
                displaySyncDetails(syncDetails);
            } else {
                console.log('🟢 Sync is INACTIVE - updating UI to show ready to sync');
                document.getElementById('syncStatus').textContent = 'Ready to sync';
                
                // Enable start button, disable stop button
                if (startSyncBtn) startSyncBtn.disabled = false;
                if (stopSyncBtn) stopSyncBtn.disabled = true;
                
                console.log('🚫 Calling hideSyncDetails to hide sync info container');
                hideSyncDetails();
            }
            
            // Update database stats
            const totalSyncedEl = document.getElementById('totalSynced');
            if (totalSyncedEl && dbStats.total_emails !== undefined) {
                totalSyncedEl.textContent = `${Number(dbStats.total_emails).toLocaleString()} emails`;
            }
            document.getElementById('syncDatabaseSize').textContent = `${dbStats.database_size_gb} GB`;
            
            // Update last sync time
            if (dbStats.latest_email_date) {
                const latestEmail = new Date(dbStats.latest_email_date);
                document.getElementById('lastSyncTime').textContent = latestEmail.toLocaleString();
            } else {
                document.getElementById('lastSyncTime').textContent = 'Recent';
            }
            
        })
        .catch(error => {
            console.debug('[error] Error loading sync monitoring:', error);
            console.debug('[sync] Falling back to loadSyncStatus due to error');
            // Fall back to regular sync status
            loadSyncStatus();
        });
}

// Start periodic sync monitoring refresh (every 5 seconds)
// Let API data determine the correct value
function forceUpdateTotalEmails() {
    // This function is no longer needed - API data will be used
    console.debug('[ok] Total emails will be updated via API data');
}

// Simple monitoring - let API data flow through
function startTotalEmailsMonitoring() {
    // This function is no longer needed - API data will be used
    console.debug('[ok] Total emails monitoring disabled - using API data');
}

function startSyncMonitoringRefresh() {
    // Clear any existing interval
    if (syncStatusInterval) {
        clearInterval(syncStatusInterval);
    }
    
    // Refresh every 3 seconds for real-time updates
    syncStatusInterval = setInterval(() => {
        console.debug('[sync] Interval triggered - calling loadSyncMonitoring');
        loadSyncMonitoring();
    }, 3000);
}

// Notification System
let notifications = [];

// Load real notifications from API
async function loadRealNotifications() {
    try {
        // Get sync status
        const syncResponse = await fetch('/api/db/sync-status');
        const syncData = await syncResponse.json();
        
        // Get dashboard data
        const dashboardResponse = await fetch('/api/db/dashboard');
        const dashboardData = await dashboardResponse.json();
        
        // Clear existing notifications
        notifications = [];
        
        // Add sync status notification
        if (syncData.sync_in_progress) {
            notifications.push({
                id: 1,
                title: 'Sync In Progress',
                message: `Currently syncing emails... ${syncData.total_emails?.toLocaleString() || 0} emails in database`,
                time: 'Now',
                type: 'info',
                read: false
            });
        } else if (syncData.last_sync_time) {
            const lastSync = new Date(syncData.last_sync_time);
            const timeAgo = getTimeAgo(lastSync);
            notifications.push({
                id: 1,
                title: 'Last Sync',
                message: `Last sync completed ${timeAgo}`,
                time: timeAgo,
                type: 'success',
                read: false
            });
        } else {
            notifications.push({
                id: 1,
                title: 'No Recent Sync',
                message: 'No sync activity detected',
                time: 'Unknown',
                type: 'warning',
                read: false
            });
        }
        
        // Add database size notification
        if (dashboardData.database_size_gb && dashboardData.database_size_gb > 10) {
            notifications.push({
                id: 2,
                title: 'Database Size Alert',
                message: `Database size is ${dashboardData.database_size_pretty || 'Unknown'}`,
                time: 'Current',
                type: 'warning',
                read: false
            });
        }
        
        // Add email count notification
        if (syncData.total_emails && syncData.total_emails > 1000000) {
            notifications.push({
                id: 3,
                title: 'Large Email Database',
                message: `${syncData.total_emails.toLocaleString()} emails stored`,
                time: 'Current',
                type: 'info',
                read: false
            });
        }
        
        // Update notification count and render
        updateNotificationCount();
        if (document.getElementById('notificationDropdown')?.classList.contains('show')) {
            renderNotifications();
        }
        
        console.debug('[ok] Real notifications loaded:', notifications.length);
        
    } catch (error) {
        console.debug('[error] Error loading real notifications:', error);
        // Fallback to basic notifications
        notifications = [
            {
                id: 1,
                title: 'System Status',
                message: 'Gmail Backup Manager is running',
                time: 'Now',
                type: 'info',
                read: false
            }
        ];
        updateNotificationCount();
    }
}

// Helper function to get time ago
function getTimeAgo(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}

// Initialize notification system
function initNotifications() {
    const notificationsBtn = document.getElementById('notificationsBtn');
    const notificationDropdown = document.getElementById('notificationDropdown');
    const notificationCount = document.getElementById('notificationCount');
    const clearAllBtn = document.getElementById('clearAllNotifications');
    
    if (!notificationsBtn || !notificationDropdown) {
        console.log('Notification elements not found');
        return;
    }
    
    // Load real notifications from API
    loadRealNotifications();
    
    // Toggle dropdown on click
    notificationsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleNotificationDropdown();
    });
    
    // Clear all notifications
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', () => {
            clearAllNotifications();
        });
    }
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!notificationsBtn.contains(e.target) && !notificationDropdown.contains(e.target)) {
            closeNotificationDropdown();
        }
    });
    
    console.debug('[ok] Notification system initialized');
}

// Toggle notification dropdown
function toggleNotificationDropdown() {
    const notificationDropdown = document.getElementById('notificationDropdown');
    if (notificationDropdown) {
        if (notificationDropdown.classList.contains('show')) {
            closeNotificationDropdown();
        } else {
            openNotificationDropdown();
        }
    }
}

// Open notification dropdown
function openNotificationDropdown() {
    const notificationDropdown = document.getElementById('notificationDropdown');
    if (notificationDropdown) {
        notificationDropdown.classList.add('show');
        renderNotifications();
    }
}

// Close notification dropdown
function closeNotificationDropdown() {
    const notificationDropdown = document.getElementById('notificationDropdown');
    if (notificationDropdown) {
        notificationDropdown.classList.remove('show');
    }
}

// Render notifications in dropdown
function renderNotifications() {
    const notificationList = document.getElementById('notificationList');
    if (!notificationList) return;
    
    if (notifications.length === 0) {
        notificationList.innerHTML = '<div class="notification-item"><div class="notification-content"><div class="notification-message">No notifications</div></div></div>';
        return;
    }
    
    notificationList.innerHTML = notifications.map(notification => `
        <div class="notification-item" data-id="${notification.id}">
            <div class="notification-icon ${notification.type}">
                <i class="fas ${getNotificationIcon(notification.type)}"></i>
            </div>
            <div class="notification-content">
                <div class="notification-title">${notification.title}</div>
                <div class="notification-message">${notification.message}</div>
                <div class="notification-time">${notification.time}</div>
            </div>
        </div>
    `).join('');
}

// Get icon for notification type
function getNotificationIcon(type) {
    const icons = {
        success: 'fa-check',
        info: 'fa-info',
        warning: 'fa-exclamation',
        error: 'fa-times'
    };
    return icons[type] || 'fa-info';
}

// Update notification count
function updateNotificationCount() {
    const notificationCount = document.getElementById('notificationCount');
    if (notificationCount) {
        const unreadCount = notifications.filter(n => !n.read).length;
        notificationCount.textContent = unreadCount;
        notificationCount.style.display = unreadCount > 0 ? 'block' : 'none';
    }
}

// Clear all notifications
function clearAllNotifications() {
    notifications = [];
    updateNotificationCount();
    renderNotifications();
    console.debug('[ok] All notifications cleared');
}

// Add new notification
function addNotification(title, message, type = 'info') {
    const notification = {
        id: Date.now(),
        title,
        message,
        time: 'Just now',
        type,
        read: false
    };
    
    notifications.unshift(notification);
    updateNotificationCount();
    
    // If dropdown is open, re-render
    const notificationDropdown = document.getElementById('notificationDropdown');
    if (notificationDropdown && notificationDropdown.classList.contains('show')) {
        renderNotifications();
    }
    
    console.debug('[ok] New notification added:', title);
}

// Initialize notifications when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initNotifications();
});
