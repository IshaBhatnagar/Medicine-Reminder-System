from datetime import date, datetime

import pytest

from mrs.medicine_schedule import ForbiddenError, NotFoundError, ValidationError

D12 = date(2026, 10, 12)


class TestMarkTakenOrSkipped:
    def test_patient_marks_taken(self, doses, patient, schedule, clock):
        clock.advance(hours=1, minutes=5)  # 08:05
        log = doses.mark_taken(patient, schedule.schedule_id, D12, "08:00")
        assert (log.status, log.dose_date, log.dose_time) == ("taken", D12, "08:00")

    def test_patient_marks_skipped(self, doses, patient, schedule, clock):
        clock.advance(hours=1, minutes=5)
        assert doses.mark_skipped(patient, schedule.schedule_id, D12, "08:00").status == "skipped"

    def test_caregiver_can_mark_for_patient(self, doses, caregiver, schedule, clock):
        clock.advance(hours=1)
        assert doses.mark_taken(caregiver, schedule.schedule_id, D12, "08:00").status == "taken"

    def test_doctor_and_other_patient_cannot_mark(self, doses, doctor, other_patient, schedule, clock):
        clock.advance(hours=1)
        for actor in (doctor, other_patient):
            with pytest.raises(ForbiddenError):
                doses.mark_taken(actor, schedule.schedule_id, D12, "08:00")

    def test_cannot_mark_twice(self, doses, patient, schedule, clock):
        clock.advance(hours=1)
        doses.mark_taken(patient, schedule.schedule_id, D12, "08:00")
        with pytest.raises(ValidationError):
            doses.mark_skipped(patient, schedule.schedule_id, D12, "08:00")

    def test_missed_dose_can_still_be_marked_taken_late(self, doses, patient, schedule, clock):
        clock.advance(hours=2)  # 09:00
        doses.mark_missed(schedule.schedule_id, D12, "08:00")
        assert doses.mark_taken(patient, schedule.schedule_id, D12, "08:00").status == "taken"

    def test_cannot_mark_a_dose_far_in_the_future(self, doses, patient, schedule):
        with pytest.raises(ValidationError):      # 20:00 while the clock says 07:00
            doses.mark_taken(patient, schedule.schedule_id, D12, "20:00")

    def test_can_mark_up_to_an_hour_early(self, doses, patient, schedule):
        assert doses.mark_taken(patient, schedule.schedule_id, D12, "08:00").status == "taken"  # 07:00 -> 60 min early

    def test_unscheduled_time_or_date_rejected(self, doses, patient, schedule, clock):
        clock.advance(days=10)
        with pytest.raises(ValidationError):
            doses.mark_taken(patient, schedule.schedule_id, D12, "12:00")
        with pytest.raises(ValidationError):
            doses.mark_taken(patient, schedule.schedule_id, date(2026, 10, 20), "08:00")

    def test_unknown_schedule(self, doses, patient):
        with pytest.raises(NotFoundError):
            doses.mark_taken(patient, 999, D12, "08:00")


class TestMarkMissed:
    def test_marks_missed(self, doses, schedule, clock):
        clock.advance(hours=2)
        assert doses.mark_missed(schedule.schedule_id, D12, "08:00").status == "missed"

    def test_is_idempotent_and_never_overwrites_a_taken_dose(self, doses, patient, schedule, clock):
        clock.advance(hours=1)
        doses.mark_taken(patient, schedule.schedule_id, D12, "08:00")
        clock.advance(hours=1)
        assert doses.mark_missed(schedule.schedule_id, D12, "08:00").status == "taken"

    def test_future_dose_cannot_be_missed(self, doses, schedule):
        with pytest.raises(ValidationError):
            doses.mark_missed(schedule.schedule_id, D12, "20:00")


