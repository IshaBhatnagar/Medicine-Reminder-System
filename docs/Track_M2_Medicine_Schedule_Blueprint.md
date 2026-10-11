# Track 2: Medicine & Schedule Management (Module M2)
**Responsible Engineer:** Isha Bhatnagar (`@IshaBhatnagar`) - Developer

## 1. Module Overview & Connections
- **Purpose:** Manages medicines, dose schedules, dose logging and dose history for the Medicine Reminder System (SRS 3.1.2; use cases UC4-UC9 and UC12). Enforces who may manage or view a patient's medicines (patient = own data, approved caregiver = linked patient, doctor = read-only, admin = none) and validates all medicine, dosage and timing data.
- **Integration:**
  - **Inputs Received:**
    - `UserContext(user_id, role)` from **M1 (Jay Prakash)** on every call; M2 only *reads* M1's `caregiver_links` (and a local `doctor_patient_links`) table to check access.
    - `mark_missed(schedule_id, dose_date, dose_time)` calls from **M3 (Himanshu Sharma)** when a response window expires.
  - **Outputs Sent:**
    - To **M3**: `register_reminders(schedule_id, dose_times)` / `cancel_reminders(schedule_id)` through the `ReminderGateway` contract (ids and times only, never the whole Schedule object); plus `get_due_doses()` and `get_overdue_doses()` lists.
    - To **M4 (Jyoti Singh)**: read-only `get_history()` and `count_by_status()` for dashboards and adherence reports.
    - To the UI: `get_calendar()`, `list_medicines()`, `get_schedules()`, `get_upcoming_doses()`.

## 2. Workspace
- **Allowed Directories:**
  - `db/` (M2 tables in `schema.sql`; `seed.sql` mock data)
  - `mrs/database.py`
  - `mrs/medicine_schedule/`
  - `tests/medicine_schedule/`
  - `demo.py`, `docs/`
- **Do Not Touch:**
  - `mrs/user_management/` (Owned by M1 / Jay Prakash)
  - `mrs/reminder/` (Owned by M3 / Himanshu Sharma)
  - `mrs/monitoring/` (Owned by M4 / Jyoti Singh)
  - The `users`, `caregiver_links`, `doctor_patient_links` tables are **stubs owned by M1**; M2 never writes to them.

## 3. Deliverables
- **`db/schema.sql` / `db/seed.sql`:** Tables `medicines`, `schedules`, `dose_logs` (plus M1 stub tables) and mock data: 2 patients, 2 caregivers (1 approved, 1 pending), 1 doctor, 1 admin.
- **`mrs/medicine_schedule/validators.py`:** Pure functions - `validate_name`, `validate_dosage`, `validate_frequency`, `validate_duration`, `validate_dose_times`, `validate_date_range`, `default_end_date`, `find_time_conflicts`.
- **`mrs/medicine_schedule/planning.py`:** `iter_doses(schedule, start, end)` expands a schedule into single doses.
- **`mrs/medicine_schedule/repository.py`:** The only file with SQL (`Repository` class).
- **`mrs/medicine_schedule/access.py`:** `SqliteAccessChecker.can_manage()` / `can_view()`, `require_manage()`, `require_view()` (raise `ForbiddenError`).
- **`mrs/medicine_schedule/medicine_service.py`:** `MedicineService`
  - `add_medicine`, `edit_medicine`, `delete_medicine`, `get_medicine`, `list_medicines`
  - `create_schedule`, `update_schedule`, `delete_schedule`, `get_schedules`, `get_calendar`
- **`mrs/medicine_schedule/dose_service.py`:** `DoseService`
  - `mark_taken`, `mark_skipped`, `mark_missed`
  - `get_due_doses`, `get_overdue_doses`, `get_upcoming_doses`
  - `get_history`, `count_by_status`
- **`mrs/medicine_schedule/reminder_gateway.py`:** `ReminderGateway` protocol, `NullReminderGateway`, `InMemoryReminderGateway`.
- **Test Suites:** `tests/medicine_schedule/test_validators.py`, `test_access.py`, `test_medicine_service.py`, `test_schedule_service.py`, `test_dose_service.py` (137 tests).

