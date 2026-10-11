"""User Pydantic schemas for request/response validation.

This module defines:
- UserCreate: Request schema for creating users
- UserUpdate: Request schema for updating users (partial)
- UserResponse: Response schema for user data
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.schemas.common_schema import UserRole


class UserCreate(BaseModel):
    """Schema for POST /users."""
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Display name, also the demo login handle (e.g. Rina)"
    )
    email: Optional[EmailStr] = Field(None, description="Unique email address")
    role: UserRole = Field(..., description="User role")
    is_demo: bool = Field(default=True, description="Seeded demo user")


class UserUpdate(BaseModel):
    """Schema for PATCH /users/{user_id}. Only provided fields change."""
    display_name: Optional[str] = Field(None, min_length=1, max_length=120, description="Display name")
    email: Optional[EmailStr] = Field(None, description="Unique email address")
    role: Optional[UserRole] = Field(None, description="User role")
    is_demo: Optional[bool] = Field(None, description="Seeded demo user")


class UserResponse(BaseModel):
    """Schema for user response data."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="User UUID")
    display_name: str = Field(..., description="Display name")
    email: Optional[str] = Field(None, description="Email address")
    role: UserRole = Field(..., description="User role")
    is_demo: bool = Field(..., description="Seeded demo user")
    created_at: datetime = Field(..., description="Creation timestamp")
