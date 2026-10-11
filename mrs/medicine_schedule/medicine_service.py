"""MedicineService - medicines AND their schedules (UC4-UC8).

Experiment 7 sequence diagram: MedicineService validates, saves, creates the
schedule and registers reminders with ReminderService (Module M3).
"""
import sqlite3
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

from .access import AccessChecker, SqliteAccessChecker, require_manage, require_view
from .errors import NotFoundError, ScheduleConflictError, ValidationError
from .models import DOSE_PENDING, CalendarEntry, Medicine, Schedule, UserContext
from .planning import iter_doses
from .reminder_gateway import NullReminderGateway, ReminderGateway
from .repository import Repository
from .validators import (FREQUENCY_SLOTS, default_end_date, find_time_conflicts, validate_date,
                         validate_date_range, validate_dosage, validate_dose_times, validate_duration,
                         validate_frequency, validate_name, validate_prescribing_doctor)

MAX_CALENDAR_DAYS = 92
_EDITABLE_FIELDS = {"name", "dosage", "frequency", "duration_days", "prescribing_doctor"}


class MedicineService:
    def __init__(self, conn: sqlite3.Connection, access: Optional[AccessChecker] = None,
                 reminders: Optional[ReminderGateway] = None,
                 clock: Optional[Callable[[], datetime]] = None) -> None:
        self._repo = Repository(conn)
        self._access = access or SqliteAccessChecker(conn)
        self._reminders = reminders or NullReminderGateway()
        self._clock = clock or datetime.now

    # ================================================================ medicines
    def add_medicine(self, actor: UserContext, patient_id: int, name: str, dosage: str, frequency: str,
                     duration_days: int, prescribing_doctor: Optional[str] = None) -> Medicine:
        """UC4 - Add Medicine."""
        require_manage(self._access, actor, patient_id)
        return self._repo.insert_medicine(
            patient_id,
            validate_name(name),
            validate_dosage(dosage),
            validate_frequency(frequency),
            validate_duration(duration_days),
            validate_prescribing_doctor(prescribing_doctor),
            self._clock().isoformat(timespec="seconds"),
        )

    def edit_medicine(self, actor: UserContext, medicine_id: int, **changes) -> Medicine:
        """UC5 - Edit Medicine. Allowed fields: name, dosage, frequency, duration_days, prescribing_doctor."""
        medicine = self._managed_medicine(actor, medicine_id)
        if not changes:
            raise ValidationError("Nothing to change.")
        unknown = set(changes) - _EDITABLE_FIELDS
        if unknown:
            raise ValidationError(f"These fields cannot be edited: {', '.join(sorted(unknown))}.")

        updates: Dict[str, object] = {}
        if "name" in changes:
            updates["name"] = validate_name(changes["name"])
        if "dosage" in changes:
            updates["dosage"] = validate_dosage(changes["dosage"])
        if "frequency" in changes:
            updates["frequency"] = validate_frequency(changes["frequency"])
        if "duration_days" in changes:
            updates["duration_days"] = validate_duration(changes["duration_days"])
        if "prescribing_doctor" in changes:
            updates["prescribing_doctor"] = validate_prescribing_doctor(changes["prescribing_doctor"])

        if "frequency" in updates:  # a schedule must still match the new frequency
            slots = FREQUENCY_SLOTS[updates["frequency"]]  # type: ignore[index]
            for schedule in self._repo.list_schedules_for_medicine(medicine.medicine_id):
                if len(schedule.dose_times) != slots:
                    raise ValidationError(
                        f"Schedule {schedule.schedule_id} has {len(schedule.dose_times)} dose time(s); "
                        f"update the schedule before changing the frequency to '{updates['frequency']}'.")
        self._repo.update_medicine(medicine.medicine_id, updates)
        return self._repo.get_medicine(medicine.medicine_id)  # type: ignore[return-value]

    def delete_medicine(self, actor: UserContext, medicine_id: int) -> None:
        """UC6 - Delete Medicine together with its schedules (and their dose logs)."""
        medicine = self._managed_medicine(actor, medicine_id)
        schedule_ids = [s.schedule_id for s in self._repo.list_schedules_for_medicine(medicine_id)]
        self._repo.delete_medicine(medicine.medicine_id)
        for schedule_id in schedule_ids:
            self._reminders.cancel_reminders(schedule_id)

    def get_medicine(self, actor: UserContext, medicine_id: int) -> Medicine:
        medicine = self._repo.get_medicine(medicine_id)
        if medicine is None:
            raise NotFoundError(f"Medicine {medicine_id} does not exist.")
        require_view(self._access, actor, medicine.patient_id)
        return medicine

    def list_medicines(self, actor: UserContext, patient_id: int, only_current: bool = False) -> List[Medicine]:
        """List a patient's medicines. only_current=True keeps those with a schedule that has not ended."""
        require_view(self._access, actor, patient_id)
        medicines = self._repo.list_medicines(patient_id)
        if not only_current:
            return medicines
        today = self._clock().date()
        current_ids = {m.medicine_id for s, m in self._repo.list_schedules_with_medicine(start=today, patient_id=patient_id)}
        return [m for m in medicines if m.medicine_id in current_ids]

    # ================================================================ schedules
    def create_schedule(self, actor: UserContext, medicine_id: int, start_date: date,
                        dose_times: Optional[List[str]] = None, end_date: Optional[date] = None,
                        allow_conflicts: bool = False) -> Schedule:
        """UC7 - Schedule Medicine. Raises ScheduleConflictError if a time slot is already used."""
        medicine = self._managed_medicine(actor, medicine_id)
        validate_date(start_date, "start_date")
        times = validate_dose_times(dose_times, medicine.frequency)
        end = end_date if end_date is not None else default_end_date(start_date, medicine.duration_days)
        validate_date_range(start_date, end)
        self._check_conflicts(medicine.patient_id, times, start_date, end, None, allow_conflicts)
        schedule = self._repo.insert_schedule(medicine.medicine_id, times, start_date, end)
        self._reminders.register_reminders(schedule.schedule_id, list(schedule.dose_times))
        return schedule

    def update_schedule(self, actor: UserContext, schedule_id: int, dose_times: Optional[List[str]] = None,
                        start_date: Optional[date] = None, end_date: Optional[date] = None,
                        allow_conflicts: bool = False) -> Schedule:
        schedule, medicine = self._managed_schedule(actor, schedule_id)
        times = validate_dose_times(dose_times if dose_times is not None else schedule.dose_times, medicine.frequency)
        start = validate_date(start_date, "start_date") if start_date is not None else schedule.start_date
        end = validate_date(end_date, "end_date") if end_date is not None else schedule.end_date
        validate_date_range(start, end)
        self._check_conflicts(medicine.patient_id, times, start, end, schedule_id, allow_conflicts)
        self._repo.update_schedule(schedule_id, times, start, end)
        self._reminders.cancel_reminders(schedule_id)
        self._reminders.register_reminders(schedule_id, times)
        return self._repo.get_schedule(schedule_id)  # type: ignore[return-value]

    def delete_schedule(self, actor: UserContext, schedule_id: int) -> None:
        self._managed_schedule(actor, schedule_id)
        self._repo.delete_schedule(schedule_id)
        self._reminders.cancel_reminders(schedule_id)

    def get_schedules(self, actor: UserContext, medicine_id: int) -> List[Schedule]:
        medicine = self.get_medicine(actor, medicine_id)  # includes the view check
        return self._repo.list_schedules_for_medicine(medicine.medicine_id)

    def get_calendar(self, actor: UserContext, patient_id: int, start: date, end: date) -> Dict[date, List[CalendarEntry]]:
        """UC8 - day-by-day list of doses with their status (taken / skipped / missed / pending)."""
        require_view(self._access, actor, patient_id)
        validate_date_range(start, end)
        if (end - start).days + 1 > MAX_CALENDAR_DAYS:
            raise ValidationError(f"Calendar range is limited to {MAX_CALENDAR_DAYS} days.")
        rows = self._repo.list_schedules_with_medicine(start=start, end=end, patient_id=patient_id)
        logged = self._repo.logged_doses([s.schedule_id for s, _ in rows], start, end)
        days: Dict[date, List[CalendarEntry]] = {}
        for schedule, medicine in rows:
            for day, slot in iter_doses(schedule, start, end):
                status = logged.get((schedule.schedule_id, day, slot), DOSE_PENDING)
                days.setdefault(day, []).append(CalendarEntry(
                    schedule.schedule_id, medicine.medicine_id, medicine.name, medicine.dosage, slot, status))
        return {d: sorted(days[d], key=lambda e: (e.dose_time, e.medicine_name)) for d in sorted(days)}

    # ================================================================ helpers
    def _managed_medicine(self, actor: UserContext, medicine_id: int) -> Medicine:
        medicine = self._repo.get_medicine(medicine_id)
        if medicine is None:
            raise NotFoundError(f"Medicine {medicine_id} does not exist.")
        require_manage(self._access, actor, medicine.patient_id)
        return medicine

    def _managed_schedule(self, actor: UserContext, schedule_id: int):
        found = self._repo.get_schedule_with_medicine(schedule_id)
        if found is None:
            raise NotFoundError(f"Schedule {schedule_id} does not exist.")
        require_manage(self._access, actor, found[1].patient_id)
        return found

    def _check_conflicts(self, patient_id: int, times: List[str], start: date, end: date,
                         exclude_schedule_id: Optional[int], allow_conflicts: bool) -> None:
        existing = [(s.schedule_id, m.name, s.dose_times, s.start_date, s.end_date)
                    for s, m in self._repo.list_schedules_with_medicine(patient_id=patient_id)
                    if s.schedule_id != exclude_schedule_id]
        conflicts = find_time_conflicts(times, start, end, existing)
        if conflicts and not allow_conflicts:
            raise ScheduleConflictError(conflicts)
