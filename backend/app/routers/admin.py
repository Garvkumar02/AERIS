from datetime import date, datetime
from typing import Optional, List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, Depends, Query, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import User, Attendance, VerificationAttempt, Campus, MerkleCommitment, AuditVerificationLog, Floor, Room
from ..schemas import (
    AdminAttendanceResponse,
    AdminPresentItem,
    AdminAbsentItem,
    AdminAttemptItem,
    AdminStatsResponse,
    CampusResponse,
    CampusUpdateRequest,
    AttendanceReportItem,
    GateReportItem,
    StaffDutyReportItem,
    VerificationReportItem,
    ConsolidatedIntegrityResponse,
    AuditLogSummaryItem,
    MerkleAnchorRequest,
    MerkleCommitmentResponse,
    MerkleProofRequest,
    MerkleProofResponse,
    MerkleVerifyRequest,
    MerkleVerifyResponse
)
from ..core.security import get_current_admin, compute_attendance_event_hash, GENESIS_HASH
from ..core.reports_service import (
    query_attendance_report,
    attendance_report_to_csv,
    query_gate_report,
    gate_report_to_csv,
    query_staff_duty_report,
    staff_duty_report_to_csv,
    query_verification_report,
    verification_report_to_csv
)
from ..core.merkle_service import (
    anchor_daily_events_to_merkle,
    build_merkle_tree,
    generate_merkle_proof,
    verify_merkle_proof
)
from ..core.integrity_service import perform_consolidated_audit

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/attendance", response_model=AdminAttendanceResponse)
def get_daily_attendance(
    day: Optional[str] = Query(None, description="Format: YYYY-MM-DD"),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    target_day = date.fromisoformat(day) if day else date.today()

    # Get all active staff and student users
    users = db.query(User).filter(User.role != "admin", User.status == "active").all()
    attendances = db.query(Attendance).filter(Attendance.day == target_day).all()
    attendance_map = {att.user_id: att for att in attendances}

    present_list = []
    absent_list = []

    for user_obj in users:
        if user_obj.id in attendance_map:
            att = attendance_map[user_obj.id]
            present_list.append(
                AdminPresentItem(
                    employee_id=user_obj.employee_id,
                    name=user_obj.name,
                    role=user_obj.role,
                    checked_in_at=att.checked_in_at.isoformat() if att.checked_in_at else "",
                    risk_score=att.risk_score
                )
            )
        else:
            absent_list.append(
                AdminAbsentItem(
                    employee_id=user_obj.employee_id,
                    name=user_obj.name,
                    role=user_obj.role
                )
            )

    return AdminAttendanceResponse(
        present=present_list,
        absent=absent_list
    )

@router.get("/attempts", response_model=List[AdminAttemptItem])
def get_verification_attempts(
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    attempts = (
        db.query(VerificationAttempt, User.name)
        .join(User, VerificationAttempt.user_id == User.id)
        .order_by(VerificationAttempt.created_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    for att, name in attempts:
        items.append(
            AdminAttemptItem(
                created_at=att.created_at.isoformat() if att.created_at else "",
                name=name,
                result=att.result,
                failure_code=att.failure_code,
                face_score=att.face_score,
                distance_m=att.distance_m,
                device_id=att.device_id
            )
        )
    return items

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    today = date.today()
    total_staff = db.query(User).filter(User.role != "admin", User.status == "active").count()
    present_today = db.query(Attendance).filter(Attendance.day == today).count()
    absent_today = max(0, total_staff - present_today)

    # Rejections today & reason breakdown
    today_start = datetime.combine(today, datetime.min.time())
    attempts_today = db.query(VerificationAttempt).filter(VerificationAttempt.created_at >= today_start).all()

    rejections_today = 0
    reasons: Dict[str, int] = defaultdict(int)
    hourly: Dict[str, int] = {f"{h:02d}:00": 0 for h in range(8, 20)}

    for att in attempts_today:
        if att.result == "REJECT":
            rejections_today += 1
            if att.failure_code:
                reasons[att.failure_code] += 1
        elif att.result == "ACCEPT":
            hour_str = f"{att.created_at.hour:02d}:00"
            if hour_str in hourly:
                hourly[hour_str] += 1

    return AdminStatsResponse(
        total_staff=total_staff,
        present_today=present_today,
        absent_today=absent_today,
        rejections_today=rejections_today,
        reasons=dict(reasons),
        hourly=hourly
    )

@router.get("/campus", response_model=CampusResponse)
def get_campus(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    campus = db.query(Campus).first()
    if not campus:
        raise HTTPException(status_code=404, detail="Campus configuration not found")
    return CampusResponse(
        name=campus.name,
        latitude=campus.latitude,
        longitude=campus.longitude,
        radius_m=campus.radius_m,
        timezone=campus.timezone
    )

@router.put("/campus")
def update_campus(
    req: CampusUpdateRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    campus = db.query(Campus).first()
    if not campus:
        campus = Campus(
            name=req.name or "Main Campus",
            latitude=req.latitude or 28.5450,
            longitude=req.longitude or 77.1926,
            radius_m=req.radius_m or 300,
            timezone="Asia/Kolkata"
        )
        db.add(campus)
    else:
        if req.name is not None:
            campus.name = req.name
        if req.latitude is not None:
            campus.latitude = req.latitude
        if req.longitude is not None:
            campus.longitude = req.longitude
        if req.radius_m is not None:
            campus.radius_m = req.radius_m

    db.commit()
    db.refresh(campus)

    return {
        "status": "updated",
        "campus": {
            "name": campus.name,
            "latitude": campus.latitude,
            "longitude": campus.longitude,
            "radius_m": campus.radius_m,
            "timezone": campus.timezone
        }
    }

@router.get("/audit/verify-integrity")
def verify_audit_integrity(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Cryptographic verification of the entire attendance event hash chain.
    Ensures no past attendance record was modified, injected, backdated, or deleted.
    """
    records = db.query(Attendance).order_by(Attendance.checked_in_at.asc()).all()
    
    if not records:
        return {
            "chain_valid": True,
            "total_records": 0,
            "message": "No attendance records recorded yet. Genesis state verified.",
            "tampered_records": []
        }

    expected_prev_hash = GENESIS_HASH
    tampered = []
    
    for idx, rec in enumerate(records):
        # 1. Verify previous hash pointer
        if rec.prev_hash != expected_prev_hash:
            tampered.append({
                "record_id": rec.id,
                "user_id": rec.user_id,
                "reason": "BROKEN_CHAIN_LINK",
                "expected_prev_hash": expected_prev_hash,
                "actual_prev_hash": rec.prev_hash
            })
        
        # 2. Recompute expected event hash
        day_str = rec.day.isoformat() if rec.day else ""
        checked_in_str = rec.checked_in_at.isoformat() if rec.checked_in_at else ""
        computed_hash = compute_attendance_event_hash(
            prev_hash=rec.prev_hash or expected_prev_hash,
            attendance_id=rec.id,
            user_id=rec.user_id,
            campus_id=rec.campus_id,
            day_str=day_str,
            checked_in_at_str=checked_in_str,
            risk_score=rec.risk_score,
            device_id=rec.device_id
        )
        
        if rec.event_hash != computed_hash:
            tampered.append({
                "record_id": rec.id,
                "user_id": rec.user_id,
                "reason": "PAYLOAD_TAMPERED",
                "expected_hash": computed_hash,
                "stored_hash": rec.event_hash
            })
            
        expected_prev_hash = rec.event_hash or computed_hash

    return {
        "chain_valid": len(tampered) == 0,
        "total_records": len(records),
        "genesis_hash": GENESIS_HASH,
        "latest_hash": expected_prev_hash,
        "tampered_records": tampered,
        "verified_at": datetime.utcnow().isoformat()
    }

# ==========================================
# Phase 8: Multi-Dimensional Reports Engine
# ==========================================

@router.get("/reports/spatial-filters")
def get_spatial_filters(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Returns available departments, roles, floors, and rooms for dynamic dashboard dropdowns."""
    depts = [r[0] for r in db.query(User.department).distinct().all() if r[0]]
    roles = ["student", "faculty", "staff", "guard", "worker", "visitor"]
    floors = [{"id": f.id, "name": f.name, "floor_number": f.floor_number} for f in db.query(Floor).all()]
    rooms = [{"id": r.id, "name": r.name, "room_number": r.room_number, "floor_id": r.floor_id} for r in db.query(Room).all()]

    return {
        "departments": sorted(list(set(depts + ["CSE", "ECE", "ME", "CIVIL", "ADMIN", "SECURITY"]))),
        "roles": roles,
        "floors": floors,
        "rooms": rooms
    }

@router.get("/reports/attendance")
def get_attendance_report(
    department: Optional[str] = Query(None),
    floor_id: Optional[str] = Query(None),
    room_id: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    status: Optional[str] = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(200, ge=1, le=1000),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    d_from = date.fromisoformat(date_from) if date_from else None
    d_to = date.fromisoformat(date_to) if date_to else None

    items = query_attendance_report(
        db=db,
        department=department,
        floor_id=floor_id,
        room_id=room_id,
        role=role,
        date_from=d_from,
        date_to=d_to,
        status_filter=status,
        limit=limit
    )

    if format == "csv":
        csv_data = attendance_report_to_csv(items)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=attendance_report.csv"}
        )

    return items

@router.get("/reports/gate-access")
def get_gate_report(
    department: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    gate_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(200, ge=1, le=1000),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    d_from = date.fromisoformat(date_from) if date_from else None
    d_to = date.fromisoformat(date_to) if date_to else None

    items = query_gate_report(
        db=db,
        department=department,
        role=role,
        direction=direction,
        event_type=event_type,
        gate_id=gate_id,
        date_from=d_from,
        date_to=d_to,
        limit=limit
    )

    if format == "csv":
        csv_data = gate_report_to_csv(items)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=gate_access_report.csv"}
        )

    return items

@router.get("/reports/staff-duty")
def get_staff_duty_report(
    department: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    shift_status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(200, ge=1, le=1000),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    d_from = date.fromisoformat(date_from) if date_from else None
    d_to = date.fromisoformat(date_to) if date_to else None

    items = query_staff_duty_report(
        db=db,
        department=department,
        role=role,
        shift_status=shift_status,
        date_from=d_from,
        date_to=d_to,
        limit=limit
    )

    if format == "csv":
        csv_data = staff_duty_report_to_csv(items)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=staff_duty_report.csv"}
        )

    return items

@router.get("/reports/verification-attempts")
def get_verification_report(
    department: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    failure_code: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(200, ge=1, le=1000),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    d_from = date.fromisoformat(date_from) if date_from else None
    d_to = date.fromisoformat(date_to) if date_to else None

    items = query_verification_report(
        db=db,
        department=department,
        role=role,
        result=result,
        failure_code=failure_code,
        date_from=d_from,
        date_to=d_to,
        limit=limit
    )

    if format == "csv":
        csv_data = verification_report_to_csv(items)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=verification_attempts_report.csv"}
        )

    return items

# ==========================================
# Phase 8: Consolidated Cryptographic Integrity
# ==========================================

@router.get("/audit/consolidated-integrity", response_model=ConsolidatedIntegrityResponse)
def get_consolidated_integrity(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Executes real-time multi-chain verification across:
    1. Attendance ledger
    2. Gate entry/exit ledger
    3. Room presence ledger
    4. Merkle Root blockchain commitments
    Persists immutable audit log record.
    """
    audit_log = perform_consolidated_audit(db=db, user_id=admin.id)
    return ConsolidatedIntegrityResponse(
        audit_id=audit_log.id,
        attendance_chain_valid=audit_log.attendance_chain_valid,
        gate_chain_valid=audit_log.gate_chain_valid,
        presence_chain_valid=audit_log.presence_chain_valid,
        overall_tamper_free=audit_log.overall_tamper_free,
        total_records_audited=audit_log.total_records_audited,
        attendance_count=audit_log.attendance_count,
        gate_count=audit_log.gate_count,
        presence_count=audit_log.presence_count,
        tampered_records=audit_log.tampered_records or [],
        details=audit_log.details or {},
        verified_at=audit_log.created_at.isoformat()
    )

@router.get("/audit/history", response_model=List[AuditLogSummaryItem])
def get_audit_history(
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Retrieves chronological audit verification execution history."""
    logs = db.query(AuditVerificationLog).order_by(AuditVerificationLog.created_at.desc()).limit(limit).all()
    items = []
    for log in logs:
        tampered_count = len(log.tampered_records) if log.tampered_records else 0
        items.append(
            AuditLogSummaryItem(
                id=log.id,
                verification_type=log.verification_type,
                overall_tamper_free=log.overall_tamper_free,
                total_records_audited=log.total_records_audited,
                attendance_chain_valid=log.attendance_chain_valid,
                gate_chain_valid=log.gate_chain_valid,
                presence_chain_valid=log.presence_chain_valid,
                tampered_count=tampered_count,
                created_at=log.created_at.isoformat()
            )
        )
    return items

# ==========================================
# Phase 8: Merkle Root & Blockchain Anchoring
# ==========================================

@router.post("/audit/merkle-anchor", response_model=MerkleCommitmentResponse)
def create_merkle_anchor(
    payload: MerkleAnchorRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Computes a cryptographic Merkle root of all daily event hashes (Attendance + Gate + Presence),
    simulates blockchain notarization on specified network, and anchors the commitment.
    """
    target_day = date.fromisoformat(payload.day) if payload.day else date.today()
    network = payload.network or "ETHEREUM_SEPOLIA_ANCHOR"

    commitment = anchor_daily_events_to_merkle(
        db=db,
        target_day=target_day,
        user_id=admin.id,
        network=network
    )

    return MerkleCommitmentResponse(
        id=commitment.id,
        day=commitment.day.isoformat(),
        merkle_root=commitment.merkle_root,
        anchor_network=commitment.anchor_network,
        transaction_hash=commitment.transaction_hash,
        block_number=commitment.block_number,
        event_count=commitment.event_count,
        tree_depth=commitment.tree_depth,
        status=commitment.status,
        created_at=commitment.created_at.isoformat()
    )

@router.get("/audit/merkle-anchors", response_model=List[MerkleCommitmentResponse])
def get_merkle_anchors(
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Lists recent Merkle commitments anchored to blockchain."""
    commitments = db.query(MerkleCommitment).order_by(MerkleCommitment.created_at.desc()).limit(limit).all()
    return [
        MerkleCommitmentResponse(
            id=c.id,
            day=c.day.isoformat(),
            merkle_root=c.merkle_root,
            anchor_network=c.anchor_network,
            transaction_hash=c.transaction_hash,
            block_number=c.block_number,
            event_count=c.event_count,
            tree_depth=c.tree_depth,
            status=c.status,
            created_at=c.created_at.isoformat()
        )
        for c in commitments
    ]

@router.post("/audit/merkle-proof", response_model=MerkleProofResponse)
def generate_merkle_inclusion_proof(
    payload: MerkleProofRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Generates a Merkle inclusion proof for a given leaf/event hash within an anchored block.
    """
    leaf = payload.leaf_hash.strip().lower()

    # If commitment_id specified, look up in that specific commitment; else search all commitments
    if payload.commitment_id:
        commitment = db.query(MerkleCommitment).filter(MerkleCommitment.id == payload.commitment_id).first()
        if not commitment:
            raise HTTPException(status_code=404, detail="Merkle commitment not found")
        commitments = [commitment]
    else:
        commitments = db.query(MerkleCommitment).order_by(MerkleCommitment.created_at.desc()).limit(30).all()

    for c in commitments:
        leaves = c.leaf_hashes or []
        if leaf in leaves:
            _, tree_levels, _ = build_merkle_tree(leaves)
            proof_data = generate_merkle_proof(leaf, tree_levels)
            return MerkleProofResponse(
                found=True,
                leaf_hash=leaf,
                merkle_root=c.merkle_root,
                commitment_id=c.id,
                anchor_network=c.anchor_network,
                transaction_hash=c.transaction_hash,
                block_number=c.block_number,
                proof=proof_data.get("proof", [])
            )

    return MerkleProofResponse(
        found=False,
        leaf_hash=leaf,
        merkle_root="",
        proof=[]
    )

@router.post("/audit/verify-merkle-proof", response_model=MerkleVerifyResponse)
def verify_merkle_inclusion_proof(
    payload: MerkleVerifyRequest,
    admin: User = Depends(get_current_admin)
):
    """
    Cryptographically verifies an inclusion proof by hashing the leaf up through sibling nodes
    and asserting equivalence to the anchored Merkle root.
    """
    is_valid = verify_merkle_proof(
        leaf_hash=payload.leaf_hash,
        proof=payload.proof,
        expected_root=payload.merkle_root
    )

    return MerkleVerifyResponse(
        verified=is_valid,
        leaf_hash=payload.leaf_hash,
        merkle_root=payload.merkle_root,
        proof_steps=len(payload.proof),
        message="Merkle inclusion proof verified: Leaf exists cryptographically in anchored root."
        if is_valid
        else "Merkle inclusion verification failed: Calculated root does not match anchored commitment."
    )

