import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aeris.db"))

def migrate():
    print(f"Applying Phase 7 Privacy, Image Security & Retention migration to SQLite DB at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Update biometric_profiles table with privacy & purpose limitation columns
    cursor.execute("PRAGMA table_info(biometric_profiles);")
    cols = [row[1] for row in cursor.fetchall()]

    new_cols = [
        ("purpose_limitation", "VARCHAR(100) DEFAULT 'CAMPUS_IDENTITY_AND_ATTENDANCE_ONLY'"),
        ("storage_classification", "VARCHAR(50) DEFAULT 'RESTRICTED_SPECIAL_CATEGORY_PVI'"),
        ("encryption_algorithm", "VARCHAR(50) DEFAULT 'AES-256-GCM/FERNET'"),
        ("consent_status", "VARCHAR(50) DEFAULT 'CONSENT_GRANTED'"),
        ("consent_timestamp", "DATETIME"),
        ("revoked_timestamp", "DATETIME"),
        ("deletion_receipt_hash", "VARCHAR(64)"),
        ("raw_image_persisted", "BOOLEAN DEFAULT 0")
    ]

    for col_name, col_def in new_cols:
        if col_name not in cols:
            print(f"Adding column {col_name} to biometric_profiles table...")
            cursor.execute(f"ALTER TABLE biometric_profiles ADD COLUMN {col_name} {col_def};")

    # 2. Create biometric_access_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS biometric_access_logs (
        id VARCHAR(36) PRIMARY KEY,
        accessor_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        target_user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        purpose VARCHAR(100) NOT NULL,
        action VARCHAR(50) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'AUTHORIZED_SUCCESS',
        client_ip VARCHAR(50),
        user_agent VARCHAR(255),
        raw_image_persisted BOOLEAN NOT NULL DEFAULT 0,
        accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_bio_acc_accessor ON biometric_access_logs(accessor_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_bio_acc_target ON biometric_access_logs(target_user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_bio_acc_accessed_at ON biometric_access_logs(accessed_at);")

    # 3. Create retention_run_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS retention_run_logs (
        id VARCHAR(36) PRIMARY KEY,
        run_by_user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        retention_threshold_days INTEGER NOT NULL DEFAULT 90,
        cutoff_date DATETIME NOT NULL,
        verification_attempts_purged INTEGER NOT NULL DEFAULT 0,
        notifications_purged INTEGER NOT NULL DEFAULT 0,
        access_logs_purged INTEGER NOT NULL DEFAULT 0,
        total_records_purged INTEGER NOT NULL DEFAULT 0,
        compliance_cert_hash VARCHAR(64) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'COMPLETED',
        executed_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_ret_run_executed ON retention_run_logs(executed_at);")

    # 4. Create backup_records table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backup_records (
        id VARCHAR(36) PRIMARY KEY,
        backup_filename VARCHAR(255) NOT NULL,
        backup_path VARCHAR(500) NOT NULL,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        sha256_checksum VARCHAR(64) NOT NULL,
        encryption_cipher VARCHAR(50) NOT NULL DEFAULT 'AES-256-GCM/FERNET',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME NOT NULL,
        is_expired BOOLEAN NOT NULL DEFAULT 0,
        recovery_tested BOOLEAN NOT NULL DEFAULT 0,
        last_recovery_test_at DATETIME,
        last_recovery_status VARCHAR(50)
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_backup_expires ON backup_records(expires_at);")

    conn.commit()
    conn.close()
    print("Phase 7 Privacy migration completed successfully.")

if __name__ == "__main__":
    migrate()
