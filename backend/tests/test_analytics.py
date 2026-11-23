from datetime import date
import pytest
from analytics.models import Deadline
from analytics.scoring import item_points, colour_for
from analytics.ics_export import build_ics


def dl(kind, day, pct: float = 0, month=11):
    return Deadline(course="X", title=f"{kind} {day}", kind=kind,
        due=date(2026, month, day), weight=pct)


def test_readme_example_sums_to_11_5():
    items = [dl("exam", 12, 30), dl("project", 13, 25), dl("assignment", 10, 5)]
    assert [item_points(d) for d in items] == [6.0, 4.5, 1.0]
    assert sum(item_points(d) for d in items) == 11.5
    assert colour_for(11.5) == "orange"


def test_heavy_boundary():
    assert item_points(dl("project", 1, 20)) == 4.5
    assert item_points(dl("project", 1, 19.9)) == 3


def test_colour_boundaries():
    assert [colour_for(s) for s in (3.99, 4, 7.99, 8, 11.99, 12)] == [
        "green", "yellow", "yellow", "orange", "orange", "red"]


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        item_points(dl("lab", 1))


def test_ics_has_one_event_per_deadline():
    data = build_ics([dl("exam", 10), dl("project", 11)])
    assert data.count(b"BEGIN:VEVENT") == 2