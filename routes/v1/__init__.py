"""Version 1 API routes.

This module aggregates all v1 domain routers. Each domain router declares
its own prefix, so routers are included here without one.
"""

from fastapi import APIRouter
from routes.v1.system_routes import router as system_router
from routes.v1.auth_routes import router as auth_router
from routes.v1.user_routes import router as user_router
from routes.v1.unit_routes import router as unit_router
from routes.v1.replay_routes import router as replay_router
from routes.v1.asset_routes import router as asset_router
from routes.v1.hazop_routes import router as hazop_router
from routes.v1.risk_rule_set_routes import router as risk_rule_set_router
from routes.v1.red_team_routes import router as red_team_router
from routes.v1.chat_routes import router as chat_router
from routes.v1.document_routes import router as document_router
from routes.v1.approval_routes import router as approval_router
from routes.v1.audit_routes import router as audit_router
from routes.v1.eval_routes import router as eval_router
from routes.v1.admin_routes import router as admin_router

router = APIRouter()

# SafeLoop MVP routes (spec Section 6)
router.include_router(system_router)
router.include_router(auth_router)
router.include_router(user_router)
router.include_router(unit_router)
router.include_router(replay_router)
router.include_router(asset_router)
router.include_router(hazop_router)
router.include_router(risk_rule_set_router)
router.include_router(red_team_router)
router.include_router(chat_router)
router.include_router(document_router)
router.include_router(approval_router)
router.include_router(audit_router)
router.include_router(eval_router)
router.include_router(admin_router)
