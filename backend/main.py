from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import asyncio
from datetime import datetime, timezone
from app.models.database import engine, Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import background services
from app.services.background_sync_service import background_sync_service
from app.services.token_refresh_service import token_refresh_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of background services."""
    # --- Startup ---
    try:
        logger.info("Starting application startup tasks...")

        if not background_sync_service.is_running:
            logger.info("Auto-starting background sync service...")
            asyncio.create_task(background_sync_service.start_background_sync(sync_interval_minutes=5))
            logger.info("Background sync service started (5-minute interval)")
        else:
            logger.info("Background sync service already running")

        if not token_refresh_service.is_running:
            logger.info("Auto-starting token refresh service...")
            asyncio.create_task(token_refresh_service.start_token_refresh_service())
            logger.info("Token refresh service started (checks every hour)")
        else:
            logger.info("Token refresh service already running")

    except Exception as e:
        logger.error(f"Error during startup: {e}")

    yield

    # --- Shutdown ---
    try:
        logger.info("Starting application shutdown tasks...")

        if background_sync_service.is_running:
            logger.info("Stopping background sync service...")
            background_sync_service.stop_background_sync()
            logger.info("Background sync service stopped")

        if token_refresh_service.is_running:
            logger.info("Stopping token refresh service...")
            token_refresh_service.stop_token_refresh_service()
            logger.info("Token refresh service stopped")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Gmail Backup & Management System",
    description="A comprehensive application for backing up and managing Gmail emails with AI-powered analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost",
        "http://127.0.0.1",
        "https://localhost",
        "https://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables (will be replaced by Alembic migrations)
Base.metadata.create_all(bind=engine)

# Include routers (API-key protected; /health is exempt below)
from app.api import emails_router, search_router, sync_router, analytics_router, labels_router, test_router, oauth_router
from app.services.auth_service import verify_api_key

_auth = [Depends(verify_api_key)]

app.include_router(emails_router, prefix="/api/v1/emails", tags=["emails"], dependencies=_auth)
app.include_router(search_router, prefix="/api/v1/search", tags=["search"], dependencies=_auth)
app.include_router(sync_router, prefix="/api/v1/sync", tags=["sync"], dependencies=_auth)
app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["analytics"], dependencies=_auth)
app.include_router(labels_router, prefix="/api/v1/labels", tags=["labels"], dependencies=_auth)
app.include_router(test_router, prefix="/api/v1/test", tags=["test"], dependencies=_auth)

# OAuth router — no API key auth (Google's redirect can't send custom headers)
app.include_router(oauth_router, prefix="/api/v1/auth/google", tags=["oauth"])


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Gmail Backup & Management System API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "emails": "/api/v1/emails",
            "search": "/api/v1/search",
            "sync": "/api/v1/sync",
            "analytics": "/api/v1/analytics",
            "test": "/api/v1/test"
        }
    }


# Enhanced health check endpoint
@app.get("/health")
async def health_check():
    try:
        from app.models.database import SessionLocal
        from app.models.user import User
        from sqlalchemy import text

        db = SessionLocal()
        warnings = []

        try:
            db.execute(text("SELECT 1"))
            db_status = "healthy"

            users = db.query(User).all()
            for user in users:
                if user.gmail_token_expiry:
                    time_until_expiry = user.gmail_token_expiry - datetime.now(timezone.utc)
                    if time_until_expiry.total_seconds() < 0:
                        warnings.append(f"Token expired for {user.email}")
                    elif time_until_expiry.total_seconds() < 86400:
                        warnings.append(f"Token expires soon for {user.email} (in {time_until_expiry.total_seconds()/3600:.1f} hours)")

                if user.last_sync:
                    time_since_sync = datetime.now(timezone.utc) - user.last_sync
                    if time_since_sync.total_seconds() > 3600:
                        warnings.append(f"No successful sync for {user.email} in {time_since_sync.total_seconds()/3600:.1f} hours")
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = "unhealthy"
        finally:
            db.close()

        sync_errors = background_sync_service.sync_stats.get("errors", 0)
        if sync_errors > 10:
            warnings.append(f"High error count in background sync: {sync_errors} errors")

        background_sync_status = {
            "is_running": background_sync_service.is_running,
            "sync_in_progress": background_sync_service.sync_in_progress,
            "last_sync_time": background_sync_service.last_sync_time.isoformat() if background_sync_service.last_sync_time else None,
            "total_syncs": background_sync_service.sync_stats.get("total_syncs", 0),
            "total_emails_synced": background_sync_service.sync_stats.get("total_emails_synced", 0),
            "errors": sync_errors
        }

        overall_status = "healthy"
        if db_status != "healthy":
            overall_status = "unhealthy"
        elif not background_sync_service.is_running:
            overall_status = "degraded"
        elif warnings:
            overall_status = "degraded"

        response = {
            "status": overall_status,
            "service": "Gmail Backup & Management System",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "database": db_status,
                "background_sync": "running" if background_sync_service.is_running else "stopped"
            },
            "background_sync": background_sync_status
        }

        if warnings:
            response["warnings"] = warnings

        return response

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "service": "Gmail Backup & Management System",
            "version": "1.0.0",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
