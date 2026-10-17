"""Auth Pydantic schemas for demo login and the current user."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from app.schemas.common_schema import UserRole


class DemoLoginRequest(BaseModel):
    """Schema for POST /auth/demo-login."""
    user: Literal["rina", "dimas", "agus", "auditor", "admin"] = Field(
        ...,
        description="Seeded demo user handle (case-insensitive)"
    )

    @field_validator("user", mode="before")
    @classmethod
    def normalize_handle(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class CurrentUser(BaseModel):
    """Authenticated user decoded from the JWT claims (sub, role, name)."""
    id: str = Field(..., description="User UUID (JWT `sub`)")
    role: UserRole = Field(..., description="User role")
    name: str = Field(..., description="Display name")
