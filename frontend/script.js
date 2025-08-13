// Global state
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

// Navigation
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const page = item.dataset.page;
        showPage(page);
        
        // Update active state
        document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
        item.classList.add('active');
    });
});

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
            loadDashboard();
            break;
        case 'emails':
            console.log('Showing emails page');
            document.getElementById('emailInterface').style.display = 'flex';
            loadEmails();
            break;
        case 'search':
            console.log('Showing search page');
            document.getElementById('searchPage').style.display = 'block';
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
        const response = await fetch('http://localhost:8000/health');
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
        // First check if sync is in progress
        const syncStatus = await fetch('http://localhost:8000/api/v1/test/sync/status')
            .then(response => response.json())
            .catch(() => ({ status: 'unknown' }));
        
        // If sync is in progress, show a message and don't load emails
        if (syncStatus.status === 'syncing') {
            document.getElementById('emailList').innerHTML = `
                <div class="sync-in-progress-message">
                    <i class="fas fa-sync fa-spin"></i>
                    <h3>Sync in Progress</h3>
                    <p>Email synchronization is currently running. Please wait for it to complete before viewing emails.</p>
                    <button class="btn btn-primary" onclick="loadEmails()">Retry</button>
                </div>
            `;
            return;
        }
        
        // Show loading state
        document.getElementById('emailList').innerHTML = '<div class="loading">Loading emails...</div>';
        
        const response = await fetch(`http://localhost:8000/api/v1/test/emails/?page=${page}&page_size=25`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
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
        
    } catch (error) {
        console.error('Error loading emails:', error);
        document.getElementById('emailList').innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Error Loading Emails</h3>
                <p>${error.message}</p>
                <button class="btn btn-primary" onclick="loadEmails()">Retry</button>
            </div>
        `;
    }
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
        await fetch(`http://localhost:8000/api/v1/test/emails/${numericEmailId}/read`, { method: 'POST' });
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
        await fetch(`http://localhost:8000/api/v1/test/emails/${numericEmailId}/unread`, { method: 'POST' });
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
        await fetch(`http://localhost:8000/api/v1/test/emails/${numericEmailId}/star`, { method: 'POST' });
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
        await fetch(`http://localhost:8000/api/v1/test/emails/${numericEmailId}`, { method: 'DELETE' });
        
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
        loadEmails();
    }
});

document.getElementById('nextPage').addEventListener('click', () => {
    const totalPages = Math.ceil(totalEmails / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        loadEmails();
    }
});

// Sort handler
document.getElementById('sortBtn').addEventListener('click', () => {
    sortOrder = sortOrder === 'desc' ? 'asc' : 'desc';
    loadEmails();
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
    // Load dashboard statistics
    fetch('http://localhost:8000/api/v1/test/emails/?page=1&page_size=1')
        .then(response => response.json())
        .then(data => {
            // Fix: Use total_count instead of total
            document.getElementById('totalEmails').textContent = (data.total_count || 0).toLocaleString();
        })
        .catch(error => {
            console.error('Error loading dashboard:', error);
            document.getElementById('totalEmails').textContent = '0';
        });
    
    // Mock data for other stats
    document.getElementById('starredEmails').textContent = '1,234';
    document.getElementById('unreadEmails').textContent = '567';
    document.getElementById('lastSync').textContent = '2 minutes ago';
}

// Search functionality
function initializeSearch() {
    const searchBtn = document.getElementById('searchBtn');
    const searchInput = document.getElementById('searchInput');
    
    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performSearch();
        }
    });
}

