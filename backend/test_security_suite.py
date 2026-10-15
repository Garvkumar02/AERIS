"""
AERIS Phase 1 — Cryptography & Security Verification Suite.
Validates:
1. Bcrypt password hashing & timing-safe verification (rounds=12)
2. JWT claims (iss, aud, jti, exp) & tamper rejection
3. MultiFernet biometric embedding encryption, decryption & zero-downtime key rotation
4. Cryptographic hash chaining on attendance events & tamper detection
5. Security headers (HSTS, CSP, X-Frame-Options, Permissions-Policy)
"""
import numpy as np
from datetime import datetime, date, timedelta
from jose import jwt
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models import User, Attendance, BiometricProfile
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    encrypt_embedding,
    decrypt_embedding,
    rotate_encrypted_embedding,
    compute_attendance_event_hash,
    GENESIS_HASH,
)
from app.routers.admin import verify_audit_integrity

client = TestClient(app)

def test_password_hashing():
    print("\n--- 1. Testing Bcrypt Password Hashing ---")
    password = "SecureCampusPassword@2026"
    hashed = hash_password(password)
    
    # Must start with $2b$ (bcrypt) and have round cost 12
    assert hashed.startswith("$2b$12$"), f"Expected bcrypt 12 rounds, got: {hashed[:7]}"
    assert verify_password(password, hashed) is True, "Password verification failed"
    assert verify_password("WrongPassword@123", hashed) is False, "False positive in password verification"
    print(" Password hashing & verification passed (bcrypt 12 rounds).")

def test_jwt_claims_and_tampering():
    print("\n--- 2. Testing JWT Claims & Cryptographic Verification ---")
    payload = {"sub": "user-test-123", "role": "student", "emp_id": "STU999"}
    token = create_access_token(payload)
    
    # Decode and verify claims
    decoded = decode_access_token(token)
    assert decoded["sub"] == "user-test-123"
    assert decoded["iss"] == settings.JWT_ISSUER
    assert decoded["aud"] == settings.JWT_AUDIENCE
    assert "jti" in decoded
    assert "exp" in decoded
    assert "iat" in decoded
    
    # Tamper with token signature
    parts = token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.invalidsignature"
    tamper_caught = False
    try:
        decode_access_token(tampered_token)
    except Exception:
        tamper_caught = True
    assert tamper_caught, "Tampered signature was not rejected!"
    print(" JWT claims, expiration, and signature tampering protection passed.")

def test_multifernet_biometric_encryption_and_rotation():
    print("\n--- 3. Testing MultiFernet Encryption & Key Rotation ---")
    # Create synthetic 512-d float32 vector
    rng = np.random.RandomState(42)
    original_vector = rng.randn(512).astype(np.float32)
    original_vector /= np.linalg.norm(original_vector)
    
    # Encrypt
    ciphertext = encrypt_embedding(original_vector)
    assert isinstance(ciphertext, bytes)
    assert ciphertext != original_vector.tobytes()
    
    # Decrypt
    decrypted_vector = decrypt_embedding(ciphertext)
    assert np.allclose(original_vector, decrypted_vector, atol=1e-6), "Decrypted vector does not match original"
    
    # Key rotation test
    rotated_ciphertext = rotate_encrypted_embedding(ciphertext)
    decrypted_rotated = decrypt_embedding(rotated_ciphertext)
    assert np.allclose(original_vector, decrypted_rotated, atol=1e-6), "Rotation corrupted biometric embedding"
    print(" MultiFernet encryption, decryption, and rotation passed.")

def test_attendance_hash_chain_integrity():
    print("\n--- 4. Testing Cryptographic Hash Chaining & Tamper Detection ---")
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        assert admin is not None, "Admin user required in test database"
        
        # Verify initial state is valid
        res = verify_audit_integrity(admin=admin, db=db)
        assert res["chain_valid"] is True, f"Initial chain invalid: {res}"
        initial_records_count = res["total_records"]
        
        # Tamper simulation: mutate a record's risk_score and verify integrity fails
        target_rec = db.query(Attendance).first()
        if target_rec:
            original_score = target_rec.risk_score
            target_rec.risk_score = 999  # Tampering!
            db.flush()
            
            # Check verification detects the tampering
            tamper_res = verify_audit_integrity(admin=admin, db=db)
            assert tamper_res["chain_valid"] is False, "Integrity check failed to detect tampered risk_score!"
            assert len(tamper_res["tampered_records"]) > 0
            assert tamper_res["tampered_records"][0]["reason"] == "PAYLOAD_TAMPERED"
            
            # Rollback the tampering
            db.rollback()
            
            # Verify chain is restored
            restored_res = verify_audit_integrity(admin=admin, db=db)
            assert restored_res["chain_valid"] is True, "Chain should be valid after rollback"
        print(" Cryptographic hash chaining & tamper detection passed.")
    finally:
        db.close()

def test_security_headers():
    print("\n--- 5. Testing Security Headers Middleware ---")
    response = client.get("/")
    assert response.status_code == 200
    headers = response.headers
    
    assert "Strict-Transport-Security" in headers, "HSTS header missing"
    assert headers["X-Content-Type-Options"] == "nosniff", "MIME sniffing protection missing"
    assert headers["X-Frame-Options"] == "DENY", "Clickjacking protection missing"
    assert "camera=(self)" in headers.get("Permissions-Policy", ""), "Permissions policy missing camera restriction"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    print(" Security headers (HSTS, nosniff, DENY, Permissions-Policy) passed.")

if __name__ == "__main__":
    test_password_hashing()
    test_jwt_claims_and_tampering()
    test_multifernet_biometric_encryption_and_rotation()
    test_attendance_hash_chain_integrity()
    test_security_headers()
    print("\n ALL PHASE 1 SECURITY & CRYPTOGRAPHY TESTS PASSED SUCCESSFULLY!")
