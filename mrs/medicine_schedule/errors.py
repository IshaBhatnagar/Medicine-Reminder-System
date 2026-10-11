"""Exceptions raised by Module M2 (Medicine & Schedule Management)."""
from typing import List


class MRSError(Exception):
    """Base class for all Medicine Reminder System errors."""


class ValidationError(MRSError):
    """Input is missing, malformed or breaks a business rule."""


class NotFoundError(MRSError):
    """The requested medicine / schedule / dose does not exist."""


class ForbiddenError(MRSError):
    """The acting user is not allowed to do this for this patient."""


class ScheduleConflictError(MRSError):
    """A new schedule uses a time slot already used by another medicine.

    The UI catches this, warns the patient, and may call again with
    allow_conflicts=True (Use case UC7 alternate flow).
    """

    def __init__(self, conflicts: List):
        self.conflicts = conflicts
        details = ", ".join(f"{c.medicine_name} at {c.dose_time}" for c in conflicts)
        super().__init__(f"Dose time conflicts with: {details}")
