import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aeris.db"))

def migrate():
    print(f"Applying Phase 4 migration to SQLite DB at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Create lecture_sessions table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lecture_sessions (
        id VARCHAR(36) PRIMARY KEY,
        timetable_session_id VARCHAR(36) REFERENCES timetable_sessions(id) ON DELETE SET NULL,
        faculty_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        room_id VARCHAR(36) NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
        subject_name VARCHAR(150) NOT NULL,
        subject_code VARCHAR(50) NOT NULL,
        section VARCHAR(50) NOT NULL DEFAULT 'Section A',
        status VARCHAR(20) NOT NULL DEFAULT 'active',
        started_at DATETIME NOT NULL,
        ended_at DATETIME,
        secret_key VARCHAR(64) NOT NULL
    );
    """)

    # Indices
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_lecture_sessions_faculty ON lecture_sessions(faculty_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_lecture_sessions_room ON lecture_sessions(room_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_lecture_sessions_status ON lecture_sessions(status);")

    # 2. Check and add columns to attendance table
    cursor.execute("PRAGMA table_info(attendance);")
    cols = [row[1] for row in cursor.fetchall()]

    new_cols = [
        ("lecture_session_id", "VARCHAR(36) REFERENCES lecture_sessions(id) ON DELETE SET NULL"),
        ("verification_method", "VARCHAR(50) NOT NULL DEFAULT 'DOUBLE_VERIFICATION'"),
        ("face_score", "FLOAT"),
        ("distance_m", "FLOAT"),
        ("os_biometric_verified", "BOOLEAN DEFAULT 0")
    ]

    for col_name, col_type in new_cols:
        if col_name not in cols:
            print(f"Adding column {col_name} to attendance table...")
            cursor.execute(f"ALTER TABLE attendance ADD COLUMN {col_name} {col_type};")

    conn.commit()
    conn.close()
    print("Phase 4 database migration completed successfully!")

if __name__ == "__main__":
    migrate()
