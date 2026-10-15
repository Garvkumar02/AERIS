#!/usr/bin/env python3
"""
AERIS Biometric Embedding Re-Encryption & Key Migration Utility.
Allows safely rotating the primary Fernet biometric encryption key.
Decodes embeddings using old key, re-encrypts using new key, and validates round-trip integrity.
"""
import sys
import os
import argparse
import base64
import numpy as np
from cryptography.fernet import Fernet

# Add parent directory to path so app modules can be loaded
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models import BiometricProfile, AuditLog
from app.config import settings

def validate_key(k: str) -> bytes:
    key_bytes = k.strip().encode("utf-8")
    try:
        decoded = base64.urlsafe_b64decode(key_bytes)
        if len(decoded) != 32:
            raise ValueError("Key must decode to exactly 32 bytes")
        return key_bytes
    except Exception as e:
        raise ValueError(f"Invalid Fernet key format: {e}")

def migrate_embeddings(old_key_str: str, new_key_str: str, dry_run: bool = False):
    old_key = validate_key(old_key_str)
    new_key = validate_key(new_key_str)

    if old_key == new_key:
        print("ERROR: Old key and new key are identical. Nothing to migrate.")
        return

    fernet_old = Fernet(old_key)
    fernet_new = Fernet(new_key)

    db = SessionLocal()
    try:
        profiles = db.query(BiometricProfile).all()
        print(f"[*] Found {len(profiles)} biometric profiles to migrate.")
        
        migrated_count = 0
        for p in profiles:
            try:
                # 1. Decrypt using old key
                raw_bytes = fernet_old.decrypt(p.encrypted_embedding)
                vector = np.frombuffer(raw_bytes, dtype=np.float32)
                
                # 2. Re-encrypt using new key
                new_ciphertext = fernet_new.encrypt(vector.astype(np.float32).tobytes())
                
                # 3. Verify round-trip decryption with new key
                verify_bytes = fernet_new.decrypt(new_ciphertext)
                verify_vector = np.frombuffer(verify_bytes, dtype=np.float32)
                
                if not np.array_equal(vector, verify_vector):
                    raise RuntimeError(f"Vector verification mismatch for user_id={p.user_id}")
                
                if not dry_run:
                    p.encrypted_embedding = new_ciphertext
                
                migrated_count += 1
                print(f" [+] Profile for user_id={p.user_id} successfully re-encrypted.")
            except Exception as ex:
                db.rollback()
                print(f" [!] FAILED migrating profile user_id={p.user_id}: {ex}")
                print(" [!] Transaction rolled back. Aborting.")
                return False

        if dry_run:
            print(f"\n[DRY RUN COMPLETE] {migrated_count}/{len(profiles)} profiles verified. No database changes committed.")
        else:
            # Record audit log entry
            audit = AuditLog(
                actor_id="SYSTEM_CLI",
                action="BIOMETRIC_KEY_ROTATION",
                entity="biometric_profiles",
                entity_id="ALL",
                metadata_json={"migrated_count": migrated_count}
            )
            db.add(audit)
            db.commit()
            print(f"\n[MIGRATION SUCCESS] {migrated_count}/{len(profiles)} biometric profiles re-encrypted and committed.")
            print("Remember to update FERNET_KEY in your .env to the new key now.")
        return True
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AERIS Biometric Key Migration Utility")
    parser.add_argument("--old-key", required=True, help="Current/old Fernet key")
    parser.add_argument("--new-key", required=True, help="New target Fernet key")
    parser.add_argument("--dry-run", action="store_true", help="Simulate re-encryption and verify without committing to DB")
    args = parser.parse_args()

    migrate_embeddings(args.old_key, args.new_key, dry_run=args.dry_run)
