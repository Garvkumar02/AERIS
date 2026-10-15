import os
import sys
import time
import base64
import json
import hmac
import hashlib
from fastapi.testclient import TestClient

# Ensure current directory in python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import app
from app.database import SessionLocal
from app.models import User, Room, LectureSession, Attendance, BiometricProfile
from app.core.security import hash_password, create_access_token, encrypt_embedding
from app.core.lecture_qr import generate_lecture_qr_token, verify_lecture_qr_token, ROTATION_INTERVAL_SECONDS

client = TestClient(app)

def test_phase4_full_suite():
    print("\n--- 1. Testing Faculty Lecture Start & End Controls ---")
    db = SessionLocal()
    try:
        # Create test faculty
        fac_user = db.query(User).filter(User.email == "prof.sharma@campusproof.edu").first()
        if not fac_user:
            fac_user = User(
                employee_id="FAC901",
                name="Prof. Sharma",
                email="prof.sharma@campusproof.edu",
                password_hash=hash_password("Faculty@123"),
                role="faculty",
                status="active"
            )
            db.add(fac_user)
            db.commit()
            db.refresh(fac_user)

        # Create test student
        stu_user = db.query(User).filter(User.email == "student.rohit@campusproof.edu").first()
        if not stu_user:
            stu_user = User(
                employee_id="STU901",
                name="Rohit Verma",
                email="student.rohit@campusproof.edu",
                password_hash=hash_password("Student@123"),
                role="student",
                status="active"
            )
            db.add(stu_user)
            db.commit()
            db.refresh(stu_user)

        # Enroll dummy biometric embedding for student
        profile = db.query(BiometricProfile).filter(BiometricProfile.user_id == stu_user.id).first()
        if not profile:
            import numpy as np
            dummy_emb = np.array([0.05] * 512, dtype=np.float32)
            profile = BiometricProfile(
                user_id=stu_user.id,
                encrypted_embedding=encrypt_embedding(dummy_emb),
                model_version="ArcFace-v1"
            )
            db.add(profile)
            db.commit()

        # Find or create room
        room = db.query(Room).filter(Room.room_number == "LT-16").first()
        if not room:
            room = db.query(Room).first()

        room_id = room.id
        fac_token = create_access_token({"sub": fac_user.id, "role": fac_user.role})
        stu_token = create_access_token({"sub": stu_user.id, "role": stu_user.role})

    finally:
        db.close()

    # Faculty starts lecture
    res = client.post(
        "/attendance/lecture/start",
        headers={"Authorization": f"Bearer {fac_token}"},
        json={
            "subject_name": "Operating Systems & Concurrency",
            "subject_code": "CS-401",
            "room_id": room_id,
            "section": "Section B"
        }
    )
    assert res.status_code == 200, f"Start lecture failed: {res.text}"
    lec_data = res.json()
    lecture_id = lec_data["id"]
    assert lec_data["status"] == "active"
    assert lec_data["subject_code"] == "CS-401"
    print(" Faculty lecture session successfully initiated (Status: ACTIVE).")

    # Student cannot start lecture
    res_unauth = client.post(
        "/attendance/lecture/start",
        headers={"Authorization": f"Bearer {stu_token}"},
        json={
            "subject_name": "Hacked Class",
            "subject_code": "HACK",
            "room_id": room_id
        }
    )
    assert res_unauth.status_code == 403, "Student should not be able to start lecture"
    print(" Unauthorized role prevention enforced (403 Forbidden for students).")

    # Query active lectures
    res_active = client.get("/attendance/lecture/active")
    assert res_active.status_code == 200
    active_list = res_active.json()
    assert any(l["id"] == lecture_id for l in active_list)
    print(" Active lecture discovered in campus-wide broadcast registry.")

    print("\n--- 2. Testing 12-Second Rotating QR Token & Anti-Replay Nonce ---")
    res_qr = client.get(f"/attendance/lecture/{lecture_id}/qr")
    assert res_qr.status_code == 200, f"Get QR failed: {res_qr.text}"
    qr_data = res_qr.json()
    token = qr_data["token"]
    assert qr_data["rotation_interval"] == 12
    assert 0 < qr_data["seconds_remaining"] <= 12
    assert len(qr_data["nonce"]) == 32  # 16 bytes in hex = 32 chars
    print(f" 12-second rotating token broadcasted (Nonce: {qr_data['nonce'][:8]}..., Remaining: {qr_data['seconds_remaining']}s).")

    # Test Tampered Signature Rejection
    b64_payload, _ = token.split(".")
    forged_token = f"{b64_payload}.0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    is_valid, err_code, _ = verify_lecture_qr_token(forged_token, lecture_id, room_id, "dummy_secret")
    assert not is_valid
    assert err_code == "QR_INVALID_SIGNATURE"
    print(" Cryptographic HMAC-SHA256 signature tampering rejected.")

    # Test Expired Epoch Rejection
    expired_payload = {
        "ver": "AERIS-LEC-v1",
        "lecture_id": lecture_id,
        "room_id": room_id,
        "subject_code": "CS-401",
        "epoch": int((time.time() - 30) // 12),  # 30 seconds ago (> 18s window)
        "nonce": os.urandom(16).hex(),
        "iat": int(time.time() - 30)
    }
    exp_json = json.dumps(expired_payload, separators=(',', ':'), sort_keys=True)
    b64_exp = base64.urlsafe_b64encode(exp_json.encode('utf-8')).decode('utf-8').rstrip('=')

    db = SessionLocal()
    lec_db = db.query(LectureSession).filter(LectureSession.id == lecture_id).first()
    sec_key = lec_db.secret_key
    db.close()

    exp_sig = hmac.new(sec_key.encode('utf-8'), b64_exp.encode('utf-8'), hashlib.sha256).hexdigest()
    expired_token = f"{b64_exp}.{exp_sig}"

    is_valid, err_code, _ = verify_lecture_qr_token(expired_token, lecture_id, room_id, sec_key)
    assert not is_valid
    assert err_code == "QR_EXPIRED"
    print(" Expired rotating QR token (> 12s window) rejected.")

    print("\n--- 3. Testing Double Verification Pipeline (QR + Geofence + Biometric) ---")
    # Fresh QR token
    res_qr2 = client.get(f"/attendance/lecture/{lecture_id}/qr")
    valid_qr_token = res_qr2.json()["token"]

    # Student verifies attendance with demo bypass frames, campus GPS (Arya Jaipur: 26.8228, 75.8648)
    verify_payload = {
        "lecture_id": lecture_id,
        "qr_token": valid_qr_token,
        "lat": 26.8228,
        "lng": 75.8648,
        "accuracy": 10.0,
        "is_mock": False,
        "device_id": "STUDENT-PHONE-901",
        "os_biometric_verified": True,
        "demo_bypass_frames": True
    }

    res_v = client.post(
        "/attendance/verify-lecture",
        headers={"Authorization": f"Bearer {stu_token}"},
        data=verify_payload
    )
    assert res_v.status_code == 200, f"Verify failed: {res_v.text}"
    v_data = res_v.json()
    assert v_data["result"] == "ACCEPT", f"Result not ACCEPT: {v_data}"
    assert v_data["confirmation"]["status"] == "CONFIRMED"
    assert v_data["confirmation"]["double_verified"] is True
    assert v_data["confirmation"]["roll_number"] == "STU901"
    assert v_data["confirmation"]["verification_hash"] is not None
    print(f" Double verification ACCEPTED: Receipt Hash {v_data['confirmation']['verification_hash'][:16]}...")

    print("\n--- 4. Testing Anti-Replay Nonce Protection ---")
    # Attempting to use the exact same QR token again must be rejected with QR_REPLAYED
    res_replay = client.post(
        "/attendance/verify-lecture",
        headers={"Authorization": f"Bearer {stu_token}"},
        data=verify_payload
    )
    assert res_replay.status_code == 200
    replay_data = res_replay.json()
    # Should fail either with DUPLICATE_ATTENDANCE (first check) or QR_REPLAYED
    # Let's test with a second student to isolate the nonce replay check
    db = SessionLocal()
    stu2 = db.query(User).filter(User.email == "student2.sneha@campusproof.edu").first()
    if not stu2:
        stu2 = User(
            employee_id="STU902",
            name="Sneha Patil",
            email="student2.sneha@campusproof.edu",
            password_hash=hash_password("Student@123"),
            role="student",
            status="active"
        )
        db.add(stu2)
        db.commit()
        db.refresh(stu2)
        # Profile
        import numpy as np
        prof2 = BiometricProfile(
            user_id=stu2.id,
            encrypted_embedding=encrypt_embedding(np.array([0.05]*512, dtype=np.float32)),
            model_version="ArcFace-v1"
        )
        db.add(prof2)
        db.commit()
    stu2_token = create_access_token({"sub": stu2.id, "role": stu2.role})
    db.close()

    res_replay_stu2 = client.post(
        "/attendance/verify-lecture",
        headers={"Authorization": f"Bearer {stu2_token}"},
        data=verify_payload  # using consumed valid_qr_token
    )
    assert res_replay_stu2.status_code == 200
    rep_stu2_data = res_replay_stu2.json()
    assert rep_stu2_data["result"] == "REJECT"
    assert rep_stu2_data["code"] == "QR_REPLAYED"
    print(" Anti-replay nonce single-use enforcement passed (QR_REPLAYED).")

    print("\n--- 5. Testing Duplicate Attendance Prevention for Student ---")
    # Fresh token for lecture
    res_qr3 = client.get(f"/attendance/lecture/{lecture_id}/qr")
    valid_qr_token3 = res_qr3.json()["token"]

    verify_payload_dup = {
        "lecture_id": lecture_id,
        "qr_token": valid_qr_token3,
        "lat": 26.8228,
        "lng": 75.8648,
        "accuracy": 10.0,
        "is_mock": False,
        "device_id": "STUDENT-PHONE-901",
        "os_biometric_verified": True,
        "demo_bypass_frames": True
    }
    # Rohit tries to mark attendance a second time for the same lecture
    res_dup = client.post(
        "/attendance/verify-lecture",
        headers={"Authorization": f"Bearer {stu_token}"},
        data=verify_payload_dup
    )
    assert res_dup.status_code == 200
    dup_data = res_dup.json()
    assert dup_data["result"] == "DUPLICATE_ATTENDANCE"
    assert dup_data["code"] == "DUPLICATE_ATTENDANCE"
    print(" Duplicate check-in prevention for same lecture enforced (DUPLICATE_ATTENDANCE).")

    print("\n--- 6. Testing Geofence & Location Spoof Defense ---")
    res_qr4 = client.get(f"/attendance/lecture/{lecture_id}/qr")
    token4 = res_qr4.json()["token"]

    # Student far outside campus boundary (e.g. Delhi coords: 28.6139, 77.2090)
    res_geo = client.post(
        "/attendance/verify-lecture",
        headers={"Authorization": f"Bearer {stu2_token}"},
        data={
            "lecture_id": lecture_id,
            "qr_token": token4,
            "lat": 28.6139,
            "lng": 77.2090,
            "accuracy": 10.0,
            "is_mock": False,
            "device_id": "STUDENT-PHONE-902",
            "os_biometric_verified": True,
            "demo_bypass_frames": True
        }
    )
    assert res_geo.status_code == 200
    geo_data = res_geo.json()
    assert geo_data["result"] == "REJECT"
    assert geo_data["code"] == "OUTSIDE_CAMPUS"
    print(" Geofence boundary breach rejected (OUTSIDE_CAMPUS).")

    print("\n--- 7. Testing Live Attendee List & Concluding Lecture ---")
    res_att = client.get(f"/attendance/lecture/{lecture_id}/attendees")
    assert res_att.status_code == 200
    att_list = res_att.json()
    assert len(att_list) >= 1
    assert any(a["roll_number"] == "STU901" for a in att_list)
    print(f" Live lecture attendee stream confirmed ({len(att_list)} student checked in).")

    # Faculty concludes lecture
    res_end = client.post(
        f"/attendance/lecture/{lecture_id}/end",
        headers={"Authorization": f"Bearer {fac_token}"}
    )
    assert res_end.status_code == 200
    end_data = res_end.json()
    assert end_data["status"] == "ended"
    assert end_data["ended_at"] is not None
    print(" Faculty lecture conclusion finalized (Status: ENDED).")

    # Verifying against ended lecture rejected
    res_qr5 = client.get(f"/attendance/lecture/{lecture_id}/qr")
    assert res_qr5.status_code == 400
    print(" Ended lecture QR broadcast terminated (400 Bad Request).")

    print("\n--- 8. Testing Attendance Records & Analytics Endpoints ---")
    res_rec = client.get("/attendance/records?limit=50")
    assert res_rec.status_code == 200
    recs = res_rec.json()
    assert len(recs) > 0
    print(f" Attendance records ledger query successful ({len(recs)} records returned).")

    res_ana = client.get("/attendance/analytics")
    assert res_ana.status_code == 200
    ana = res_ana.json()
    assert ana["present_rate_pct"] > 0
    assert ana["debarment_risk_count"] > 0
    assert len(ana["subject_percentages"]) > 0
    print(" Attendance analytics and debarment risk intelligence verified.")

    print("\n ALL PHASE 4 LECTURE ATTENDANCE & DOUBLE VERIFICATION TESTS PASSED SUCCESSFULLY!\n")

if __name__ == "__main__":
    test_phase4_full_suite()
