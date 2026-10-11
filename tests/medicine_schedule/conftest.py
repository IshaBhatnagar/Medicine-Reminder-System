from datetime import date, datetime, timedelta

import pytest

from mrs.database import connect, init_db
from mrs.medicine_schedule import DoseService, InMemoryReminderGateway, MedicineService, UserContext


class FakeClock:
    """A clock the tests can move forward."""

    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


@pytest.fixture
def conn():
    connection = connect()
    init_db(connection, with_seed=True)
    yield connection
    connection.close()


@pytest.fixture
def clock():
    return FakeClock(datetime(2026, 10, 12, 7, 0))


@pytest.fixture
def gateway():
    return InMemoryReminderGateway()


@pytest.fixture
def meds(conn, clock, gateway):
    return MedicineService(conn, reminders=gateway, clock=clock)


@pytest.fixture
def doses(conn, clock):
    return DoseService(conn, clock=clock)


# --- people from db/seed.sql -------------------------------------------------
@pytest.fixture
def patient():
    return UserContext(1, "patient")


@pytest.fixture
def other_patient():
    return UserContext(2, "patient")


@pytest.fixture
def caregiver():          # approved caregiver of patient 1
    return UserContext(3, "caregiver")


@pytest.fixture
def pending_caregiver():  # link to patient 2 is still pending
    return UserContext(4, "caregiver")


@pytest.fixture
def doctor():             # treats patient 1
    return UserContext(5, "doctor")


@pytest.fixture
def admin():
    return UserContext(6, "admin")


# --- ready-made data ---------------------------------------------------------
@pytest.fixture
def paracetamol(meds, patient):
    return meds.add_medicine(patient, 1, "Paracetamol", "500 mg", "twice daily", 5, "Dr. Mehta")


@pytest.fixture
def schedule(meds, patient, paracetamol):
    """08:00 and 20:00 from 12 Oct to 16 Oct 2026."""
    return meds.create_schedule(patient, paracetamol.medicine_id, date(2026, 10, 12))
