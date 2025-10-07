# Architecture Improvements for Gmail Backup Manager

## Current Architecture Assessment

### ✅ Good Architectural Practices
- Microservices-like separation (backend/frontend/database)
- Docker containerization
- API-first design
- Background processing
- Database abstraction layer

### 🔧 Recommended Architecture Enhancements

## 1. Service Architecture

### Current Issues
- Monolithic backend service
- Direct database access from frontend
- Tight coupling between services
- No service discovery
- No load balancing

### Improvements

#### Microservices Architecture
```yaml
# docker-compose.microservices.yml
version: '3.8'

services:
  # API Gateway
  api-gateway:
    build: ./gateway
    ports:
      - "8000:8000"
    environment:
      - AUTH_SERVICE_URL=http://auth-service:8001
      - EMAIL_SERVICE_URL=http://email-service:8002
      - SYNC_SERVICE_URL=http://sync-service:8003
      - ANALYTICS_SERVICE_URL=http://analytics-service:8004
    depends_on:
      - auth-service
      - email-service
      - sync-service
      - analytics-service

  # Authentication Service
  auth-service:
    build: ./services/auth
    environment:
      - DATABASE_URL=postgresql://auth_user:auth_pass@postgres:5432/auth_db
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  # Email Service
  email-service:
    build: ./services/email
    environment:
      - DATABASE_URL=postgresql://email_user:email_pass@postgres:5432/email_db
      - REDIS_URL=redis://redis:6379
      - ELASTICSEARCH_URL=http://elasticsearch:9200
    depends_on:
      - postgres
      - redis
      - elasticsearch

  # Sync Service
  sync-service:
    build: ./services/sync
    environment:
      - DATABASE_URL=postgresql://sync_user:sync_pass@postgres:5432/sync_db
      - REDIS_URL=redis://redis:6379
      - GMAIL_CLIENT_ID=${GMAIL_CLIENT_ID}
      - GMAIL_CLIENT_SECRET=${GMAIL_CLIENT_SECRET}
    depends_on:
      - postgres
      - redis

  # Analytics Service
  analytics-service:
    build: ./services/analytics
    environment:
      - DATABASE_URL=postgresql://analytics_user:analytics_pass@postgres:5432/analytics_db
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  # Service Discovery
  consul:
    image: consul:latest
    ports:
      - "8500:8500"
    command: agent -server -bootstrap-expect=1 -ui -client=0.0.0.0

  # Load Balancer
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - api-gateway
```

#### Service Communication
```python
# services/email/email_service.py
import httpx
from typing import Dict, Any

class EmailService:
    def __init__(self):
        self.auth_service_url = os.getenv("AUTH_SERVICE_URL")
        self.sync_service_url = os.getenv("SYNC_SERVICE_URL")
    
    async def get_emails(self, user_id: int, token: str) -> Dict[str, Any]:
        """Get emails with authentication check"""
        # Verify token with auth service
        async with httpx.AsyncClient() as client:
            auth_response = await client.post(
                f"{self.auth_service_url}/verify",
                json={"token": token}
            )
            
            if auth_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            # Get emails from database
            emails = await self._fetch_emails_from_db(user_id)
            return {"emails": emails}
    
    async def sync_emails(self, user_id: int, token: str) -> Dict[str, Any]:
        """Trigger email sync via sync service"""
        async with httpx.AsyncClient() as client:
            sync_response = await client.post(
                f"{self.sync_service_url}/sync",
                json={"user_id": user_id, "token": token}
            )
            return sync_response.json()
```

## 2. Event-Driven Architecture

### Current Issues
- Synchronous communication between services
- No event handling for real-time updates
- Tight coupling between sync and email services

### Improvements

