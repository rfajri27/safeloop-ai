"""Example User Pydantic schemas for request/response validation.

This module defines:
- ExampleUserCreate: Request schema for creating users
- ExampleUserUpdate: Request schema for updating users
- ExampleUserResponse: Response schema for user data
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class ExampleUserCreate(BaseModel):
    """Schema for creating a new user."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User's display name"
    )
    email: EmailStr = Field(
        ...,
        description="User's email address"
    )
    role: str = Field(
        default="user",
        description="User role: user, admin, superadmin"
    )


class ExampleUserUpdate(BaseModel):
    """Schema for updating an existing user."""
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="User's display name"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="User's email address"
    )
    role: Optional[str] = Field(
        None,
        description="User role: user, admin, superadmin"
    )
    status: Optional[int] = Field(
        None,
        ge=0,
        le=1,
        description="Account status: 1=active, 0=inactive"
    )


class ExampleUserResponse(BaseModel):
    """Schema for user response data."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="User UUID")
    name: str = Field(..., description="User's display name")
    email: str = Field(..., description="User's email address")
    role: str = Field(..., description="User role")
    status: int = Field(..., description="Account status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(
        None, description="Last update timestamp")


class ExampleUserListResponse(BaseModel):
    """Schema for paginated user list response."""
    items: list[ExampleUserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum items per page")
