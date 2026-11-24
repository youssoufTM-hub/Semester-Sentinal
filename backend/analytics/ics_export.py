import uuid
from datetime import datetime, timedelta, timezone
from icalendar import Calendar, Event
from .models import Deadline


def build_ics(deadlines: list[Deadline]) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Semester Sentinel//EN")
    cal.add("version", "2.0")
    for d in deadlines:
        ev = Event()
        key = f"{d.course}|{d.title}|{d.due.isoformat()}"
        ev.add("uid", f"{uuid.uuid5(uuid.NAMESPACE_DNS, key)}@semester-sentinel")
        ev.add("dtstamp", datetime.now(timezone.utc))
        ev.add("summary", f"{d.course}: {d.title}")
        ev.add("dtstart", d.due)                       
        # a date, so the event is all-day
        ev.add("dtend", d.due + timedelta(days=1))
        ev.add("description", f"{d.kind}, {d.weight}% of grade")
        cal.add_component(ev)
    return cal.to_ical()