#### Event Bus Implementation
```python
# services/events/event_bus.py
import asyncio
import json
from typing import Dict, List, Callable, Any
from datetime import datetime

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history: List[Dict] = []
    
    async def publish(self, event_type: str, data: Dict[str, Any]):
        """Publish event to all subscribers"""
        event = {
            "id": self._generate_event_id(),
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0"
        }
        
        self.event_history.append(event)
        
        # Notify subscribers
        if event_type in self.subscribers:
            tasks = []
            for callback in self.subscribers[event_type]:
                task = asyncio.create_task(callback(event))
                tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        return f"evt_{datetime.utcnow().timestamp()}_{len(self.event_history)}"

# Event types
EMAIL_SYNC_STARTED = "email.sync.started"
EMAIL_SYNC_COMPLETED = "email.sync.completed"
EMAIL_SYNC_FAILED = "email.sync.failed"
EMAIL_ANALYZED = "email.analyzed"
USER_AUTHENTICATED = "user.authenticated"
```

#### Event Handlers
```python
# services/email/event_handlers.py
from services.events.event_bus import EventBus, EMAIL_SYNC_COMPLETED, EMAIL_ANALYZED

class EmailEventHandlers:
    def __init__(self, event_bus: EventBus, email_service):
        self.event_bus = event_bus
        self.email_service = email_service
        self._register_handlers()
    
    def _register_handlers(self):
        """Register event handlers"""
        self.event_bus.subscribe(EMAIL_SYNC_COMPLETED, self.handle_sync_completed)
        self.event_bus.subscribe(EMAIL_ANALYZED, self.handle_email_analyzed)
    
    async def handle_sync_completed(self, event: Dict):
        """Handle email sync completion"""
        user_id = event["data"]["user_id"]
        email_count = event["data"]["email_count"]
        
        # Update user's email count
        await self.email_service.update_user_email_count(user_id, email_count)
        
        # Trigger analytics update
        await self.event_bus.publish("analytics.update_required", {
            "user_id": user_id,
            "sync_type": "completed"
        })
    
    async def handle_email_analyzed(self, event: Dict):
        """Handle email analysis completion"""
        email_id = event["data"]["email_id"]
        analysis_result = event["data"]["analysis"]
        
        # Update email with analysis results
        await self.email_service.update_email_analysis(email_id, analysis_result)
```

## 3. Database Architecture

### Current Issues
- Single database for all services
- No data partitioning strategy
- No read replicas
- No backup strategy

### Improvements

#### Database Sharding
```python
# services/database/shard_manager.py
from typing import Dict, Any
import hashlib

class DatabaseShardManager:
    def __init__(self, shard_configs: Dict[str, str]):
        self.shards = shard_configs
        self.shard_count = len(shard_configs)
    
    def get_shard_for_user(self, user_id: int) -> str:
        """Determine which shard to use for a user"""
        shard_index = user_id % self.shard_count
        return list(self.shards.keys())[shard_index]
    
    def get_shard_connection(self, user_id: int):
        """Get database connection for user's shard"""
        shard_name = self.get_shard_for_user(user_id)
        return self.shards[shard_name]
    
    def get_all_shards(self) -> Dict[str, Any]:
        """Get connections to all shards"""
        return self.shards

# Usage
shard_manager = DatabaseShardManager({
    "shard_0": "postgresql://user:pass@shard0:5432/gmail_backup_0",
    "shard_1": "postgresql://user:pass@shard1:5432/gmail_backup_1",
    "shard_2": "postgresql://user:pass@shard2:5432/gmail_backup_2",
    "shard_3": "postgresql://user:pass@shard3:5432/gmail_backup_3"
})
```

