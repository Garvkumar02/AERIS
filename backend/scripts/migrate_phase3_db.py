import sqlite3
import os

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aeris.db"))
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# 1. Ensure visitor_passes table exists
cur.execute("""
CREATE TABLE IF NOT EXISTS visitor_passes (
    id VARCHAR(36) PRIMARY KEY,
    visitor_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    host_user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    purpose VARCHAR(255) NOT NULL,
    badge_number VARCHAR(50) NOT NULL,
    valid_from DATETIME NOT NULL,
    valid_until DATETIME NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active'
);
""")

# 2. Ensure gate_devices table exists
cur.execute("""
CREATE TABLE IF NOT EXISTS gate_devices (
    id VARCHAR(36) PRIMARY KEY,
    device_id VARCHAR(100) UNIQUE NOT NULL,
    gate_id VARCHAR(50) NOT NULL,
    gate_name VARCHAR(150) NOT NULL,
    location VARCHAR(150) DEFAULT 'Main Campus Entry',
    status VARCHAR(50) NOT NULL DEFAULT 'authorized',
    api_key_hash VARCHAR(64),
    registered_at DATETIME,
    last_heartbeat DATETIME
);
""")

# 3. Ensure gate_events table exists
cur.execute("""
CREATE TABLE IF NOT EXISTS gate_events (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    gate_id VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    guard_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
    override_reason VARCHAR(255),
    device_id VARCHAR(255) NOT NULL,
    timestamp DATETIME NOT NULL,
    client_event_id VARCHAR(64),
    synced_offline BOOLEAN NOT NULL DEFAULT 0,
    offline_device_timestamp DATETIME,
    prev_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL
);
""")

# 4. Check if client_event_id column exists on gate_events
cur.execute("PRAGMA table_info(gate_events);")
cols = [c[1] for c in cur.fetchall()]
if "client_event_id" not in cols:
    try:
        cur.execute("ALTER TABLE gate_events ADD COLUMN client_event_id VARCHAR(64);")
        print("Added client_event_id column to gate_events.")
    except Exception as e:
        print(f"Error adding client_event_id: {e}")

# 5. Create indices
indices = [
    "CREATE INDEX IF NOT EXISTS idx_gate_events_user ON gate_events(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_gate_events_gate ON gate_events(gate_id);",
    "CREATE INDEX IF NOT EXISTS idx_gate_events_time ON gate_events(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_gate_events_client_id ON gate_events(client_event_id);",
    "CREATE INDEX IF NOT EXISTS idx_visitor_passes_badge ON visitor_passes(badge_number);",
    "CREATE INDEX IF NOT EXISTS idx_gate_devices_dev_id ON gate_devices(device_id);"
]

for idx in indices:
    cur.execute(idx)

conn.commit()
conn.close()
print("Phase 3 gate access & offline sync database migration complete.")
