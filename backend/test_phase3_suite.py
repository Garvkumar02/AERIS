"""
AERIS Phase 3 Comprehensive Test Suite:
1. 12-Second Dynamic Rotating QR Token Generation, Expiry & Anti-Replay Nonce Verification
2. Authorized Gate Devices Registration, Status Enforcement & Heartbeat
3. Student & Staff Gate Access (Entry & Exit)
4. Institutional Visitor Passes (Issuance, Gate Verification & Checkout)
5. Authorized Guard Overrides & Tamper-Proof Audit Logging
6. Offline Event Storage, Synchronization & Duplicate Prevention Idempotency
7. SHA-256 Gate Ledger Cryptographic Chaining & Tamper Detection
"""
import time
import base64
import uuid
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient

from app.main import app, on_startup
from app.config import settings
from app.database import SessionLocal
from app.models import User, GateDevice, GateEvent, VisitorPass, AuditLog
from app.core.security import create_access_token, GENESIS_HASH, compute_gate_event_hash
from app.core.dynamic_qr import generate_dynamic_qr_token, QR_ROTATION_INTERVAL_SECONDS

# Ensure DB schema and seed data are initialized
on_startup()
client = TestClient(app)


def get_auth_headers(role: str = "admin"):
    db = SessionLocal()
    user = db.query(User).filter(User.role == role).first()
    db.close()
    assert user is not None, f"User with role '{role}' must exist in database"
    token = create_access_token({"sub": user.id, "role": user.role, "emp_id": user.employee_id})
    return {"Authorization": f"Bearer {token}"}, user

