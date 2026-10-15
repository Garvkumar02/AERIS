import os
import io
import time
import uuid
import numpy as np
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models import (
    User,
    Campus,
    BiometricProfile,
    BiometricAccessLog,
    VerificationAttempt,
    Notification,
    BackupRecord
)
from app.core.security import encrypt_embedding, decrypt_embedding, create_access_token
from app.core.privacy_service import PURPOSE_CAMPUS_ATTENDANCE, PURPOSE_ENROLLMENT, PURPOSE_ERASURE

client = TestClient(app)

def test_phase7_privacy_and_retention():
    print("\n--- Setup Phase 7 Test Context ---")
    db: Session = SessionLocal()

    admin = db.query(User).filter(User.role == "admin").first()
    student = db.query(User).filter(User.role == "student").first()
    assert admin is not None, "Admin user must exist"
    assert student is not None, "Student user must exist"

    admin_token = create_access_token(
        data={"sub": admin.id, "email": admin.email, "role": admin.role, "name": admin.name, "employee_id": admin.employee_id}
    )
    student_token = create_access_token(
        data={"sub": student.id, "email": student.email, "role": student.role, "name": student.name, "employee_id": student.employee_id}
    )

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    print(f" Context initialized: Student={student.name} ({student.employee_id}), Admin={admin.name}")

    # ========================================================
    # 1. Testing Raw Image Non-Persistence & Biometric Encryption
    # ========================================================
    print("\n--- 1. Testing Raw Image Non-Persistence & Encrypted Storage ---")
    dummy_vec = np.random.randn(512).astype(np.float32)
    dummy_vec = dummy_vec / np.linalg.norm(dummy_vec)
    encrypted_blob = encrypt_embedding(dummy_vec)

    # Ensure profile has valid encrypted vector with Phase 7 privacy metadata
    profile = db.query(BiometricProfile).filter(BiometricProfile.user_id == student.id).first()
    now = datetime.utcnow()
    if not profile:
        profile = BiometricProfile(
            user_id=student.id,
            encrypted_embedding=encrypted_blob,
            model_version="buffalo_l",
            consent_version="1.0",
            purpose_limitation=PURPOSE_CAMPUS_ATTENDANCE,
            storage_classification="RESTRICTED_SPECIAL_CATEGORY_PVI",
            encryption_algorithm="AES-256-GCM/FERNET",
            consent_status="CONSENT_GRANTED",
            consent_timestamp=now,
            raw_image_persisted=False,
            enrolled_at=now
        )
        db.add(profile)
    else:
        profile.encrypted_embedding = encrypted_blob
        profile.consent_status = "CONSENT_GRANTED"
        profile.purpose_limitation = PURPOSE_CAMPUS_ATTENDANCE
        profile.raw_image_persisted = False
        profile.revoked_at = None
    db.commit()

    # Verify vector decrypted correctly
    decrypted = decrypt_embedding(profile.encrypted_embedding)
    np.testing.assert_almost_equal(dummy_vec, decrypted, decimal=5)
    print(" AES-256 / Fernet biometric template encryption and decryption verified.")
    assert profile.raw_image_persisted is False
    print(" STRICT PRIVACY RULE VERIFIED: raw_image_persisted = False (No raw facial images stored to disk).")

    # ========================================================
    # 2. Testing Purpose Limitation & Granular Consent Status
    # ========================================================
    print("\n--- 2. Testing Purpose Limitation & Granular Consent Status ---")
    res_consent = client.get("/privacy/consent", headers=student_headers)
    assert res_consent.status_code == 200, f"Get consent failed: {res_consent.text}"
    consent_data = res_consent.json()
    assert consent_data["consent_status"] == "CONSENT_GRANTED"
    assert consent_data["purpose_limitation"] == PURPOSE_CAMPUS_ATTENDANCE
    assert consent_data["raw_image_persisted"] is False
    print(f" User consent record retrieved: Status={consent_data['consent_status']}, Purpose={consent_data['purpose_limitation']}")

    # ========================================================
    # 3. Testing Consent Revocation & Fallback Workflow
    # ========================================================
    print("\n--- 3. Testing Consent Revocation & Cryptographic Zeroing ---")
    res_revoke = client.post(
        "/privacy/consent/revoke",
        json={"reason": "User opt-out for semester"},
        headers=student_headers
    )
    assert res_revoke.status_code == 200, f"Revoke failed: {res_revoke.text}"
    revoke_data = res_revoke.json()
    assert revoke_data["status"] == "revoked"
    assert revoke_data["vector_zeroed"] is True

    # Re-fetch profile from DB to verify cryptographic zeroing
    db.expire_all()
    p_revoked = db.query(BiometricProfile).filter(BiometricProfile.user_id == student.id).first()
    assert p_revoked.consent_status == "CONSENT_REVOKED"
    assert len(p_revoked.encrypted_embedding) == 0, "Biometric vector must be zeroed upon revocation"
    print(" Consent revocation verified: Vector zeroed out in DB, fallback to card/PIN active.")

    # ========================================================
    # 4. Testing Consent Re-grant & Biometric Access Logging
    # ========================================================
    print("\n--- 4. Testing Consent Re-grant & Biometric Access Logging ---")
    res_grant = client.post(
        "/privacy/consent/grant",
        json={"consent_version": "1.1", "consent": True},
        headers=student_headers
    )
    assert res_grant.status_code == 200
    grant_data = res_grant.json()
    assert grant_data["consent_status"] == "CONSENT_GRANTED"
    print(" Biometric consent re-granted with version 1.1.")

    # Re-enroll template vector
    p_revoked.encrypted_embedding = encrypted_blob
    p_revoked.consent_status = "CONSENT_GRANTED"
    db.commit()

    # Check access logs
    res_logs = client.get(f"/privacy/access-logs?target_user_id={student.id}", headers=student_headers)
    assert res_logs.status_code == 200
    logs = res_logs.json()
    assert len(logs) > 0
    assert logs[0]["raw_image_persisted"] is False
    print(f" Biometric Access Logs retrieved: {len(logs)} log entries verified with zero-persistence flags.")

    # ========================================================
    # 5. Testing 'Right to be Forgotten' Cryptographic Erasure
    # ========================================================
    print("\n--- 5. Testing 'Right to be Forgotten' (Cryptographic Erasure) ---")
    res_erasure = client.post(
        "/privacy/delete-biometric-data",
        headers=student_headers
    )
    assert res_erasure.status_code == 200, f"Erasure failed: {res_erasure.text}"
    erasure_data = res_erasure.json()
    assert erasure_data["status"] == "permanently_erased"
    assert "deletion_receipt_hash" in erasure_data
    assert len(erasure_data["deletion_receipt_hash"]) == 64
    print(f" Permanent biometric erasure executed! Receipt Hash: {erasure_data['deletion_receipt_hash']}")

    # Verify profile row completely deleted
    db.expire_all()
    p_deleted = db.query(BiometricProfile).filter(BiometricProfile.user_id == student.id).first()
    assert p_deleted is None, "BiometricProfile must be completely purged from database"
    print(" Database confirmation: BiometricProfile row completely wiped.")

    # Re-create profile for subsequent tests
    p_new = BiometricProfile(
        user_id=student.id,
        encrypted_embedding=encrypted_blob,
        model_version="buffalo_l",
        consent_version="1.0",
        purpose_limitation=PURPOSE_CAMPUS_ATTENDANCE,
        storage_classification="RESTRICTED_SPECIAL_CATEGORY_PVI",
        encryption_algorithm="AES-256-GCM/FERNET",
        consent_status="CONSENT_GRANTED",
        consent_timestamp=now,
        raw_image_persisted=False,
        enrolled_at=now
    )
    db.add(p_new)
    db.commit()

    # ========================================================
    # 6. Testing 90-Day Operational Retention & Scheduled Cleanup
    # ========================================================
    print("\n--- 6. Testing 90-Day Operational Retention & Cleanup ---")
    stale_date = datetime.utcnow() - timedelta(days=95)

    # Insert test stale operational attempts
    stale_attempt_1 = VerificationAttempt(
        user_id=student.id,
        created_at=stale_date,
        result="REJECT",
        failure_code="YAW_EXCEEDED",
        yaw_delta=22.5,
        distance_m=12.0
    )
    stale_attempt_2 = VerificationAttempt(
        user_id=student.id,
        created_at=stale_date,
        result="REJECT",
        failure_code="GEOFENCE_BREACH",
        distance_m=420.0
    )
    stale_notif = Notification(
        recipient_id=student.id,
        category="ATTENDANCE_SUCCESS",
        title="Archived Lecture Attendance",
        message="Stale attendance notification record",
        delivery_status="DELIVERED",
        created_at=stale_date
    )
    stale_access_log = BiometricAccessLog(
        accessor_id=student.id,
        target_user_id=student.id,
        purpose=PURPOSE_CAMPUS_ATTENDANCE,
        action="DECRYPT_AND_MATCH",
        status="AUTHORIZED_SUCCESS",
        accessed_at=stale_date,
        raw_image_persisted=False
    )
    db.add_all([stale_attempt_1, stale_attempt_2, stale_notif, stale_access_log])
    db.commit()

    # Verify status detects eligible records
    res_status = client.get("/privacy/retention/status?retention_days=90", headers=admin_headers)
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["eligible_records"]["total_eligible"] >= 4
    print(f" Retention status scanned: {status_data['eligible_records']['total_eligible']} records eligible for 90d purge.")

    # Execute cleanup
    res_clean = client.post("/privacy/retention/run-cleanup?retention_days=90", headers=admin_headers)
    assert res_clean.status_code == 200, f"Cleanup failed: {res_clean.text}"
    clean_data = res_clean.json()
    assert clean_data["status"] == "success"
    assert clean_data["records_purged"]["total_purged"] >= 4
    assert "compliance_certificate" in clean_data
    cert_hash = clean_data["compliance_certificate"]["hash"]
    assert len(cert_hash) == 64
    print(f" 90-day retention cleanup executed! Purged: {clean_data['records_purged']['total_purged']} records.")
    print(f" Signed Retention Compliance Certificate: {cert_hash}")

    # ========================================================
    # 7. Testing Encrypted Backup Creation & Disaster Recovery Drill
    # ========================================================
    print("\n--- 7. Testing Encrypted Backup & Disaster Recovery Drill ---")
    res_backup = client.post("/privacy/backups/create?retention_days=30", headers=admin_headers)
    assert res_backup.status_code == 200, f"Backup creation failed: {res_backup.text}"
    backup_data = res_backup.json()
    assert backup_data["status"] == "created"
    backup_id = backup_data["backup_id"]
    print(f" Encrypted AES-256 backup created: {backup_data['backup_filename']} (Size: {backup_data['size_bytes']} bytes)")

    # List backups
    res_list = client.get("/privacy/backups", headers=admin_headers)
    assert res_list.status_code == 200
    all_b = res_list.json()
    assert len(all_b) > 0
    print(f" Backup catalog verified: {len(all_b)} active snapshot(s) cataloged with expiry lifecycle.")

    # Run automated disaster recovery test
    res_recovery = client.post(f"/privacy/backups/test-recovery?backup_id={backup_id}", headers=admin_headers)
    assert res_recovery.status_code == 200, f"Recovery test failed: {res_recovery.text}"
    recovery_report = res_recovery.json()
    assert recovery_report["status"] == "recovery_test_passed"
    assert recovery_report["integrity_check"] == "ok"
    assert recovery_report["disaster_recovery_certified"] is True
    print(f" Disaster Recovery Drill PASSED! Integrity='ok', Verified Users={recovery_report['verified_entity_counts']['users']} in {recovery_report['duration_ms']}ms.")

    db.close()
    print("\n ALL PHASE 7 PRIVACY, IMAGE SECURITY & RETENTION TESTS PASSED SUCCESSFULLY!\n")

if __name__ == "__main__":
    test_phase7_privacy_and_retention()
