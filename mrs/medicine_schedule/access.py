"""Who may manage / view a patient's medicines.

Rules (from the requirement reports):
  * Patient            - manages and views OWN data
  * Caregiver          - manages and views a patient they are APPROVED-linked to
  * Doctor             - read-only, only for patients linked to that doctor
  * Admin              - no access (admins manage accounts, not medicines)

The role comes from Module M1's session, so it is trusted here. The link
tables are owned by M1; M2 only reads them.
"""
import sqlite3
from typing import Protocol

from .errors import ForbiddenError
from .models import ROLE_CAREGIVER, ROLE_DOCTOR, ROLE_PATIENT, UserContext


class AccessChecker(Protocol):
    def can_manage(self, actor: UserContext, patient_id: int) -> bool: ...
    def can_view(self, actor: UserContext, patient_id: int) -> bool: ...


class SqliteAccessChecker:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def can_manage(self, actor: UserContext, patient_id: int) -> bool:
        if actor.role == ROLE_PATIENT:
            return actor.user_id == patient_id
        if actor.role == ROLE_CAREGIVER:
            row = self._conn.execute(
                "SELECT 1 FROM caregiver_links WHERE caregiver_id = ? AND patient_id = ? AND status = 'approved'",
                (actor.user_id, patient_id),
            ).fetchone()
            return row is not None
        return False

    def can_view(self, actor: UserContext, patient_id: int) -> bool:
        if self.can_manage(actor, patient_id):
            return True
        if actor.role == ROLE_DOCTOR:
            row = self._conn.execute(
                "SELECT 1 FROM doctor_patient_links WHERE doctor_id = ? AND patient_id = ?",
                (actor.user_id, patient_id),
            ).fetchone()
            return row is not None
        return False


def require_manage(checker: AccessChecker, actor: UserContext, patient_id: int) -> None:
    if not checker.can_manage(actor, patient_id):
        raise ForbiddenError("You are not allowed to change this patient's medicines.")


def require_view(checker: AccessChecker, actor: UserContext, patient_id: int) -> None:
    if not checker.can_view(actor, patient_id):
        raise ForbiddenError("You are not allowed to view this patient's medicines.")
