from fastapi import FastAPI, HTTPException
from schemas import EventInput, HeatmapBucket
from calculate_weekly_heatmap import calculate_weekly_heatmap

# I think this needs to be initialized in main.py,
# can use the router with FastAPI if need be but it's a few more steps.
app = FastAPI()


# .model_dump() is a BaseModel method that creates a dict of the class.
@app.post("/api/heatmap/calculate", response_model=list[HeatmapBucket])
def generate_heatmap(events: list[EventInput]):
    try:
        raw_events = [event.model_dump() for event in events]
        return calculate_weekly_heatmap(raw_events)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {err}")

"""
from models import Deadline, WeekScore

@app.post("/api/heatmap/calculate", response_model=list[WeekScore])
def generate_heatmap(events: list[dict]):
    try:
        return calculate_weekly_heatmap(events)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {err}")

Would need to syncronize the shape of the input dictionary with the calculate function.
"""
