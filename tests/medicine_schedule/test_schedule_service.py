from datetime import date

import pytest

from mrs.medicine_schedule import ForbiddenError, NotFoundError, ScheduleConflictError, ValidationError


class TestCreateSchedule:
    def test_uses_frequency_defaults_and_course_length(self, schedule):
        assert schedule.dose_times == ["08:00", "20:00"]
        assert (schedule.start_date, schedule.end_date) == (date(2026, 10, 12), date(2026, 10, 16))

    def test_custom_times_and_end_date(self, meds, patient, paracetamol):
        s = meds.create_schedule(patient, paracetamol.medicine_id, date(2026, 10, 12), ["21:00", "09:30"], date(2026, 10, 20))
        assert s.dose_times == ["09:30", "21:00"]
        assert s.end_date == date(2026, 10, 20)

    def test_registers_reminders_with_ids_and_times_only(self, schedule, gateway):
        assert gateway.registered == {schedule.schedule_id: ["08:00", "20:00"]}

    def test_wrong_number_of_times_rejected(self, meds, patient, paracetamol, gateway):
        with pytest.raises(ValidationError):
            meds.create_schedule(patient, paracetamol.medicine_id, date(2026, 10, 12), ["08:00"])
        assert gateway.registered == {}

    def test_end_before_start_rejected(self, meds, patient, paracetamol):
        with pytest.raises(ValidationError):
            meds.create_schedule(patient, paracetamol.medicine_id, date(2026, 10, 12), end_date=date(2026, 10, 1))

    def test_start_must_be_a_date(self, meds, patient, paracetamol):
        with pytest.raises(ValidationError):
            meds.create_schedule(patient, paracetamol.medicine_id, "2026-10-12")

    def test_forbidden_for_other_patient_and_doctor(self, meds, other_patient, doctor, paracetamol):
        for actor in (other_patient, doctor):
            with pytest.raises(ForbiddenError):
                meds.create_schedule(actor, paracetamol.medicine_id, date(2026, 10, 12))

    def test_unknown_medicine(self, meds, patient):
        with pytest.raises(NotFoundError):
            meds.create_schedule(patient, 999, date(2026, 10, 12))


class TestConflicts:
    def test_same_time_overlapping_dates_raises_with_details(self, meds, patient, schedule):
        aspirin = meds.add_medicine(patient, 1, "Aspirin", "75 mg", "once daily", 3)
        with pytest.raises(ScheduleConflictError) as err:
            meds.create_schedule(patient, aspirin.medicine_id, date(2026, 10, 13), ["08:00"])
        assert [(c.medicine_name, c.dose_time) for c in err.value.conflicts] == [("Paracetamol", "08:00")]

    def test_allow_conflicts_saves_anyway(self, meds, patient, schedule):
        aspirin = meds.add_medicine(patient, 1, "Aspirin", "75 mg", "once daily", 3)
        assert meds.create_schedule(patient, aspirin.medicine_id, date(2026, 10, 13), ["08:00"], allow_conflicts=True)

    def test_different_time_is_fine(self, meds, patient, schedule):
        aspirin = meds.add_medicine(patient, 1, "Aspirin", "75 mg", "once daily", 3)
        assert meds.create_schedule(patient, aspirin.medicine_id, date(2026, 10, 13), ["09:00"])

    def test_other_patients_schedules_do_not_conflict(self, meds, other_patient, schedule):
        vitamin = meds.add_medicine(other_patient, 2, "Vitamin C", "1 tablet", "once daily", 5)
        assert meds.create_schedule(other_patient, vitamin.medicine_id, date(2026, 10, 12), ["08:00"])


class TestUpdateAndDeleteSchedule:
    def test_update_times_reregisters_reminders(self, meds, patient, schedule, gateway):
        updated = meds.update_schedule(patient, schedule.schedule_id, dose_times=["07:00", "19:00"])
        assert updated.dose_times == ["07:00", "19:00"]
        assert gateway.registered[schedule.schedule_id] == ["07:00", "19:00"]
        assert schedule.schedule_id in gateway.cancelled

    def test_update_ignores_its_own_slots_when_checking_conflicts(self, meds, patient, schedule):
        assert meds.update_schedule(patient, schedule.schedule_id, end_date=date(2026, 10, 18)).end_date == date(2026, 10, 18)

    def test_update_conflict_detected(self, meds, patient, schedule):
        aspirin = meds.add_medicine(patient, 1, "Aspirin", "75 mg", "once daily", 3)
        other = meds.create_schedule(patient, aspirin.medicine_id, date(2026, 10, 12), ["09:00"])
        with pytest.raises(ScheduleConflictError):
            meds.update_schedule(patient, other.schedule_id, dose_times=["08:00"])

    def test_update_forbidden(self, meds, other_patient, schedule):
        with pytest.raises(ForbiddenError):
            meds.update_schedule(other_patient, schedule.schedule_id, dose_times=["07:00", "19:00"])

    def test_delete_schedule(self, meds, patient, paracetamol, schedule, gateway):
        meds.delete_schedule(patient, schedule.schedule_id)
        assert meds.get_schedules(patient, paracetamol.medicine_id) == []
        assert schedule.schedule_id in gateway.cancelled

    def test_get_schedules_for_doctor_view(self, meds, doctor, paracetamol, schedule):
        assert [s.schedule_id for s in meds.get_schedules(doctor, paracetamol.medicine_id)] == [schedule.schedule_id]


class TestCalendar:
    def test_groups_by_day_sorted_by_time(self, meds, patient, schedule):
        cal = meds.get_calendar(patient, 1, date(2026, 10, 11), date(2026, 10, 14))
        assert list(cal) == [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)]
        day = cal[date(2026, 10, 12)]
        assert [(e.dose_time, e.medicine_name, e.status) for e in day] == [("08:00", "Paracetamol", "pending"),
                                                                           ("20:00", "Paracetamol", "pending")]

    def test_shows_logged_status(self, meds, doses, patient, schedule, clock):
        clock.advance(hours=1, minutes=5)  # 08:05
        doses.mark_taken(patient, schedule.schedule_id, date(2026, 10, 12), "08:00")
        cal = meds.get_calendar(patient, 1, date(2026, 10, 12), date(2026, 10, 12))
        assert [e.status for e in cal[date(2026, 10, 12)]] == ["taken", "pending"]

    def test_caregiver_and_doctor_can_view_others_cannot(self, meds, caregiver, doctor, other_patient, schedule):
        assert meds.get_calendar(caregiver, 1, date(2026, 10, 12), date(2026, 10, 12))
        assert meds.get_calendar(doctor, 1, date(2026, 10, 12), date(2026, 10, 12))
        with pytest.raises(ForbiddenError):
            meds.get_calendar(other_patient, 1, date(2026, 10, 12), date(2026, 10, 12))

    def test_empty_when_nothing_scheduled(self, meds, patient):
        assert meds.get_calendar(patient, 1, date(2026, 10, 12), date(2026, 10, 14)) == {}

    def test_range_limit(self, meds, patient):
        with pytest.raises(ValidationError):
            meds.get_calendar(patient, 1, date(2026, 1, 1), date(2026, 12, 31))

    def test_bad_range(self, meds, patient):
        with pytest.raises(ValidationError):
            meds.get_calendar(patient, 1, date(2026, 10, 14), date(2026, 10, 12))