## 4. The "Vibecoding" System Prompt
```text
You are an expert Python Backend Engineer working on the Medicine Reminder System, Module M2: Medicine & Schedule Management.
Your owner is Isha Bhatnagar (@IshaBhatnagar).

YOUR SCOPE:
- Allowed paths: db/, mrs/database.py, mrs/medicine_schedule/, tests/medicine_schedule/, demo.py, docs/
- DO NOT edit files outside these paths. Tables users, caregiver_links and doctor_patient_links belong to Module M1.

BINDING RULES:
1. Pure Functions & Separation: Validation and schedule maths live in validators.py / planning.py (no database, no clock). SQL lives ONLY in repository.py. Services coordinate: check access -> validate -> repository.
2. Security & Access: Every public service method must check access first (require_manage / require_view). Never trust a patient_id from the caller without the access check. Doctors are read-only; admins have no access.
3. Low Coupling: Talk to Module M3 only through ReminderGateway and pass only schedule_id and dose_times. Expose history to Module M4 only through read-only DoseService methods.
4. Naming: Python and SQL both use snake_case. Dates are datetime.date objects in Python and ISO strings in SQLite.
5. Test-Driven Verification: Write pytest tests first to define the contract, then implement, run the tests, and fix failures on the spot without weakening the assertions.
```

## 5. TDD Execution Plan

### Micro-Chunks
- **Chunk 1: Validation & Planning (`validators.py`, `planning.py`)**
  - Dosage, frequency, duration, dose times, date range, conflict detection, dose expansion.
- **Chunk 2: Database & Repository (`db/`, `database.py`, `repository.py`)**
  - Schema, seed data, all SQL for medicines, schedules and dose logs.
- **Chunk 3: Access Control (`access.py`)**
  - Patient / approved caregiver / read-only doctor / admin rules.
- **Chunk 4: Medicine & Schedule Service (`medicine_service.py`)**
  - UC4-UC8: add, edit, delete, schedule with conflict check, calendar, reminder registration.
- **Chunk 5: Dose Service (`dose_service.py`)**
  - UC9 and UC12: take / skip, missed, due / overdue lists, history.

### Step-by-Step Execution Loop
1. **Step 1 - Generate Tests:** *"Write pytest tests for Chunk 1 in `tests/medicine_schedule/test_validators.py`. Cover valid input, normalisation, invalid input and edge cases."*
2. **Step 2 - Generate Implementation:** *"Now implement `mrs/medicine_schedule/validators.py` to satisfy all tests in `test_validators.py`."*
3. **Step 3 - Run & Verify:** `python -m pytest tests/medicine_schedule/test_validators.py -q` and confirm PASS.
4. **Step 4 - Remediate (If Failed):** Paste the exact pytest output into the prompt: *"Fix the implementation to resolve this failure without changing the test assertions."*
5. **Repeat for Chunks 2 to 5 in order.**

## 6. Developer Work Checklist (Isha)
| # | Task | Status |
|---|---|---|
| 1 | Create GitHub repo and demonstrate version control (Experiment 1) | Done |
| 2 | Feasibility, requirements, SRS, UML and design reports (Experiments 2-8) | Done |
| 3 | M2 database tables and seed data | Done |
| 4 | Validators and schedule planning | Done |
| 5 | Repository, access control and services | Done |
| 6 | 137 pytest tests passing | Done |
| 7 | Push code to GitHub on `feature/medicine-schedule-module` and merge via Pull Request | **To do (commands provided)** |
| 8 | Agree the `ReminderGateway` contract with Himanshu (M3) and the `UserContext` / link tables with Jay (M1) | **To do** |
| 9 | Give Jyoti (M4) the read-only calls `get_history()` and `count_by_status()` | **To do** |
| 10 | Read through the code once and practise `python demo.py` for the viva | **To do** |
