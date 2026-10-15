import os
import io
import csv
import uuid
import hashlib
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models import (
    User,
    Campus,
    Building,
    Floor,
    Room,
    Attendance,
    GateEvent,
    GateDevice,
    VerificationAttempt,
    WorkShift,
    LectureSession,
    RoomPresence,
    MerkleCommitment,
    AuditVerificationLog
)
from app.core.security import (
    create_access_token,
    compute_attendance_event_hash,
    compute_gate_event_hash,
    compute_room_presence_hash,
    GENESIS_HASH
)
from app.core.merkle_service import (
    build_merkle_tree,
    generate_merkle_proof,
    verify_merkle_proof,
    anchor_daily_events_to_merkle
)
from app.core.integrity_service import (
    verify_attendance_chain,
    verify_gate_chain,
    verify_presence_chain,
    perform_consolidated_audit
)

client = TestClient(app)

def test_phase8_admin_dashboard_and_integrity_suite():
    print("\n========================================================")
    print("[START] AERIS Phase 8 - Admin Dashboard & Integrity Reports Test Suite")
    print("========================================================")

    db: Session = SessionLocal()
    admin = db.query(User).filter(User.role == "admin").first()
    assert admin is not None, "Admin user must exist"

    admin_token = create_access_token(
        data={"sub": admin.id, "email": admin.email, "role": admin.role, "name": admin.name, "employee_id": admin.employee_id}
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Ensure test environment has campus, building, floor, room, staff, and student
    campus = db.query(Campus).first()
    if not campus:
        campus = Campus(name="Tech Campus", latitude=28.545, longitude=77.1926, radius_m=300)
        db.add(campus)
        db.commit()
        db.refresh(campus)

    building = db.query(Building).first()
    if not building:
        building = Building(campus_id=campus.id, name="Computing Block", code="COMP-01")
        db.add(building)
        db.commit()
        db.refresh(building)

    floor = db.query(Floor).first()
    if not floor:
        floor = Floor(building_id=building.id, floor_number=2, name="Floor 2 - AI Labs")
        db.add(floor)
        db.commit()
        db.refresh(floor)

    room = db.query(Room).first()
    if not room:
        room = Room(floor_id=floor.id, room_number="LAB-204", name="Advanced ML Lab", capacity=40)
        db.add(room)
        db.commit()
        db.refresh(room)

    # Ensure student & staff users
    student = db.query(User).filter(User.role == "student").first()
    if not student:
        student = User(
            employee_id="STU-PHASE8-01",
            name="Aarav Sharma",
            email="aarav.phase8@campus.aeris",
            password_hash="mock_hash",
            role="student",
            department="CSE",
            campus_id=campus.id
        )
        db.add(student)
        db.commit()
        db.refresh(student)

    staff = db.query(User).filter(User.role.in_(["staff", "guard", "worker"])).first()
    if not staff:
        staff = User(
            employee_id="STAFF-PHASE8-01",
            name="Rajesh Kumar",
            email="rajesh.guard@campus.aeris",
            password_hash="mock_hash",
            role="guard",
            department="SECURITY",
            campus_id=campus.id
        )
        db.add(staff)
        db.commit()
        db.refresh(staff)

    # Ensure work shift for staff
    shift = db.query(WorkShift).filter(WorkShift.user_id == staff.id).first()
    if not shift:
        shift = WorkShift(
            user_id=staff.id,
            shift_name="Morning Gate Patrol",
            start_time="08:00",
            end_time="16:00",
            assigned_location="North Gate",
            days="Mon,Tue,Wed,Thu,Fri"
        )
        db.add(shift)
        db.commit()
        db.refresh(shift)

    # Create dummy attendance record for today if absent
    today = date.today()
    att = db.query(Attendance).filter(Attendance.user_id == student.id, Attendance.day == today).first()
    if not att:
        att_id = str(uuid.uuid4())
        now = datetime.utcnow()
        ev_hash = compute_attendance_event_hash(
            prev_hash=GENESIS_HASH,
            attendance_id=att_id,
            user_id=student.id,
            campus_id=campus.id,
            day_str=today.isoformat(),
            checked_in_at_str=now.isoformat(),
            risk_score=10,
            device_id="DEV-KIOSK-01"
        )
        att = Attendance(
            id=att_id,
            user_id=student.id,
            campus_id=campus.id,
            day=today,
            checked_in_at=now,
            verification_method="DOUBLE_VERIFICATION",
            face_score=0.94,
            distance_m=12.5,
            os_biometric_verified=True,
            risk_score=10,
            device_id="DEV-KIOSK-01",
            prev_hash=GENESIS_HASH,
            event_hash=ev_hash
        )
        db.add(att)
        db.commit()
        db.refresh(att)

    # Create dummy gate event if absent
    gate_device = db.query(GateDevice).first()
    if not gate_device:
        gate_device = GateDevice(
            name="Main North Gate Turnstile",
            gate_id="GATE-NORTH-01",
            campus_id=campus.id,
            device_key="GATE_KEY_TEST_01"
        )
        db.add(gate_device)
        db.commit()
        db.refresh(gate_device)

    gate_evt = db.query(GateEvent).first()
    if not gate_evt:
        ge_id = str(uuid.uuid4())
        ge_time = datetime.utcnow()
        ge_hash = compute_gate_event_hash(
            prev_hash=GENESIS_HASH,
            event_id=ge_id,
            user_id=student.id,
            gate_id="GATE-NORTH-01",
            direction="IN",
            event_type="ENTRY",
            device_id=gate_device.id,
            timestamp_str=ge_time.isoformat(),
            synced_offline=False
        )
        gate_evt = GateEvent(
            id=ge_id,
            user_id=student.id,
            gate_id="GATE-NORTH-01",
            direction="IN",
            event_type="ENTRY",
            device_id=gate_device.id,
            timestamp=ge_time,
            synced_offline=False,
            prev_hash=GENESIS_HASH,
            event_hash=ge_hash
        )
        db.add(gate_evt)
        db.commit()

    # Create dummy verification attempt if absent
    attempt = db.query(VerificationAttempt).first()
    if not attempt:
        attempt = VerificationAttempt(
            user_id=student.id,
            result="ACCEPT",
            failure_code="NONE",
            face_score=0.95,
            distance_m=15.0,
            device_id="DEV-TEST-01",
            created_at=datetime.utcnow()
        )
        db.add(attempt)
        db.commit()

    # ========================================================
    # 1. Multi-Dimensional Spatial & Department Filter Endpoints
    # ========================================================
    print("\n--- 1. Testing Spatial Filters & Report Generation ---")
    resp_filters = client.get("/admin/reports/spatial-filters", headers=admin_headers)
    assert resp_filters.status_code == 200
    filters_data = resp_filters.json()
    assert "departments" in filters_data
    assert "roles" in filters_data
    assert "floors" in filters_data
    assert "rooms" in filters_data
    print(f" [PASS] Spatial filters retrieved: {len(filters_data['departments'])} depts, {len(filters_data['roles'])} roles")

    # 1.1 Attendance Report JSON
    resp_att = client.get(
        "/admin/reports/attendance",
        params={"department": "CSE", "role": "student", "format": "json"},
        headers=admin_headers
    )
    assert resp_att.status_code == 200
    att_items = resp_att.json()
    assert isinstance(att_items, list)
    assert len(att_items) >= 1
    assert att_items[0]["role"] == "student"
    assert "CSE" in att_items[0]["department"]
    print(f" [PASS] Attendance JSON report filtered: {len(att_items)} records returned")

    # 1.2 Attendance Report CSV
    resp_att_csv = client.get(
        "/admin/reports/attendance",
        params={"role": "student", "format": "csv"},
        headers=admin_headers
    )
    assert resp_att_csv.status_code == 200
    assert "text/csv" in resp_att_csv.headers["content-type"]
    csv_content = resp_att_csv.text
    csv_reader = list(csv.reader(io.StringIO(csv_content)))
    assert len(csv_reader) >= 2  # Header + at least 1 row
    assert "Attendance ID" in csv_reader[0]
    assert "Employee ID" in csv_reader[0]
    print(f" [PASS] Attendance CSV export verified ({len(csv_reader) - 1} data rows)")

    # 1.3 Gate Access Report (JSON & CSV)
    resp_gate = client.get(
        "/admin/reports/gate-access",
        params={"direction": "IN", "format": "json"},
        headers=admin_headers
    )
    assert resp_gate.status_code == 200
    gate_items = resp_gate.json()
    assert isinstance(gate_items, list)
    assert len(gate_items) >= 1
    assert gate_items[0]["direction"] in ["IN", "ENTRY"]

    resp_gate_csv = client.get(
        "/admin/reports/gate-access",
        params={"direction": "IN", "format": "csv"},
        headers=admin_headers
    )
    assert resp_gate_csv.status_code == 200
    assert "text/csv" in resp_gate_csv.headers["content-type"]
    assert "Gate ID" in resp_gate_csv.text
    print(f" [PASS] Gate Access report verified (JSON + CSV export)")

    # 1.4 Staff Duty Report (JSON & CSV)
    resp_staff = client.get(
        "/admin/reports/staff-duty",
        params={"role": "guard", "format": "json"},
        headers=admin_headers
    )
    assert resp_staff.status_code == 200
    staff_items = resp_staff.json()
    assert isinstance(staff_items, list)
    assert len(staff_items) >= 1
    assert staff_items[0]["role"] == "guard"
    assert len(staff_items[0]["shift_name"]) > 0

    resp_staff_csv = client.get(
        "/admin/reports/staff-duty",
        params={"format": "csv"},
        headers=admin_headers
    )
    assert resp_staff_csv.status_code == 200
    assert "text/csv" in resp_staff_csv.headers["content-type"]
    assert "Shift Name" in resp_staff_csv.text
    print(f" [PASS] Staff Duty report verified with shifts & duty compliance status")

    # 1.5 Verification Attempts Report
    resp_ver = client.get(
        "/admin/reports/verification-attempts",
        params={"result": "ACCEPT", "format": "json"},
        headers=admin_headers
    )
    assert resp_ver.status_code == 200
    ver_items = resp_ver.json()
    assert isinstance(ver_items, list)
    assert len(ver_items) >= 1
    assert ver_items[0]["result"] == "ACCEPT"

    resp_ver_csv = client.get(
        "/admin/reports/verification-attempts",
        params={"format": "csv"},
        headers=admin_headers
    )
    assert resp_ver_csv.status_code == 200
    assert "text/csv" in resp_ver_csv.headers["content-type"]
    print(f" [PASS] Verification attempts report verified (JSON + CSV)")

    # ========================================================
    # 2. Consolidated Multi-Ledger Tamper Verification
    # ========================================================
    print("\n--- 2. Testing Consolidated Multi-Ledger Cryptographic Integrity ---")
    resp_audit = client.get("/admin/audit/consolidated-integrity", headers=admin_headers)
    assert resp_audit.status_code == 200
    audit_data = resp_audit.json()
    assert "audit_id" in audit_data
    assert audit_data["attendance_chain_valid"] is True
    assert audit_data["gate_chain_valid"] is True
    assert audit_data["presence_chain_valid"] is True
    assert audit_data["overall_tamper_free"] is True
    assert len(audit_data["tampered_records"]) == 0
    print(f" [PASS] Real-time consolidated audit passed: {audit_data['total_records_audited']} total records checked across 3 ledgers")

    # Verify audit history
    resp_history = client.get("/admin/audit/history", headers=admin_headers)
    assert resp_history.status_code == 200
    history_items = resp_history.json()
    assert len(history_items) >= 1
    assert history_items[0]["overall_tamper_free"] is True
    print(f" [PASS] Audit verification history contains {len(history_items)} recorded audits")

    # 2.1 Tampering Simulation Test
    print("\n--- 2.1 Simulating Data Injection / Payload Tampering ---")
    first_att = db.query(Attendance).first()
    original_risk = first_att.risk_score
    original_hash = first_att.event_hash

    try:
        # Tamper the record risk_score in the database without recomputing hash
        first_att.risk_score = 999
        db.commit()

        # Run consolidated audit again — it MUST catch the tampering
        tamper_audit = client.get("/admin/audit/consolidated-integrity", headers=admin_headers).json()
        assert tamper_audit["overall_tamper_free"] is False
        assert tamper_audit["attendance_chain_valid"] is False
        assert len(tamper_audit["tampered_records"]) >= 1
        assert tamper_audit["tampered_records"][0]["reason"] == "PAYLOAD_TAMPERED"
        assert tamper_audit["tampered_records"][0]["record_id"] == first_att.id
        print(f" [PASS] Tamper detection successfully flagged payload alteration: {tamper_audit['tampered_records'][0]}")
    finally:
        # Restore record to original state
        first_att.risk_score = original_risk
        first_att.event_hash = original_hash
        db.commit()

    # Re-verify that recovery restores clean state
    clean_audit = client.get("/admin/audit/consolidated-integrity", headers=admin_headers).json()
    assert clean_audit["overall_tamper_free"] is True
    print(f" [PASS] Ledger integrity fully restored after tamper remediation")

    # ========================================================
    # 3. Merkle Root Generation, Blockchain Anchoring & Inclusion Proofs
    # ========================================================
    print("\n--- 3. Testing Merkle Tree Computation & Blockchain Anchoring ---")

    # 3.1 Unit test Merkle Tree logic with known leaves
    sample_leaves = [
        hashlib.sha256(f"leaf_{i}".encode()).hexdigest() for i in range(7)
    ]
    root, levels, depth = build_merkle_tree(sample_leaves)
    assert len(root) == 64
    assert depth == 4

    # Generate proof for leaf 3
    proof_3 = generate_merkle_proof(sample_leaves[3], levels)
    assert proof_3["found"] is True
    assert len(proof_3["proof"]) == 3

    # Cryptographically verify the inclusion proof
    is_valid = verify_merkle_proof(sample_leaves[3], proof_3["proof"], root)
    assert is_valid is True, "Valid proof must verify successfully"

    # Corrupt leaf and assert verification failure
    corrupted_leaf = hashlib.sha256(b"corrupted_leaf").hexdigest()
    assert verify_merkle_proof(corrupted_leaf, proof_3["proof"], root) is False

    print(" [PASS] Cryptographic binary Merkle Tree algorithm verified with odd/even leaves")

    # 3.2 Anchor daily events to blockchain via endpoint
    anchor_payload = {
        "day": today.isoformat(),
        "network": "ETHEREUM_SEPOLIA_ANCHOR"
    }
    resp_anchor = client.post("/admin/audit/merkle-anchor", json=anchor_payload, headers=admin_headers)
    assert resp_anchor.status_code == 200
    anchor_data = resp_anchor.json()
    assert "merkle_root" in anchor_data
    assert len(anchor_data["merkle_root"]) == 64
    assert anchor_data["transaction_hash"].startswith("0x")
    assert anchor_data["status"] == "ANCHORED_ON_CHAIN"
    commitment_id = anchor_data["id"]
    anchored_root = anchor_data["merkle_root"]
    print(f" [PASS] Merkle root anchored on blockchain: Root={anchored_root[:16]}... Tx={anchor_data['transaction_hash'][:18]}...")

    # 3.3 Retrieve commitments list
    resp_list = client.get("/admin/audit/merkle-anchors", headers=admin_headers)
    assert resp_list.status_code == 200
    anchors_list = resp_list.json()
    assert len(anchors_list) >= 1
    assert any(a["id"] == commitment_id for a in anchors_list)
    print(f" [PASS] Merkle commitments list verified: {len(anchors_list)} total anchors recorded")

    # 3.4 Generate Merkle inclusion proof for attendance event
    proof_req = {
        "leaf_hash": att.event_hash,
        "commitment_id": commitment_id
    }
    resp_proof = client.post("/admin/audit/merkle-proof", json=proof_req, headers=admin_headers)
    assert resp_proof.status_code == 200
    proof_res = resp_proof.json()
    assert proof_res["found"] is True
    assert proof_res["merkle_root"] == anchored_root
    proof_steps = proof_res["proof"]
    print(f" [PASS] Merkle inclusion proof generated ({len(proof_steps)} path steps)")

    # 3.5 Verify Merkle inclusion proof via API endpoint
    verify_req = {
        "leaf_hash": att.event_hash,
        "merkle_root": anchored_root,
        "proof": proof_steps
    }
    resp_verify = client.post("/admin/audit/verify-merkle-proof", json=verify_req, headers=admin_headers)
    assert resp_verify.status_code == 200
    verify_data = resp_verify.json()
    assert verify_data["verified"] is True
    assert "Merkle inclusion proof verified" in verify_data["message"]
    print(f" [PASS] Merkle inclusion proof verified on-chain commitment!")

    # 3.6 Negative verify test (altered root fails)
    tampered_verify_req = {
        "leaf_hash": att.event_hash,
        "merkle_root": "0" * 64,
        "proof": proof_steps
    }
    resp_bad_verify = client.post("/admin/audit/verify-merkle-proof", json=tampered_verify_req, headers=admin_headers)
    assert resp_bad_verify.status_code == 200
    assert resp_bad_verify.json()["verified"] is False
    print(" [PASS] Invalid / corrupted Merkle root rejected as expected")

    # ========================================================
    # 4. Disaster Recovery & Backup Integrity Drill
    # ========================================================
    print("\n--- 4. Testing Backup Integrity & Disaster Recovery Drill ---")
    resp_backup = client.post("/privacy/backups/create", headers=admin_headers)
    assert resp_backup.status_code == 200
    backup_id = resp_backup.json()["backup_id"]

    resp_recovery = client.post(
        "/privacy/backups/test-recovery",
        params={"backup_id": backup_id},
        headers=admin_headers
    )
    assert resp_recovery.status_code == 200
    rec_data = resp_recovery.json()
    assert rec_data["status"].lower() == "recovery_test_passed"
    assert rec_data["disaster_recovery_certified"] is True
    assert rec_data["integrity_check"] == "ok"
    print(f" [PASS] Disaster Recovery Drill passed: verified SQLite integrity check 'ok'")

    print("\n========================================================")
    print("[SUCCESS] ALL PHASE 8 ADMIN DASHBOARD & INTEGRITY TESTS PASSED 100%!")
    print("========================================================")

if __name__ == "__main__":
    test_phase8_admin_dashboard_and_integrity_suite()
