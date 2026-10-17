"""Asset API routes.

Endpoints:
    GET /assets                      - Asset list with health index and band
    GET /assets/{tag}                - Asset detail, standby, last band change, linked rows
    GET /assets/{tag}/trend          - Sensor series for one tag and the alert line
    GET /assets/{tag}/health-history - Health index per replay hour
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import get_current_user
from app.services.asset_service import AssetService
from app.schemas.common_schema import DEFAULT_LIMIT, MAX_LIMIT, HealthBand

router = APIRouter(
    prefix="/assets",
    tags=["Assets"],
    dependencies=[Depends(get_current_user)],
)


def get_asset_service(db: AsyncSession = Depends(get_db)) -> AssetService:
    """Dependency: Create AssetService."""
    return AssetService(db)


@router.get("", summary="List assets with health")
async def get_assets(
    node: Optional[str] = Query(None, description="Process node code, e.g. N1"),
    band: Optional[HealthBand] = Query(None, description="Health band filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum records to return"),
    service: AssetService = Depends(get_asset_service)
):
    """List assets with health index and band."""
    return await service.get_assets(node, band, skip, limit)


@router.get("/{tag}", summary="Get an asset by tag")
async def get_asset(
    tag: str,
    service: AssetService = Depends(get_asset_service)
):
    """Asset detail, standby, last band change, sensor tags and linked HAZOP rows."""
    return await service.get_asset(tag)


@router.get("/{tag}/trend", summary="Get a sensor trend for an asset")
async def get_trend(
    tag: str,
    sensor_tag: Optional[str] = Query(None, description="Sensor tag, e.g. P101_DE_VIB_RMS"),
    from_hour: int = Query(0, ge=0, description="First replay hour"),
    to_hour: Optional[int] = Query(None, ge=0, description="Last replay hour"),
    service: AssetService = Depends(get_asset_service)
):
    """Sensor series (max 500 points) with the alert line and a text summary."""
    return await service.get_trend(tag, sensor_tag, from_hour, to_hour)


@router.get("/{tag}/health-history", summary="Get health index history for an asset")
async def get_health_history(
    tag: str,
    service: AssetService = Depends(get_asset_service)
):
    """Health index and band per replay hour for the current run."""
    return await service.get_health_history(tag)
