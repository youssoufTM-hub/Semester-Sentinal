from fastapi import APIRouter, HTTPException
from schemas import EventInput, HeatmapBucket
from calculate_weekly_heatmap import calculate_weekly_heatmap

router = APIRouter(prefix="/api/heatmap", tags=["heatmap"])

@router.post("/api/heatmap/calculate", response_model=list[HeatmapBucket])
def generate_heatmap(events: list[EventInput]):
    try:
        raw_events = [event.model_dump() for event in events]
        return calculate_weekly_heatmap(raw_events)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {err}")

