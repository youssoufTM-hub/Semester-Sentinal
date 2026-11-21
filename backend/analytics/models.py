from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Deadline:
    course: str
    title: str
    
    kind: str     
    due: date
    weight: float   

@dataclass
class WeekScore:
    week_start: date    
    score: float
    level: str          
    is_final_boss: bool
    items: list[Deadline]