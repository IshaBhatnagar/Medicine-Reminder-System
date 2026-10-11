"""Plain data classes used by Module M2 (matches the Experiment 6 class diagram)."""
from dataclasses import dataclass, asdict
from datetime import date
from typing import Any, Dict, List, Optional

# Roles (set by Module M1 at login)
ROLE_PATIENT = "patient"
ROLE_CAREGIVER = "caregiver"
ROLE_DOCTOR = "doctor"
ROLE_ADMIN = "admin"

# Dose statuses stored in dose_logs
DOSE_TAKEN = "taken"
DOSE_SKIPPED = "skipped"
DOSE_MISSED = "missed"
DOSE_PENDING = "pending"  # calendar only - nothing stored yet
VALID_DOSE_STATUSES = (DOSE_TAKEN, DOSE_SKIPPED, DOSE_MISSED)


@dataclass(frozen=True)
class UserContext:
    """Who is calling. Produced by Module M1 after login."""
    user_id: int
    role: str


@dataclass(frozen=True)
class Medicine:
    medicine_id: int
    patient_id: int
    name: str
    dosage: str
    frequency: str
    duration_days: int
    prescribing_doctor: Optional[str]
    created_at: str


@dataclass(frozen=True)
class Schedule:
    schedule_id: int
    medicine_id: int
    dose_times: List[str]
    start_date: date
    end_date: date


@dataclass(frozen=True)
class DoseLog:
    log_id: int
    schedule_id: int
    dose_date: date
    dose_time: str
    status: str
    logged_at: str


@dataclass(frozen=True)
class DueDose:
    """One scheduled dose that has no log yet. Used by Module M3 for reminders."""
    schedule_id: int
    medicine_id: int
    patient_id: int
    medicine_name: str
    dosage: str
    dose_date: date
    dose_time: str


@dataclass(frozen=True)
class CalendarEntry:
    """One line of the calendar / list view."""
    schedule_id: int
    medicine_id: int
    medicine_name: str
    dosage: str
    dose_time: str
    status: str  # taken | skipped | missed | pending


@dataclass(frozen=True)
class TimeConflict:
    schedule_id: int
    medicine_name: str
    dose_time: str


def to_dict(obj: Any) -> Dict[str, Any]:
    """Dataclass -> plain dict with ISO dates (handy for JSON / printing)."""
    data = asdict(obj)
    for key, value in data.items():
        if isinstance(value, date):
            data[key] = value.isoformat()
    return data
