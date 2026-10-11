"""Walk-through of Module M2 (Medicine & Schedule Management) - run:  python demo.py

Uses an in-memory database with the mock users from db/seed.sql and a fake clock,
so the output is the same every time. Good for the viva / live demo.
"""
from datetime import date, datetime, timedelta

from mrs.database import connect, init_db
from mrs.medicine_schedule import (DoseService, InMemoryReminderGateway, MedicineService,
                                   ScheduleConflictError, UserContext, ValidationError)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def title(text):
    print(f"\n=== {text} ===")


def main():
    conn = connect()
    init_db(conn, with_seed=True)
    clock = Clock(datetime(2026, 10, 12, 7, 0))
    reminders = InMemoryReminderGateway()          # stands in for Module M3
    meds, doses = MedicineService(conn, reminders=reminders, clock=clock), DoseService(conn, clock=clock)

    asha, neha, doctor = UserContext(1, "patient"), UserContext(3, "caregiver"), UserContext(5, "doctor")

    title("UC4 Add Medicine (patient Asha)")
    para = meds.add_medicine(asha, 1, "Paracetamol", "500mg", "twice daily", 5, "Dr. Mehta")
    print(f"Added #{para.medicine_id}: {para.name} {para.dosage}, {para.frequency}, {para.duration_days} days")

    title("Validation: bad dosage is rejected")
    try:
        meds.add_medicine(asha, 1, "Aspirin", "lots", "once daily", 3)
    except ValidationError as err:
        print("Rejected ->", err)

    title("UC7 Schedule Medicine (default times) + reminders registered with M3")
    sched = meds.create_schedule(asha, para.medicine_id, date(2026, 10, 12))
    print(f"Schedule #{sched.schedule_id}: {sched.dose_times} from {sched.start_date} to {sched.end_date}")
    print("Reminders registered with M3:", reminders.registered)

    title("UC7 alternate flow: conflicting time slot")
    aspirin = meds.add_medicine(neha, 1, "Aspirin", "75 mg", "once daily", 3)   # caregiver adds for Asha
    try:
        meds.create_schedule(neha, aspirin.medicine_id, date(2026, 10, 13), ["08:00"])
    except ScheduleConflictError as err:
        print("Warning ->", err)
        meds.create_schedule(neha, aspirin.medicine_id, date(2026, 10, 13), ["09:00"])
        print("Saved with a free slot (09:00) instead")

    title("UC8 View Medication Schedule (calendar 12-13 Oct)")
    for day, entries in meds.get_calendar(asha, 1, date(2026, 10, 12), date(2026, 10, 13)).items():
        for e in entries:
            print(f"{day}  {e.dose_time}  {e.medicine_name:<12} {e.dosage:<7} [{e.status}]")

    title("UC9 Take / Skip Dose")
    clock.now = datetime(2026, 10, 12, 8, 5)
    print("Due now (what Module M3 reminds about):", [(d.medicine_name, d.dose_time) for d in doses.get_due_doses()])
    print("Marked:", doses.mark_taken(asha, sched.schedule_id, date(2026, 10, 12), "08:00").status)

    title("Missed dose (Module M3 calls get_overdue_doses -> mark_missed)")
    clock.now = datetime(2026, 10, 12, 20, 45)
    for d in doses.get_overdue_doses(grace_minutes=30):
        log = doses.mark_missed(d.schedule_id, d.dose_date, d.dose_time)
        print(f"{d.medicine_name} {d.dose_time} -> {log.status}")

    title("UC12 Adherence history (read-only for doctor / Module M4)")
    for log in doses.get_history(doctor, 1):
        print(f"{log.dose_date} {log.dose_time}  {log.status}")
    print("Counts:", doses.count_by_status(doctor, 1))

    title("UC6 Delete Medicine")
    meds.delete_medicine(asha, para.medicine_id)
    print("Remaining medicines:", [m.name for m in meds.list_medicines(asha, 1)])
    print("Reminders cancelled for schedule:", reminders.cancelled)


if __name__ == "__main__":
    main()