class TestDueAndOverdue:
    def test_due_doses_in_lookback_window(self, doses, schedule, clock):
        clock.advance(hours=1, minutes=2)  # 08:02
        due = doses.get_due_doses()
        assert [(d.dose_time, d.medicine_name, d.patient_id) for d in due] == [("08:00", "Paracetamol", 1)]

    def test_nothing_due_outside_window(self, doses, schedule, clock):
        clock.advance(hours=2)  # 09:00
        assert doses.get_due_doses() == []

    def test_logged_dose_is_not_due(self, doses, patient, schedule, clock):
        clock.advance(hours=1, minutes=2)
        doses.mark_taken(patient, schedule.schedule_id, D12, "08:00")
        assert doses.get_due_doses() == []

    def test_overdue_after_grace_period(self, doses, schedule, clock):
        clock.advance(hours=1, minutes=40)  # 08:40, 40 min after the dose
        assert [d.dose_time for d in doses.get_overdue_doses(grace_minutes=30)] == ["08:00"]
        assert doses.get_overdue_doses(grace_minutes=60) == []

    def test_overdue_dose_disappears_once_marked_missed(self, doses, schedule, clock):
        clock.advance(hours=2)
        for dose in doses.get_overdue_doses():
            doses.mark_missed(dose.schedule_id, dose.dose_date, dose.dose_time)
        assert doses.get_overdue_doses() == []

    def test_explicit_now_argument(self, doses, schedule):
        assert len(doses.get_due_doses(now=datetime(2026, 10, 13, 20, 1))) == 1


class TestUpcoming:
    def test_next_24_hours(self, doses, patient, schedule):
        up = doses.get_upcoming_doses(patient, 1, hours_ahead=24)   # 07:00 -> next day 07:00
        assert [(d.dose_date, d.dose_time) for d in up] == [(D12, "08:00"), (D12, "20:00")]

    def test_taken_dose_is_not_upcoming(self, doses, patient, schedule):
        doses.mark_taken(patient, schedule.schedule_id, D12, "08:00")
        assert [d.dose_time for d in doses.get_upcoming_doses(patient, 1, hours_ahead=14)] == ["20:00"]

    def test_forbidden_for_stranger(self, doses, other_patient, schedule):
        with pytest.raises(ForbiddenError):
            doses.get_upcoming_doses(other_patient, 1)


class TestHistory:
    @pytest.fixture
    def history(self, doses, patient, schedule, clock):
        clock.advance(hours=1)
        doses.mark_taken(patient, schedule.schedule_id, D12, "08:00")
        clock.advance(hours=13)  # 21:00
        doses.mark_missed(schedule.schedule_id, D12, "20:00")
        clock.advance(hours=11)  # next day 08:00
        doses.mark_skipped(patient, schedule.schedule_id, date(2026, 10, 13), "08:00")

    def test_full_history_in_order(self, doses, patient, history):
        assert [(l.dose_date, l.dose_time, l.status) for l in doses.get_history(patient, 1)] == [
            (D12, "08:00", "taken"), (D12, "20:00", "missed"), (date(2026, 10, 13), "08:00", "skipped")]

    def test_filter_by_status_and_dates(self, doses, patient, history):
        assert len(doses.get_history(patient, 1, status="missed")) == 1
        assert len(doses.get_history(patient, 1, start=date(2026, 10, 13), end=date(2026, 10, 13))) == 1

    def test_count_by_status(self, doses, patient, history):
        assert doses.count_by_status(patient, 1) == {"taken": 1, "skipped": 1, "missed": 1}

    def test_doctor_and_caregiver_can_read(self, doses, doctor, caregiver, history):
        assert len(doses.get_history(doctor, 1)) == 3
        assert len(doses.get_history(caregiver, 1)) == 3

    def test_stranger_cannot_read(self, doses, other_patient, history):
        with pytest.raises(ForbiddenError):
            doses.get_history(other_patient, 1)

    def test_bad_status_filter(self, doses, patient, history):
        with pytest.raises(ValidationError):
            doses.get_history(patient, 1, status="eaten")

    def test_history_is_deleted_with_the_medicine(self, meds, doses, patient, paracetamol, history):
        meds.delete_medicine(patient, paracetamol.medicine_id)
        assert doses.get_history(patient, 1) == []
