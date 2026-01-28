from handlers.start import router as start_router
from handlers.edit import router as edit_router
from handlers.analyze import router as analyze_router
from handlers.fix import router as fix_router
from handlers.common import router as common_router

__all__ = [
    "start_router",
    "edit_router",
    "analyze_router",
    "fix_router",
    "common_router",
]
