from pydantic import BaseModel # Used by Fastapi
from typing import Optional

class EventInput(BaseModel):
    title: str
    start: str
    end: Optional[str] = None
    type: str
    weight_pct: Optional[float] = None


class HeatmapBucket(BaseModel):
    week_start: str
    score: int
    colour: str
    is_final_boss_week: bool
    collision_count: int
    event_count: int
