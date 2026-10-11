"""The ONLY file in Module M2 that contains SQL. Services never write SQL."""
import sqlite3
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from .models import DoseLog, Medicine, Schedule

_MEDICINE_COLUMNS = {"name", "dosage", "frequency", "duration_days", "prescribing_doctor"}

_JOIN_SELECT = """
    SELECT s.schedule_id AS s_id, s.medicine_id AS s_med, s.dose_times AS s_times,
           s.start_date AS s_start, s.end_date AS s_end,
           m.medicine_id AS m_id, m.patient_id AS m_patient, m.name AS m_name,
           m.dosage AS m_dosage, m.frequency AS m_freq, m.duration_days AS m_dur,
           m.prescribing_doctor AS m_doc, m.created_at AS m_created
    FROM schedules s JOIN medicines m ON m.medicine_id = s.medicine_id
"""


def _medicine(row: sqlite3.Row) -> Medicine:
    return Medicine(row["medicine_id"], row["patient_id"], row["name"], row["dosage"],
                    row["frequency"], row["duration_days"], row["prescribing_doctor"], row["created_at"])


def _schedule(row: sqlite3.Row) -> Schedule:
    return Schedule(row["schedule_id"], row["medicine_id"], row["dose_times"].split(","),
                    date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"]))


def _log(row: sqlite3.Row) -> DoseLog:
    return DoseLog(row["log_id"], row["schedule_id"], date.fromisoformat(row["dose_date"]),
                   row["dose_time"], row["status"], row["logged_at"])


def _joined(row: sqlite3.Row) -> Tuple[Schedule, Medicine]:
    schedule = Schedule(row["s_id"], row["s_med"], row["s_times"].split(","),
                        date.fromisoformat(row["s_start"]), date.fromisoformat(row["s_end"]))
    medicine = Medicine(row["m_id"], row["m_patient"], row["m_name"], row["m_dosage"],
                        row["m_freq"], row["m_dur"], row["m_doc"], row["m_created"])
    return schedule, medicine


class Repository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    # ------------------------------------------------------------ medicines
    def insert_medicine(self, patient_id: int, name: str, dosage: str, frequency: str,
                        duration_days: int, prescribing_doctor: Optional[str], created_at: str) -> Medicine:
        with self._c:
            cur = self._c.execute(
                "INSERT INTO medicines (patient_id, name, dosage, frequency, duration_days, "
                "prescribing_doctor, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (patient_id, name, dosage, frequency, duration_days, prescribing_doctor, created_at),
            )
        return self.get_medicine(cur.lastrowid)  # type: ignore[return-value]

    def get_medicine(self, medicine_id: int) -> Optional[Medicine]:
        row = self._c.execute("SELECT * FROM medicines WHERE medicine_id = ?", (medicine_id,)).fetchone()
        return _medicine(row) if row else None

    def list_medicines(self, patient_id: int) -> List[Medicine]:
        rows = self._c.execute("SELECT * FROM medicines WHERE patient_id = ? ORDER BY name, medicine_id",
                               (patient_id,)).fetchall()
        return [_medicine(r) for r in rows]

    def update_medicine(self, medicine_id: int, fields: Dict[str, object]) -> None:
        unknown = set(fields) - _MEDICINE_COLUMNS
        if unknown or not fields:
            raise ValueError(f"Cannot update columns: {sorted(unknown) or 'none given'}")
        assignments = ", ".join(f"{col} = ?" for col in fields)  # columns are whitelisted above
        with self._c:
            self._c.execute(f"UPDATE medicines SET {assignments} WHERE medicine_id = ?",
                            (*fields.values(), medicine_id))

    def delete_medicine(self, medicine_id: int) -> None:
        with self._c:  # schedules and dose_logs are removed by ON DELETE CASCADE
            self._c.execute("DELETE FROM medicines WHERE medicine_id = ?", (medicine_id,))

    # ------------------------------------------------------------ schedules
    def insert_schedule(self, medicine_id: int, dose_times: List[str], start: date, end: date) -> Schedule:
        with self._c:
            cur = self._c.execute(
                "INSERT INTO schedules (medicine_id, dose_times, start_date, end_date) VALUES (?, ?, ?, ?)",
                (medicine_id, ",".join(dose_times), start.isoformat(), end.isoformat()),
            )
        return self.get_schedule(cur.lastrowid)  # type: ignore[return-value]

    def get_schedule(self, schedule_id: int) -> Optional[Schedule]:
        row = self._c.execute("SELECT * FROM schedules WHERE schedule_id = ?", (schedule_id,)).fetchone()
        return _schedule(row) if row else None

    def get_schedule_with_medicine(self, schedule_id: int) -> Optional[Tuple[Schedule, Medicine]]:
        row = self._c.execute(_JOIN_SELECT + " WHERE s.schedule_id = ?", (schedule_id,)).fetchone()
        return _joined(row) if row else None

    def list_schedules_for_medicine(self, medicine_id: int) -> List[Schedule]:
        rows = self._c.execute("SELECT * FROM schedules WHERE medicine_id = ? ORDER BY start_date, schedule_id",
                               (medicine_id,)).fetchall()
        return [_schedule(r) for r in rows]

    def list_schedules_with_medicine(self, start: Optional[date] = None, end: Optional[date] = None,
                                     patient_id: Optional[int] = None) -> List[Tuple[Schedule, Medicine]]:
        """Schedules that overlap [start, end] (either bound optional), optionally for one patient."""
        where, params = [], []
        if start is not None:
            where.append("s.end_date >= ?")
            params.append(start.isoformat())
        if end is not None:
            where.append("s.start_date <= ?")
            params.append(end.isoformat())
        if patient_id is not None:
            where.append("m.patient_id = ?")
            params.append(patient_id)
        sql = _JOIN_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY s.schedule_id"
        return [_joined(r) for r in self._c.execute(sql, params).fetchall()]

    def update_schedule(self, schedule_id: int, dose_times: List[str], start: date, end: date) -> None:
        with self._c:
            self._c.execute(
                "UPDATE schedules SET dose_times = ?, start_date = ?, end_date = ? WHERE schedule_id = ?",
                (",".join(dose_times), start.isoformat(), end.isoformat(), schedule_id),
            )

    def delete_schedule(self, schedule_id: int) -> None:
        with self._c:
            self._c.execute("DELETE FROM schedules WHERE schedule_id = ?", (schedule_id,))

    # ------------------------------------------------------------ dose logs
    def get_log(self, schedule_id: int, dose_date: date, dose_time: str) -> Optional[DoseLog]:
        row = self._c.execute(
            "SELECT * FROM dose_logs WHERE schedule_id = ? AND dose_date = ? AND dose_time = ?",
            (schedule_id, dose_date.isoformat(), dose_time),
        ).fetchone()
        return _log(row) if row else None

    def upsert_log(self, schedule_id: int, dose_date: date, dose_time: str, status: str, logged_at: str) -> DoseLog:
        with self._c:
            self._c.execute(
                "INSERT INTO dose_logs (schedule_id, dose_date, dose_time, status, logged_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (schedule_id, dose_date, dose_time) "
                "DO UPDATE SET status = excluded.status, logged_at = excluded.logged_at",
                (schedule_id, dose_date.isoformat(), dose_time, status, logged_at),
            )
        return self.get_log(schedule_id, dose_date, dose_time)  # type: ignore[return-value]

    def logged_doses(self, schedule_ids: Sequence[int], start: date, end: date) -> Dict[Tuple[int, date, str], str]:
        """(schedule_id, date, time) -> status for every logged dose in the range."""
        if not schedule_ids:
            return {}
        marks = ",".join("?" for _ in schedule_ids)
        rows = self._c.execute(
            f"SELECT schedule_id, dose_date, dose_time, status FROM dose_logs "
            f"WHERE schedule_id IN ({marks}) AND dose_date BETWEEN ? AND ?",
            (*schedule_ids, start.isoformat(), end.isoformat()),
        ).fetchall()
        return {(r["schedule_id"], date.fromisoformat(r["dose_date"]), r["dose_time"]): r["status"] for r in rows}

    def list_logs(self, patient_id: int, start: Optional[date] = None, end: Optional[date] = None,
                  status: Optional[str] = None) -> List[DoseLog]:
        where, params = ["m.patient_id = ?"], [patient_id]
        if start is not None:
            where.append("l.dose_date >= ?")
            params.append(start.isoformat())
        if end is not None:
            where.append("l.dose_date <= ?")
            params.append(end.isoformat())
        if status is not None:
            where.append("l.status = ?")
            params.append(status)
        sql = ("SELECT l.* FROM dose_logs l JOIN schedules s ON s.schedule_id = l.schedule_id "
               "JOIN medicines m ON m.medicine_id = s.medicine_id WHERE " + " AND ".join(where) +
               " ORDER BY l.dose_date, l.dose_time, l.log_id")
        return [_log(r) for r in self._c.execute(sql, params).fetchall()]
