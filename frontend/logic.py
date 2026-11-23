"""Frontend calculations: risk score, collisions, suggested start dates, .ics export.

Same rules as the Analytics branch, so the demo works without a server.

A deadline is a dictionary like this one:
    {"course": "PHY1030", "title": "Midterm", "kind": "exam", "due": date(2026, 10, 15), "weight": 30}
"""
from datetime import date, datetime, timedelta

# ----- Scoring rules -----

# Points for each type of deadline
POINTS = {"exam": 4, "project": 3, "quiz": 1.5, "assignment": 1}

# The 4 possible types (for the dropdown in the Review table)
KINDS = ["exam", "project", "quiz", "assignment"]

# How many days ahead to start, by type
LEAD_DAYS = {"exam": 10, "project": 14, "quiz": 3, "assignment": 4}


# ----- 1. Clean the data -----

def to_date(value):
    """Turns a value into a date. Returns None if it is not a valid date."""
    if value is None or value != value:  # empty cell (value != value is True for NaN and NaT)
        return None
    if isinstance(value, datetime):  # date + time: keep only the date
        return value.date()
    if isinstance(value, date):
        return value
    try:
        # Take the first 10 characters: "2026-10-15"
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def clean(deadlines):
    """Keeps only deadlines with a valid date, and fixes the other fields."""
    result = []
    for d in deadlines:
        due = to_date(d.get("due"))
        if due is None:
            continue  # no date: we cannot place it in a week

        kind = str(d.get("kind") or "").lower()
        if kind not in POINTS:
            kind = "assignment"  # unknown type: treat it as an assignment

        weight = d.get("weight")
        if weight is None or weight != weight:  # weight != weight is True for an empty cell (NaN)
            weight = 0

        result.append({
            "course": str(d.get("course") or "?"),
            "title": str(d.get("title") or "Untitled"),
            "kind": kind,
            "due": due,
            "weight": float(weight),
        })
    return result


# ----- 2. The score -----

def item_points(d):
    """Points for one deadline: based on its type, x1.5 if it is worth 20% or more."""
    points = POINTS[d["kind"]]
    if d["weight"] >= 20:
        points = points * 1.5
    return points


def level_for(score):
    """Colour of a week based on its score."""
    if score < 4:
        return "green"
    elif score < 8:
        return "yellow"
    elif score < 12:
        return "orange"
    else:
        return "red"


def week_start(day):
    """Monday of the week. weekday() is 0 on Monday, 6 on Sunday."""
    return day - timedelta(days=day.weekday())


def weekly_scores(deadlines):
    """One result per week, from the first to the last (empty weeks included)."""
    items = clean(deadlines)
    if len(items) == 0:
        return []

    # Find the first and last dates
    first_day = items[0]["due"]
    last_day = items[0]["due"]
    for d in items:
        if d["due"] < first_day:
            first_day = d["due"]
        if d["due"] > last_day:
            last_day = d["due"]

    weeks = []
    monday = week_start(first_day)
    while monday <= week_start(last_day):
        # The deadlines in this week
        week_items = []
        score = 0
        for d in items:
            if week_start(d["due"]) == monday:
                week_items.append(d)
                score = score + item_points(d)

        weeks.append({
            "week_start": monday,
            "score": round(score, 1),
            "level": level_for(score),
            "is_final_boss": score >= 12,
            "items": week_items,
        })
        monday = monday + timedelta(days=7)  # next week
    return weeks


# ----- 3. Collisions -----

def is_heavy(d):
    """A "heavy" deadline: exam, project, or worth 20% or more."""
    return d["kind"] == "exam" or d["kind"] == "project" or d["weight"] >= 20


def find_collisions(deadlines):
    """Finds times when there are 3 or more heavy deadlines within 4 days.

    Step 1: keep only heavy deadlines, sorted by date.
    Step 2: for each one, look at what falls within the next 4 days (itself included).
    Step 3: if there are 3 or more, it is a collision.
            We skip the deadlines already counted in the previous collision,
            so the same thing is not reported twice.
    """
    # Step 1
    heavy = []
    for d in clean(deadlines):
        if is_heavy(d):
            heavy.append(d)
    heavy.sort(key=lambda d: d["due"])

    collisions = []
    i = 0
    while i < len(heavy):
        # Step 2: 4-day window = day D and the 3 following days
        window_end = heavy[i]["due"] + timedelta(days=3)
        group = []
        for d in heavy[i:]:
            if d["due"] <= window_end:
                group.append(d)

        # Step 3
        if len(group) >= 3:
            collisions.append({"start": group[0]["due"], "end": group[-1]["due"], "items": group})
            i = i + len(group)  # move past this group
        else:
            i = i + 1
    return collisions


# ----- 4. Suggested start dates -----

def suggested_starts(deadlines):
    """For each deadline in an orange or red week: when to start working on it."""
    # The Mondays of the risky weeks
    risky_mondays = []
    for w in weekly_scores(deadlines):
        if w["level"] == "orange" or w["level"] == "red":
            risky_mondays.append(w["week_start"])

    rows = []
    for d in clean(deadlines):
        if week_start(d["due"]) in risky_mondays:
            days = LEAD_DAYS[d["kind"]]
            if d["weight"] >= 20:
                days = days + 3  # important item: 3 more days
            rows.append({
                "course": d["course"],
                "title": d["title"],
                "due": d["due"],
                "start_by": d["due"] - timedelta(days=days),
                "days_ahead": days,
            })
    rows.sort(key=lambda r: r["due"])
    return rows


# ----- 5. .ics export (calendar) -----

def to_ics(deadlines):
    """Builds the text of an .ics file: one all-day event per deadline,
    with a reminder the day before. Standard format read by Google Calendar, Outlook, etc."""
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Semester Sentinel//EN"]

    number = 0
    for d in clean(deadlines):
        number = number + 1
        day = d["due"].strftime("%Y%m%d")
        next_day = (d["due"] + timedelta(days=1)).strftime("%Y%m%d")
        # In an .ics file, commas and semicolons need a \ in front of them
        title = (d["course"] + " - " + d["title"]).replace(",", "\\,").replace(";", "\\;")

        lines.append("BEGIN:VEVENT")
        lines.append("UID:" + day + "-" + str(number) + "@semester-sentinel")
        lines.append("DTSTAMP:" + now)
        lines.append("DTSTART;VALUE=DATE:" + day)
        lines.append("DTEND;VALUE=DATE:" + next_day)
        lines.append("SUMMARY:" + title)
        lines.append("DESCRIPTION:Type " + d["kind"] + " - weight " + str(d["weight"]) + "%")
        lines.append("BEGIN:VALARM")       # the reminder
        lines.append("ACTION:DISPLAY")
        lines.append("DESCRIPTION:" + title)
        lines.append("TRIGGER:-P1D")        # 1 day before
        lines.append("END:VALARM")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"  # the .ics format requires \r\n between lines
