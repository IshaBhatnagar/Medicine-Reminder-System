from datetime import date

import pytest

from mrs.medicine_schedule.errors import ValidationError
from mrs.medicine_schedule.models import Schedule
from mrs.medicine_schedule.planning import iter_doses
from mrs.medicine_schedule.validators import (default_end_date, find_time_conflicts, parse_time, validate_date_range,
                                              validate_dosage, validate_dose_times, validate_duration,
                                              validate_frequency, validate_name, validate_prescribing_doctor)


class TestName:
    def test_trims_and_collapses_spaces(self):
        assert validate_name("  Vitamin   D3 ") == "Vitamin D3"

    @pytest.mark.parametrize("bad", ["", "   ", None, 42])
    def test_rejects_empty_or_non_text(self, bad):
        with pytest.raises(ValidationError):
            validate_name(bad)

    def test_rejects_too_long(self):
        with pytest.raises(ValidationError):
            validate_name("x" * 101)


class TestDosage:
    @pytest.mark.parametrize("raw, expected", [("500 mg", "500 mg"), ("500mg", "500 mg"), ("1 Tablet", "1 tablet"),
                                                 ("2.5 ML", "2.5 ml"), (" 10 units ", "10 units")])
    def test_accepts_and_normalises(self, raw, expected):
        assert validate_dosage(raw) == expected

    @pytest.mark.parametrize("bad", ["", "abc", "mg", "0 mg", "-5 mg", "5 kg", None, 500])
    def test_rejects_invalid(self, bad):
        with pytest.raises(ValidationError):
            validate_dosage(bad)


class TestFrequencyAndDuration:
    def test_frequency_normalised(self):
        assert validate_frequency("Twice   Daily") == "twice daily"

    def test_frequency_invalid(self):
        with pytest.raises(ValidationError):
            validate_frequency("four times daily")

    @pytest.mark.parametrize("days", [1, 30, 365])
    def test_duration_valid(self, days):
        assert validate_duration(days) == days

    @pytest.mark.parametrize("bad", [0, -1, 366, "5", 2.5, True, None])
    def test_duration_invalid(self, bad):
        with pytest.raises(ValidationError):
            validate_duration(bad)

    def test_prescribing_doctor_optional(self):
        assert validate_prescribing_doctor(None) is None
        assert validate_prescribing_doctor("   ") is None
        assert validate_prescribing_doctor(" Dr.  Mehta ") == "Dr. Mehta"


class TestDoseTimes:
    def test_defaults_follow_frequency(self):
        assert validate_dose_times(None, "once daily") == ["08:00"]
        assert validate_dose_times(None, "twice daily") == ["08:00", "20:00"]
        assert validate_dose_times(None, "thrice daily") == ["08:00", "14:00", "20:00"]

    def test_custom_times_sorted(self):
        assert validate_dose_times(["21:30", "07:15"], "twice daily") == ["07:15", "21:30"]

    @pytest.mark.parametrize("bad", ["8:00", "25:00", "08:60", "noon", ""])
    def test_bad_format(self, bad):
        with pytest.raises(ValidationError):
            validate_dose_times([bad], "once daily")

    def test_duplicates_rejected(self):
        with pytest.raises(ValidationError):
            validate_dose_times(["08:00", "08:00"], "twice daily")

    def test_count_must_match_frequency(self):
        with pytest.raises(ValidationError):
            validate_dose_times(["08:00"], "twice daily")

    def test_string_instead_of_list_rejected(self):
        with pytest.raises(ValidationError):
            validate_dose_times("08:00", "once daily")

    def test_parse_time(self):
        assert parse_time("07:05").hour == 7
        with pytest.raises(ValidationError):
            parse_time("7:5")


class TestDates:
    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError):
            validate_date_range(date(2026, 10, 12), date(2026, 10, 11))

    def test_same_day_ok(self):
        validate_date_range(date(2026, 10, 12), date(2026, 10, 12))

    def test_default_end_date_counts_first_day(self):
        assert default_end_date(date(2026, 10, 12), 5) == date(2026, 10, 16)
        assert default_end_date(date(2026, 10, 12), 1) == date(2026, 10, 12)


class TestConflicts:
    existing = [(7, "Aspirin", ["08:00", "20:00"], date(2026, 10, 10), date(2026, 10, 15))]

    def test_same_time_and_overlapping_dates_conflict(self):
        found = find_time_conflicts(["08:00"], date(2026, 10, 14), date(2026, 10, 20), self.existing)
        assert [(c.medicine_name, c.dose_time) for c in found] == [("Aspirin", "08:00")]

    def test_same_time_but_different_dates_no_conflict(self):
        assert find_time_conflicts(["08:00"], date(2026, 10, 16), date(2026, 10, 20), self.existing) == []

    def test_different_time_no_conflict(self):
        assert find_time_conflicts(["09:00"], date(2026, 10, 12), date(2026, 10, 13), self.existing) == []


class TestPlanning:
    schedule = Schedule(1, 1, ["08:00", "20:00"], date(2026, 10, 12), date(2026, 10, 14))

    def test_expands_all_days(self):
        doses = list(iter_doses(self.schedule, date(2026, 10, 1), date(2026, 10, 31)))
        assert len(doses) == 6
        assert doses[0] == (date(2026, 10, 12), "08:00")

    def test_clipped_to_requested_range(self):
        doses = list(iter_doses(self.schedule, date(2026, 10, 13), date(2026, 10, 13)))
        assert doses == [(date(2026, 10, 13), "08:00"), (date(2026, 10, 13), "20:00")]

    def test_range_outside_schedule_is_empty(self):
        assert list(iter_doses(self.schedule, date(2026, 11, 1), date(2026, 11, 5))) == []
