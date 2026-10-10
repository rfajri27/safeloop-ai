"""Unified response handling for consistent API responses.

Response Format:
    {
        "status": 1 | 0,
        "data": {...} | null,
        "metadata": {...} | null,
        "message": "..."
    }

HTTP Status Codes (Simplified):
    200 - All success
    400 - All client errors (validation, not found, conflict, auth)
    500 - Server error

Usage:
    return response_success(user, msg="User created")
    return response_error("User not found")
"""
from typing import Any, Optional
from fastapi import Request
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError


# =============================================================================
# CUSTOM EXCEPTION (used internally by response_error)
# =============================================================================

class CustomHTTPException(FastAPIHTTPException):
    """Custom HTTP exception with data payload for consistent error responses."""
    def __init__(self, status_code: int, message: str, data: Any = None):
        super().__init__(status_code=status_code, detail=message)
        self.data = data


# =============================================================================
# RESPONSE FUNCTIONS
# =============================================================================

def response_success(
    data: Any = None,
    metadata: Optional[dict] = None,
    msg: str = "Success",
    code: int = 200
) -> JSONResponse:
    """
    Return a standardized success JSON response.
    
    Args:
        data: Response payload
        metadata: Optional metadata (pagination, etc.)
        msg: Success message
        code: HTTP status code (default: 200)
    
    Examples:
        return response_success(user, msg="User retrieved")
        return response_success(user, msg="User created")
    """
    return JSONResponse(
        status_code=code,
        content=jsonable_encoder({
            "status": 1,
            "data": data,
            "metadata": metadata,
            "message": msg
        })
    )


def response_error(msg: str, code: int = 400, data: Any = None) -> None:
    """
    Raise a standardized error response (caught by global handler).
    
    Args:
        msg: Error message (REQUIRED)
        code: HTTP status code (default: 400)
              - 400: All client errors (validation, not found, auth, conflict)
              - 401: Unauthorized
              - 403: Forbidden
              - 404: Not Found
              - 500: Server error
        data: Optional error details
    
    Examples:
        return response_error("User not found")
        return response_error("Email already exists")
        return response_error("Database error", code=500)
    """
    raise CustomHTTPException(status_code=code, message=msg, data=data)


# =============================================================================
# EXCEPTION HANDLERS (register in kernel.py)
# =============================================================================

def custom_http_exception_handler(request: Request, exc: CustomHTTPException) -> JSONResponse:
    """
    Global handler for CustomHTTPException - ensures consistent format.
    
    Register in kernel.py:
        app.add_exception_handler(CustomHTTPException, custom_http_exception_handler)
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({
            "status": 0,
            "data": exc.data,
            "metadata": None,
            "message": exc.detail
        })
    )


def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle Pydantic validation errors with consistent format.
    
    Register in kernel.py:
        app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    """
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=400,
        content=jsonable_encoder({
            "status": 0,
            "data": errors,
            "metadata": None,
            "message": "Validation failed"
        })
    )


def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions (500 errors).
    
    Register in kernel.py:
        app.add_exception_handler(Exception, generic_exception_handler)
    """
    return JSONResponse(
        status_code=500,
        content=jsonable_encoder({
            "status": 0,
            "data": None,
            "metadata": None,
            "message": "Internal server error"
        })
    )