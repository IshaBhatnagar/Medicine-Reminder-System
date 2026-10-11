"""Pure validation helpers - no database, no clock. Easy to unit test."""
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, List, Optional, Tuple

from .errors import ValidationError
from .models import TimeConflict

FREQUENCY_SLOTS = {"once daily": 1, "twice daily": 2, "thrice daily": 3}
DEFAULT_DOSE_TIMES = {
    "once daily": ["08:00"],
    "twice daily": ["08:00", "20:00"],
    "thrice daily": ["08:00", "14:00", "20:00"],
}
MAX_DURATION_DAYS = 365
MAX_NAME_LENGTH = 100

_DOSAGE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(mg|g|mcg|ml|tablets?|capsules?|drops?|units?)$", re.IGNORECASE)
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def validate_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("Medicine name is required.")
    cleaned = " ".join(name.split())
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValidationError(f"Medicine name must be at most {MAX_NAME_LENGTH} characters.")
    return cleaned


def validate_dosage(dosage: Any) -> str:
    """Accepts '500 mg', '500mg', '5 ml', '1 Tablet' ... and normalises to '500 mg'."""
    if not isinstance(dosage, str):
        raise ValidationError("Dosage is required, for example '500 mg' or '1 tablet'.")
    match = _DOSAGE_RE.match(dosage.strip())
    if not match:
        raise ValidationError("Dosage must look like '500 mg', '5 ml' or '1 tablet'.")
    if float(match.group(1)) <= 0:
        raise ValidationError("Dosage amount must be greater than zero.")
    return f"{match.group(1)} {match.group(2).lower()}"


def validate_frequency(frequency: Any) -> str:
    normalized = " ".join(str(frequency).lower().split())
    if normalized not in FREQUENCY_SLOTS:
        raise ValidationError("Frequency must be 'once daily', 'twice daily' or 'thrice daily'.")
    return normalized


def validate_duration(days: Any) -> int:
    if isinstance(days, bool) or not isinstance(days, int):
        raise ValidationError("Duration must be a whole number of days.")
    if not 1 <= days <= MAX_DURATION_DAYS:
        raise ValidationError(f"Duration must be between 1 and {MAX_DURATION_DAYS} days.")
    return days


def validate_prescribing_doctor(doctor: Any) -> Optional[str]:
    if doctor is None:
        return None
    if not isinstance(doctor, str):
        raise ValidationError("Prescribing doctor must be text.")
    cleaned = " ".join(doctor.split())
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValidationError("Prescribing doctor name is too long.")
    return cleaned or None


def validate_dose_times(times: Optional[Iterable[Any]], frequency: str) -> List[str]:
    """Check HH:MM format, no duplicates, and that the count matches the frequency.

    If times is None the frequency default (e.g. 08:00 / 20:00) is used.
    """
    if times is None:
        return list(DEFAULT_DOSE_TIMES[frequency])
    if isinstance(times, (str, bytes)):
        raise ValidationError("Dose times must be a list such as ['08:00', '20:00'].")
    cleaned: List[str] = []
    for item in times:
        if not isinstance(item, str) or not _TIME_RE.match(item.strip()):
            raise ValidationError(f"'{item}' is not a valid time. Use HH:MM (24-hour).")
        cleaned.append(item.strip())
    if len(set(cleaned)) != len(cleaned):
        raise ValidationError("Dose times must not repeat.")
    expected = FREQUENCY_SLOTS[frequency]
    if len(cleaned) != expected:
        raise ValidationError(f"'{frequency}' needs exactly {expected} dose time(s); got {len(cleaned)}.")
    return sorted(cleaned)


def validate_date(value: Any, field: str) -> date:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise ValidationError(f"{field} must be a date.")
    return value


def validate_date_range(start: date, end: date) -> None:
    validate_date(start, "start_date")
    validate_date(end, "end_date")
    if end < start:
        raise ValidationError("End date cannot be before the start date.")


def default_end_date(start: date, duration_days: int) -> date:
    """A 5-day course starting on the 12th ends on the 16th."""
    return start + timedelta(days=duration_days - 1)


def parse_time(value: str) -> time:
    if not isinstance(value, str) or not _TIME_RE.match(value.strip()):
        raise ValidationError(f"'{value}' is not a valid time. Use HH:MM (24-hour).")
    hour, minute = value.strip().split(":")
    return time(int(hour), int(minute))


def find_time_conflicts(
    dose_times: Iterable[str],
    start: date,
    end: date,
    existing: Iterable[Tuple[int, str, List[str], date, date]],
) -> List[TimeConflict]:
    """Return the time slots that are already used by another schedule.

    existing = (schedule_id, medicine_name, dose_times, start_date, end_date)
    A conflict needs BOTH overlapping dates and the same HH:MM.
    """
    conflicts: List[TimeConflict] = []
    for schedule_id, medicine_name, times, other_start, other_end in existing:
        if other_start <= end and start <= other_end:
            for slot in dose_times:
                if slot in times:
                    conflicts.append(TimeConflict(schedule_id, medicine_name, slot))
    return conflicts
