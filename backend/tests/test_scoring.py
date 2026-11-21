from datetime import date
from analytics.models import Deadline
from analytics.scoring import score_weeks


def test_readme_example_scores_11_5_orange():
    deadlines = [
        Deadline("PHY", "Midterm", "exam", date(2026, 11, 12), 30),
        Deadline("CSCI", "Project", "project", date(2026, 11, 13), 25),
        Deadline("MATH", "Assignment 4", "assignment", date(2026, 11, 10), 5),
    ]
    weeks = score_weeks(deadlines)
    assert len(weeks) == 1
    assert weeks[0].score == 11.5
    assert weeks[0].level == "orange"
    assert weeks[0].is_final_boss is False