"""DoseService - dose logging, history and the calls Module M3 needs (UC9)."""
import sqlite3
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

from .access import AccessChecker, SqliteAccessChecker, require_manage, require_view
from .errors import NotFoundError, ValidationError
from .models import (DOSE_MISSED, DOSE_SKIPPED, DOSE_TAKEN, VALID_DOSE_STATUSES, DoseLog, DueDose, UserContext)
from .planning import iter_doses
from .repository import Repository
from .validators import parse_time, validate_date_range

EARLY_WINDOW_MINUTES = 60  # a dose may be marked at most 60 minutes before its time


class DoseService:
    def __init__(self, conn: sqlite3.Connection, access: Optional[AccessChecker] = None,
                 clock: Optional[Callable[[], datetime]] = None) -> None:
        self._repo = Repository(conn)
        self._access = access or SqliteAccessChecker(conn)
        self._clock = clock or datetime.now

    # ============================================== patient / caregiver actions
    def mark_taken(self, actor: UserContext, schedule_id: int, dose_date: date, dose_time: str) -> DoseLog:
        return self._mark(actor, schedule_id, dose_date, dose_time, DOSE_TAKEN)

    def mark_skipped(self, actor: UserContext, schedule_id: int, dose_date: date, dose_time: str) -> DoseLog:
        return self._mark(actor, schedule_id, dose_date, dose_time, DOSE_SKIPPED)

    def _mark(self, actor: UserContext, schedule_id: int, dose_date: date, dose_time: str, status: str) -> DoseLog:
        """UC9 - Take / Skip Dose."""
        if status not in (DOSE_TAKEN, DOSE_SKIPPED):
            raise ValidationError("A dose can only be marked 'taken' or 'skipped' by a user.")
        schedule, medicine = self._scheduled_dose(schedule_id, dose_date, dose_time)
        require_manage(self._access, actor, medicine.patient_id)
        now = self._clock()
        dose_dt = datetime.combine(dose_date, parse_time(dose_time))
        if dose_dt - now > timedelta(minutes=EARLY_WINDOW_MINUTES):
            raise ValidationError(f"This dose is not due yet (it can be marked {EARLY_WINDOW_MINUTES} minutes before its time).")
        existing = self._repo.get_log(schedule_id, dose_date, dose_time)
        if existing is not None and existing.status != DOSE_MISSED:
            raise ValidationError(f"This dose is already recorded as '{existing.status}'.")
        return self._repo.upsert_log(schedule_id, dose_date, dose_time, status, now.isoformat(timespec="seconds"))

    # ============================================== system call from Module M3
    def mark_missed(self, schedule_id: int, dose_date: date, dose_time: str) -> DoseLog:
        """Called by Module M3 when the response window has expired. Safe to call twice."""
        self._scheduled_dose(schedule_id, dose_date, dose_time)
        now = self._clock()
        if datetime.combine(dose_date, parse_time(dose_time)) > now:
            raise ValidationError("A dose in the future cannot be missed yet.")
        existing = self._repo.get_log(schedule_id, dose_date, dose_time)
        if existing is not None:
            return existing
        return self._repo.upsert_log(schedule_id, dose_date, dose_time, DOSE_MISSED, now.isoformat(timespec="seconds"))

    def get_due_doses(self, now: Optional[datetime] = None, lookback_minutes: int = 5) -> List[DueDose]:
        """Doses whose time arrived in the last few minutes and are not logged yet (M3 sends reminders)."""
        now = now or self._clock()
        return self._unlogged(now - timedelta(minutes=lookback_minutes), now)

    def get_overdue_doses(self, now: Optional[datetime] = None, grace_minutes: int = 30,
                          lookback_hours: int = 24) -> List[DueDose]:
        """Doses older than the grace period with no log - M3 turns these into 'missed' + alerts."""
        now = now or self._clock()
        return self._unlogged(now - timedelta(hours=lookback_hours), now - timedelta(minutes=grace_minutes))

    # ============================================== read-only views
    def get_upcoming_doses(self, actor: UserContext, patient_id: int, hours_ahead: int = 24) -> List[DueDose]:
        require_view(self._access, actor, patient_id)
        now = self._clock()
        return self._unlogged(now, now + timedelta(hours=hours_ahead), patient_id)

    def get_history(self, actor: UserContext, patient_id: int, start: Optional[date] = None,
                    end: Optional[date] = None, status: Optional[str] = None) -> List[DoseLog]:
        """Dose history - used by the patient (UC12) and by Module M4 (read-only)."""
        require_view(self._access, actor, patient_id)
        if start is not None and end is not None:
            validate_date_range(start, end)
        if status is not None and status not in VALID_DOSE_STATUSES:
            raise ValidationError(f"Status must be one of {', '.join(VALID_DOSE_STATUSES)}.")
        return self._repo.list_logs(patient_id, start, end, status)

    def count_by_status(self, actor: UserContext, patient_id: int, start: Optional[date] = None,
                        end: Optional[date] = None) -> Dict[str, int]:
        counts = {status: 0 for status in VALID_DOSE_STATUSES}
        for log in self.get_history(actor, patient_id, start, end):
            counts[log.status] += 1
        return counts

    # ============================================== helpers
    def _scheduled_dose(self, schedule_id: int, dose_date: date, dose_time: str):
        found = self._repo.get_schedule_with_medicine(schedule_id)
        if found is None:
            raise NotFoundError(f"Schedule {schedule_id} does not exist.")
        schedule, medicine = found
        parse_time(dose_time)
        if dose_time not in schedule.dose_times or not schedule.start_date <= dose_date <= schedule.end_date:
            raise ValidationError(f"{dose_date.isoformat()} {dose_time} is not a scheduled dose of this medicine.")
        return schedule, medicine

    def _unlogged(self, start_dt: datetime, end_dt: datetime, patient_id: Optional[int] = None) -> List[DueDose]:
        rows = self._repo.list_schedules_with_medicine(start=start_dt.date(), end=end_dt.date(), patient_id=patient_id)
        logged = self._repo.logged_doses([s.schedule_id for s, _ in rows], start_dt.date(), end_dt.date())
        found: List[DueDose] = []
        for schedule, medicine in rows:
            for day, slot in iter_doses(schedule, start_dt.date(), end_dt.date()):
                when = datetime.combine(day, parse_time(slot))
                if start_dt <= when <= end_dt and (schedule.schedule_id, day, slot) not in logged:
                    found.append(DueDose(schedule.schedule_id, medicine.medicine_id, medicine.patient_id,
                                         medicine.name, medicine.dosage, day, slot))
        return sorted(found, key=lambda d: (d.dose_date, d.dose_time, d.schedule_id))