#### Read Replicas
```python
# services/database/replica_manager.py
from typing import List, Dict
import random

class ReplicaManager:
    def __init__(self, primary_url: str, replica_urls: List[str]):
        self.primary_url = primary_url
        self.replica_urls = replica_urls
        self.available_replicas = replica_urls.copy()
    
    def get_read_connection(self) -> str:
        """Get connection for read operations (load balanced)"""
        if self.available_replicas:
            return random.choice(self.available_replicas)
        return self.primary_url
    
    def get_write_connection(self) -> str:
        """Get connection for write operations (primary only)"""
        return self.primary_url
    
    def mark_replica_unavailable(self, replica_url: str):
        """Mark replica as unavailable"""
        if replica_url in self.available_replicas:
            self.available_replicas.remove(replica_url)
    
    def mark_replica_available(self, replica_url: str):
        """Mark replica as available"""
        if replica_url not in self.available_replicas:
            self.available_replicas.append(replica_url)

# Usage
replica_manager = ReplicaManager(
    primary_url="postgresql://user:pass@primary:5432/gmail_backup",
    replica_urls=[
        "postgresql://user:pass@replica1:5432/gmail_backup",
        "postgresql://user:pass@replica2:5432/gmail_backup",
        "postgresql://user:pass@replica3:5432/gmail_backup"
    ]
)
```

## 4. API Gateway

### Current Issues
- No centralized API management
- No rate limiting
- No authentication middleware
- No request/response transformation

### Improvements

#### API Gateway Implementation
```python
# gateway/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import jwt
from typing import Dict, Any

app = FastAPI(title="Gmail Backup API Gateway")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class APIGateway:
    def __init__(self):
        self.services = {
            "auth": os.getenv("AUTH_SERVICE_URL"),
            "email": os.getenv("EMAIL_SERVICE_URL"),
            "sync": os.getenv("SYNC_SERVICE_URL"),
            "analytics": os.getenv("ANALYTICS_SERVICE_URL")
        }
    
    async def authenticate_request(self, request: Request) -> Dict[str, Any]:
        """Authenticate incoming request"""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header")
        
        token = auth_header.split(" ")[1]
        
        # Verify token with auth service
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.services['auth']}/verify",
                json={"token": token}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            return response.json()
    
    async def route_request(self, request: Request, service: str, path: str):
        """Route request to appropriate service"""
        # Authenticate request
        user_data = await self.authenticate_request(request)
        
        # Get service URL
        service_url = self.services.get(service)
        if not service_url:
            raise HTTPException(status_code=404, detail="Service not found")
        
        # Forward request to service
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method,
                url=f"{service_url}{path}",
                headers=dict(request.headers),
                params=dict(request.query_params),
                json=await request.json() if request.method in ["POST", "PUT", "PATCH"] else None
            )
            
            return response

gateway = APIGateway()

# Route patterns
@app.api_route("/api/v1/emails/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def email_routes(request: Request, path: str):
    return await gateway.route_request(request, "email", f"/api/v1/emails/{path}")

@app.api_route("/api/v1/sync/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def sync_routes(request: Request, path: str):
    return await gateway.route_request(request, "sync", f"/api/v1/sync/{path}")

@app.api_route("/api/v1/analytics/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def analytics_routes(request: Request, path: str):
    return await gateway.route_request(request, "analytics", f"/api/v1/analytics/{path}")
```

## 5. Configuration Management

### Current Issues
- Hardcoded configuration
- No environment-specific configs
- No configuration validation
- No dynamic configuration updates

### Improvements

