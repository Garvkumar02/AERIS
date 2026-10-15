import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Notification, MentorAlert, LectureSession
from ..schemas import (
    NotificationResponse, RescheduleClassRequest, RoomChangeAlertRequest,
    ExamAlertRequest, MentorAlertResponse, UpdateMentorAlertStatusRequest,
    BroadcastAlertResponse, CheckAbsenceAlertsResponse
)
from ..core.security import get_current_user
from ..core.notification_service import (
    create_notification, retry_notification_delivery, evaluate_and_trigger_mentor_absence_alerts
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

def _to_notif_resp(n: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=n.id,
        recipient_id=n.recipient_id,
        recipient_name=n.recipient.name if n.recipient else None,
        recipient_role=n.recipient.role if n.recipient else None,
        category=n.category,
        title=n.title,
        message=n.message,
        priority=n.priority,
        channel=n.channel,
        delivery_status=n.delivery_status,
        retry_count=n.retry_count,
        max_retries=n.max_retries,
        last_attempt_at=n.last_attempt_at.isoformat() if n.last_attempt_at else None,
        delivered_at=n.delivered_at.isoformat() if n.delivered_at else None,
        read_at=n.read_at.isoformat() if n.read_at else None,
        is_read=n.is_read,
        dedup_key=n.dedup_key,
        metadata_payload=n.metadata_payload,
        created_at=n.created_at.isoformat() if n.created_at else datetime.utcnow().isoformat()
    )

def _to_mentor_alert_resp(a: MentorAlert) -> MentorAlertResponse:
    return MentorAlertResponse(
        id=a.id,
        student_id=a.student_id,
        student_name=a.student.name if a.student else "Student",
        student_roll=a.student.employee_id if a.student else "N/A",
        student_department=a.student.department if a.student else None,
        mentor_id=a.mentor_id,
        mentor_name=a.mentor.name if a.mentor else "Mentor",
        subject_name=a.subject_name,
        subject_code=a.subject_code,
        room_number=a.room_number,
        absence_duration_minutes=a.absence_duration_minutes,
        gate_presence_status=a.gate_presence_status,
        room_presence_status=a.room_presence_status,
        status=a.status,
        is_misconduct_charge=a.is_misconduct_charge,  # Strictly False: Advisory inquiry
        disclaimer=a.disclaimer,
        mentor_notes=a.mentor_notes,
        triggered_at=a.triggered_at.isoformat() if a.triggered_at else datetime.utcnow().isoformat(),
        resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
        notification_id=a.notification_id
    )

@router.get("/my", response_model=List[NotificationResponse])
def get_my_notifications(
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetches in-app notifications for the logged-in user."""
    query = db.query(Notification).filter(Notification.recipient_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return [_to_notif_resp(n) for n in notifications]

@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Marks a notification as read."""
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.recipient_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    notif.read_at = datetime.utcnow()
    db.commit()
    db.refresh(notif)
    return _to_notif_resp(notif)

@router.post("/{notification_id}/retry", response_model=NotificationResponse)
def retry_single_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retries transmission for a failed or pending notification."""
    try:
        updated = retry_notification_delivery(db, notification_id)
        return _to_notif_resp(updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/retry-failed", response_model=Dict[str, Any])
def retry_all_failed_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retries all pending/failed notifications across the system (admin/faculty only)."""
    if current_user.role not in ["admin", "faculty"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    failed = db.query(Notification).filter(
        Notification.delivery_status.in_(["FAILED", "PENDING"]),
        Notification.retry_count < Notification.max_retries
    ).all()

    retried_count = 0
    for n in failed:
        retry_notification_delivery(db, n.id)
        retried_count += 1

    return {"status": "ok", "retried_count": retried_count}

@router.post("/broadcast/reschedule", response_model=BroadcastAlertResponse)
def broadcast_class_rescheduling(
    payload: RescheduleClassRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Broadcasts a class rescheduling alert to students and faculty."""
    if current_user.role not in ["admin", "faculty"]:
        raise HTTPException(status_code=403, detail="Only faculty or administrators can reschedule classes")

    students = db.query(User).filter(User.role == "student", User.status == "active").all()
    created_list = []
    suppressed_count = 0

    title = f"Class Rescheduled: {payload.subject_code}"
    message = (
        f"Notice: Class for {payload.subject_code} ({payload.section}) originally at {payload.original_time} "
        f"has been rescheduled to {payload.new_time} on {payload.new_date}. Reason: {payload.reason}."
    )

    for stu in students:
        notif = create_notification(
            db=db,
            recipient_id=stu.id,
            category="CLASS_RESCHEDULED",
            title=title,
            message=message,
            priority="HIGH",
            channel="IN_APP",
            reference_id=f"{payload.subject_code}:{payload.new_date}:{payload.new_time}",
            metadata_payload=payload.dict(),
            dedup_window_minutes=30
        )
        if notif.delivery_status == "SUPPRESSED_DUPLICATE":
            suppressed_count += 1
        created_list.append(notif)

    return BroadcastAlertResponse(
        status="BROADCAST_COMPLETED",
        recipients_count=len(created_list),
        suppressed_count=suppressed_count,
        category="CLASS_RESCHEDULED",
        message=f"Class rescheduling alert broadcasted to {len(created_list)} students.",
        notifications=[_to_notif_resp(n) for n in created_list[:10]]
    )

@router.post("/broadcast/room-change", response_model=BroadcastAlertResponse)
def broadcast_room_change(
    payload: RoomChangeAlertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Broadcasts an urgent venue/room change notification."""
    if current_user.role not in ["admin", "faculty"]:
        raise HTTPException(status_code=403, detail="Only faculty or administrators can dispatch room change alerts")

    students = db.query(User).filter(User.role == "student", User.status == "active").all()
    created_list = []
    suppressed_count = 0

    title = f"Room Change Notice: {payload.subject_code}"
    message = (
        f"Venue Update: Class {payload.subject_code} ({payload.section}) has been relocated from "
        f"{payload.original_room} to {payload.new_room} ({payload.new_floor}). Reason: {payload.reason}."
    )

    for stu in students:
        notif = create_notification(
            db=db,
            recipient_id=stu.id,
            category="ROOM_CHANGED",
            title=title,
            message=message,
            priority="URGENT",
            channel="IN_APP",
            reference_id=f"{payload.subject_code}:{payload.original_room}->{payload.new_room}",
            metadata_payload=payload.dict(),
            dedup_window_minutes=20
        )
        if notif.delivery_status == "SUPPRESSED_DUPLICATE":
            suppressed_count += 1
        created_list.append(notif)

    return BroadcastAlertResponse(
        status="BROADCAST_COMPLETED",
        recipients_count=len(created_list),
        suppressed_count=suppressed_count,
        category="ROOM_CHANGED",
        message=f"Room change alert broadcasted to {len(created_list)} students.",
        notifications=[_to_notif_resp(n) for n in created_list[:10]]
    )

@router.post("/broadcast/exam-alert", response_model=BroadcastAlertResponse)
def broadcast_exam_alert(
    payload: ExamAlertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Broadcasts high-priority examination instructions and desk allocation alerts."""
    if current_user.role not in ["admin", "faculty"]:
        raise HTTPException(status_code=403, detail="Only administrators or faculty can dispatch exam alerts")

    students = db.query(User).filter(User.role == "student", User.status == "active").all()
    created_list = []
    suppressed_count = 0

    title = f"Exam Alert: {payload.exam_title} ({payload.subject_code})"
    message = (
        f"Important: {payload.exam_title} for {payload.subject_name} ({payload.subject_code}) is scheduled "
        f"on {payload.exam_date} from {payload.start_time} to {payload.end_time} in {payload.room_number}. "
        f"Reporting time is 15 minutes prior. Biometric gate & double verification will be required."
    )

    for stu in students:
        notif = create_notification(
            db=db,
            recipient_id=stu.id,
            category="EXAM_ALERT",
            title=title,
            message=message,
            priority="URGENT",
            channel="IN_APP",
            reference_id=f"{payload.subject_code}:{payload.exam_title}:{payload.exam_date}",
            metadata_payload=payload.dict(),
            dedup_window_minutes=60
        )
        if notif.delivery_status == "SUPPRESSED_DUPLICATE":
            suppressed_count += 1
        created_list.append(notif)

    return BroadcastAlertResponse(
        status="BROADCAST_COMPLETED",
        recipients_count=len(created_list),
        suppressed_count=suppressed_count,
        category="EXAM_ALERT",
        message=f"Exam alert broadcasted to {len(created_list)} students.",
        notifications=[_to_notif_resp(n) for n in created_list[:10]]
    )

@router.post("/check-absences", response_model=CheckAbsenceAlertsResponse)
def check_absences_and_notify_mentors(
    min_absence_minutes: int = Query(10, ge=1, le=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Evaluates running lectures > min_absence_minutes (default 10 min).
    Generates supportive mentor alerts for verified absences.
    Mandatory: Alert does NOT constitute an automatic misconduct decision.
    """
    if current_user.role not in ["admin", "faculty"]:
        raise HTTPException(status_code=403, detail="Only faculty and admin can trigger absence evaluations")

    active_count = db.query(LectureSession).filter(LectureSession.status == "active").count()
    alerts = evaluate_and_trigger_mentor_absence_alerts(db, min_absence_minutes=min_absence_minutes)

    return CheckAbsenceAlertsResponse(
        lectures_checked=active_count,
        alerts_generated=len(alerts),
        alerts=[_to_mentor_alert_resp(a) for a in alerts]
    )

@router.get("/mentor/alerts", response_model=List[MentorAlertResponse])
def get_mentor_alerts(
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetches mentor alerts for the current faculty member or all if admin."""
    query = db.query(MentorAlert)
    if current_user.role != "admin":
        query = query.filter(MentorAlert.mentor_id == current_user.id)

    if status_filter:
        query = query.filter(MentorAlert.status == status_filter)

    alerts = query.order_by(MentorAlert.triggered_at.desc()).limit(limit).all()
    return [_to_mentor_alert_resp(a) for a in alerts]

@router.post("/mentor/alerts/{alert_id}/update-status", response_model=MentorAlertResponse)
def update_mentor_alert_status(
    alert_id: str,
    payload: UpdateMentorAlertStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates the pastoral action status of a mentor alert."""
    alert = db.query(MentorAlert).filter(MentorAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Mentor alert not found")

    if current_user.role != "admin" and alert.mentor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to update this mentor alert")

    alert.status = payload.status
    if payload.mentor_notes:
        alert.mentor_notes = payload.mentor_notes
    if payload.status in ["STUDENT_CONTACTED", "EXPLAINED_AUTHORIZED", "DEFERRED", "ESCALATED_COUNSELING"]:
        alert.resolved_at = datetime.utcnow()

    db.commit()
    db.refresh(alert)
    return _to_mentor_alert_resp(alert)

@router.get("/all", response_model=List[NotificationResponse])
def get_all_notifications_admin(
    limit: int = Query(100, ge=1, le=500),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """System-wide notification feed for administration audit."""
    if current_user.role not in ["admin", "faculty"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    query = db.query(Notification)
    if category:
        query = query.filter(Notification.category == category)
    if status:
        query = query.filter(Notification.delivery_status == status)

    items = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return [_to_notif_resp(n) for n in items]
