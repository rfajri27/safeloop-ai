"""FastAPI application kernel with lifespan and exception handlers."""
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi_limiter import FastAPILimiter
from fastapi.exceptions import RequestValidationError
from config.ratelimit import custom_callback, service_name_identifier
from config.databases.redis import redis_client
from config.settings import env
from app.utils.response import (
    CustomHTTPException,
    custom_http_exception_handler,
    request_validation_exception_handler,
    generic_exception_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup/shutdown events."""
    await FastAPILimiter.init(
        redis_client,
        prefix=f"{env.app_name}-limiter",
        identifier=service_name_identifier,
        http_callback=custom_callback,
    )
    yield
    await FastAPILimiter.close()


if env.app_env.lower() == "development":
    app = FastAPI(lifespan=lifespan)
else:
    app = FastAPI(
        lifespan=lifespan,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )

# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

# Custom HTTP exception (for response_error and middleware)
app.add_exception_handler(CustomHTTPException, custom_http_exception_handler)

# Pydantic validation errors (422)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

# Catch-all for unexpected exceptions (500 errors)
app.add_exception_handler(Exception, generic_exception_handler)
