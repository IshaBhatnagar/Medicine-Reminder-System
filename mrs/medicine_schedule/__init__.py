"""Module M2 - Medicine & Schedule Management (owner: Isha Bhatnagar).

Public API used by the other modules:
    MedicineService  - medicines + schedules (UC4-UC8)
    DoseService      - dose logs, due / overdue doses, history (UC9, UC12)
    ReminderGateway  - contract that Module M3 implements
    UserContext      - who is calling (comes from Module M1)
"""
from .access import AccessChecker, SqliteAccessChecker
from .dose_service import DoseService
from .errors import (ForbiddenError, MRSError, NotFoundError, ScheduleConflictError, ValidationError)
from .medicine_service import MedicineService
from .models import (CalendarEntry, DoseLog, DueDose, Medicine, Schedule, TimeConflict, UserContext, to_dict)
from .reminder_gateway import InMemoryReminderGateway, NullReminderGateway, ReminderGateway

__all__ = [
    "AccessChecker", "SqliteAccessChecker", "DoseService", "MedicineService",
    "ForbiddenError", "MRSError", "NotFoundError", "ScheduleConflictError", "ValidationError",
    "CalendarEntry", "DoseLog", "DueDose", "Medicine", "Schedule", "TimeConflict", "UserContext", "to_dict",
    "InMemoryReminderGateway", "NullReminderGateway", "ReminderGateway",
]
