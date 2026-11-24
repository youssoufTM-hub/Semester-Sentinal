from datetime import date, datetime
from pydantic import BaseModel


class Deadline(BaseModel):
    course: str = ""
    title: str
    type: str
    due: date
    weight_pct: float = 0


def deadline_from_event(ev: dict) -> Deadline:
    return Deadline(
        course=ev.get("course", ""),
        title=ev.get("title", ""),
        type=ev.get("type", "assignment").lower(),
        due=datetime.fromisoformat(ev["start"]).date(),
        weight_pct=ev.get("weight_pct") or 0,
    )