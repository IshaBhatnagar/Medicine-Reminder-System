PRAGMA foreign_keys = ON;

-- =====================================================================
-- STUB TABLES  (owned by Module M1 - User & Account Management, Jay Prakash)
-- They exist ONLY so that Module M2 can run and be tested on its own.
-- M1 replaces them with the real tables; M2 never writes to them.
-- =====================================================================
CREATE TABLE IF NOT EXISTS users (
    user_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    email    TEXT NOT NULL UNIQUE,
    role     TEXT NOT NULL CHECK (role IN ('patient', 'caregiver', 'doctor', 'admin')),
    status   TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS caregiver_links (
    link_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    caregiver_id  INTEGER NOT NULL REFERENCES users(user_id),
    patient_id    INTEGER NOT NULL REFERENCES users(user_id),
    status        TEXT NOT NULL DEFAULT 'approved' CHECK (status IN ('pending', 'approved', 'revoked')),
    UNIQUE (caregiver_id, patient_id)
);

CREATE TABLE IF NOT EXISTS doctor_patient_links (
    doctor_id   INTEGER NOT NULL REFERENCES users(user_id),
    patient_id  INTEGER NOT NULL REFERENCES users(user_id),
    PRIMARY KEY (doctor_id, patient_id)
);

-- =====================================================================
-- MODULE M2 TABLES  (owned by Isha Bhatnagar)
-- =====================================================================
CREATE TABLE IF NOT EXISTS medicines (
    medicine_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id          INTEGER NOT NULL REFERENCES users(user_id),
    name                TEXT NOT NULL,
    dosage              TEXT NOT NULL,
    frequency           TEXT NOT NULL CHECK (frequency IN ('once daily', 'twice daily', 'thrice daily')),
    duration_days       INTEGER NOT NULL CHECK (duration_days BETWEEN 1 AND 365),
    prescribing_doctor  TEXT,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_medicines_patient ON medicines (patient_id);

-- A medicine has one or more schedules (class diagram: Medicine 1 --> 1..* Schedule)
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id  INTEGER NOT NULL REFERENCES medicines(medicine_id) ON DELETE CASCADE,
    dose_times   TEXT NOT NULL,          -- comma separated 24h times, e.g. '08:00,20:00'
    start_date   TEXT NOT NULL,          -- ISO date
    end_date     TEXT NOT NULL           -- ISO date
);
CREATE INDEX IF NOT EXISTS idx_schedules_medicine ON schedules (medicine_id);

-- One row per scheduled dose that has been taken / skipped / missed
CREATE TABLE IF NOT EXISTS dose_logs (
    log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id  INTEGER NOT NULL REFERENCES schedules(schedule_id) ON DELETE CASCADE,
    dose_date    TEXT NOT NULL,
    dose_time    TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('taken', 'skipped', 'missed')),
    logged_at    TEXT NOT NULL,
    UNIQUE (schedule_id, dose_date, dose_time)
);
CREATE INDEX IF NOT EXISTS idx_dose_logs_schedule ON dose_logs (schedule_id, dose_date);
