import sqlite3
import os

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aeris.db"))
conn = sqlite3.connect(db_path)
cur = conn.cursor()

columns_to_add = [
    ('department', 'VARCHAR(100) DEFAULT "CSE"'),
    ('designation', 'VARCHAR(100)'),
    ('phone', 'VARCHAR(30)')
]

for col, col_type in columns_to_add:
    try:
        cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
        print(f"Added {col} to users table.")
    except Exception as e:
        print(f"{col}: {e}")

conn.commit()
conn.close()
print("Phase 2 database column check complete.")