function performSearch() {
    const searchTerm = document.getElementById('searchInput').value.trim();
    const searchFilter = document.getElementById('searchFilter').value;
    const dateFrom = document.getElementById('dateFrom').value;
    const dateTo = document.getElementById('dateTo').value;
    
    if (!searchTerm) {
        showSearchResults([]);
        return;
    }
    
    showLoading(true);
    
    // Use real API for search
    const searchUrl = `http://localhost:8000/api/v1/test/emails/?page=1&page_size=50&search=${encodeURIComponent(searchTerm)}`;
    
    fetch(searchUrl)
        .then(response => response.json())
        .then(data => {
            let results = data.emails || [];
            
            // Apply additional filters if specified
            if (searchFilter === 'subject') {
                results = results.filter(email => 
                    email.subject.toLowerCase().includes(searchTerm.toLowerCase())
                );
            } else if (searchFilter === 'sender') {
                results = results.filter(email => 
                    email.sender.toLowerCase().includes(searchTerm.toLowerCase())
                );
            }
            
            // Apply date filters if specified
            if (dateFrom) {
                const fromDate = new Date(dateFrom);
                results = results.filter(email => 
                    new Date(email.date_received) >= fromDate
                );
            }
            
            if (dateTo) {
                const toDate = new Date(dateTo);
                toDate.setHours(23, 59, 59); // End of day
                results = results.filter(email => 
                    new Date(email.date_received) <= toDate
                );
            }
            
            showSearchResults(results);
        })
        .catch(error => {
            console.error('Error performing search:', error);
            showSearchResults([]);
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

    // Load initial sync status
    loadSyncStatus();
    
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

function loadSyncStatus() {
    fetch('http://localhost:8000/api/v1/test/sync/status')
        .then(response => response.json())
        .then(data => {
            document.getElementById('syncStatus').textContent = 'Ready to sync';
            document.getElementById('lastSyncTime').textContent = data.last_sync ? 
                new Date(data.last_sync).toLocaleString() : 'Never';
            document.getElementById('totalSynced').textContent = 
                `${data.total_emails_in_database?.toLocaleString() || 0} emails`;
            document.getElementById('databaseSize').textContent = 
                `${data.total_emails_in_database?.toLocaleString() || 0} emails`;
        })
        .catch(error => {
            console.error('Error loading sync status:', error);
            document.getElementById('syncStatus').textContent = 'Error loading status';
            addLogEntry('Error', 'Failed to load sync status');
        });
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
    
    // Update UI
    startBtn.disabled = true;
    stopBtn.disabled = false;
    progress.style.display = 'block';
    monitoring.style.display = 'block';
    
    // Initialize progress tracking
    const syncStartTime = new Date();
    let emailsSynced = 0;
    let totalEmails = params.max_emails || 1000;
    let errorCount = 0;
    
    // Update progress details
    document.getElementById('syncStartTime').textContent = syncStartTime.toLocaleTimeString();
    document.getElementById('syncElapsedTime').textContent = '0:00';
    document.getElementById('syncEstimatedTime').textContent = 'Calculating...';
    
    // Determine API endpoint based on sync type
    let endpoint = 'http://localhost:8000/api/v1/test/sync/start';
    if (type === 'date-range') {
        endpoint = `http://localhost:8000/api/v1/test/sync/start-from-date?start_date=${params.start_date}&max_emails=${params.max_emails}`;
    } else if (type === 'full') {
        endpoint = `http://localhost:8000/api/v1/test/sync/start-full?max_emails=${params.max_emails}`;
    } else {
        endpoint = `http://localhost:8000/api/v1/test/sync/start?max_emails=${params.max_emails}`;
    }
    
    addLogEntry('Sync Started', `${type} sync initiated with ${params.max_emails} emails`);
    showNotification(`Starting ${type} sync...`, 'info');
    
    // Start the sync
    fetch(endpoint, {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            emailsSynced = data.result?.emails_synced || 0;
            completeSyncOperation(emailsSynced, totalEmails, syncStartTime);
        } else {
            throw new Error(data.error || 'Sync failed');
        }
    })
    .catch(error => {
        console.error('Sync error:', error);
        errorCount++;
        addLogEntry('Sync Error', error.message);
        showNotification('Sync failed: ' + error.message, 'error');
        completeSyncOperation(0, totalEmails, syncStartTime, true);
    });
    
    // Store sync state for stopping
    window.currentSync = {
        type,
        startTime: syncStartTime,
        totalEmails,
        emailsSynced: 0,
        errorCount: 0,
        isRunning: true
    };
}

function stopSync() {
    if (window.currentSync) {
        window.currentSync.isRunning = false;
    }
    
    const startBtn = document.getElementById('startSync');
    const stopBtn = document.getElementById('stopSync');
    const syncStatus = document.getElementById('syncStatus');
    
    startBtn.disabled = false;
    stopBtn.disabled = true;
    syncStatus.textContent = 'Sync stopped';
    
    addLogEntry('Sync Stopped', 'User stopped the sync process');
    showNotification('Sync stopped by user', 'info');
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

function addLogEntry(time, message) {
    const logEntries = document.getElementById('logEntries');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    
    const timestamp = new Date().toLocaleTimeString();
    entry.innerHTML = `
        <span class="log-time">${timestamp}</span>
        <span class="log-message">${message}</span>
    `;
    
    logEntries.appendChild(entry);
    logEntries.scrollTop = logEntries.scrollHeight;
    
    // Keep only last 100 entries
    while (logEntries.children.length > 100) {
        logEntries.removeChild(logEntries.firstChild);
    }
}

// Analytics functionality
function loadAnalytics() {
    // Analytics data is already in the HTML
    // In a real app, this would fetch data from the backend
    console.log('Analytics loaded');
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
    document.getElementById('themeToggle').addEventListener('click', () => {
        document.body.classList.toggle('dark-theme');
    });
    
    // Logout handler
    document.querySelector('.btn-logout').addEventListener('click', () => {
        if (confirm('Are you sure you want to sign out?')) {
            // Handle logout
            console.log('User logged out');
        }
    });
    
    // Search page close detail button
    const closeSearchDetailBtn = document.getElementById('closeSearchDetail');
    if (closeSearchDetailBtn) {
        closeSearchDetailBtn.addEventListener('click', closeSearchEmailDetail);
    }
    
    console.log('App initialization complete');
});

// Global functions for onclick handlers
window.toggleStar = toggleStar;
window.selectEmail = selectEmail;
window.selectSearchEmail = selectSearchEmail;
window.toggleReadStatus = toggleReadStatus;
window.deleteEmail = deleteEmail;
window.closeSearchEmailDetail = closeSearchEmailDetail;
