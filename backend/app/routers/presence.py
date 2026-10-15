import uuid
import time
import os
import hmac
import hashlib
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Room, Floor, Building, RoomPresence, TimetableSession, LectureSession
from ..schemas import (
    RoomCheckInRequest, RoomCheckOutRequest, RoomPresenceReceiptResponse,
    RoomOccupancyStatusResponse, FloorPresenceSummaryResponse, ConfirmedAttendeeItem
)
from ..core.security import get_current_user, compute_room_presence_hash, GENESIS_HASH

router = APIRouter(prefix="/presence", tags=["presence"])

ALLOWED_INDOOR_METHODS = {
    "INDOOR_QR": "Indoor Physical / Digital Wall QR Badge",
    "BLE_BEACON": "Bluetooth Low Energy Proximity Beacon (RSSI)",
    "WIFI_BSSID": "Floor Access Point BSSID Fingerprint",
    "RFID_NFC": "Contactless RFID / NFC Door Sensor",
    "FACIAL_KIOSK": "Indoor Facial Recognition Kiosk",
    "MANUAL_OVERRIDE": "Authorized Staff / Guard Clearance"
}

def calculate_room_occupancy(room: Room, db: Session) -> Dict[str, Any]:
    """
    Computes confirmed presence vs estimated occupancy:
    1. Confirmed Presence = count of authenticated users with active room check-in.
    2. Estimated Occupancy = mathematically modeled count combining confirmed presence,
       scheduled timetable classes in session, and sensor weighting.
    """
    # 1. Confirmed Presence Roster
    active_presences = db.query(RoomPresence).filter(
        RoomPresence.room_id == room.id,
        RoomPresence.status == "active",
        RoomPresence.check_out_at.is_(None)
    ).all()
    confirmed_count = len(active_presences)

    attendee_items = []
    for p in active_presences:
        u = p.user
        if u:
            attendee_items.append(ConfirmedAttendeeItem(
                id=p.id,
                user_id=u.id,
                name=u.name,
                employee_id=u.employee_id,
                role=u.role,
                department=u.department or "General",
                check_in_at=p.check_in_at.isoformat() if p.check_in_at else "",
                verification_method=p.verification_method
            ))

    # 2. Check Timetable Scheduled Class Right Now
    now_dt = datetime.utcnow()
    # Map weekday (Mon=0)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    current_day = day_names[now_dt.weekday()]
    current_time_str = now_dt.strftime("%H:%M")

    # Find active scheduled class or active lecture
    active_lecture = db.query(LectureSession).filter(
        LectureSession.room_id == room.id,
        LectureSession.status == "active"
    ).first()

    scheduled_session = db.query(TimetableSession).filter(
        TimetableSession.room_id == room.id,
        TimetableSession.day_of_week == current_day,
        TimetableSession.start_time <= current_time_str,
        TimetableSession.end_time >= current_time_str
    ).first()

    scheduled_info = None
    expected_students = 0

    if active_lecture:
        scheduled_info = {
            "type": "LIVE_LECTURE",
            "subject_name": active_lecture.subject_name,
            "subject_code": active_lecture.subject_code,
            "faculty_name": active_lecture.faculty.name if active_lecture.faculty else "Faculty",
            "section": active_lecture.section
        }
        # In a live lecture session, expected students is typically 50-80% of capacity
        expected_students = int(room.capacity * 0.70)
    elif scheduled_session:
        scheduled_info = {
            "type": "TIMETABLE_CLASS",
            "subject_name": scheduled_session.subject_name,
            "subject_code": scheduled_session.subject_code,
            "faculty_name": scheduled_session.faculty.name if scheduled_session.faculty else "Faculty",
            "section": scheduled_session.section
        }
        expected_students = int(room.capacity * 0.65)

    # 3. Blended Estimated Occupancy Model
    # Blend: Max between confirmed presence and estimated crowd based on schedule/flow
    if expected_students > 0:
        # Scheduled class is underway: confirmed check-ins + estimated students yet to scan
        estimated = max(confirmed_count, min(room.capacity, int(confirmed_count * 1.10 + expected_students * 0.75)))
    else:
        # Incidental traffic (e.g. library, staff lounge, lab work)
        estimated = max(confirmed_count, int(confirmed_count * 1.15))

    estimated = max(0, min(room.capacity, estimated))
    occupancy_pct = round((estimated / max(room.capacity, 1)) * 100, 1)

    # Status evaluation
    if estimated == 0:
        occ_status = "Vacant"
    elif occupancy_pct > 95:
        occ_status = "Over Capacity"
    elif occupancy_pct > 75:
        occ_status = "Crowded"
    else:
        occ_status = "Optimal"

    return {
        "confirmed_presence": confirmed_count,
        "estimated_occupancy": estimated,
        "occupancy_rate_pct": occupancy_pct,
        "status": occ_status,
        "scheduled_class": scheduled_info,
        "confirmed_attendees": attendee_items
    }

