import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aeris.db"))

def migrate():
    print(f"Applying Phase 6 Notifications & Mentor Alerts migration to SQLite DB at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Add mentor_id to users table if not exists
    cursor.execute("PRAGMA table_info(users);")
    cols = [row[1] for row in cursor.fetchall()]
    if "mentor_id" not in cols:
        print("Adding column mentor_id to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN mentor_id VARCHAR(36) REFERENCES users(id);")

    # 2. Create notifications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id VARCHAR(36) PRIMARY KEY,
        recipient_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        category VARCHAR(50) NOT NULL,
        title VARCHAR(200) NOT NULL,
        message TEXT NOT NULL,
        priority VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
        channel VARCHAR(30) NOT NULL DEFAULT 'IN_APP',
        delivery_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
        retry_count INTEGER NOT NULL DEFAULT 0,
        max_retries INTEGER NOT NULL DEFAULT 3,
        last_attempt_at DATETIME,
        delivered_at DATETIME,
        read_at DATETIME,
        is_read BOOLEAN NOT NULL DEFAULT 0,
        dedup_key VARCHAR(128),
        metadata_payload JSON,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_notif_recipient ON notifications(recipient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_notif_category ON notifications(category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_notif_status ON notifications(delivery_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_notif_dedup ON notifications(dedup_key);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_notif_created ON notifications(created_at);")

    # 3. Create mentor_alerts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mentor_alerts (
        id VARCHAR(36) PRIMARY KEY,
        student_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        mentor_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        lecture_session_id VARCHAR(36) REFERENCES lecture_sessions(id) ON DELETE SET NULL,
        timetable_session_id VARCHAR(36) REFERENCES timetable_sessions(id) ON DELETE SET NULL,
        subject_name VARCHAR(150) NOT NULL,
        subject_code VARCHAR(50) NOT NULL,
        room_number VARCHAR(50),
        absence_duration_minutes INTEGER NOT NULL DEFAULT 10,
        gate_presence_status VARCHAR(50) DEFAULT 'UNKNOWN',
        room_presence_status VARCHAR(50) DEFAULT 'NOT_IN_ASSIGNED_ROOM',
        status VARCHAR(50) NOT NULL DEFAULT 'ADVISORY_PENDING',
        is_misconduct_charge BOOLEAN NOT NULL DEFAULT 0,
        disclaimer VARCHAR(255) NOT NULL DEFAULT 'Advisory wellness inquiry only. Not a disciplinary finding or misconduct charge.',
        mentor_notes TEXT,
        triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        resolved_at DATETIME,
        notification_id VARCHAR(36) REFERENCES notifications(id) ON DELETE SET NULL
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_mentor_alerts_student ON mentor_alerts(student_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_mentor_alerts_mentor ON mentor_alerts(mentor_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_mentor_alerts_status ON mentor_alerts(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_mentor_alerts_time ON mentor_alerts(triggered_at);")

    # 4. Link seeded faculty to students as mentors if not already assigned
    cursor.execute("SELECT id FROM users WHERE role = 'faculty' LIMIT 1;")
    fac_row = cursor.fetchone()
    if fac_row:
        faculty_id = fac_row[0]
        cursor.execute("UPDATE users SET mentor_id = ? WHERE role = 'student' AND (mentor_id IS NULL OR mentor_id = '');", (faculty_id,))
        print(f"Assigned default faculty mentor {faculty_id} to students.")

    conn.commit()
    conn.close()
    print("Phase 6 Notifications & Mentor Alerts DB migration finished successfully!")

if __name__ == "__main__":
    migrate()