#### Configuration Service
```python
# services/config/config_service.py
import os
import yaml
from typing import Dict, Any, Optional
from pydantic import BaseSettings, validator

class ServiceConfig(BaseSettings):
    """Base configuration for all services"""
    service_name: str
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str
    redis_url: str
    
    @validator('environment')
    def validate_environment(cls, v):
        if v not in ['development', 'staging', 'production']:
            raise ValueError('Environment must be development, staging, or production')
        return v

class ConfigService:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        return {}
    
    def get_service_config(self, service_name: str) -> ServiceConfig:
        """Get configuration for specific service"""
        service_config = self.config.get(service_name, {})
        return ServiceConfig(**service_config)
    
    def get_database_config(self, service_name: str) -> Dict[str, str]:
        """Get database configuration for service"""
        service_config = self.get_service_config(service_name)
        return {
            "url": service_config.database_url,
            "pool_size": self.config.get("database", {}).get("pool_size", 20),
            "max_overflow": self.config.get("database", {}).get("max_overflow", 30)
        }
    
    def get_redis_config(self, service_name: str) -> Dict[str, str]:
        """Get Redis configuration for service"""
        service_config = self.get_service_config(service_name)
        return {
            "url": service_config.redis_url,
            "pool_size": self.config.get("redis", {}).get("pool_size", 10)
        }

# Configuration file example
config_example = """
# config/config.yaml
email_service:
  service_name: email_service
  environment: production
  log_level: INFO
  database_url: postgresql://user:pass@email-db:5432/email_db
  redis_url: redis://redis:6379/0

sync_service:
  service_name: sync_service
  environment: production
  log_level: INFO
  database_url: postgresql://user:pass@sync-db:5432/sync_db
  redis_url: redis://redis:6379/1

database:
  pool_size: 50
  max_overflow: 100
  pool_recycle: 3600

redis:
  pool_size: 20
  max_connections: 100
"""
```

## 6. Monitoring and Observability

### Current Issues
- Limited monitoring
- No distributed tracing
- No centralized logging
- No health checks

### Improvements

#### Distributed Tracing
```python
# services/monitoring/tracing.py
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def setup_tracing(service_name: str):
    """Setup distributed tracing"""
    # Create tracer provider
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)
    
    # Create Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name="jaeger",
        agent_port=6831,
    )
    
    # Add span processor
    span_processor = BatchSpanProcessor(jaeger_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    # Instrument HTTP client
    HTTPXClientInstrumentor().instrument()
    
    return tracer

# Usage in services
tracer = setup_tracing("email_service")

@tracer.start_as_current_span("get_emails")
async def get_emails(user_id: int):
    with tracer.start_as_current_span("database_query"):
        # Database query
        pass
```

#### Centralized Logging
```python
# services/monitoring/logging.py
import logging
import json
from datetime import datetime
from typing import Dict, Any
import structlog

def setup_structured_logging(service_name: str):
    """Setup structured logging"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    logger = structlog.get_logger()
    logger = logger.bind(service=service_name)
    
    return logger

# Usage
logger = setup_structured_logging("email_service")

def log_email_access(user_id: int, email_id: int, action: str):
    """Log email access with structured data"""
    logger.info(
        "email_accessed",
        user_id=user_id,
        email_id=email_id,
        action=action,
        timestamp=datetime.utcnow().isoformat()
    )
```

## 7. Deployment Architecture

### Current Issues
- Single deployment target
- No blue-green deployment
- No auto-scaling
- No health checks

### Improvements

#### Kubernetes Deployment
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: email-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: email-service
  template:
    metadata:
      labels:
        app: email-service
    spec:
      containers:
      - name: email-service
        image: gmail-backup/email-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: redis-secret
              key: url
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"

---
apiVersion: v1
kind: Service
metadata:
  name: email-service
spec:
  selector:
    app: email-service
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: email-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: email-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Implementation Priority

1. **High Priority**: API Gateway, Service Separation, Configuration Management
2. **Medium Priority**: Event-Driven Architecture, Database Sharding, Monitoring
3. **Low Priority**: Kubernetes Deployment, Advanced Tracing

## Migration Strategy

### Phase 1: Service Separation
1. Extract authentication logic into separate service
2. Create API gateway
3. Implement service-to-service communication

### Phase 2: Event-Driven Architecture
1. Implement event bus
2. Add event handlers
3. Migrate to asynchronous communication

### Phase 3: Database Optimization
1. Implement database sharding
2. Add read replicas
3. Optimize queries and indexes

### Phase 4: Monitoring and Deployment
1. Add distributed tracing
2. Implement centralized logging
3. Deploy to Kubernetes
