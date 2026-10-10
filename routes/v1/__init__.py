"""Version 1 API routes.

This module aggregates all v1 domain routers.
"""

from fastapi import APIRouter
from routes.v1.example_user_routes import router as example_user_router

router = APIRouter()

# Include the example user routes
router.include_router(example_user_router, prefix="/users", tags=["users"])