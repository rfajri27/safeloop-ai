"""JWT authentication and role-based access dependencies.

Usage:
    @router.get("/assets")
    async def get_assets(user: CurrentUser = Depends(get_current_user)): ...

    @router.post("/approval-items/{item_id}/decision")
    async def decide(user: CurrentUser = Depends(require_role(UserRole.PROCESS_SAFETY_ENGINEER))): ...
"""
import uuid
from typing import Optional
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.schemas.auth_schema import CurrentUser
from app.schemas.common_schema import UserRole
from app.utils.jwt_utils import JwtUtils
from app.utils.response import response_error

bearer_scheme = HTTPBearer(auto_error=False)


# =============================================================================
# ROLE GROUPS (API conventions, Section 4)
# =============================================================================

ALL_ROLES = tuple(UserRole)
CHAT_ROLES = tuple(r for r in UserRole if r != UserRole.AUDITOR)
REPLAY_ROLES = (
    UserRole.RELIABILITY_ENGINEER,
    UserRole.PROCESS_SAFETY_ENGINEER,
    UserRole.ADMIN,
)
RED_TEAM_ROLES = (UserRole.PROCESS_SAFETY_ENGINEER, UserRole.ADMIN)
APPROVAL_ROLES = (UserRole.PROCESS_SAFETY_ENGINEER,)
EVAL_ROLES = (UserRole.ADMIN, UserRole.PROCESS_SAFETY_ENGINEER)
ADMIN_ROLES = (UserRole.ADMIN,)


# =============================================================================
# DEPENDENCIES
# =============================================================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> CurrentUser:
    """Decode the bearer token into a CurrentUser, or raise 401."""
    if credentials is None:
        response_error("Not authenticated", code=401)

    payload = JwtUtils.decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub") or not payload.get("role"):
        response_error("Not authenticated", code=401)
    try:
        uuid.UUID(str(payload["sub"]))
        return CurrentUser(id=payload["sub"], role=payload["role"], name=payload.get("name", ""))
    except ValueError:  # bad UUID, or unknown role (pydantic ValidationError)
        response_error("Not authenticated", code=401)


def require_role(*roles: UserRole, action: str = "perform this action"):
    """Dependency factory: allow only the given roles, else raise 403."""
    async def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            response_error(f"Role {user.role.value} cannot {action}", code=403)
        return user
    return checker
