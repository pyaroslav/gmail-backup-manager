# Performance Improvements for Gmail Backup Manager

## Current Performance Assessment

### ✅ Good Performance Practices
- PostgreSQL with connection pooling
- Batch processing for email sync
- Optimized database indexes
- Background sync service
- Redis for caching

### 🔧 Recommended Performance Enhancements

## 1. Database Performance

### Current Issues
- Large email table without partitioning
- No query optimization for large datasets
- Missing composite indexes
- No database connection pooling optimization

### Improvements

#### Database Partitioning
```sql
-- Partition emails table by date
CREATE TABLE emails (
    id SERIAL,
    gmail_id VARCHAR(255),
    subject VARCHAR(1000),
    sender VARCHAR(500),
    date_received TIMESTAMP WITH TIME ZONE,
    -- other columns...
) PARTITION BY RANGE (date_received);

-- Create monthly partitions
CREATE TABLE emails_2024_01 PARTITION OF emails
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE emails_2024_02 PARTITION OF emails
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
```

#### Optimized Indexes
```sql
-- Composite indexes for common queries
CREATE INDEX CONCURRENTLY idx_emails_sender_date_read 
ON emails(sender, date_received DESC, is_read);

CREATE INDEX CONCURRENTLY idx_emails_subject_sender 
ON emails USING gin(to_tsvector('english', subject), sender);

CREATE INDEX CONCURRENTLY idx_emails_labels_gin 
ON emails USING gin(labels);

-- Partial indexes for better performance
CREATE INDEX CONCURRENTLY idx_emails_unread 
ON emails(date_received DESC) WHERE is_read = false;

CREATE INDEX CONCURRENTLY idx_emails_starred 
ON emails(date_received DESC) WHERE is_starred = true;
```

#### Connection Pool Optimization
```python
# backend/app/models/database.py
from sqlalchemy.pool import QueuePool

# Optimize connection pool for high concurrency
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=50,  # Increased for sync operations
    max_overflow=100,  # Increased for peak load
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections every hour
    pool_timeout=30,
    echo=False,
    connect_args={
        "application_name": "gmail_backup_manager",
        "options": "-c timezone=utc -c statement_timeout=600000 -c work_mem=256MB -c shared_buffers=1GB"
    }
)
```

## 2. Caching Strategy

### Current Issues
- No Redis caching implementation
- Database queries repeated frequently
- No cache invalidation strategy

### Improvements

#### Redis Caching Implementation
```python
# backend/app/services/cache_service.py
import redis
import json
import pickle
from typing import Any, Optional
from datetime import timedelta

class CacheService:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.redis_binary = redis.from_url(redis_url, decode_responses=False)
    
    def get_email_count(self, user_id: int) -> Optional[int]:
        """Get cached email count"""
        key = f"email_count:{user_id}"
        cached = self.redis.get(key)
        return int(cached) if cached else None
    
    def set_email_count(self, user_id: int, count: int, ttl: int = 300):
        """Cache email count for 5 minutes"""
        key = f"email_count:{user_id}"
        self.redis.setex(key, ttl, count)
    
    def get_recent_emails(self, user_id: int, limit: int = 10) -> Optional[list]:
        """Get cached recent emails"""
        key = f"recent_emails:{user_id}:{limit}"
        cached = self.redis.get(key)
        return json.loads(cached) if cached else None
    
    def set_recent_emails(self, user_id: int, emails: list, limit: int = 10, ttl: int = 60):
        """Cache recent emails for 1 minute"""
        key = f"recent_emails:{user_id}:{limit}"
        self.redis.setex(key, ttl, json.dumps(emails))
    
    def invalidate_user_cache(self, user_id: int):
        """Invalidate all cache for a user"""
        pattern = f"*:{user_id}:*"
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)
```

#### Cache Decorators
```python
# backend/app/utils/cache_decorators.py
from functools import wraps
from typing import Callable, Any
import hashlib
import json

def cache_result(ttl: int = 300, key_prefix: str = ""):
    """Cache decorator for function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_data = f"{key_prefix}:{func.__name__}:{args}:{kwargs}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = cache_service.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache_service.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
```

## 3. Search Performance

### Current Issues
- Basic ILIKE search
- No full-text search optimization
- No search result caching

### Improvements

