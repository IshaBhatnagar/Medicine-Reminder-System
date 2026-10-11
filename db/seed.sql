-- Mock data for LOCAL DEVELOPMENT ONLY (stands in for Module M1's real accounts)
INSERT INTO users (user_id, name, email, role) VALUES
    (1, 'Asha Verma',  'asha@example.com',  'patient'),
    (2, 'Ravi Kumar',  'ravi@example.com',  'patient'),
    (3, 'Neha Verma',  'neha@example.com',  'caregiver'),
    (4, 'Sunil Rao',   'sunil@example.com', 'caregiver'),
    (5, 'Dr. Mehta',   'mehta@example.com', 'doctor'),
    (6, 'Admin User',  'admin@example.com', 'admin');

-- Neha (3) is an approved caregiver of Asha (1). Sunil (4) request for Ravi (2) is still pending.
INSERT INTO caregiver_links (caregiver_id, patient_id, status) VALUES
    (3, 1, 'approved'),
    (4, 2, 'pending');

-- Dr. Mehta (5) treats Asha (1)
INSERT INTO doctor_patient_links (doctor_id, patient_id) VALUES (5, 1);
