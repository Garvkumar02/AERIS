import csv
import io
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from ..models import (
    User,
    Attendance,
    GateEvent,
    GateDevice,
    VerificationAttempt,
    WorkShift,
    LectureSession,
    Room,
    Floor,
    RoomPresence
)

def export_to_csv(headers: List[str], rows: List[List[Any]]) -> str:
    """Formats a list of headers and rows into a valid CSV string."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([str(item) if item is not None else "" for item in row])
    return output.getvalue()

def query_attendance_report(
    db: Session,
    department: Optional[str] = None,
    floor_id: Optional[str] = None,
    room_id: Optional[str] = None,
    role: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status_filter: Optional[str] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    query = (
        db.query(Attendance, User, Room, Floor)
        .join(User, Attendance.user_id == User.id)
        .outerjoin(LectureSession, Attendance.lecture_session_id == LectureSession.id)
        .outerjoin(Room, LectureSession.room_id == Room.id)
        .outerjoin(Floor, Room.floor_id == Floor.id)
    )

    if department:
        query = query.filter(User.department.ilike(f"%{department}%"))
    if role:
        query = query.filter(User.role == role.lower())
    if room_id:
        # Check either directly through lecture session or room presences
        query = query.filter(Room.id == room_id)
    if floor_id:
        query = query.filter(Floor.id == floor_id)
    if date_from:
        query = query.filter(Attendance.day >= date_from)
    if date_to:
        query = query.filter(Attendance.day <= date_to)

    query = query.order_by(desc(Attendance.checked_in_at)).limit(limit)
    results = query.all()

    report_items = []
    for att, user, room, floor in results:
        # Determine status
        att_status = "VERIFIED_PRESENT"
        if att.risk_score and att.risk_score > 60:
            att_status = "HIGH_RISK_FLAG"
        elif att.risk_score and att.risk_score > 30:
            att_status = "MEDIUM_RISK"

        if status_filter and status_filter.upper() != "ALL" and status_filter.upper() not in att_status:
            continue

        report_items.append({
            "id": att.id,
            "employee_id": user.employee_id,
            "name": user.name,
            "role": user.role,
            "department": user.department or "General",
            "day": att.day.isoformat() if att.day else "",
            "checked_in_at": att.checked_in_at.isoformat() if att.checked_in_at else "",
            "verification_method": att.verification_method,
            "room_name": room.name if room else "Campus Wide",
            "floor_name": floor.name if floor else "General",
            "face_score": att.face_score,
            "risk_score": att.risk_score or 0,
            "event_hash": att.event_hash or "",
            "status": att_status
        })

    return report_items

def attendance_report_to_csv(items: List[Dict[str, Any]]) -> str:
    headers = [
        "Attendance ID",
        "Employee ID",
        "Name",
        "Role",
        "Department",
        "Date",
        "Checked In At",
        "Verification Method",
        "Room",
        "Floor",
        "Face Score",
        "Risk Score",
        "Status",
        "Event Hash"
    ]
    rows = []
    for it in items:
        rows.append([
            it["id"],
            it["employee_id"],
            it["name"],
            it["role"],
            it["department"],
            it["day"],
            it["checked_in_at"],
            it["verification_method"],
            it["room_name"],
            it["floor_name"],
            it["face_score"],
            it["risk_score"],
            it["status"],
            it["event_hash"]
        ])
    return export_to_csv(headers, rows)

def query_gate_report(
    db: Session,
    department: Optional[str] = None,
    role: Optional[str] = None,
    direction: Optional[str] = None,
    event_type: Optional[str] = None,
    gate_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    query = (
        db.query(GateEvent, User, GateDevice)
        .join(User, GateEvent.user_id == User.id)
        .outerjoin(GateDevice, or_(GateEvent.device_id == GateDevice.device_id, GateEvent.device_id == GateDevice.id))
    )

    if department:
        query = query.filter(User.department.ilike(f"%{department}%"))
    if role:
        query = query.filter(User.role == role.lower())
    if direction and direction.upper() != "ALL":
        d_val = direction.upper()
        if d_val in ["IN", "ENTRY"]:
            query = query.filter(GateEvent.direction.in_(["IN", "ENTRY"]))
        elif d_val in ["OUT", "EXIT"]:
            query = query.filter(GateEvent.direction.in_(["OUT", "EXIT"]))
        else:
            query = query.filter(GateEvent.direction == d_val)
    if event_type and event_type.upper() != "ALL":
        query = query.filter(GateEvent.event_type == event_type.upper())
    if gate_id:
        query = query.filter(GateEvent.gate_id == gate_id)
    if date_from:
        start_dt = datetime.combine(date_from, datetime.min.time())
        query = query.filter(GateEvent.timestamp >= start_dt)
    if date_to:
        end_dt = datetime.combine(date_to, datetime.max.time())
        query = query.filter(GateEvent.timestamp <= end_dt)

    query = query.order_by(desc(GateEvent.timestamp)).limit(limit)
    results = query.all()

    items = []
    for evt, user, dev in results:
        g_name = dev.gate_name if (dev and hasattr(dev, "gate_name") and dev.gate_name) else evt.gate_id
        items.append({
            "id": evt.id,
            "employee_id": user.employee_id,
            "name": user.name,
            "role": user.role,
            "department": user.department or "General",
            "gate_id": evt.gate_id,
            "gate_name": g_name,
            "direction": evt.direction,
            "event_type": evt.event_type,
            "timestamp": evt.timestamp.isoformat() if evt.timestamp else "",
            "synced_offline": bool(evt.synced_offline),
            "event_hash": evt.event_hash or ""
        })
    return items

def gate_report_to_csv(items: List[Dict[str, Any]]) -> str:
    headers = [
        "Event ID",
        "Employee ID",
        "Name",
        "Role",
        "Department",
        "Gate ID",
        "Gate Name",
        "Direction",
        "Event Type",
        "Timestamp",
        "Offline Synced",
        "Event Hash"
    ]
    rows = []
    for it in items:
        rows.append([
            it["id"],
            it["employee_id"],
            it["name"],
            it["role"],
            it["department"],
            it["gate_id"],
            it["gate_name"],
            it["direction"],
            it["event_type"],
            it["timestamp"],
            "Yes" if it["synced_offline"] else "No",
            it["event_hash"]
        ])
    return export_to_csv(headers, rows)

def query_staff_duty_report(
    db: Session,
    department: Optional[str] = None,
    role: Optional[str] = None,
    shift_status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    target_roles = ["staff", "guard", "worker", "faculty"]
    if role and role.lower() in target_roles:
        target_roles = [role.lower()]

    query = (
        db.query(WorkShift, User)
        .join(User, WorkShift.user_id == User.id)
        .filter(User.role.in_(target_roles))
    )

    if department:
        query = query.filter(User.department.ilike(f"%{department}%"))

    query = query.limit(limit)
    shifts = query.all()

    target_date = date_from or date.today()
    # Check if staff checked in on target_date
    user_ids = [u.id for _, u in shifts]
    attendances = (
        db.query(Attendance)
        .filter(Attendance.user_id.in_(user_ids), Attendance.day == target_date)
        .all()
    )
    att_by_user = {att.user_id: att for att in attendances}

    items = []
    for shift, user in shifts:
        has_checked_in = user.id in att_by_user
        att = att_by_user.get(user.id)
        computed_status = "COMPLETED" if has_checked_in else "PENDING_OR_ABSENT"

        if shift_status and shift_status.upper() != "ALL":
            if shift_status.upper() == "COMPLETED" and not has_checked_in:
                continue
            if shift_status.upper() in ["ABSENT", "PENDING"] and has_checked_in:
                continue

        items.append({
            "shift_id": shift.id,
            "employee_id": user.employee_id,
            "name": user.name,
            "role": user.role,
            "department": user.department or "General",
            "shift_name": shift.shift_name,
            "start_time": shift.start_time,
            "end_time": shift.end_time,
            "assigned_location": shift.assigned_location,
            "scheduled_days": shift.days,
            "duty_date": target_date.isoformat(),
            "checked_in_at": att.checked_in_at.isoformat() if (att and att.checked_in_at) else "N/A",
            "duty_status": computed_status
        })

    return items

def staff_duty_report_to_csv(items: List[Dict[str, Any]]) -> str:
    headers = [
        "Shift ID",
        "Employee ID",
        "Name",
        "Role",
        "Department",
        "Shift Name",
        "Start Time",
        "End Time",
        "Assigned Location",
        "Duty Date",
        "Checked In At",
        "Duty Status"
    ]
    rows = []
    for it in items:
        rows.append([
            it["shift_id"],
            it["employee_id"],
            it["name"],
            it["role"],
            it["department"],
            it["shift_name"],
            it["start_time"],
            it["end_time"],
            it["assigned_location"],
            it["duty_date"],
            it["checked_in_at"],
            it["duty_status"]
        ])
    return export_to_csv(headers, rows)

def query_verification_report(
    db: Session,
    department: Optional[str] = None,
    role: Optional[str] = None,
    result: Optional[str] = None,
    failure_code: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    query = (
        db.query(VerificationAttempt, User)
        .join(User, VerificationAttempt.user_id == User.id)
    )

    if department:
        query = query.filter(User.department.ilike(f"%{department}%"))
    if role:
        query = query.filter(User.role == role.lower())
    if result and result.upper() != "ALL":
        query = query.filter(VerificationAttempt.result == result.upper())
    if failure_code and failure_code.upper() != "ALL":
        query = query.filter(VerificationAttempt.failure_code == failure_code.upper())
    if date_from:
        start_dt = datetime.combine(date_from, datetime.min.time())
        query = query.filter(VerificationAttempt.created_at >= start_dt)
    if date_to:
        end_dt = datetime.combine(date_to, datetime.max.time())
        query = query.filter(VerificationAttempt.created_at <= end_dt)

    query = query.order_by(desc(VerificationAttempt.created_at)).limit(limit)
    results = query.all()

    items = []
    for att, user in results:
        items.append({
            "id": att.id,
            "employee_id": user.employee_id,
            "name": user.name,
            "role": user.role,
            "department": user.department or "General",
            "result": att.result,
            "failure_code": att.failure_code or "NONE",
            "face_score": att.face_score,
            "distance_m": att.distance_m,
            "device_id": att.device_id or "DEVICE-UNKNOWN",
            "created_at": att.created_at.isoformat() if att.created_at else ""
        })
    return items

def verification_report_to_csv(items: List[Dict[str, Any]]) -> str:
    headers = [
        "Attempt ID",
        "Employee ID",
        "Name",
        "Role",
        "Department",
        "Result",
        "Failure Code",
        "Face Score",
        "Distance (m)",
        "Device ID",
        "Timestamp"
    ]
    rows = []
    for it in items:
        rows.append([
            it["id"],
            it["employee_id"],
            it["name"],
            it["role"],
            it["department"],
            it["result"],
            it["failure_code"],
            it["face_score"],
            it["distance_m"],
            it["device_id"],
            it["created_at"]
        ])
    return export_to_csv(headers, rows)