#### Full-Text Search with PostgreSQL
```python
# backend/app/services/search_service.py
from sqlalchemy import text, func
from sqlalchemy.dialects.postgresql import TSVECTOR

class OptimizedSearchService:
    def __init__(self, db: Session):
        self.db = db
    
    def search_emails_fts(self, query: str, user_id: int, page: int = 1, page_size: int = 50):
        """Full-text search using PostgreSQL tsvector"""
        
        # Create search vector
        search_vector = func.to_tsvector('english', 
            func.coalesce(Email.subject, '') + ' ' + 
            func.coalesce(Email.body_plain, '') + ' ' + 
            func.coalesce(Email.sender, '')
        )
        
        # Build query
        search_query = func.plainto_tsquery('english', query)
        
        # Execute search with ranking
        results = self.db.query(
            Email,
            func.ts_rank(search_vector, search_query).label('rank')
        ).filter(
            search_vector.op('@@')(search_query)
        ).order_by(
            text('rank DESC'),
            Email.date_received.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        
        return results
```

#### Elasticsearch Integration
```python
# backend/app/services/elasticsearch_service.py
from elasticsearch import Elasticsearch
from typing import List, Dict, Any

class ElasticsearchService:
    def __init__(self, es_url: str):
        self.es = Elasticsearch([es_url])
    
    def index_email(self, email_data: Dict[str, Any]):
        """Index email in Elasticsearch"""
        doc = {
            'id': email_data['id'],
            'subject': email_data['subject'],
            'sender': email_data['sender'],
            'body': email_data['body_plain'],
            'date_received': email_data['date_received'],
            'labels': email_data['labels'],
            'is_read': email_data['is_read']
        }
        
        self.es.index(
            index='emails',
            id=email_data['id'],
            body=doc
        )
    
    def search_emails(self, query: str, page: int = 1, page_size: int = 50):
        """Search emails using Elasticsearch"""
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["subject^3", "sender^2", "body"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            },
            "highlight": {
                "fields": {
                    "subject": {},
                    "body": {"fragment_size": 150}
                }
            },
            "from": (page - 1) * page_size,
            "size": page_size,
            "sort": [{"date_received": {"order": "desc"}}]
        }
        
        response = self.es.search(index='emails', body=search_body)
        return response['hits']
```

## 4. Sync Performance

### Current Issues
- Sequential processing
- No parallel sync for multiple users
- Memory usage during large syncs

### Improvements

#### Parallel Processing
```python
# backend/app/services/sync_service.py
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import List, Dict

class ParallelSyncService:
    def __init__(self):
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        self.process_pool = ProcessPoolExecutor(max_workers=4)
    
    async def sync_multiple_users(self, users: List[User]) -> Dict[int, int]:
        """Sync multiple users in parallel"""
        tasks = []
        for user in users:
            task = asyncio.create_task(self.sync_user_emails(user))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        sync_results = {}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Sync failed for user {users[i].id}: {result}")
                sync_results[users[i].id] = 0
            else:
                sync_results[users[i].id] = result
        
        return sync_results
    
    async def sync_user_emails(self, user: User) -> int:
        """Sync emails for a single user with parallel processing"""
        loop = asyncio.get_event_loop()
        
        # Process email batches in parallel
        batches = self.create_email_batches(user)
        
        # Use thread pool for I/O operations
        tasks = []
        for batch in batches:
            task = loop.run_in_executor(
                self.thread_pool, 
                self.process_email_batch, 
                user, batch
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return sum(results)
```

#### Memory Optimization
```python
# backend/app/services/memory_optimized_sync.py
import gc
from typing import Iterator, Dict, Any

class MemoryOptimizedSync:
    def __init__(self):
        self.batch_size = 100
        self.max_memory_mb = 512
    
    def process_emails_in_stream(self, emails: Iterator[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """Process emails in a memory-efficient stream"""
        batch = []
        
        for email in emails:
            batch.append(email)
            
            if len(batch) >= self.batch_size:
                # Process batch
                for processed_email in self.process_batch(batch):
                    yield processed_email
                
                # Clear batch and force garbage collection
                batch.clear()
                gc.collect()
        
        # Process remaining emails
        if batch:
            for processed_email in self.process_batch(batch):
                yield processed_email
    
    def process_batch(self, batch: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """Process a batch of emails"""
        for email in batch:
            # Process email (AI analysis, etc.)
            processed_email = self.process_single_email(email)
            yield processed_email
```

## 5. Frontend Performance

### Current Issues
- Large JavaScript bundle
- No code splitting
- No lazy loading
- Direct database queries from frontend

### Improvements

