"""Middleware configuration for FastAPI application."""
from starlette.middleware.cors import CORSMiddleware
from config.settings import env

origins = env.allowed_origins.split(",")


def setup_middleware(app):
    """Configure application middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_headers=["*"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        max_age=3600,
    )
