from fastapi import APIRouter

from .emails import router as emails_router
from .search import router as search_router
from .sync import router as sync_router
from .analytics import router as analytics_router
from .labels import router as labels_router

# Compose the "test" router from the split modules
from .sync_control import router as _sync_control_router
from .bg_sync import router as _bg_sync_router
from .email_ops import router as _email_ops_router
from .db_direct import router as _db_direct_router
from .test_analytics import router as _test_analytics_router
from .search_ops import router as _search_ops_router

test_router = APIRouter()
test_router.include_router(_sync_control_router)
test_router.include_router(_bg_sync_router)
test_router.include_router(_email_ops_router)
test_router.include_router(_db_direct_router)
test_router.include_router(_test_analytics_router)
test_router.include_router(_search_ops_router)

__all__ = [
    "emails_router",
    "search_router",
    "sync_router",
    "analytics_router",
    "labels_router",
    "test_router",
]
