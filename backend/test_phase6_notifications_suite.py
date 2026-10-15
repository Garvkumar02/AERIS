"""
Phase 6 Automated Test Suite: Notifications & Mentor Alerts — AERIS
- Attendance success/failure notifications.
- Class rescheduling, room changes aur exam alerts.
- Verified absence 10 minutes se zyada hone par mentor alert.
- Notification delivery status, retry aur duplicate suppression.
- STRICT CONSTRAINT: Alert does NOT constitute an automatic misconduct decision.
"""

import os
import time
from datetime import datetime, timedelta, date
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import (
    User, Campus, Device, BiometricProfile, LectureSession, Room, Attendance,
    GateEvent, RoomPresence, Notification, MentorAlert
)
from app.core.security import hash_password, create_access_token

client = TestClient(app)

def test_notifications_and_mentor_suite():
    db = SessionLocal()

    print("\n--- Setup Phase 6 Test Context ---")
    # 1. Fetch or create test campus, mentor faculty, and mentee student
    campus = db.query(Campus).first()
    assert campus is not None, "Campus must exist"

    # Faculty Mentor
    mentor_email = "mentor.sharma@campusproof.edu"
    mentor = db.query(User).filter(User.email == mentor_email).first()
    if not mentor:
        mentor = User(
            employee_id="FAC-MENTOR-01",
            name="Prof. Rajesh Sharma",
            email=mentor_email,
            password_hash=hash_password("Faculty@123"),
            role="faculty",
            department="CSE",
            status="active",
            campus_id=campus.id
        )
        db.add(mentor)
        db.commit()
        db.refresh(mentor)

    # Student with assigned mentor
    student_email = "rohit.verma@campusproof.edu"
    student = db.query(User).filter(User.email == student_email).first()
    if not student:
        student = User(
            employee_id="STU-2026-088",
            name="Rohit Verma",
            email=student_email,
            password_hash=hash_password("Student@123"),
            role="student",
            department="CSE",
            status="active",
            campus_id=campus.id,
            mentor_id=mentor.id
        )
        db.add(student)
        db.commit()
        db.refresh(student)
    else:
        student.mentor_id = mentor.id
        db.commit()

    # Admin
    admin_user = db.query(User).filter(User.role == "admin").first()
    assert admin_user is not None

    mentor_token = create_access_token({"sub": mentor.id, "role": mentor.role, "emp_id": mentor.employee_id})
    student_token = create_access_token({"sub": student.id, "role": student.role, "emp_id": student.employee_id})
    admin_token = create_access_token({"sub": admin_user.id, "role": admin_user.role, "emp_id": admin_user.employee_id})

    # Target Room
    room = db.query(Room).filter(Room.room_number == "LT-16").first()
    if not room:
        room = db.query(Room).first()

    # Lecture Session
    lecture = db.query(LectureSession).filter(LectureSession.status == "active").first()
    if not lecture:
        lecture = LectureSession(
            faculty_id=mentor.id,
            room_id=room.id,
            subject_name="Operating Systems & Distributed Systems",
            subject_code="CS401",
            section="Section A",
            status="active",
            started_at=datetime.utcnow() - timedelta(minutes=15),  # Started 15 mins ago to test >10m absence rule
            secret_key=os.urandom(32).hex()
        )
        db.add(lecture)
        db.commit()
        db.refresh(lecture)
    else:
        # Adjust started_at to simulate >10 minutes elapsed
        lecture.started_at = datetime.utcnow() - timedelta(minutes=14)
        db.commit()

    # Clean previous test notifications and alerts to ensure test repeatability
    db.query(MentorAlert).filter(MentorAlert.student_id == student.id).delete()
    db.query(Notification).filter(Notification.recipient_id.in_([student.id, mentor.id])).delete()
    db.commit()

    print(f" Context initialized: Student={student.name}, Mentor={mentor.name}, Lecture={lecture.subject_code} in Room={room.room_number}")

    # ========================================================
    # 1. Attendance Success & Failure Notifications
    # ========================================================
    print("\n--- 1. Testing Attendance Success & Failure Notifications ---")

    from app.core.notification_service import send_attendance_notification

    # Test A: Dispatch Attendance Success Notification
    notif_success = send_attendance_notification(
        db=db,
        user=student,
        lecture=lecture,
        result="ACCEPT",
        receipt_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert notif_success.category == "ATTENDANCE_SUCCESS"
    assert notif_success.delivery_status == "DELIVERED"
    assert "CS401" in notif_success.title or "Confirmed" in notif_success.title
    print(f" Attendance success notification delivered: '{notif_success.title}'")

    # Test B: Dispatch Attendance Failure Notification (e.g. Geofence breach)
    notif_fail = send_attendance_notification(
        db=db,
        user=student,
        lecture=lecture,
        result="REJECT",
        code="OUTSIDE_CAMPUS",
        failure_message="You are outside the campus boundary"
    )
    assert notif_fail.category == "ATTENDANCE_FAILURE"
    assert notif_fail.priority == "HIGH"
    assert "OUTSIDE_CAMPUS" in notif_fail.title or "Failed" in notif_fail.title
    print(f" Attendance failure notification dispatched: '{notif_fail.title}'")

    # Test C: Retrieve Notifications via API
    res_my = client.get("/notifications/my", headers={"Authorization": f"Bearer {student_token}"})
    assert res_my.status_code == 200
    my_notifs = res_my.json()
    assert len(my_notifs) >= 2
    categories = [n["category"] for n in my_notifs]
    assert "ATTENDANCE_SUCCESS" in categories
    assert "ATTENDANCE_FAILURE" in categories

    # Test D: Mark Notification as Read
    first_id = my_notifs[0]["id"]
    res_read = client.post(f"/notifications/{first_id}/read", headers={"Authorization": f"Bearer {student_token}"})
    assert res_read.status_code == 200
    assert res_read.json()["is_read"] is True
    print(" Notification read receipt acknowledged.")

    # ========================================================
    # 2. Academic Alerts: Class Rescheduling, Room Change & Exams
    # ========================================================
    print("\n--- 2. Testing Class Rescheduling, Room Changes & Exam Alerts ---")

    # A. Class Rescheduling Alert
    res_resched = client.post(
        "/notifications/broadcast/reschedule",
        headers={"Authorization": f"Bearer {mentor_token}"},
        json={
            "subject_code": "CS401",
            "section": "Section A",
            "original_time": "10:00 AM",
            "new_time": "02:30 PM",
            "new_date": "2026-10-16",
            "reason": "Faculty attending research conference"
        }
    )
    assert res_resched.status_code == 200
    resched_data = res_resched.json()
    assert resched_data["category"] == "CLASS_RESCHEDULED"
    assert resched_data["recipients_count"] >= 1
    print(f" Class rescheduling broadcasted to {resched_data['recipients_count']} student recipients.")

    # B. Room Change Alert
    res_room_chg = client.post(
        "/notifications/broadcast/room-change",
        headers={"Authorization": f"Bearer {mentor_token}"},
        json={
            "subject_code": "CS401",
            "section": "Section A",
            "original_room": "LT-16",
            "new_room": "LT-24",
            "new_floor": "2nd Floor (CSE)",
            "reason": "Projector maintenance in LT-16"
        }
    )
    assert res_room_chg.status_code == 200
    room_chg_data = res_room_chg.json()
    assert room_chg_data["category"] == "ROOM_CHANGED"
    print(f" Room change alert broadcasted to {room_chg_data['recipients_count']} recipients.")

    # C. Exam Alert
    res_exam = client.post(
        "/notifications/broadcast/exam-alert",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "subject_code": "CS401",
            "subject_name": "Operating Systems",
            "exam_title": "Mid-Semester Theory Examination",
            "exam_date": "2026-11-04",
            "start_time": "09:30 AM",
            "end_time": "12:30 PM",
            "room_number": "AUDI-MAIN",
            "hall_ticket_info": "Desk #B-14",
            "invigilator": "Dr. Vikram Malhotra"
        }
    )
    assert res_exam.status_code == 200
    exam_data = res_exam.json()
    assert exam_data["category"] == "EXAM_ALERT"
    print(f" Exam schedule and desk allocation alert dispatched to {exam_data['recipients_count']} recipients.")

    # ========================================================
    # 3. Verified Absence > 10 Minutes & Mentor Alert
    # ========================================================
    print("\n--- 3. Testing Verified Absence > 10m & Supportive Mentor Alert ---")

    # Ensure student has NOT checked in to this lecture
    db.query(Attendance).filter(
        Attendance.user_id == student.id,
        Attendance.lecture_session_id == lecture.id
    ).delete()
    # Delete any previous mentor alert for clean test
    db.query(MentorAlert).filter(
        MentorAlert.student_id == student.id,
        MentorAlert.lecture_session_id == lecture.id
    ).delete()
    db.commit()

    # Trigger absence evaluation endpoint
    res_eval = client.post(
        "/notifications/check-absences?min_absence_minutes=10",
        headers={"Authorization": f"Bearer {mentor_token}"}
    )
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert eval_data["alerts_generated"] >= 1
    print(f" Absence evaluation completed: {eval_data['alerts_generated']} mentor alerts created.")

    # Retrieve Mentor Alerts for Mentor Faculty
    res_mentor_alerts = client.get("/notifications/mentor/alerts", headers={"Authorization": f"Bearer {mentor_token}"})
    assert res_mentor_alerts.status_code == 200
    mentor_alerts = res_mentor_alerts.json()
    assert len(mentor_alerts) >= 1

    target_alert = next((a for a in mentor_alerts if a["student_id"] == student.id), mentor_alerts[0])
    
    # CRITICAL SPECIFICATION VERIFICATION:
    # "alert ka matlab automatic misconduct decision nahi hoga"
    assert target_alert["is_misconduct_charge"] is False, "Violation: Alert MUST NOT be an automatic misconduct charge"
    assert "Advisory wellness inquiry only" in target_alert["disclaimer"], "Disclaimer must guarantee advisory nature"
    assert target_alert["status"] == "ADVISORY_PENDING"
    assert target_alert["absence_duration_minutes"] >= 10
    print(f" Verified absence ({target_alert['absence_duration_minutes']}m) triggered mentor alert for {target_alert['student_name']}.")
    print(f" STRICT CONSTRAINT SATISFIED: is_misconduct_charge={target_alert['is_misconduct_charge']} | Disclaimer='{target_alert['disclaimer']}'")

    # Test Mentor Action / Status Update
    res_update = client.post(
        f"/notifications/mentor/alerts/{target_alert['id']}/update-status",
        headers={"Authorization": f"Bearer {mentor_token}"},
        json={
            "status": "EXPLAINED_AUTHORIZED",
            "mentor_notes": "Student had prior approval for participating in Smart India Hackathon finals."
        }
    )
    assert res_update.status_code == 200
    updated_alert = res_update.json()
    assert updated_alert["status"] == "EXPLAINED_AUTHORIZED"
    assert "Hackathon" in updated_alert["mentor_notes"]
    assert updated_alert["resolved_at"] is not None
    print(f" Mentor advisory review completed: Status updated to {updated_alert['status']} with pastoral notes.")

    # ========================================================
    # 4. Duplicate Suppression & Delivery Retry Workflow
    # ========================================================
    print("\n--- 4. Testing Duplicate Suppression & Delivery Retry ---")

    # Test A: Immediate duplicate broadcast within window is suppressed
    res_dup = client.post(
        "/notifications/broadcast/room-change",
        headers={"Authorization": f"Bearer {mentor_token}"},
        json={
            "subject_code": "CS401",
            "section": "Section A",
            "original_room": "LT-16",
            "new_room": "LT-24",
            "new_floor": "2nd Floor (CSE)",
            "reason": "Projector maintenance in LT-16"
        }
    )
    assert res_dup.status_code == 200
    dup_data = res_dup.json()
    assert dup_data["suppressed_count"] >= 1, "Duplicate notification must be suppressed"
    print(f" Duplicate suppression verified: {dup_data['suppressed_count']} duplicate notifications suppressed.")

    # Test B: Retry Workflow for Pending / Failed Notification
    from app.core.notification_service import create_notification
    failed_notif = create_notification(
        db=db,
        recipient_id=student.id,
        category="SYSTEM_ADVISORY",
        title="Test Pending Retry",
        message="Simulated notification waiting for gateway ack",
        reference_id=f"RETRY_TEST_{time.time()}",
        force_deliver=False  # Will create as PENDING
    )
    assert failed_notif.delivery_status == "PENDING"
    assert failed_notif.retry_count == 0

    res_retry = client.post(
        f"/notifications/{failed_notif.id}/retry",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_retry.status_code == 200
    retry_resp = res_retry.json()
    assert retry_resp["delivery_status"] == "DELIVERED"
    assert retry_resp["retry_count"] == 1
    print(" Notification delivery retry succeeded: Status transitioned PENDING -> DELIVERED (Retry Count: 1).")

    # ========================================================
    # 5. System-wide Notification Feed
    # ========================================================
    print("\n--- 5. Testing Admin System-wide Notification Audit Feed ---")
    res_all = client.get("/notifications/all?limit=20", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_all.status_code == 200
    all_notifs = res_all.json()
    assert len(all_notifs) >= 4
    print(f" System-wide audit log query returned {len(all_notifs)} notifications across all categories.")

    print("\n ALL PHASE 6 NOTIFICATIONS & MENTOR ALERTS TESTS PASSED SUCCESSFULLY!\n")

if __name__ == "__main__":
    test_notifications_and_mentor_suite()
