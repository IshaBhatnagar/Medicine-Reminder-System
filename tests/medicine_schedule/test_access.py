from mrs.medicine_schedule import SqliteAccessChecker, UserContext


def test_patient_manages_only_own_data(conn):
    checker = SqliteAccessChecker(conn)
    assert checker.can_manage(UserContext(1, "patient"), 1)
    assert not checker.can_manage(UserContext(1, "patient"), 2)


def test_approved_caregiver_can_manage(conn):
    assert SqliteAccessChecker(conn).can_manage(UserContext(3, "caregiver"), 1)


def test_pending_caregiver_cannot_manage(conn):
    assert not SqliteAccessChecker(conn).can_manage(UserContext(4, "caregiver"), 2)


def test_doctor_can_view_but_not_manage(conn):
    checker = SqliteAccessChecker(conn)
    doctor = UserContext(5, "doctor")
    assert checker.can_view(doctor, 1)
    assert not checker.can_manage(doctor, 1)
    assert not checker.can_view(doctor, 2)


def test_admin_has_no_access(conn):
    checker = SqliteAccessChecker(conn)
    assert not checker.can_view(UserContext(6, "admin"), 1)
    assert not checker.can_manage(UserContext(6, "admin"), 1)
