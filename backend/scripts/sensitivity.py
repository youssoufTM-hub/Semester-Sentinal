import json
from pathlib import Path

from analytics import calculate_weekly_heatmap as hm

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "deadlines.json"


def colours(events):
    #keep the week and colour so comparisons are easier later
    return {b["week_start"]: b["level"] for b in hm.calculate_weekly_heatmap(events)}


def with_scale(events, factor, only=None):
    #copy so we can put everything back afterwards
    original = dict(hm.WEIGHTS)
    try:
        for kind in hm.WEIGHTS:
            #either change all weights or only the one we're testing
            if only is None or kind == only:
                hm.WEIGHTS[kind] = original[kind] * factor
        return colours(events)
    finally:
        hm.WEIGHTS.update(original)


if __name__ == "__main__":
    events = json.loads(SAMPLES.read_text())
    base = colours(events)
    print(f"{len(events)} deadlines, {len(base)} weeks")

    for factor in (0.8, 1.2):
        after = with_scale(events, factor)
        changed = sum(base[w] != after[w] for w in base)
        #how many weeks ended up with a different colour
        print(f"All points x{factor}: {changed} of {len(base)} weeks change colour")
        for kind in ("exam", "project", "quiz", "assignment"):
            after = with_scale(events, factor, only=kind)
            changed = sum(base[w] != after[w] for w in base)
            print(f"  {kind} x{factor}: {changed} weeks change colour")