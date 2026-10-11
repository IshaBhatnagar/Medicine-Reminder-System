from datetime import date

import pytest

from mrs.medicine_schedule import ForbiddenError, NotFoundError, ValidationError


class TestAddMedicine:
    def test_patient_adds_own_medicine(self, meds, patient):
        med = meds.add_medicine(patient, 1, " Paracetamol ", "500mg", "Twice Daily", 5, "Dr. Mehta")
        assert med.medicine_id > 0
        assert (med.name, med.dosage, med.frequency) == ("Paracetamol", "500 mg", "twice daily")
        assert med.prescribing_doctor == "Dr. Mehta"

    def test_prescribing_doctor_is_optional(self, meds, patient):
        assert meds.add_medicine(patient, 1, "Vitamin D", "1 tablet", "once daily", 30).prescribing_doctor is None

    def test_linked_caregiver_can_add_for_patient(self, meds, caregiver):
        assert meds.add_medicine(caregiver, 1, "Aspirin", "75 mg", "once daily", 10).patient_id == 1

    def test_pending_caregiver_forbidden(self, meds, pending_caregiver):
        with pytest.raises(ForbiddenError):
            meds.add_medicine(pending_caregiver, 2, "Aspirin", "75 mg", "once daily", 10)

    def test_patient_cannot_add_for_someone_else(self, meds, patient):
        with pytest.raises(ForbiddenError):
            meds.add_medicine(patient, 2, "Aspirin", "75 mg", "once daily", 10)

    def test_doctor_is_read_only(self, meds, doctor):
        with pytest.raises(ForbiddenError):
            meds.add_medicine(doctor, 1, "Aspirin", "75 mg", "once daily", 10)

    def test_admin_forbidden(self, meds, admin):
        with pytest.raises(ForbiddenError):
            meds.add_medicine(admin, 1, "Aspirin", "75 mg", "once daily", 10)

    @pytest.mark.parametrize("field, value", [("name", ""), ("dosage", "lots"), ("frequency", "hourly"),
                                              ("duration_days", 0)])
    def test_invalid_input_is_rejected_and_nothing_saved(self, meds, patient, field, value):
        args = dict(name="Aspirin", dosage="75 mg", frequency="once daily", duration_days=10)
        args[field] = value
        with pytest.raises(ValidationError):
            meds.add_medicine(patient, 1, **args)
        assert meds.list_medicines(patient, 1) == []


class TestEditMedicine:
    def test_edit_fields(self, meds, patient, paracetamol):
        edited = meds.edit_medicine(patient, paracetamol.medicine_id, dosage="650mg", name="Paracetamol XR")
        assert (edited.dosage, edited.name) == ("650 mg", "Paracetamol XR")

    def test_caregiver_can_edit(self, meds, caregiver, paracetamol):
        assert meds.edit_medicine(caregiver, paracetamol.medicine_id, duration_days=7).duration_days == 7

    def test_cannot_edit_someone_elses_medicine(self, meds, other_patient, paracetamol):
        with pytest.raises(ForbiddenError):
            meds.edit_medicine(other_patient, paracetamol.medicine_id, dosage="1 g")

    def test_unknown_field_rejected(self, meds, patient, paracetamol):
        with pytest.raises(ValidationError):
            meds.edit_medicine(patient, paracetamol.medicine_id, patient_id=2)

    def test_empty_edit_rejected(self, meds, patient, paracetamol):
        with pytest.raises(ValidationError):
            meds.edit_medicine(patient, paracetamol.medicine_id)

    def test_invalid_value_leaves_record_unchanged(self, meds, patient, paracetamol):
        with pytest.raises(ValidationError):
            meds.edit_medicine(patient, paracetamol.medicine_id, dosage="abc")
        assert meds.get_medicine(patient, paracetamol.medicine_id).dosage == "500 mg"

    def test_frequency_change_blocked_while_schedule_has_other_slot_count(self, meds, patient, paracetamol, schedule):
        with pytest.raises(ValidationError):
            meds.edit_medicine(patient, paracetamol.medicine_id, frequency="thrice daily")

    def test_frequency_change_allowed_without_schedule(self, meds, patient, paracetamol):
        assert meds.edit_medicine(patient, paracetamol.medicine_id, frequency="thrice daily").frequency == "thrice daily"

    def test_missing_medicine(self, meds, patient):
        with pytest.raises(NotFoundError):
            meds.edit_medicine(patient, 999, name="X")


class TestDeleteMedicine:
    def test_delete_removes_medicine_schedule_and_cancels_reminders(self, meds, patient, paracetamol, schedule, gateway):
        meds.delete_medicine(patient, paracetamol.medicine_id)
        with pytest.raises(NotFoundError):
            meds.get_medicine(patient, paracetamol.medicine_id)
        assert schedule.schedule_id in gateway.cancelled
        assert schedule.schedule_id not in gateway.registered

    def test_cannot_delete_someone_elses(self, meds, other_patient, paracetamol):
        with pytest.raises(ForbiddenError):
            meds.delete_medicine(other_patient, paracetamol.medicine_id)

    def test_delete_missing(self, meds, patient):
        with pytest.raises(NotFoundError):
            meds.delete_medicine(patient, 999)


class TestListAndGet:
    def test_list_sorted_by_name(self, meds, patient):
        meds.add_medicine(patient, 1, "Zinc", "10 mg", "once daily", 5)
        meds.add_medicine(patient, 1, "Aspirin", "75 mg", "once daily", 5)
        assert [m.name for m in meds.list_medicines(patient, 1)] == ["Aspirin", "Zinc"]

    def test_patient_only_sees_own(self, meds, patient, other_patient, paracetamol):
        assert meds.list_medicines(other_patient, 2) == []
        with pytest.raises(ForbiddenError):
            meds.list_medicines(other_patient, 1)

    def test_doctor_can_view(self, meds, doctor, paracetamol):
        assert [m.name for m in meds.list_medicines(doctor, 1)] == ["Paracetamol"]
        assert meds.get_medicine(doctor, paracetamol.medicine_id).name == "Paracetamol"

    def test_only_current_hides_finished_courses(self, meds, patient, clock):
        old = meds.add_medicine(patient, 1, "OldCourse", "5 mg", "once daily", 2)
        meds.create_schedule(patient, old.medicine_id, date(2026, 10, 1))              # ends 2 Oct
        new = meds.add_medicine(patient, 1, "NewCourse", "5 mg", "once daily", 5)
        meds.create_schedule(patient, new.medicine_id, date(2026, 10, 12), ["09:00"])  # ends 16 Oct
        assert [m.name for m in meds.list_medicines(patient, 1, only_current=True)] == ["NewCourse"]
        assert len(meds.list_medicines(patient, 1)) == 2