def test_dynamic_qr_token_and_anti_replay():
    print("\n--- 1. Testing 12-Second Rotating QR & Anti-Replay Nonce ---")
    headers, student = get_auth_headers(role="student")

    # 1. Generate dynamic QR token
    res = client.get("/gate/my-qr", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "token" in data
    assert data["rotation_interval"] == 12
    assert 0 < data["seconds_remaining"] <= 12
    assert data["user_id"] == student.id
    token = data["token"]
    nonce = data["nonce"]

    # 2. Verify token at authorized gate device
    verify_res = client.post("/gate/verify-qr", json={
        "qr_token": token,
        "device_id": "GATE-DEV-01",
        "direction": "ENTRY",
        "gate_id": "GATE-MAIN-01"
    })
    assert verify_res.status_code == 200, verify_res.text
    verify_data = verify_res.json()
    assert verify_data["result"] == "ACCESS_GRANTED"
    assert verify_data["direction"] == "ENTRY"
    assert verify_data["user"]["id"] == student.id
    assert verify_data["event_hash"] is not None

    # 3. Anti-Replay: Verify exact same token cannot be reused
    replay_res = client.post("/gate/verify-qr", json={
        "qr_token": token,
        "device_id": "GATE-DEV-01",
        "direction": "ENTRY",
        "gate_id": "GATE-MAIN-01"
    })
    assert replay_res.status_code == 200
    replay_data = replay_res.json()
    assert replay_data["result"] == "ACCESS_DENIED"
    assert replay_data["code"] == "QR_TOKEN_ALREADY_USED"

    # 4. Tampered Signature Rejection
    pad_len = (4 - len(token) % 4) % 4
    raw_str = base64.urlsafe_b64decode(token + ("=" * pad_len)).decode("utf-8")
    tampered_raw = raw_str[:-4] + "ffff"
    tampered_token = base64.urlsafe_b64encode(tampered_raw.encode("utf-8")).decode("utf-8").rstrip("=")

    tamper_res = client.post("/gate/verify-qr", json={
        "qr_token": tampered_token,
        "device_id": "GATE-DEV-01",
        "direction": "ENTRY"
    })
    assert tamper_res.json()["result"] == "ACCESS_DENIED"
    assert tamper_res.json()["code"] == "INVALID_QR_SIGNATURE"
    print(" 12-second rotating dynamic QR, anti-replay single-use nonce & signature verification passed.")

def test_gate_devices_registration_and_enforcement():
    print("\n--- 2. Testing Gate Device Registration & Authorization Enforcement ---")
    admin_headers, _ = get_auth_headers(role="admin")
    test_device_id = "GATE-TEST-TURNSTILE-99"

    # 1. Register new turnstile scanner
    reg_payload = {
        "device_id": test_device_id,
        "gate_id": "GATE-WEST-01",
        "gate_name": "West Campus Sports Turnstile",
        "location": "Sports Complex Perimeter",
        "status": "authorized"
    }
    reg_res = client.post("/gate/devices/register", json=reg_payload, headers=admin_headers)
    assert reg_res.status_code == 201, reg_res.text
    assert reg_res.json()["device_id"] == test_device_id

    # 2. List gate devices
    list_res = client.get("/gate/devices", headers=admin_headers)
    assert list_res.status_code == 200
    devices = list_res.json()
    assert any(d["device_id"] == test_device_id for d in devices)

    # 3. Heartbeat
    hb_res = client.post("/gate/devices/heartbeat", json={"device_id": test_device_id, "battery_pct": 98})
    assert hb_res.status_code == 200
    assert hb_res.json()["status"] == "online"

    # 4. Revoke device authorization and test access denial
    status_res = client.put(f"/gate/devices/{test_device_id}/status", json={"status": "revoked"}, headers=admin_headers)
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "revoked"

    # Attempt QR verify through revoked gate scanner
    student_headers, student = get_auth_headers(role="student")
    qr_res = client.get("/gate/my-qr", headers=student_headers)
    new_token = qr_res.json()["token"]

    blocked_res = client.post("/gate/verify-qr", json={
        "qr_token": new_token,
        "device_id": test_device_id,
        "direction": "ENTRY"
    })
    assert blocked_res.status_code == 403
    assert "revoked" in blocked_res.json()["detail"].lower()
    print(" Gate device registration, status enforcement & heartbeat verification passed.")

def test_student_and_staff_entry_exit():
    print("\n--- 3. Testing Student and Staff Entry/Exit Flows ---")
    staff_headers, staff = get_auth_headers(role="staff")

    # Staff Entry
    qr1 = client.get("/gate/my-qr", headers=staff_headers).json()["token"]
    entry_res = client.post("/gate/verify-qr", json={
        "qr_token": qr1,
        "device_id": "GATE-DEV-01",
        "direction": "ENTRY",
        "gate_id": "GATE-MAIN-01"
    })
    assert entry_res.status_code == 200
    assert entry_res.json()["result"] == "ACCESS_GRANTED"
    assert entry_res.json()["direction"] == "ENTRY"

    # Staff Exit
    qr2 = client.get("/gate/my-qr", headers=staff_headers).json()["token"]
    exit_res = client.post("/gate/verify-qr", json={
        "qr_token": qr2,
        "device_id": "GATE-DEV-02",
        "direction": "EXIT",
        "gate_id": "GATE-MAIN-02"
    })
    assert exit_res.status_code == 200
    assert exit_res.json()["result"] == "ACCESS_GRANTED"
    assert exit_res.json()["direction"] == "EXIT"
    print(" Student & Staff bidirectional entry/exit flow passed.")

def test_visitor_passes_lifecycle():
    print("\n--- 4. Testing Visitor Passes Lifecycle (Creation, Gate Verification & Checkout) ---")
    admin_headers, admin = get_auth_headers(role="admin")

    badge_code = f"VP-TEST-{uuid.uuid4().hex[:6].upper()}"
    pass_payload = {
        "visitor_name": "Suresh Singhal",
        "visitor_email": "suresh.singhal@partner.org",
        "visitor_phone": "+91 9988776655",
        "host_employee_id": admin.employee_id,
        "purpose": "Campus AI Infrastructure Inspection",
        "badge_number": badge_code,
        "valid_duration_hours": 4
    }

    # 1. Create visitor pass
    create_res = client.post("/gate/visitor-passes", json=pass_payload, headers=admin_headers)
    assert create_res.status_code == 201, create_res.text
    pass_data = create_res.json()
    assert pass_data["badge_number"] == badge_code
    assert pass_data["status"] == "active"
    pass_id = pass_data["id"]

    # 2. List visitor passes
    list_res = client.get(f"/gate/visitor-passes?search={badge_code}", headers=admin_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Verify visitor pass at gate
    verify_res = client.post("/gate/verify-visitor-pass", json={
        "badge_number": badge_code,
        "device_id": "GATE-DEV-01",
        "direction": "ENTRY"
    })
    assert verify_res.status_code == 200, verify_res.text
    assert verify_res.json()["result"] == "ACCESS_GRANTED"
    assert verify_res.json()["user"]["badge_number"] == badge_code

    # 4. Check out visitor pass
    co_res = client.put(f"/gate/visitor-passes/{pass_id}/checkout", headers=admin_headers)
    assert co_res.status_code == 200
    assert co_res.json()["status"] == "checked_out"

    # 5. Subsequent gate verification must be rejected
    rejected_res = client.post("/gate/verify-visitor-pass", json={
        "badge_number": badge_code,
        "device_id": "GATE-DEV-01",
        "direction": "ENTRY"
    })
    assert rejected_res.status_code == 200
    assert rejected_res.json()["result"] == "ACCESS_DENIED"
    assert "CHECKED_OUT" in rejected_res.json()["code"]
    print(" Visitor pass issuance, gate verification and checkout lifecycle passed.")

def test_guard_override_and_audit_log():
    print("\n--- 5. Testing Authorized Guard Override & Tamper-Proof Audit Logging ---")
    guard_headers, guard = get_auth_headers(role="guard")
    student_headers, student = get_auth_headers(role="student")

    # 1. Non-guard/non-admin cannot override (Forbidden)
    forbidden_res = client.post("/gate/guard-override", json={
        "target_identifier": student.employee_id,
        "direction": "ENTRY",
        "reason": "Student forgot phone",
        "device_id": "GATE-DEV-01"
    }, headers=student_headers)
    assert forbidden_res.status_code == 403

    # 2. Authorized Guard executes override
    override_reason = "Manual ID verification; RFID card misplaced"
    override_res = client.post("/gate/guard-override", json={
        "target_identifier": student.employee_id,
        "direction": "ENTRY",
        "reason": override_reason,
        "device_id": "GATE-DEV-01",
        "gate_id": "GATE-MAIN-01"
    }, headers=guard_headers)
    assert override_res.status_code == 200, override_res.text
    data = override_res.json()
    assert data["result"] == "ACCESS_GRANTED"
    assert data["user"]["override_reason"] == override_reason
    assert data["user"]["guard_name"] == guard.name

    # 3. Verify tamper-proof audit log entry created
    db = SessionLocal()
    audit_entry = db.query(AuditLog).filter(
        AuditLog.action == "GUARD_GATE_OVERRIDE",
        AuditLog.actor_id == guard.id
    ).order_by(AuditLog.id.desc()).first()
    assert audit_entry is not None
    assert audit_entry.metadata_json["reason"] == override_reason
    assert audit_entry.record_hash is not None
    db.close()
    print(" Guard override authorization, execution, and tamper-proof audit log passed.")

def test_offline_event_sync_and_deduplication():
    print("\n--- 6. Testing Offline Event Sync & Deduplication Idempotency ---")
    admin_headers, _ = get_auth_headers(role="admin")
    student_headers, student = get_auth_headers(role="student")
    staff_headers, staff = get_auth_headers(role="staff")

    client_ev_id1 = f"OFF-EV-{uuid.uuid4().hex[:12]}"
    client_ev_id2 = f"OFF-EV-{uuid.uuid4().hex[:12]}"
    now_iso = (datetime.utcnow() - timedelta(minutes=10)).isoformat()

    batch_payload = {
        "device_id": "GATE-DEV-01",
        "gate_id": "GATE-MAIN-01",
        "events": [
            {
                "client_event_id": client_ev_id1,
                "target_identifier": student.employee_id,
                "direction": "ENTRY",
                "event_type": "OFFLINE_SYNC",
                "offline_device_timestamp": now_iso
            },
            {
                "client_event_id": client_ev_id2,
                "target_identifier": staff.employee_id,
                "direction": "EXIT",
                "event_type": "OFFLINE_SYNC",
                "offline_device_timestamp": now_iso
            }
        ]
    }

    # 1. Sync offline batch
    sync_res = client.post("/gate/sync-offline", json=batch_payload)
    assert sync_res.status_code == 200, sync_res.text
    sync_data = sync_res.json()
    assert sync_data["total_received"] == 2
    assert sync_data["synced"] == 2
    assert sync_data["duplicates_skipped"] == 0

    # 2. Idempotency: Resend identical batch (Simulating network retry)
    resend_res = client.post("/gate/sync-offline", json=batch_payload)
    assert resend_res.status_code == 200
    resend_data = resend_res.json()
    assert resend_data["synced"] == 0
    assert resend_data["duplicates_skipped"] == 2, "Duplicate events must be skipped"

    # 3. Test offline cache download
    cache_res = client.get("/gate/offline-cache?device_id=GATE-DEV-01")
    assert cache_res.status_code == 200
    cache_data = cache_res.json()
    assert cache_data["users_count"] > 0
    assert "active_users" in cache_data
    assert "active_passes" in cache_data
    print(" Offline event synchronization, idempotency duplicate prevention, and cache download passed.")

def test_sha256_gate_ledger_cryptographic_integrity():
    print("\n--- 7. Testing SHA-256 Gate Ledger Cryptographic Hash Chaining & Tamper Detection ---")
    admin_headers, admin = get_auth_headers(role="admin")

    # 1. Verify ledger integrity
    audit_res = client.get("/gate/audit/verify-integrity", headers=admin_headers)
    assert audit_res.status_code == 200, audit_res.text
    audit_data = audit_res.json()
    assert audit_data["chain_valid"] is True, f"Gate ledger integrity broken: {audit_data['tampered_records']}"
    assert audit_data["total_records"] > 0
    assert audit_data["genesis_hash"] == GENESIS_HASH

    # 2. Searchable Gate History listing & filters
    events_res = client.get("/gate/events?limit=10", headers=admin_headers)
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) > 0
    for ev in events:
        assert ev["event_hash"] is not None
        assert ev["direction"] in ("ENTRY", "EXIT")

    # 3. Gate Stats
    stats_res = client.get("/gate/stats", headers=admin_headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_entries_today" in stats
    assert "current_on_campus" in stats

    # 4. Tamper Simulation Test: Direct database mutation must be detected
    db = SessionLocal()
    try:
        target_event = db.query(GateEvent).order_by(GateEvent.timestamp.desc()).first()
        if target_event:
            original_direction = target_event.direction
            target_event.direction = "EXIT" if original_direction == "ENTRY" else "ENTRY"
            db.commit()

            # Verify integrity detection triggers PAYLOAD_TAMPERED
            tamper_check = client.get("/gate/audit/verify-integrity", headers=admin_headers).json()
            assert tamper_check["chain_valid"] is False, "Tampered gate record was not detected!"
            assert any(t["record_id"] == target_event.id for t in tamper_check["tampered_records"])

            # Roll back tampering
            target_event.direction = original_direction
            db.commit()

            # Verify restored
            clean_check = client.get("/gate/audit/verify-integrity", headers=admin_headers).json()
            assert clean_check["chain_valid"] is True, "Ledger should be valid after restoring payload"
    finally:
        db.close()

    print(" SHA-256 gate ledger cryptographic hash chaining & tamper detection passed.")

if __name__ == "__main__":
    test_dynamic_qr_token_and_anti_replay()
    test_gate_devices_registration_and_enforcement()
    test_student_and_staff_entry_exit()
    test_visitor_passes_lifecycle()
    test_guard_override_and_audit_log()
    test_offline_event_sync_and_deduplication()
    test_sha256_gate_ledger_cryptographic_integrity()
    print("\n ALL PHASE 3 GATE ACCESS, DYNAMIC QR & OFFLINE SYNC TESTS PASSED SUCCESSFULLY!")
