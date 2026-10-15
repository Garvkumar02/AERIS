import os
import sys
import uuid
import time
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import app, on_startup
from app.database import SessionLocal
from app.models import User, Room, Floor, RoomPresence
from app.core.security import hash_password, create_access_token

on_startup()
client = TestClient(app)

def test_floor_presence_suite():
    print("\n--- 1. Testing Room Authorization & Role Enforcement ---")
    db = SessionLocal()
    try:
        # Fetch or create student user
        student = db.query(User).filter(User.email == "student.rohit@campusproof.edu").first()
        if not student:
            student = User(
                employee_id="STU901",
                name="Rohit Verma",
                email="student.rohit@campusproof.edu",
                password_hash=hash_password("Student@123"),
                role="student",
                status="active"
            )
            db.add(student)
            db.commit()
            db.refresh(student)

        # Fetch or create faculty user
        faculty = db.query(User).filter(User.email == "prof.sharma@campusproof.edu").first()
        if not faculty:
            faculty = User(
                employee_id="FAC901",
                name="Prof. Sharma",
                email="prof.sharma@campusproof.edu",
                password_hash=hash_password("Faculty@123"),
                role="faculty",
                status="active"
            )
            db.add(faculty)
            db.commit()
            db.refresh(faculty)

        # Find classrooms, labs, library, staff room, and common areas
        staff_room = db.query(Room).filter(Room.room_type == "staff_room").first()
        library = db.query(Room).filter(Room.room_type == "library").first()
        classroom = db.query(Room).filter(Room.room_number == "LT-16").first() or db.query(Room).first()
        lab = db.query(Room).filter(Room.room_type == "lab").first()
        cafe = db.query(Room).filter(Room.room_type == "common_area").first()

        assert staff_room is not None, "Staff room must be seeded"
        assert library is not None, "Library must be seeded"

        student_token = create_access_token({"sub": student.id, "role": student.role})
        faculty_token = create_access_token({"sub": faculty.id, "role": faculty.role})

    finally:
        db.close()

    # Attempt 1: Student attempts to check in to restricted Staff Lounge
    res_unauth = client.post(
        "/presence/check-in",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "room_id": staff_room.id,
            "verification_method": "INDOOR_QR",
            "evidence_payload": {"badge": "STAFF-LOUNGE-QR"}
        }
    )
    assert res_unauth.status_code == 403, f"Student should be rejected from staff room, got: {res_unauth.status_code}"
    print(" Role-based room authorization enforced (Student restricted from Faculty Staff Room: 403 Forbidden).")

    # Attempt 2: Faculty checks in to Staff Lounge
    res_fac = client.post(
        "/presence/check-in",
        headers={"Authorization": f"Bearer {faculty_token}"},
        json={
            "room_id": staff_room.id,
            "verification_method": "RFID_NFC",
            "evidence_payload": {"nfc_tag": "FAC-NFC-8812", "door_id": "DOOR-STAFF-01"}
        }
    )
    assert res_fac.status_code == 200, f"Faculty check-in failed: {res_fac.text}"
    fac_receipt = res_fac.json()
    assert fac_receipt["status"] == "CONFIRMED"
    assert fac_receipt["verification_method"] == "RFID_NFC"
    assert fac_receipt["presence_hash"] is not None
    print(f" Authorized faculty check-in granted with RFID_NFC evidence (Hash: {fac_receipt['presence_hash'][:14]}...).")

    print("\n--- 2. Testing Indoor Validated Verification Methods (Non-GPS) ---")
    # Method A: Indoor QR check-in at Central Library
    res_lib = client.post(
        "/presence/check-in",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "room_id": library.id,
            "verification_method": "INDOOR_QR",
            "evidence_payload": {"badge_token": "AERIS-INDOOR-LIB-HOUR-4", "wall_kiosk_id": "LIB-WALL-01"}
        }
    )
    assert res_lib.status_code == 200, f"Library check-in failed: {res_lib.text}"
    lib_receipt = res_lib.json()
    assert lib_receipt["status"] == "CONFIRMED"
    assert lib_receipt["verification_method"] == "INDOOR_QR"
    print(" Indoor QR verification validated for Central Library presence.")

    # Method B: BLE Beacon proximity check-in at Classroom
    res_ble = client.post(
        "/presence/check-in",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "room_id": classroom.id,
            "verification_method": "BLE_BEACON",
            "evidence_payload": {"beacon_rssi": -62, "uuid": "4f2a71c8-e042-4b2a", "major": 1, "minor": 16}
        }
    )
    assert res_ble.status_code == 200
    ble_receipt = res_ble.json()
    assert ble_receipt["status"] == "CONFIRMED"
    assert ble_receipt["verification_method"] == "BLE_BEACON"
    print(" BLE Beacon RSSI proximity verification validated for Classroom presence.")

    # Method C: Wi-Fi BSSID floor mapping check-in at Lab
    if lab:
        res_wifi = client.post(
            "/presence/check-in",
            headers={"Authorization": f"Bearer {student_token}"},
            json={
                "room_id": lab.id,
                "verification_method": "WIFI_BSSID",
                "evidence_payload": {"bssid": "a4:b2:39:cd:ef:01", "ssid": "ARYA_CAMPUS_SECURE"}
            }
        )
        assert res_wifi.status_code == 200
        print(" Wi-Fi BSSID floor-mapped fingerprint verification validated for Lab presence.")

    # Reject weak BLE signal
    res_weak_ble = client.post(
        "/presence/check-in",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "room_id": classroom.id,
            "verification_method": "BLE_BEACON",
            "evidence_payload": {"beacon_rssi": -98}  # too weak (-98 < -85)
        }
    )
    assert res_weak_ble.status_code == 400
    print(" Weak indoor sensor signal rejected (< -85 dBm).")

    print("\n--- 3. Testing Confirmed Presence vs. Estimated Occupancy ---")
    # Student returns to classroom to test room status and roster
    client.post(
        "/presence/check-in",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "room_id": classroom.id,
            "verification_method": "INDOOR_QR",
            "evidence_payload": {"qr_token": "AERIS-INDOOR-DEMO"}
        }
    )
    res_room_stat = client.get(f"/presence/room/{classroom.id}/status")
    assert res_room_stat.status_code == 200
    stat_data = res_room_stat.json()
    assert "confirmed_presence" in stat_data
    assert "estimated_occupancy" in stat_data
    assert "confirmed_attendees" in stat_data
    assert stat_data["confirmed_presence"] >= 1  # Student is confirmed checked in
    assert stat_data["estimated_occupancy"] >= stat_data["confirmed_presence"]
    print(f" Room {stat_data['room_number']}: Confirmed Presence = {stat_data['confirmed_presence']} users | Estimated Occupancy = {stat_data['estimated_occupancy']} persons.")
    print(f" Clear distinction verified: {len(stat_data['confirmed_attendees'])} authenticated persons on roster vs {stat_data['estimated_occupancy']} model estimate.")

    print("\n--- 4. Testing Room Check-Out & Lease Handover ---")
    res_out = client.post(
        "/presence/check-out",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"room_id": classroom.id}
    )
    assert res_out.status_code == 200
    out_data = res_out.json()
    assert out_data["status"] == "COMPLETED"
    print(f" Authorized room check-out recorded (Duration: {out_data['duration_minutes']} min).")

    # Query active presence returns false or next room
    res_my = client.get("/presence/my-active", headers={"Authorization": f"Bearer {student_token}"})
    assert res_my.status_code == 200

    print("\n--- 5. Testing Floor-wise Hierarchy Across All Spaces ---")
    res_floors = client.get("/presence/floors")
    assert res_floors.status_code == 200
    floors = res_floors.json()
    assert len(floors) >= 2

    # Verify breakdown
    for fl in floors:
        print(f" Floor {fl['floor_number']} ({fl['floor_name']}): Confirmed Presence = {fl['total_confirmed_presence']} | Estimated = {fl['total_estimated_occupancy']} | Density: {fl['density_status']} | Rooms: {len(fl['rooms'])}")
        room_types = [r["room_type"] for r in fl["rooms"]]
        for rt in room_types:
            assert rt in ["lecture_hall", "lab", "auditorium", "library", "staff_room", "common_area", "gate", "office"]

    print("\n--- 6. Testing Indoor QR Token Generator ---")
    res_qr = client.get(f"/presence/room/{classroom.id}/qr")
    assert res_qr.status_code == 200
    qr_data = res_qr.json()
    assert "AERIS-INDOOR" in qr_data["qr_token"]
    assert qr_data["expires_in_seconds"] > 0
    print(f" Signed indoor room badge generated: {qr_data['qr_token'][:30]}...")

    print("\n ALL FLOOR-WISE PRESENCE & COMMON ROOMS TESTS PASSED SUCCESSFULLY!\n")

if __name__ == "__main__":
    test_floor_presence_suite()
