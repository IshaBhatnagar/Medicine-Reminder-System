"""Pure helper that expands a schedule into individual doses."""
from datetime import date, timedelta
from typing import Iterator, Tuple

from .models import Schedule


def iter_doses(schedule: Schedule, range_start: date, range_end: date) -> Iterator[Tuple[date, str]]:
    """Yield (date, 'HH:MM') for every dose of the schedule inside the date range."""
    first = max(schedule.start_date, range_start)
    last = min(schedule.end_date, range_end)
    day = first
    while day <= last:
        for slot in schedule.dose_times:
            yield day, slot
        day += timedelta(days=1)
