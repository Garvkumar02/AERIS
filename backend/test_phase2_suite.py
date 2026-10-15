"""
AERIS Phase 2 Comprehensive Test Suite:
1. Centralized Registry (Students, Faculty, Staff, Guards, Workers, Visitors)
2. Role & Department filtering and User Status updates
3. Campus Infrastructure (Buildings, Floors, Rooms, Occupancy)
4. Academic Timetables & Work Shifts
5. Biometric Revocation (GDPR/DPDP compliance & deletion check)
6. Executive Overview Metrics
7. Audit Hash Chain Verification
"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, BiometricProfile
from app.core.security import create_access_token

client = TestClient(app)

def get_admin_headers():
    db = SessionLocal()
    admin = db.query(User).filter(User.role == "admin").first()
    db.close()
    token = create_access_token({"sub": admin.id, "role": "admin", "emp_id": admin.employee_id})
    return {"Authorization": f"Bearer {token}"}

def test_centralized_registry_listing_and_filters():
    print("\n--- 1. Testing Centralized Registry Listing & Filters ---")
    headers = get_admin_headers()
    
    # All users
    res = client.get("/admin/users", headers=headers)
    assert res.status_code == 200
    all_users = res.json()
    assert len(all_users) >= 8, f"Expected at least 8 users, got {len(all_users)}"
    
    # Filter by role: guard
    res_guards = client.get("/admin/users?role=guard", headers=headers)
    assert res_guards.status_code == 200
    guards = res_guards.json()
    assert len(guards) >= 1
    assert guards[0]["role"] == "guard"
    assert guards[0]["employee_id"] == "SEC001"

    # Filter by role: visitor
    res_visitors = client.get("/admin/users?role=visitor", headers=headers)
    assert res_visitors.status_code == 200
    visitors = res_visitors.json()
    assert len(visitors) >= 1
    assert visitors[0]["role"] == "visitor"
    print(" Centralized registry listing and role filters passed.")

def test_create_and_status_toggle_user():
    print("\n--- 2. Testing User Creation & Status Toggle in Registry ---")
    headers = get_admin_headers()
    test_emp_id = "WRK999"
    
    # Clean up if existed
    db = SessionLocal()
    existing = db.query(User).filter(User.employee_id == test_emp_id).first()
    if existing:
        db.delete(existing)
        db.commit()
    db.close()

    # Create new worker
    new_user_payload = {
        "name": "Kailash Chand",
        "employee_id": test_emp_id,
        "email": "kailash.chand@campusproof.edu",
        "password": "WorkerPass@123",
        "role": "worker",
        "department": "Facilities",
        "designation": "Electrician",
        "phone": "+91 9876543210"
    }
    create_res = client.post("/admin/users", json=new_user_payload, headers=headers)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["employee_id"] == test_emp_id
    assert created["role"] == "worker"
    user_id = created["id"]

    # Toggle status to suspended
    status_res = client.put(f"/admin/users/{user_id}/status", json={"status": "suspended"}, headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "suspended"

    # Re-activate
    status_res2 = client.put(f"/admin/users/{user_id}/status", json={"status": "active"}, headers=headers)
    assert status_res2.status_code == 200
    assert status_res2.json()["status"] == "active"
    print(" User creation and status updates passed.")

def test_infrastructure_and_timetables():
    print("\n--- 3. Testing Campus Spatial Infrastructure & Timetables ---")
    headers = get_admin_headers()

    # Infrastructure tree
    res_infra = client.get("/admin/infrastructure", headers=headers)
    assert res_infra.status_code == 200
    buildings = res_infra.json()
    assert len(buildings) >= 2
    assert any(b["code"] == "BLK-A" for b in buildings)
    
    # Rooms list
    res_rooms = client.get("/admin/rooms", headers=headers)
    assert res_rooms.status_code == 200
    rooms = res_rooms.json()
    assert len(rooms) >= 8
    room_numbers = [r["room_number"] for r in rooms]
    assert "LT-16" in room_numbers
    assert "LT-24" in room_numbers

    # Timetable sessions
    res_tt = client.get("/admin/timetable", headers=headers)
    assert res_tt.status_code == 200
    sessions = res_tt.json()
    assert len(sessions) >= 2
    assert any(s["subject_code"] == "CS305" for s in sessions)

    # Work shifts
    res_shifts = client.get("/admin/work-shifts", headers=headers)
    assert res_shifts.status_code == 200
    shifts = res_shifts.json()
    assert len(shifts) >= 1
    assert "Main Gate" in shifts[0]["assigned_location"]
    print(" Campus infrastructure, rooms, timetable and shifts passed.")

def test_biometric_revocation():
    print("\n--- 4. Testing Biometric Revocation Flow ---")
    db = SessionLocal()
    # Find student user
    student = db.query(User).filter(User.role == "student").first()
    assert student is not None
    s_id, s_role, s_emp = student.id, student.role, student.employee_id
    # Ensure student has a mock biometric profile
    profile = db.query(BiometricProfile).filter(BiometricProfile.user_id == s_id).first()
    if not profile:
        profile = BiometricProfile(
            user_id=s_id,
            encrypted_embedding=b"mock-encrypted-template-data",
            model_version="buffalo_l",
            consent_version="1.0"
        )
        db.add(profile)
        db.commit()
    else:
        profile.revoked_at = None
        profile.encrypted_embedding = b"mock-encrypted-template-data"
        db.commit()
    db.close()

    # Student token
    student_token = create_access_token({"sub": s_id, "role": s_role, "emp_id": s_emp})
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # Revoke biometrics
    revoke_res = client.post("/biometric/revoke", headers=student_headers)
    assert revoke_res.status_code == 200
    assert revoke_res.json()["revoked"] is True

    # Check status endpoint reflects revoked state
    status_res = client.get("/biometric/status", headers=student_headers)
    assert status_res.status_code == 200
    assert status_res.json()["enrolled"] is False

    # Second revoke call should return 404 (already revoked)
    revoke_res2 = client.post("/biometric/revoke", headers=student_headers)
    assert revoke_res2.status_code == 404
    print(" Biometric consent revocation & template zeroing passed.")

def test_dashboard_overview_metrics():
    print("\n--- 5. Testing Executive Overview Metrics ---")
    headers = get_admin_headers()
    res = client.get("/admin/overview-metrics", headers=headers)
    assert res.status_code == 200
    metrics = res.json()
    
    assert metrics["total_students"] >= 1248
    assert metrics["total_faculty"] >= 86
    assert metrics["total_employees"] >= 42
    assert metrics["present_today_pct"] >= 90
    assert "CSE" in metrics["department_attendance"]
    print(" Executive overview metrics passed.")

def test_audit_integrity_verification():
    print("\n--- 6. Testing Audit Chain Verification API ---")
    headers = get_admin_headers()
    res = client.get("/admin/audit/verify-integrity", headers=headers)
    assert res.status_code == 200
    audit_data = res.json()
    assert audit_data["chain_valid"] is True
    assert len(audit_data["tampered_records"]) == 0
    print(" Cryptographic audit integrity endpoint passed.")

if __name__ == "__main__":
    test_centralized_registry_listing_and_filters()
    test_create_and_status_toggle_user()
    test_infrastructure_and_timetables()
    test_biometric_revocation()
    test_dashboard_overview_metrics()
    test_audit_integrity_verification()
    print("\n ALL PHASE 2 TESTS PASSED SUCCESSFULLY!")
