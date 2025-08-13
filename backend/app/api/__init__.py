from .emails import router as emails_router
from .search import router as search_router
from .sync import router as sync_router
from .analytics import router as analytics_router
from .labels import router as labels_router
from .test import router as test_router

__all__ = [
    "emails_router",
    "search_router", 
    "sync_router",
    "analytics_router",
    "labels_router",
    "test_router"
]
