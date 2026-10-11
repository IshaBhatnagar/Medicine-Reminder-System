# Medicine Reminder System (MRS)

Software Engineering project - KIET Deemed To Be University (Section B)

| Name | Role | Module |
|---|---|---|
| Isha Bhatnagar | Developer | **M2 - Medicine & Schedule Management** (this code) |
| Jay Prakash | Domain Expert | M1 - User & Account Management |
| Himanshu Sharma | Tester | M3 - Reminder & Notification |
| Jyoti Singh | Advisor | M4 - Monitoring, Reports & Dashboards |

## Module M2 - what it does
Medicines, dose schedules, dose logging and dose history (use cases UC4-UC9, UC12).

| Use case | Method |
|---|---|
| UC4 Add Medicine | `MedicineService.add_medicine` |
| UC5 Edit Medicine | `MedicineService.edit_medicine` |
| UC6 Delete Medicine | `MedicineService.delete_medicine` |
| UC7 Schedule Medicine | `MedicineService.create_schedule` / `update_schedule` |
| UC8 View Medication Schedule | `MedicineService.get_calendar`, `list_medicines`, `get_schedules` |
| UC9 Take / Skip Dose | `DoseService.mark_taken` / `mark_skipped` |
| UC12 Adherence history | `DoseService.get_history`, `count_by_status` |

## How the other modules connect
* **M1 (Jay)** gives each call a `UserContext(user_id, role)`. M2 only reads M1's `caregiver_links` table to check access.
* **M3 (Himanshu)** implements `ReminderGateway` (`register_reminders`, `cancel_reminders`) and calls
  `DoseService.get_due_doses()`, `get_overdue_doses()` and `mark_missed()`.
* **M4 (Jyoti)** reads `DoseService.get_history()` / `count_by_status()` (read-only).

## Run
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -v          # 137 tests
python demo.py               # live walk-through of the module
```

## Structure
```
db/schema.sql, db/seed.sql        tables (M1 stub tables + M2 tables) and mock data
mrs/database.py                   SQLite connection + init
mrs/medicine_schedule/            Module M2
    validators.py planning.py     pure functions
    repository.py                 the only file with SQL
    medicine_service.py           medicines + schedules
    dose_service.py               dose logs, due/overdue, history
    access.py                     who may manage / view
    reminder_gateway.py           contract with M3
tests/medicine_schedule/          pytest suite
demo.py                           demo script
docs/                             blueprint and experiment reports
```