#### Code Splitting and Lazy Loading
```javascript
// frontend/script.js
// Lazy load components
const Dashboard = () => import('./components/Dashboard.js');
const EmailList = () => import('./components/EmailList.js');
const Analytics = () => import('./components/Analytics.js');

// Implement virtual scrolling for large email lists
class VirtualScroller {
    constructor(container, itemHeight, totalItems) {
        this.container = container;
        this.itemHeight = itemHeight;
        this.totalItems = totalItems;
        this.visibleItems = Math.ceil(container.clientHeight / itemHeight);
        this.scrollTop = 0;
        this.startIndex = 0;
        this.endIndex = this.visibleItems;
        
        this.init();
    }
    
    init() {
        this.container.style.height = `${this.totalItems * this.itemHeight}px`;
        this.container.addEventListener('scroll', this.onScroll.bind(this));
        this.render();
    }
    
    onScroll() {
        this.scrollTop = this.container.scrollTop;
        this.startIndex = Math.floor(this.scrollTop / this.itemHeight);
        this.endIndex = Math.min(
            this.startIndex + this.visibleItems,
            this.totalItems
        );
        this.render();
    }
    
    render() {
        // Only render visible items
        const items = [];
        for (let i = this.startIndex; i < this.endIndex; i++) {
            items.push(this.createItem(i));
        }
        this.container.innerHTML = items.join('');
    }
}
```

#### Service Worker for Caching
```javascript
// frontend/sw.js
const CACHE_NAME = 'gmail-backup-v1';
const urlsToCache = [
    '/',
    '/styles.css',
    '/script.js',
    '/api/db/dashboard'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    return response;
                }
                return fetch(event.request);
            })
    );
});
```

## 6. API Performance

### Current Issues
- No response compression
- No API versioning
- No request/response optimization

### Improvements

#### Response Compression
```python
# backend/main.py
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Optimize JSON responses
from fastapi.responses import JSONResponse
import orjson

class OptimizedJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_SERIALIZE_NUMPY)
```

#### API Response Optimization
```python
# backend/app/api/emails.py
from fastapi import Query
from typing import Optional

@router.get("/")
async def get_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include"),
    sort_by: str = Query("date_received", regex="^(date_received|sender|subject)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """Get emails with optimized response"""
    
    # Parse fields to include
    include_fields = fields.split(',') if fields else ['id', 'subject', 'sender', 'date_received']
    
    # Build query with only required fields
    query = db.query(Email)
    for field in include_fields:
        if hasattr(Email, field):
            query = query.add_columns(getattr(Email, field))
    
    # Apply sorting
    sort_column = getattr(Email, sort_by)
    if sort_order == 'desc':
        sort_column = sort_column.desc()
    
    query = query.order_by(sort_column)
    
    # Apply pagination
    total = query.count()
    emails = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "emails": emails,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    }
```

## 7. Monitoring and Metrics

### Performance Monitoring
```python
# backend/app/utils/performance_monitor.py
import time
import psutil
from functools import wraps
from typing import Dict, Any

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
    
    def monitor_function(self, func_name: str = None):
        """Decorator to monitor function performance"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.time()
                    end_memory = psutil.Process().memory_info().rss
                    
                    duration = end_time - start_time
                    memory_used = end_memory - start_memory
                    
                    self.record_metric(
                        func_name or func.__name__,
                        duration,
                        memory_used
                    )
            return wrapper
        return decorator
    
    def record_metric(self, name: str, duration: float, memory_used: int):
        """Record performance metric"""
        if name not in self.metrics:
            self.metrics[name] = {
                'count': 0,
                'total_duration': 0,
                'total_memory': 0,
                'min_duration': float('inf'),
                'max_duration': 0
            }
        
        metric = self.metrics[name]
        metric['count'] += 1
        metric['total_duration'] += duration
        metric['total_memory'] += memory_used
        metric['min_duration'] = min(metric['min_duration'], duration)
        metric['max_duration'] = max(metric['max_duration'], duration)
```

## Implementation Priority

1. **High Priority**: Database indexing, caching, search optimization
2. **Medium Priority**: Parallel processing, memory optimization, API optimization
3. **Low Priority**: Frontend optimizations, monitoring, service workers

## Performance Testing

```bash
# Database performance testing
pgbench -h localhost -U gmail_user -d gmail_backup -c 10 -t 1000

# API performance testing
ab -n 1000 -c 10 http://localhost:8000/api/v1/emails

# Memory usage monitoring
docker stats gmail-backup-backend

# Load testing
locust -f load_test.py --host=http://localhost:8000
```
