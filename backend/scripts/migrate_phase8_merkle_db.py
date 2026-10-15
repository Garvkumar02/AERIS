import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aeris.db"))

def migrate():
    print(f"Applying Phase 8 Merkle Commitment & Audit Verification Logs migration to: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Create merkle_commitments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS merkle_commitments (
        id VARCHAR(36) PRIMARY KEY,
        day DATE NOT NULL,
        merkle_root VARCHAR(64) NOT NULL,
        anchor_network VARCHAR(50) NOT NULL DEFAULT 'ETHEREUM_SEPOLIA_ANCHOR',
        transaction_hash VARCHAR(66) NOT NULL,
        block_number INTEGER NOT NULL,
        event_count INTEGER NOT NULL DEFAULT 0,
        tree_depth INTEGER NOT NULL DEFAULT 0,
        leaf_hashes JSON NOT NULL DEFAULT '[]',
        status VARCHAR(50) NOT NULL DEFAULT 'ANCHORED_ON_CHAIN',
        anchored_by_user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_merkle_commitments_day ON merkle_commitments(day);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_merkle_commitments_root ON merkle_commitments(merkle_root);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_merkle_commitments_created ON merkle_commitments(created_at);")

    # 2. Create audit_verification_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_verification_logs (
        id VARCHAR(36) PRIMARY KEY,
        verified_by_user_id VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
        verification_type VARCHAR(50) NOT NULL DEFAULT 'CONSOLIDATED_FULL_AUDIT',
        attendance_chain_valid BOOLEAN NOT NULL DEFAULT 1,
        gate_chain_valid BOOLEAN NOT NULL DEFAULT 1,
        presence_chain_valid BOOLEAN NOT NULL DEFAULT 1,
        overall_tamper_free BOOLEAN NOT NULL DEFAULT 1,
        total_records_audited INTEGER NOT NULL DEFAULT 0,
        attendance_count INTEGER NOT NULL DEFAULT 0,
        gate_count INTEGER NOT NULL DEFAULT 0,
        presence_count INTEGER NOT NULL DEFAULT 0,
        tampered_records JSON NOT NULL DEFAULT '[]',
        details JSON NOT NULL DEFAULT '{}',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_created ON audit_verification_logs(created_at);")

    conn.commit()
    conn.close()
    print("Phase 8 Migration completed successfully!")

if __name__ == "__main__":
    migrate()
