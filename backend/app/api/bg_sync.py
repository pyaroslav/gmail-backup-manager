from fastapi import APIRouter
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bg_sync"])


@router.post("/background-sync/start")
async def start_background_sync(interval_minutes: int = 5):
    """Start the background sync service"""
    try:
        from ..services.background_sync_service import background_sync_service

        # Start the background sync in a separate task
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(background_sync_service.start_background_sync(interval_minutes))

        return {
            "message": f"Background sync started with {interval_minutes} minute interval",
            "status": "started",
            "interval_minutes": interval_minutes
        }
    except Exception as e:
        logger.error(f"Error starting background sync: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }

@router.post("/background-sync/stop")
async def stop_background_sync():
    """Stop the background sync service"""
    try:
        from ..services.background_sync_service import background_sync_service
        background_sync_service.stop_background_sync()

        return {
            "message": "Background sync stopped",
            "status": "stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping background sync: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }

@router.get("/background-sync/status")
async def get_background_sync_status():
    """Get background sync status"""
    try:
        from ..services.background_sync_service import background_sync_service

        sync_status = background_sync_service.get_sync_status()
        db_stats = background_sync_service.get_database_stats()

        return {
            "sync_status": sync_status,
            "database_stats": db_stats,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error getting background sync status: {e}")
        return {
            "error": str(e),
            "status": "failed"
        }
