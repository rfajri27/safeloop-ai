"""Repository for SensorReading entity (append-only)."""
from typing import Optional, Sequence
from sqlalchemy import select
from app.repositories.base import AppendOnlyRepository
from app.models.sensor_reading_model import SensorReading
from app.models.sensor_tag_model import SensorTag


class SensorReadingRepository(AppendOnlyRepository[SensorReading]):
    """Repository for SensorReading queries. Composite key: no get_by_id."""
    model_class = SensorReading

    async def get_series(
        self,
        replay_run_id: str,
        tag_id: str,
        from_hour: int = 0,
        to_hour: Optional[int] = None
    ) -> Sequence[SensorReading]:
        """Readings of one tag in a run, ordered by replay hour (trend chart)."""
        query = select(SensorReading).where(
            SensorReading.replay_run_id == replay_run_id,
            SensorReading.tag_id == tag_id,
            SensorReading.replay_hour >= from_hour,
        )
        if to_hour is not None:
            query = query.where(SensorReading.replay_hour <= to_hour)
        result = await self.session.execute(query.order_by(SensorReading.replay_hour))
        return result.scalars().all()

    async def get_reading(self, replay_run_id: str, tag_id: str, replay_hour: int) -> Optional[SensorReading]:
        """One reading (the trigger value in the "Why it moved" panel)."""
        result = await self.session.execute(
            select(SensorReading).where(
                SensorReading.replay_run_id == replay_run_id,
                SensorReading.tag_id == tag_id,
                SensorReading.replay_hour == replay_hour,
            )
        )
        return result.scalar_one_or_none()

    async def get_hour_values(self, replay_run_id: str, replay_hour: int) -> Sequence[tuple[str, float]]:
        """(sensor tag, value) for every tag at one replay hour (`replay_tick` event)."""
        result = await self.session.execute(
            select(SensorTag.tag, SensorReading.value)
            .join(SensorTag, SensorTag.id == SensorReading.tag_id)
            .where(
                SensorReading.replay_run_id == replay_run_id,
                SensorReading.replay_hour == replay_hour,
            )
        )
        return result.tuples().all()
