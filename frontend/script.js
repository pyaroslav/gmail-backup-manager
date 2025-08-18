// Global state
console.log('🚀 SCRIPT LOADING STARTED');
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
        const response = await fetch('http://localhost:3002/api/db/health');
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
            `http://localhost:3002/api/db/emails?page=${page}&page_size=25`,  // Node.js direct server
            `http://localhost:3002/api/db/email-count`  // Fallback to just count if emails fail
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
        fetch(`http://localhost:8000/api/v1/test/emails/?page=${page}&page_size=10`),
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

// Load email detail
function loadEmailDetail(email) {
    console.log('loadEmailDetail called with email:', email);
    console.log('detailContent element:', detailContent);
    
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
            ${email.body_html ? email.body_html : (email.body_plain || 'No content available')}
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
    
    if (detailContent) {
        detailContent.innerHTML = emailDetailHtml;
        console.log('Email detail content loaded successfully');
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
function loadSearchEmailDetail(email, detailContent) {
    console.log('Loading search email detail for:', email);
    console.log('Detail content element:', detailContent);
    
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
            ${email.body_html ? email.body_html : (email.body_plain || 'No content available')}
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
    
    if (detailContent) {
        detailContent.innerHTML = emailDetailHtml;
        console.log('Email detail content loaded successfully');
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
        await fetch(`http://localhost:3002/api/db/emails/${numericEmailId}/read`, { method: 'POST' });
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
        await fetch(`http://localhost:3002/api/db/emails/${numericEmailId}/unread`, { method: 'POST' });
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
        await fetch(`http://localhost:3002/api/db/emails/${numericEmailId}/star`, { method: 'POST' });
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
        await fetch(`http://localhost:3002/api/db/emails/${numericEmailId}`, { method: 'DELETE' });
        
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
    // Try multiple endpoints in order of reliability
    const endpoints = [
        'http://localhost:3002/api/db/email-count',  // Node.js direct server
        'http://localhost:8000/api/v1/test/db/raw-count',
        'http://localhost:8000/api/v1/test/db/frontend-count',
        'http://localhost:8000/api/v1/test/cache/file-count',
        'http://localhost:8000/api/v1/test/db/direct-count'
    ];
    
    let currentEndpoint = 0;
    
    function tryEndpoint() {
        if (currentEndpoint >= endpoints.length) {
            document.getElementById('syncStatus').textContent = 'Status unavailable';
            document.getElementById('lastSyncTime').textContent = 'Unknown';
            document.getElementById('totalSynced').textContent = 'Loading...';
            document.getElementById('databaseSize').textContent = 'Loading...';
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
                if (data.status) {
                    document.getElementById('syncStatus').textContent = 
                        data.sync_in_progress ? 'Sync in progress' : 'Ready to sync';
                    
                    if (data.last_sync_time) {
                        const lastSync = new Date(data.last_sync_time);
                        document.getElementById('lastSyncTime').textContent = lastSync.toLocaleString();
                    } else if (data.latest_email_date) {
                        const latestEmail = new Date(data.latest_email_date);
                        document.getElementById('lastSyncTime').textContent = latestEmail.toLocaleString();
                    } else {
                        document.getElementById('lastSyncTime').textContent = 'Recent';
                    }
                } else {
                    document.getElementById('syncStatus').textContent = 'Ready to sync';
                    document.getElementById('lastSyncTime').textContent = 'Recent';
                }
                
                document.getElementById('totalSynced').textContent = 
                    `${data.total_emails?.toLocaleString() || 0} emails`;
                
                // Display database size in GB if available
                console.log('Database size data:', { 
                    database_size_gb: data.database_size_gb, 
                    database_size_pretty: data.database_size_pretty 
                });
                
                if (data.database_size_gb !== undefined) {
                    document.getElementById('databaseSize').textContent = 
                        `${data.database_size_gb} GB`;
                    console.log('Set database size to:', `${data.database_size_gb} GB`);
                } else {
                    document.getElementById('databaseSize').textContent = 
                        `${data.total_emails?.toLocaleString() || 0} emails`;
                    console.log('Set database size to email count:', `${data.total_emails?.toLocaleString() || 0} emails`);
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
                } else {
                    console.log('Calling hideSyncDetails');
                    hideSyncDetails();
                }
                
                console.log(`Sync status loaded using: ${endpoint}`);
            } else {
                throw new Error('Invalid response format');
            }
        })
        .catch(error => {
            console.log(`Endpoint ${endpoint} failed: ${error.message}`);
            currentEndpoint++;
            setTimeout(tryEndpoint, 500);
        });
    }
    
    tryEndpoint();
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
        `http://localhost:3002/api/db/search?q=${encodeURIComponent(searchTerm)}&page=${page}&page_size=${searchPageSize}`  // Node.js direct server
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
            <div class="email-preview">${(email.body_plain || '').substring(0, 100)}...</div>
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

// Sync functionality
function initializeSync() {
    // Initialize all sync buttons
    const quickSyncBtn = document.getElementById('quickSyncBtn');
    const dateRangeSyncBtn = document.getElementById('dateRangeSyncBtn');
    const fullSyncBtn = document.getElementById('fullSyncBtn');
    const startBackgroundSyncBtn = document.getElementById('startBackgroundSyncBtn');
    const stopBackgroundSyncBtn = document.getElementById('stopBackgroundSyncBtn');
    const startSyncBtn = document.getElementById('startSync');
    const stopSyncBtn = document.getElementById('stopSync');
    const resetLastSyncBtn = document.getElementById('resetLastSyncBtn');
    const clearLogBtn = document.getElementById('clearLogBtn');
    const exportLogBtn = document.getElementById('exportLogBtn');

    // Add event listeners
    quickSyncBtn.addEventListener('click', () => performQuickSync());
    dateRangeSyncBtn.addEventListener('click', () => performDateRangeSync());
    fullSyncBtn.addEventListener('click', () => performFullSync());
    startBackgroundSyncBtn.addEventListener('click', () => startBackgroundSync());
    stopBackgroundSyncBtn.addEventListener('click', () => stopBackgroundSync());
    startSyncBtn.addEventListener('click', () => startManualSync());
    stopSyncBtn.addEventListener('click', () => stopSync());
    resetLastSyncBtn.addEventListener('click', () => resetLastSync());
    clearLogBtn.addEventListener('click', () => clearLog());
    exportLogBtn.addEventListener('click', () => exportLog());

    // Load initial sync monitoring data
    loadSyncMonitoring();
    
    // Start periodic sync monitoring refresh (every 5 seconds)
    startSyncMonitoringRefresh();
    
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
    // Use Node.js endpoints only to avoid hanging backend calls
    const endpoints = [
        'http://localhost:3002/api/db/sync-status',  // Node.js sync status
        'http://localhost:3002/api/db/email-count'   // Node.js direct server
    ];
    
    let currentEndpoint = 0;
    
    function tryEndpoint() {
        if (currentEndpoint >= endpoints.length) {
            document.getElementById('syncStatus').textContent = 'Status unavailable';
            document.getElementById('lastSyncTime').textContent = 'Unknown';
            document.getElementById('totalSynced').textContent = 'Loading...';
            document.getElementById('databaseSize').textContent = 'Loading...';
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
                if (data.status) {
                    document.getElementById('syncStatus').textContent = 
                        data.sync_in_progress ? 'Sync in progress' : 'Ready to sync';
                    
                    if (data.last_sync_time) {
                        const lastSync = new Date(data.last_sync_time);
                        document.getElementById('lastSyncTime').textContent = lastSync.toLocaleString();
                    } else if (data.latest_email_date) {
                        const latestEmail = new Date(data.latest_email_date);
                        document.getElementById('lastSyncTime').textContent = latestEmail.toLocaleString();
                    } else {
                        document.getElementById('lastSyncTime').textContent = 'Recent';
                    }
                } else {
                    document.getElementById('syncStatus').textContent = 'Ready to sync';
                    document.getElementById('lastSyncTime').textContent = 'Recent';
                }
                
                document.getElementById('totalSynced').textContent = 
                    `${data.total_emails?.toLocaleString() || 0} emails`;
                
                // Display database size in GB if available
                console.log('Database size data:', { 
                    database_size_gb: data.database_size_gb, 
                    database_size_pretty: data.database_size_pretty 
                });
                
                if (data.database_size_gb !== undefined) {
                    document.getElementById('databaseSize').textContent = 
                        `${data.database_size_gb} GB`;
                    console.log('Set database size to:', `${data.database_size_gb} GB`);
                } else {
                    document.getElementById('databaseSize').textContent = 
                        `${data.total_emails?.toLocaleString() || 0} emails`;
                    console.log('Set database size to email count:', `${data.total_emails?.toLocaleString() || 0} emails`);
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
                } else {
                    console.log('Calling hideSyncDetails');
                    hideSyncDetails();
                }
                
                console.log(`Sync status loaded using: ${endpoint}`);
            } else {
                throw new Error('Invalid response format');
            }
        })
        .catch(error => {
            console.log(`Endpoint ${endpoint} failed: ${error.message}`);
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
            fetch('http://localhost:3002/api/db/email-count'),
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
    
    fetch('http://localhost:8000/api/v1/test/background-sync/start', {
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
    fetch('http://localhost:8000/api/v1/test/background-sync/stop', {
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
    console.log('🔍 Checking if sync is already running...');
    checkSyncStatusAndStart(type, params, startBtn, stopBtn, progress, monitoring);
}

function checkSyncStatusAndStart(type, params, startBtn, stopBtn, progress, monitoring, retryCount = 0) {
    console.log('🔍 Starting sync status check (attempt ' + (retryCount + 1) + '/3)...');
    fetch('http://localhost:3002/api/db/sync-monitoring')
        .then(response => response.json())
        .then(data => {
            console.log('🔍 Sync status check result (attempt ' + (retryCount + 1) + '):', data.sync_progress);
            if (data.sync_progress.is_active) {
                console.log('⚠️ Sync already running - switching to monitoring mode');
                addLogEntry('Sync Status', 'Sync already in progress - monitoring existing sync');
                showNotification('Sync already running - monitoring progress', 'info');
                
                // Update UI to show sync is running
                startBtn.disabled = true;
                stopBtn.disabled = false;
                progress.style.display = 'block';
                monitoring.style.display = 'block';
                
                // Start monitoring the existing sync
                startRealTimeMonitoring();
                console.log('🛑 Returning early - not starting new sync');
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
            console.log('✅ No active sync found after ' + (retryCount + 1) + ' checks - starting new sync');
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
            console.log('⚠️ Proceeding with sync start after ' + (retryCount + 1) + ' failed attempts');
            startNewSyncOperation(type, params, startBtn, stopBtn, progress, monitoring);
        });
}

function startNewSyncOperation(type, params, startBtn, stopBtn, progress, monitoring) {
    console.log('🚀 startNewSyncOperation called with type:', type, 'params:', params);
    
    // Final safety check - make sure no sync is running before we start
    console.log('🔒 Final safety check - verifying no active sync...');
    fetch('http://localhost:3002/api/db/sync-monitoring')
        .then(response => response.json())
        .then(data => {
            if (data.sync_progress.is_active) {
                console.log('🚨 SAFETY CHECK FAILED: Active sync detected during startNewSyncOperation!');
                console.log('🔄 Switching to monitoring mode instead of starting new sync');
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
            console.log('✅ Safety check passed - no active sync, proceeding with new sync');
            proceedWithNewSync(type, params, startBtn, stopBtn, progress, monitoring);
        })
        .catch(error => {
            console.error('Error in final safety check:', error);
            console.log('⚠️ Proceeding with sync start despite safety check error');
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
    const endpoint = 'http://localhost:3002/api/sync/start';
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
    console.log('🚀 Starting sync operation with:', requestBody);
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
                console.log('⚠️ Sync already in progress (409) - parsing response...');
                return response.json().then(data => {
                    console.log('📋 409 response data:', data);
                    throw new Error(`Sync already in progress: ${data.error}`);
                }).catch(parseError => {
                    console.error('❌ Error parsing 409 response:', parseError);
                    throw new Error(`Sync already in progress: Unable to parse response`);
                });
            }
            console.log('❌ HTTP error - status:', response.status);
            // Try to get error details from response
            return response.text().then(text => {
                console.log('❌ Error response body:', text);
                throw new Error(`HTTP error! status: ${response.status} - ${text}`);
            }).catch(textError => {
                console.error('❌ Error reading error response:', textError);
                throw new Error(`HTTP error! status: ${response.status}`);
            });
        }
        console.log('✅ Sync start successful - parsing response...');
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            emailsSynced = data.result?.emails_synced || 0;
            addLogEntry('Sync Completed', `Successfully synced ${emailsSynced} emails`);
            completeSyncOperation(emailsSynced, totalEmails, syncStartTime);
        } else {
            throw new Error(data.error || 'Sync failed');
        }
    })
    .catch(error => {
        console.error('Sync error:', error);
        errorCount++;
        
        // Check if this is a "sync already in progress" error
        if (error.message.includes('Sync already in progress')) {
            console.log('🔄 Sync already running - switching to monitoring mode');
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
    fetch('http://localhost:3002/api/sync/stop', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Stop sync response:', data);
        if (data.status === 'success') {
            if (data.sync_stopped) {
                addLogEntry('Backend Sync Stopped', 'Sync process stopped on server');
                showNotification('Sync stopped successfully', 'success');
            } else {
                addLogEntry('No Active Sync', 'No active sync found to stop');
                showNotification('No active sync to stop', 'info');
            }
        } else {
            addLogEntry('Stop Error', data.error || 'Unknown error stopping sync');
            showNotification('Error stopping sync: ' + (data.error || 'Unknown error'), 'error');
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
        fetch('http://localhost:8000/api/v1/test/sync/reset-last-sync', {
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
    console.log('🔄 Starting real-time sync monitoring...');
    
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
    
    fetch('http://localhost:8000/api/v1/test/sync/status')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'syncing') {
                // Update progress from backend data
                const progress = data.progress || {};
                
                window.currentSync.emailsSynced = progress.emails_synced || window.currentSync.emailsSynced;
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

// Analytics functionality
function loadAnalytics() {
    console.log('🔄 ANALYTICS FUNCTION CALLED - START');
    console.log('🔄 Loading analytics...');
    
    // Show loading state
    const analyticsPage = document.getElementById('analyticsPage');
    console.log('📊 Analytics page element in loadAnalytics:', analyticsPage);
    
    if (!analyticsPage) {
        console.error('❌ Analytics page element not found!');
        return;
    }
    
    console.log('✅ Setting loading HTML...');
    analyticsPage.innerHTML = `
        <h2>Email Analytics</h2>
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p>Loading comprehensive analytics data...</p>
        </div>
    `;
    console.log('✅ Loading HTML set, starting API calls...');
    
    // Use Node.js endpoints for real-time data
    Promise.all([
        // Get current email count and analytics data
        fetch('http://localhost:3002/api/db/email-count'),
        fetch('http://localhost:3002/api/db/sync-status'),
        fetch('http://localhost:3002/api/db/emails?page=1&page_size=1000')
    ])
    .then(responses => {
        console.log('🌐 All API responses received:', responses.map(r => r.status));
        return Promise.all(responses.map(r => r.json()));
    })
    .then(([emailCount, syncStatus, emailsData]) => {
        console.log('📊 Analytics data loaded successfully!');
        console.log('📈 Email count data:', emailCount);
        console.log('📊 Sync status data:', syncStatus);
        console.log('📧 Emails data:', emailsData);
        console.log('🎯 Calling displayDashboardAnalytics...');
        displayDashboardAnalytics(emailCount, syncStatus, emailsData);
        console.log('✅ Analytics display complete!');
    })
    .catch(error => {
        console.error('❌ Error loading analytics:', error);
        console.error('❌ Error details:', error.message, error.stack);
        analyticsPage.innerHTML = `
            <h2>Email Analytics</h2>
            <div class="error-message">
                <p>Error loading analytics data: ${error.message}</p>
                <button onclick="loadAnalytics()" class="btn btn-primary">Retry</button>
            </div>
        `;
    });
}

function displayDashboardAnalytics(emailCount, syncStatus, emailsData) {
    console.log('🎨 displayDashboardAnalytics called');
    const analyticsPage = document.getElementById('analyticsPage');
    console.log('📊 Analytics page element in display function:', analyticsPage);
    
    if (!analyticsPage) {
        console.error('❌ Analytics page element not found in display function!');
        return;
    }
    
    // Format numbers with commas
    const formatNumber = (num) => num.toLocaleString();
    const formatPercentage = (num) => num.toFixed(1) + '%';
    
    console.log('🔢 Formatting functions ready');
    
    // Calculate storage estimate (rough estimate: 35KB per email)
    const storageEstimateMB = Math.round((emailCount.total_emails * 35) / 1024);
    const storageEstimateGB = (storageEstimateMB / 1024).toFixed(2);
    
    // Calculate unread emails from the emails data
    const unreadEmails = emailsData.emails ? emailsData.emails.filter(email => !email.is_read).length : 0;
    
    // Get last sync time from sync status
    const lastSyncTime = syncStatus.last_sync_time || 'Never';
    
    // Get top sender from emails data
    const topSender = emailsData.emails && emailsData.emails.length > 0 ? emailsData.emails[0].sender : 'Unknown';
    
    analyticsPage.innerHTML = `
        <h2>Email Dashboard</h2>
        
        <!-- Key Metrics Dashboard -->
        <div class="analytics-metrics">
            <div class="metric-card">
                <h3>Total Emails</h3>
                <div class="metric-value">${formatNumber(emailCount.total_emails)}</div>
                <div class="metric-subtitle">All time</div>
            </div>
            <div class="metric-card">
                <h3>Unread Emails</h3>
                <div class="metric-value">${formatNumber(unreadEmails)}</div>
                <div class="metric-subtitle">${formatPercentage((unreadEmails / emailCount.total_emails) * 100)} of total</div>
            </div>
            <div class="metric-card">
                <h3>Last Sync</h3>
                <div class="metric-value">${lastSyncTime}</div>
                <div class="metric-subtitle">Last synchronization</div>
            </div>
            <div class="metric-card">
                <h3>Storage Used</h3>
                <div class="metric-value">${storageEstimateGB} GB</div>
                <div class="metric-subtitle">Estimated storage</div>
            </div>
        </div>
        
        <!-- Sync Status Section -->
        <div class="sync-status-section">
            <h3>Sync Status</h3>
            <div class="status-grid">
                <div class="status-card">
                    <h4>Current Status</h4>
                    <div class="status-value ${syncStatus.status === 'syncing' ? 'active' : 'inactive'}">${syncStatus.status || 'Unknown'}</div>
                </div>
                <div class="status-card">
                    <h4>Database Size</h4>
                    <div class="status-value">${syncStatus.database_size_pretty || 'Unknown'}</div>
                </div>
                <div class="status-card">
                    <h4>Latest Email</h4>
                    <div class="status-value">${syncStatus.latest_email_date ? new Date(syncStatus.latest_email_date).toLocaleDateString() : 'Unknown'}</div>
                </div>
            </div>
        </div>
        
        <!-- Recent Emails Section -->
        <div class="recent-emails-section">
            <h3>Recent Emails</h3>
            <div class="emails-list">
                ${emailsData.emails && emailsData.emails.length > 0 ? 
                    emailsData.emails.slice(0, 10).map(email => `
                        <div class="email-item ${email.is_read ? 'read' : 'unread'}">
                            <div class="email-sender">${email.sender || 'Unknown'}</div>
                            <div class="email-subject">${email.subject || 'No Subject'}</div>
                            <div class="email-date">${email.date_received ? new Date(email.date_received).toLocaleDateString() : 'Unknown'}</div>
                        </div>
                    `).join('') : 
                    '<div class="no-emails">No emails found</div>'
                }
            </div>
        </div>
    `;
    
    console.log('🎨 Analytics HTML generated, setting innerHTML...');
    console.log('📏 HTML length:', analyticsPage.innerHTML.length);
    console.log('✅ Analytics display function complete!');
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
        console.error('❌ Error during app initialization:', error);
        console.error('❌ Error stack:', error.stack);
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
    console.log('🧪 TEST ANALYTICS CALLED');
    console.log('🧪 loadAnalytics function type:', typeof loadAnalytics);
    console.log('🧪 Calling loadAnalytics...');
    loadAnalytics();
};

console.log('🎯 SCRIPT LOADING COMPLETED - testAnalytics should be available');

// Function to clear all sync intervals and force refresh
window.clearAllSyncIntervals = function() {
    console.log('🧹 Clearing all sync intervals...');
    if (syncStatusInterval) {
        clearInterval(syncStatusInterval);
        syncStatusInterval = null;
        console.log('✅ Cleared syncStatusInterval');
    }
    if (window.progressUpdateInterval) {
        clearInterval(window.progressUpdateInterval);
        window.progressUpdateInterval = null;
        console.log('✅ Cleared progressUpdateInterval');
    }
    if (window.monitoringInterval) {
        clearInterval(window.monitoringInterval);
        window.monitoringInterval = null;
        console.log('✅ Cleared monitoringInterval');
    }
};

// Function to force refresh sync status
window.forceRefreshSyncStatus = function() {
    console.log('🔄 Force refreshing sync status...');
    clearAllSyncIntervals();
    loadSyncMonitoring();
};

// Global error handler
window.addEventListener('error', (event) => {
    console.error('❌ Global JavaScript Error:', event.error);
    console.error('❌ Error message:', event.message);
    console.error('❌ Error filename:', event.filename);
    console.error('❌ Error line:', event.lineno);
    console.error('❌ Error column:', event.colno);
});

// Unhandled promise rejection handler
window.addEventListener('unhandledrejection', (event) => {
    console.error('❌ Unhandled Promise Rejection:', event.reason);
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
    detailsHTML += '<h4>🔄 Current Sync Process</h4>';
    
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
        let emailIcon = '📧';
        if (emailCount > 1000) emailIcon = '📬';
        if (emailCount > 10000) emailIcon = '📭';
        
        detailsHTML += `<p><strong>Emails synced:</strong> <span class="live-count" style="color: #28a745; font-size: 1.1em;">${emailCount.toLocaleString()}</span> ${emailIcon}</p>`;
    }
    
    // Speed with trend indicator
    if (syncDetails.emails_per_minute !== undefined) {
        const speed = syncDetails.emails_per_minute;
        let speedIcon = '📈';
        if (speed > 100) speedIcon = '🚀';
        else if (speed > 50) speedIcon = '⚡';
        else if (speed > 10) speedIcon = '📈';
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
            
            detailsHTML += `<p><strong>Estimated completion:</strong> ${estimatedTime.toLocaleString()} (${timeLeftText}) ⏰</p>`;
        } else {
            detailsHTML += `<p><strong>Estimated completion:</strong> ${estimatedTime.toLocaleString()} (completing soon) ⏰</p>`;
        }
    }
    
    // Current batch
    if (syncDetails.current_batch !== undefined && syncDetails.total_batches !== undefined) {
        detailsHTML += `<p><strong>Batch:</strong> ${syncDetails.current_batch} of ${syncDetails.total_batches} 📦</p>`;
    }
    
    // Note
    if (syncDetails.note) {
        detailsHTML += `<p><strong>Activity:</strong> ${syncDetails.note} 📊</p>`;
    }
    
    // Auto-refresh indicator
    detailsHTML += '<p class="refresh-indicator">🔄 Auto-refreshing every 5 seconds</p>';
    
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

// Load real-time sync monitoring data
function loadSyncMonitoring() {
    console.log('🔄 loadSyncMonitoring called - fetching latest sync status...');
    fetch('http://localhost:3002/api/db/sync-monitoring')
        .then(response => response.json())
        .then(data => {
            console.log('📊 Sync monitoring data received:', data);
            
            const syncProgress = data.sync_progress;
            const dbStats = data.database_stats;
            const activityStats = data.activity_stats;
            
            // Update sync status and button states
            const startSyncBtn = document.getElementById('startSync');
            const stopSyncBtn = document.getElementById('stopSync');
            
            console.log('🔍 Sync progress check - is_active:', syncProgress.is_active, 'status:', syncProgress.status);
            
            if (syncProgress.is_active) {
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
            document.getElementById('totalSynced').textContent = `${dbStats.total_emails.toLocaleString()} emails`;
            document.getElementById('databaseSize').textContent = `${dbStats.database_size_gb} GB`;
            
            // Update last sync time
            if (dbStats.latest_email_date) {
                const latestEmail = new Date(dbStats.latest_email_date);
                document.getElementById('lastSyncTime').textContent = latestEmail.toLocaleString();
            } else {
                document.getElementById('lastSyncTime').textContent = 'Recent';
            }
            
        })
        .catch(error => {
            console.error('Error loading sync monitoring:', error);
            // Fall back to regular sync status
            loadSyncStatus();
        });
}

// Start periodic sync monitoring refresh (every 5 seconds)
function startSyncMonitoringRefresh() {
    // Clear any existing interval
    if (syncStatusInterval) {
        clearInterval(syncStatusInterval);
    }
    
    // Refresh every 5 seconds for real-time updates
    syncStatusInterval = setInterval(() => {
        loadSyncMonitoring();
    }, 5000);
}
