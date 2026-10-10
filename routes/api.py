"""Main API router that aggregates all version routers.

This is the entry point for all API routes. Each version has its own
router module that aggregates domain-specific routes.
"""
from fastapi import APIRouter
from routes.v1 import router as v1_router

router = APIRouter()
router.include_router(v1_router, prefix="/v1")