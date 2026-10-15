import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from ..models import (
    Notification, MentorAlert, User, LectureSession, TimetableSession, Attendance, GateEvent, RoomPresence
)

def compute_dedup_key(recipient_id: str, category: str, reference_id: str, window_minutes: int = 30) -> str:
    """
    Computes a deterministic deduplication key bucketed by time window (default 30 min).
    Prevents repeated spamming of identical alerts.
    """
    time_bucket = int(time.time() // (window_minutes * 60))
    raw_str = f"{recipient_id}:{category}:{reference_id}:{time_bucket}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

def create_notification(
    db: Session,
    recipient_id: str,
    category: str,
    title: str,
    message: str,
    priority: str = "NORMAL",
    channel: str = "IN_APP",
    reference_id: Optional[str] = None,
    metadata_payload: Optional[Dict[str, Any]] = None,
    dedup_window_minutes: int = 30,
    force_deliver: bool = True
) -> Notification:
    """
    Creates a notification with duplicate suppression and delivery lifecycle tracking.
    """
    ref = reference_id or category
    dedup = compute_dedup_key(recipient_id, category, ref, dedup_window_minutes)

    # Check for existing notification with same dedup_key within suppression window
    cutoff = datetime.utcnow() - timedelta(minutes=dedup_window_minutes)
    existing = db.query(Notification).filter(
        Notification.recipient_id == recipient_id,
        Notification.dedup_key == dedup,
        Notification.created_at >= cutoff
    ).first()

    now = datetime.utcnow()
    delivery_status = "DELIVERED" if force_deliver else "PENDING"
    delivered_at = now if force_deliver else None

    if existing:
        # Duplicate suppressed
        delivery_status = "SUPPRESSED_DUPLICATE"
        delivered_at = None

    notif = Notification(
        recipient_id=recipient_id,
        category=category,
        title=title,
        message=message,
        priority=priority,
        channel=channel,
        delivery_status=delivery_status,
        retry_count=0,
        max_retries=3,
        last_attempt_at=now,
        delivered_at=delivered_at,
        is_read=False,
        dedup_key=dedup,
        metadata_payload=metadata_payload or {},
        created_at=now
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif

def retry_notification_delivery(db: Session, notification_id: str) -> Notification:
    """
    Retries delivery for a failed or pending notification.
    """
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise ValueError("Notification not found")

    if notif.delivery_status == "DELIVERED":
        return notif

    notif.retry_count += 1
    notif.last_attempt_at = datetime.utcnow()

    if notif.retry_count <= notif.max_retries:
        # Simulated transmission through delivery channel
        notif.delivery_status = "DELIVERED"
        notif.delivered_at = datetime.utcnow()
    else:
        notif.delivery_status = "FAILED"

    db.commit()
    db.refresh(notif)
    return notif

def send_attendance_notification(
    db: Session,
    user: User,
    lecture: Optional[LectureSession],
    result: str,
    code: Optional[str] = None,
    receipt_hash: Optional[str] = None,
    failure_message: Optional[str] = None
) -> Notification:
    """
    Dispatches immediate attendance success or failure notification to student.
    """
    subj = lecture.subject_code if lecture else "CLASS"
    subj_name = lecture.subject_name if lecture else "Scheduled Lecture"
    room_code = lecture.room.room_number if (lecture and lecture.room) else "Classroom"

    if result == "ACCEPT":
        category = "ATTENDANCE_SUCCESS"
        title = f"Attendance Confirmed: {subj}"
        msg = f"Your double-verified attendance for {subj_name} in {room_code} was recorded. Receipt Hash: {receipt_hash[:16] if receipt_hash else 'verified'}..."
        meta = {
            "lecture_id": lecture.id if lecture else None,
            "subject_code": subj,
            "room": room_code,
            "receipt_hash": receipt_hash,
            "status": "CONFIRMED"
        }
        priority = "NORMAL"
    else:
        category = "ATTENDANCE_FAILURE"
        title = f"Attendance Failed: {subj} ({code or 'VERIFICATION_ERROR'})"
        msg = f"Your attendance attempt for {subj_name} was rejected: {failure_message or 'Verification requirements not satisfied'}. Please retry before lecture conclusion."
        meta = {
            "lecture_id": lecture.id if lecture else None,
            "subject_code": subj,
            "failure_code": code,
            "reason": failure_message,
            "status": "REJECTED"
        }
        priority = "HIGH"

    return create_notification(
        db=db,
        recipient_id=user.id,
        category=category,
        title=title,
        message=msg,
        priority=priority,
        reference_id=f"{lecture.id if lecture else 'L'}:{result}:{code or 'OK'}",
        metadata_payload=meta,
        dedup_window_minutes=5  # 5-min window for rapid attendance feedback
    )

def evaluate_and_trigger_mentor_absence_alerts(
    db: Session,
    min_absence_minutes: int = 10
) -> List[MentorAlert]:
    """
    Core Phase 6 Requirement:
    - Verified absence > 10 minutes from lecture start triggers an alert to the student's mentor.
    - STRICT REQUIREMENT: "Alert ka matlab automatic misconduct decision nahi hoga."
      -> Marked as an advisory/wellness inquiry (is_misconduct_charge=False), NOT disciplinary action.
    """
    now = datetime.utcnow()
    active_lectures = db.query(LectureSession).filter(LectureSession.status == "active").all()
    created_alerts: List[MentorAlert] = []

    for lec in active_lectures:
        elapsed = (now - lec.started_at).total_seconds() / 60.0
        if elapsed < min_absence_minutes:
            continue

        # Find candidate students in the same department/section or campus
        # Default: all active students in the lecture's department (or section)
        candidate_students = db.query(User).filter(
            User.role == "student",
            User.status == "active"
        )
        if lec.faculty and lec.faculty.department:
            dept_students = candidate_students.filter(User.department == lec.faculty.department).all()
            if dept_students:
                candidate_students = dept_students
            else:
                candidate_students = candidate_students.limit(10).all()
        else:
            candidate_students = candidate_students.limit(10).all()

        for student in candidate_students:
            # 1. Check if student already checked in to this lecture
            att = db.query(Attendance).filter(
                Attendance.user_id == student.id,
                Attendance.lecture_session_id == lec.id
            ).first()
            if att:
                continue

            # 2. Check if a mentor alert was already created for this student and lecture
            existing_alert = db.query(MentorAlert).filter(
                MentorAlert.student_id == student.id,
                MentorAlert.lecture_session_id == lec.id
            ).first()
            if existing_alert:
                continue

            # 3. Find Mentor (student.mentor or default faculty)
            mentor = student.mentor
            if not mentor:
                mentor = lec.faculty or db.query(User).filter(User.role == "faculty").first()
            if not mentor:
                continue

            # 4. Determine Gate Presence (Entered campus today?)
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            latest_gate_entry = db.query(GateEvent).filter(
                GateEvent.user_id == student.id,
                GateEvent.direction == "ENTRY",
                GateEvent.timestamp >= today_start
            ).order_by(GateEvent.timestamp.desc()).first()

            latest_gate_exit = db.query(GateEvent).filter(
                GateEvent.user_id == student.id,
                GateEvent.direction == "EXIT",
                GateEvent.timestamp >= today_start
            ).order_by(GateEvent.timestamp.desc()).first()

            gate_status = "UNKNOWN"
            if latest_gate_entry:
                if latest_gate_exit and latest_gate_exit.timestamp > latest_gate_entry.timestamp:
                    gate_status = "OFF_CAMPUS"
                else:
                    gate_status = "ON_CAMPUS_GATE_VERIFIED"
            else:
                gate_status = "OFF_CAMPUS"

            # 5. Determine Room Presence
            room_presence = db.query(RoomPresence).filter(
                RoomPresence.user_id == student.id,
                RoomPresence.room_id == lec.room_id,
                RoomPresence.status == "active",
                RoomPresence.check_out_at.is_(None)
            ).first()
            room_status = "IN_ASSIGNED_ROOM" if room_presence else "NOT_IN_ASSIGNED_ROOM"

            # If in room, student is physically present, skip alert
            if room_status == "IN_ASSIGNED_ROOM":
                continue

            absence_mins = int(elapsed)
            room_num = lec.room.room_number if lec.room else "Room"

            # 6. Create Notification for Mentor
            notif_msg = (
                f"Advisory Wellness Alert: Student {student.name} ({student.employee_id}) has not checked in to "
                f"{lec.subject_name} ({lec.subject_code}, {room_num}) after {absence_mins} minutes. "
                f"Gate status: {gate_status}. Please conduct an advisory wellness check. "
                f"Note: This alert is for pastoral support and is NOT a misconduct finding."
            )

            notif = create_notification(
                db=db,
                recipient_id=mentor.id,
                category="MENTOR_ABSENCE_ALERT",
                title=f"Wellness Alert: {student.name} Absent ({absence_mins}m in {lec.subject_code})",
                message=notif_msg,
                priority="HIGH",
                channel="IN_APP",
                reference_id=f"{student.id}:{lec.id}:ABSENCE",
                metadata_payload={
                    "student_id": student.id,
                    "student_name": student.name,
                    "student_roll": student.employee_id,
                    "lecture_id": lec.id,
                    "subject_code": lec.subject_code,
                    "room_number": room_num,
                    "absence_duration_minutes": absence_mins,
                    "gate_presence_status": gate_status,
                    "is_misconduct_charge": False
                },
                dedup_window_minutes=60
            )

            # 7. Create MentorAlert Record
            alert = MentorAlert(
                student_id=student.id,
                mentor_id=mentor.id,
                lecture_session_id=lec.id,
                timetable_session_id=lec.timetable_session_id,
                subject_name=lec.subject_name,
                subject_code=lec.subject_code,
                room_number=room_num,
                absence_duration_minutes=absence_mins,
                gate_presence_status=gate_status,
                room_presence_status=room_status,
                status="ADVISORY_PENDING",
                is_misconduct_charge=False,  # STRICT REQUIREMENT: Not an automatic misconduct decision
                disclaimer="Advisory wellness inquiry only. Not a disciplinary finding or misconduct charge.",
                mentor_notes=None,
                triggered_at=now,
                notification_id=notif.id
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            created_alerts.append(alert)

    return created_alerts
