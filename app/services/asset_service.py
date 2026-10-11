"""Asset service for the Asset health screen.

Endpoints served:
    GET /assets                     - Asset list with health index and band
    GET /assets/{tag}               - Asset detail, standby, last band change, linked rows
    GET /assets/{tag}/trend         - Sensor series for one tag and the alert line
    GET /assets/{tag}/health-history - Health index per replay hour

Reads: assets, asset_links, sensor_tags, sensor_readings, health_assessments
"""
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.response import response_error


class AssetService:
    """
    Service for assets and their health.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize AssetService with a DB session."""
        self.db = db

    async def get_assets(
        self,
        node: Optional[str] = None,
        band: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> JSONResponse:
        """List assets with their latest health index and band."""
        return response_error("Not implemented", code=501)

    async def get_asset(self, tag: str) -> JSONResponse:
        """Return asset detail; 404 for an unknown tag."""
        return response_error("Not implemented", code=501)

    async def get_trend(
        self,
        tag: str,
        sensor_tag: Optional[str],
        from_hour: int,
        to_hour: Optional[int]
    ) -> JSONResponse:
        """Return at most 500 points (downsampled) plus a code-template summary."""
        return response_error("Not implemented", code=501)

    async def get_health_history(self, tag: str) -> JSONResponse:
        """Return [{replay_hour, health_index, band}] for the current run."""
        return response_error("Not implemented", code=501)
