#!/usr/bin/env python3
"""
Background Sync Service Starter

This script starts the background email sync service that runs continuously
to keep the email database updated.
"""

import asyncio
import logging
import signal
import sys
import time
from datetime import datetime

# Add the backend directory to the path
sys.path.append('backend')

from app.services.background_sync_service import background_sync_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('background_sync.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True

async def main():
    """Main function to run the background sync service"""
    global shutdown_requested
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting Gmail Background Sync Service")
    logger.info("Press Ctrl+C to stop the service")
    
    try:
        # Start the background sync service
        sync_task = asyncio.create_task(
            background_sync_service.start_background_sync(sync_interval_minutes=5)
        )
        
        # Wait for shutdown signal
        while not shutdown_requested:
            await asyncio.sleep(1)
            
            # Print status every 5 minutes
            if int(time.time()) % 300 == 0:
                status = background_sync_service.get_sync_status()
                logger.info(f"Service Status: {status['is_running']}, "
                          f"Total Syncs: {status['stats']['total_syncs']}, "
                          f"Total Emails: {status['stats']['total_emails_synced']}")
        
        # Graceful shutdown
        logger.info("Stopping background sync service...")
        background_sync_service.stop_background_sync()
        
        # Wait for the sync task to complete
        try:
            await asyncio.wait_for(sync_task, timeout=30)
        except asyncio.TimeoutError:
            logger.warning("Sync task did not complete within 30 seconds")
        
        logger.info("Background sync service stopped successfully")
        
    except Exception as e:
        logger.error(f"Error in background sync service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