@router.post("/check-in", response_model=RoomPresenceReceiptResponse)
def room_check_in(
    payload: RoomCheckInRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Authorized room-level check-in using indoor non-GPS validated verification methods:
    INDOOR_QR, BLE_BEACON, WIFI_BSSID, RFID_NFC, FACIAL_KIOSK, or MANUAL_OVERRIDE.
    """
    room = db.query(Room).filter(Room.id == payload.room_id).first()
    if not room:
        room = db.query(Room).filter(Room.room_number == payload.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Designated room or venue not found")

    method = payload.verification_method.upper()
    if method not in ALLOWED_INDOOR_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid verification method '{method}'. Must be one of: {list(ALLOWED_INDOOR_METHODS.keys())}"
        )

    target_user = current_user
    if current_user.role == "admin" and payload.user_id:
        lookup_u = db.query(User).filter((User.id == payload.user_id) | (User.employee_id == payload.user_id)).first()
        if lookup_u:
            target_user = lookup_u

    # 1. Role Authorization Check
    # Staff rooms and offices require staff, faculty, or admin role
    if room.room_type in ["staff_room", "office"] and target_user.role not in ["staff", "faculty", "admin"]:
        raise HTTPException(
            status_code=403,
            detail=f"Access Denied: Room {room.room_number} ({room.name}) is restricted to faculty and authorized institutional staff. Role '{target_user.role}' is not authorized."
        )

    # Check custom authorized_roles if defined
    if room.authorized_roles and isinstance(room.authorized_roles, list) and len(room.authorized_roles) > 0:
        if "all" not in room.authorized_roles and target_user.role not in room.authorized_roles and target_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail=f"Access Denied: User role '{target_user.role}' not authorized for {room.room_number}."
            )

    # 2. Indoor Verification Evidence Validation (Reject sole GPS)
    ev = payload.evidence_payload or {}
    if method == "BLE_BEACON":
        rssi = ev.get("rssi", ev.get("beacon_rssi", -65))
        if rssi < -85:
            raise HTTPException(status_code=400, detail="BLE beacon signal too weak for confirmed room presence.")
    elif method == "WIFI_BSSID":
        bssid = ev.get("bssid", "")
        if not bssid:
            raise HTTPException(status_code=400, detail="Floor Wi-Fi BSSID evidence is required.")

    # 3. Clean Handover: End any existing active presence session for this user
    active_previous = db.query(RoomPresence).filter(
        RoomPresence.user_id == target_user.id,
        RoomPresence.status == "active",
        RoomPresence.check_out_at.is_(None)
    ).all()
    for prev_p in active_previous:
        prev_p.status = "completed"
        prev_p.check_out_at = datetime.utcnow()

    # 4. Cryptographic Chaining
    now = datetime.utcnow()
    last_presence = db.query(RoomPresence).order_by(RoomPresence.check_in_at.desc()).first()
    prev_hash = last_presence.presence_hash if (last_presence and last_presence.presence_hash) else GENESIS_HASH

    presence_id = str(uuid.uuid4())
    time_str = now.isoformat()

    presence_hash = compute_room_presence_hash(
        prev_hash=prev_hash,
        presence_id=presence_id,
        user_id=target_user.id,
        room_id=room.id,
        verification_method=method,
        check_in_at_str=time_str
    )

    presence = RoomPresence(
        id=presence_id,
        user_id=target_user.id,
        room_id=room.id,
        check_in_at=now,
        verification_method=method,
        device_id=payload.device_id or "DEVICE-DEFAULT",
        evidence_payload=ev,
        status="active",
        prev_hash=prev_hash,
        presence_hash=presence_hash
    )
    db.add(presence)

    # Update room occupancy
    room.current_occupancy = db.query(RoomPresence).filter(
        RoomPresence.room_id == room.id,
        RoomPresence.status == "active",
        RoomPresence.check_out_at.is_(None)
    ).count() + 1

    db.commit()

    floor_name = room.floor.name if room.floor else "Floor"

    return RoomPresenceReceiptResponse(
        status="CONFIRMED",
        message=f"Successfully checked in to {room.room_number} ({room.name}) on {floor_name}.",
        presence_id=presence.id,
        room_id=room.id,
        room_number=room.room_number,
        room_name=room.name,
        floor_name=floor_name,
        user_name=target_user.name,
        check_in_at=time_str,
        verification_method=method,
        presence_hash=presence_hash
    )

@router.post("/check-out")
def room_check_out(
    payload: RoomCheckOutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Checks out of a room presence session."""
    target_user = current_user
    if current_user.role == "admin" and payload.user_id:
        lookup_u = db.query(User).filter((User.id == payload.user_id) | (User.employee_id == payload.user_id)).first()
        if lookup_u:
            target_user = lookup_u

    query = db.query(RoomPresence).filter(
        RoomPresence.user_id == target_user.id,
        RoomPresence.status == "active",
        RoomPresence.check_out_at.is_(None)
    )

    if payload.room_id:
        query = query.filter(RoomPresence.room_id == payload.room_id)

    active_p = query.first()
    if not active_p:
        return {"status": "ok", "message": "No active presence session found to check out."}

    now = datetime.utcnow()
    active_p.check_out_at = now
    active_p.status = "completed"

    # Recalculate room occupancy
    room = active_p.room
    if room:
        room.current_occupancy = max(0, db.query(RoomPresence).filter(
            RoomPresence.room_id == room.id,
            RoomPresence.status == "active",
            RoomPresence.check_out_at.is_(None)
        ).count() - 1)

    db.commit()

    duration_min = round((now - active_p.check_in_at).total_seconds() / 60, 1)

    return {
        "status": "COMPLETED",
        "message": f"Checked out of {room.room_number if room else 'Room'}. Duration: {duration_min} minutes.",
        "presence_id": active_p.id,
        "duration_minutes": duration_min
    }

@router.get("/room/{room_id}/status", response_model=RoomOccupancyStatusResponse)
def get_room_presence_status(
    room_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns live room status with distinct confirmed presence count vs estimated occupancy.
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        room = db.query(Room).filter(Room.room_number == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    occ_data = calculate_room_occupancy(room, db)

    return RoomOccupancyStatusResponse(
        room_id=room.id,
        room_number=room.room_number,
        room_name=room.name,
        room_type=room.room_type,
        floor_id=room.floor_id,
        floor_name=room.floor.name if room.floor else "Floor",
        floor_number=room.floor.floor_number if room.floor else 0,
        capacity=room.capacity,
        confirmed_presence=occ_data["confirmed_presence"],
        estimated_occupancy=occ_data["estimated_occupancy"],
        occupancy_rate_pct=occ_data["occupancy_rate_pct"],
        status=occ_data["status"],
        scheduled_class=occ_data["scheduled_class"],
        confirmed_attendees=occ_data["confirmed_attendees"]
    )

@router.get("/floors", response_model=List[FloorPresenceSummaryResponse])
def get_floor_presence_hierarchy(
    db: Session = Depends(get_db)
):
    """
    Returns full floor-wise hierarchy across classrooms, labs, libraries, staff rooms, and common areas.
    Distinguishes confirmed presence from estimated occupancy on every floor.
    """
    floors = db.query(Floor).order_by(Floor.floor_number.asc()).all()
    results = []

    for fl in floors:
        bldg_name = fl.building.name if fl.building else "Main Academic Block"
        room_responses = []

        total_floor_confirmed = 0
        total_floor_estimated = 0
        total_floor_capacity = 0

        for rm in fl.rooms:
            occ = calculate_room_occupancy(rm, db)
            total_floor_confirmed += occ["confirmed_presence"]
            total_floor_estimated += occ["estimated_occupancy"]
            total_floor_capacity += rm.capacity

            room_responses.append(RoomOccupancyStatusResponse(
                room_id=rm.id,
                room_number=rm.room_number,
                room_name=rm.name,
                room_type=rm.room_type,
                floor_id=fl.id,
                floor_name=fl.name,
                floor_number=fl.floor_number,
                capacity=rm.capacity,
                confirmed_presence=occ["confirmed_presence"],
                estimated_occupancy=occ["estimated_occupancy"],
                occupancy_rate_pct=occ["occupancy_rate_pct"],
                status=occ["status"],
                scheduled_class=occ["scheduled_class"],
                confirmed_attendees=occ["confirmed_attendees"]
            ))

        floor_pct = round((total_floor_estimated / max(total_floor_capacity, 1)) * 100, 1)
        if floor_pct > 90:
            density = "Critical"
        elif floor_pct > 70:
            density = "High"
        elif floor_pct > 30:
            density = "Moderate"
        else:
            density = "Low"

        results.append(FloorPresenceSummaryResponse(
            floor_id=fl.id,
            floor_number=fl.floor_number,
            floor_name=fl.name,
            building_name=bldg_name,
            total_confirmed_presence=total_floor_confirmed,
            total_estimated_occupancy=total_floor_estimated,
            total_capacity=total_floor_capacity,
            occupancy_rate_pct=floor_pct,
            density_status=density,
            rooms=room_responses
        ))

    return results

@router.get("/my-active")
def get_my_active_presence(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns the current user's active room presence."""
    p = db.query(RoomPresence).filter(
        RoomPresence.user_id == current_user.id,
        RoomPresence.status == "active",
        RoomPresence.check_out_at.is_(None)
    ).order_by(RoomPresence.check_in_at.desc()).first()

    if not p:
        return {"active": False, "presence": None}

    return {
        "active": True,
        "presence": {
            "id": p.id,
            "room_id": p.room_id,
            "room_number": p.room.room_number if p.room else "",
            "room_name": p.room.name if p.room else "",
            "floor_name": p.room.floor.name if (p.room and p.room.floor) else "",
            "check_in_at": p.check_in_at.isoformat() if p.check_in_at else "",
            "verification_method": p.verification_method,
            "presence_hash": p.presence_hash
        }
    }

@router.get("/room/{room_id}/qr")
def get_indoor_room_qr(
    room_id: str,
    db: Session = Depends(get_db)
):
    """
    Generates an indoor signed physical / digital badge QR for mounting inside classrooms, labs, or libraries.
    """
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        room = db.query(Room).filter(Room.room_number == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    sec = room.qr_secret or "INDOOR-SECRET-KEY-023"
    t_hour = int(time.time() // 3600)  # Rotates hourly
    payload = f"AERIS-INDOOR:{room.id}:{room.room_number}:{t_hour}"
    sig = hmac.new(sec.encode(), payload.encode(), hashlib.sha256).hexdigest()

    return {
        "room_id": room.id,
        "room_number": room.room_number,
        "room_name": room.name,
        "room_type": room.room_type,
        "floor_name": room.floor.name if room.floor else "Floor",
        "qr_token": f"{payload}:{sig}",
        "expires_in_seconds": 3600 - int(time.time() % 3600),
        "instructions": "Scan with AERIS Mobile or turnstile reader upon entering room."
    }
