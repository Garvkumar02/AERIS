import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aeris.db"))

def migrate():
    print(f"Applying Room Presence migration to SQLite DB at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Create room_presences table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS room_presences (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        room_id VARCHAR(36) NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
        check_in_at DATETIME NOT NULL,
        check_out_at DATETIME,
        verification_method VARCHAR(50) NOT NULL,
        device_id VARCHAR(255),
        evidence_payload JSON,
        status VARCHAR(20) NOT NULL DEFAULT 'active',
        prev_hash VARCHAR(64),
        presence_hash VARCHAR(64) NOT NULL
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_room_presences_user ON room_presences(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_room_presences_room ON room_presences(room_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_room_presences_checkin ON room_presences(check_in_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_room_presences_hash ON room_presences(presence_hash);")

    # 2. Check and add columns to rooms table
    cursor.execute("PRAGMA table_info(rooms);")
    cols = [row[1] for row in cursor.fetchall()]

    new_cols = [
        ("authorized_roles", "JSON"),
        ("indoor_beacon_uuid", "VARCHAR(100)"),
        ("wifi_bssid", "VARCHAR(50)"),
        ("qr_secret", "VARCHAR(64)")
    ]

    for col_name, col_type in new_cols:
        if col_name not in cols:
            print(f"Adding column {col_name} to rooms table...")
            cursor.execute(f"ALTER TABLE rooms ADD COLUMN {col_name} {col_type};")

    conn.commit()
    conn.close()
    print("Room Presence database migration completed successfully!")

if __name__ == "__main__":
    migrate()
