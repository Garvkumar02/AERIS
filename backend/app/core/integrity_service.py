from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ..models import Attendance, GateEvent, RoomPresence, MerkleCommitment, AuditVerificationLog
from ..core.security import (
    GENESIS_HASH,
    compute_attendance_event_hash,
    compute_gate_event_hash,
    compute_room_presence_hash
)
from ..core.merkle_service import build_merkle_tree

def verify_attendance_chain(db: Session) -> Dict[str, Any]:
    records = db.query(Attendance).order_by(Attendance.checked_in_at.asc()).all()
    if not records:
        return {"valid": True, "count": 0, "tampered": [], "message": "Genesis state verified"}

    expected_prev = GENESIS_HASH
    tampered = []

    for rec in records:
        if rec.prev_hash != expected_prev:
            tampered.append({
                "record_id": rec.id,
                "ledger": "ATTENDANCE",
                "reason": "BROKEN_CHAIN_LINK",
                "expected_prev": expected_prev,
                "actual_prev": rec.prev_hash
            })

        day_str = rec.day.isoformat() if rec.day else ""
        checked_in_str = rec.checked_in_at.isoformat() if rec.checked_in_at else ""
        computed = compute_attendance_event_hash(
            prev_hash=rec.prev_hash or expected_prev,
            attendance_id=rec.id,
            user_id=rec.user_id,
            campus_id=rec.campus_id,
            day_str=day_str,
            checked_in_at_str=checked_in_str,
            risk_score=rec.risk_score,
            device_id=rec.device_id
        )

        if rec.event_hash != computed:
            tampered.append({
                "record_id": rec.id,
                "ledger": "ATTENDANCE",
                "reason": "PAYLOAD_TAMPERED",
                "expected_hash": computed,
                "stored_hash": rec.event_hash
            })

        expected_prev = rec.event_hash or computed

    return {
        "valid": len(tampered) == 0,
        "count": len(records),
        "latest_hash": expected_prev,
        "tampered": tampered
    }

def verify_gate_chain(db: Session) -> Dict[str, Any]:
    all_records = db.query(GateEvent).all()
    if not all_records:
        return {"valid": True, "count": 0, "tampered": [], "message": "Genesis state verified"}

    # Reconstruct true chain sequence following prev_hash pointers from GENESIS_HASH
    by_prev = {r.prev_hash: r for r in all_records if r.prev_hash}
    ordered = []
    curr = GENESIS_HASH
    seen_ids = set()
    while curr in by_prev and by_prev[curr].id not in seen_ids:
        r = by_prev[curr]
        ordered.append(r)
        seen_ids.add(r.id)
        curr = r.event_hash

    # Append any remaining detached or orphaned records to detect tamper
    for r in sorted(all_records, key=lambda x: (x.timestamp or datetime.min, x.id)):
        if r.id not in seen_ids:
            ordered.append(r)

    records = ordered
    expected_prev = GENESIS_HASH
    tampered = []

    for rec in records:
        if rec.prev_hash != expected_prev:
            tampered.append({
                "record_id": rec.id,
                "ledger": "GATE_ACCESS",
                "reason": "BROKEN_CHAIN_LINK",
                "expected_prev": expected_prev,
                "actual_prev": rec.prev_hash
            })

        time_str = rec.timestamp.isoformat() if rec.timestamp else ""
        computed = compute_gate_event_hash(
            prev_hash=rec.prev_hash or expected_prev,
            event_id=rec.id,
            user_id=rec.user_id,
            gate_id=rec.gate_id,
            direction=rec.direction,
            event_type=rec.event_type,
            device_id=rec.device_id,
            timestamp_str=time_str,
            synced_offline=rec.synced_offline
        )

        if rec.event_hash != computed:
            tampered.append({
                "record_id": rec.id,
                "ledger": "GATE_ACCESS",
                "reason": "PAYLOAD_TAMPERED",
                "expected_hash": computed,
                "stored_hash": rec.event_hash
            })

        expected_prev = rec.event_hash or computed

    return {
        "valid": len(tampered) == 0,
        "count": len(records),
        "latest_hash": expected_prev,
        "tampered": tampered
    }

def verify_presence_chain(db: Session) -> Dict[str, Any]:
    records = db.query(RoomPresence).order_by(RoomPresence.check_in_at.asc()).all()
    if not records:
        return {"valid": True, "count": 0, "tampered": [], "message": "Genesis state verified"}

    expected_prev = GENESIS_HASH
    tampered = []

    for rec in records:
        if rec.prev_hash != expected_prev:
            tampered.append({
                "record_id": rec.id,
                "ledger": "ROOM_PRESENCE",
                "reason": "BROKEN_CHAIN_LINK",
                "expected_prev": expected_prev,
                "actual_prev": rec.prev_hash
            })

        time_str = rec.check_in_at.isoformat() if rec.check_in_at else ""
        computed = compute_room_presence_hash(
            prev_hash=rec.prev_hash or expected_prev,
            presence_id=rec.id,
            user_id=rec.user_id,
            room_id=rec.room_id,
            verification_method=rec.verification_method,
            check_in_at_str=time_str
        )

        if rec.presence_hash != computed:
            tampered.append({
                "record_id": rec.id,
                "ledger": "ROOM_PRESENCE",
                "reason": "PAYLOAD_TAMPERED",
                "expected_hash": computed,
                "stored_hash": rec.presence_hash
            })

        expected_prev = rec.presence_hash or computed

    return {
        "valid": len(tampered) == 0,
        "count": len(records),
        "latest_hash": expected_prev,
        "tampered": tampered
    }

def verify_merkle_commitments(db: Session) -> Dict[str, Any]:
    commitments = db.query(MerkleCommitment).order_by(MerkleCommitment.created_at.desc()).all()
    tampered = []

    for c in commitments:
        leaves = c.leaf_hashes or []
        recomputed_root, _, _ = build_merkle_tree(leaves)
        if recomputed_root != c.merkle_root:
            tampered.append({
                "commitment_id": c.id,
                "day": c.day.isoformat(),
                "network": c.anchor_network,
                "expected_root": recomputed_root,
                "stored_root": c.merkle_root,
                "reason": "MERKLE_ROOT_MISMATCH"
            })

    return {
        "valid": len(tampered) == 0,
        "count": len(commitments),
        "tampered": tampered
    }

def perform_consolidated_audit(db: Session, user_id: Optional[str] = None) -> AuditVerificationLog:
    """
    Executes a comprehensive, cross-ledger integrity audit across Attendance, Gate Access,
    Room Presence, and Merkle Blockchain Commitments. Logs the result into audit_verification_logs.
    """
    att_res = verify_attendance_chain(db)
    gate_res = verify_gate_chain(db)
    presence_res = verify_presence_chain(db)
    merkle_res = verify_merkle_commitments(db)

    all_tampered = (
        att_res.get("tampered", []) +
        gate_res.get("tampered", []) +
        presence_res.get("tampered", []) +
        merkle_res.get("tampered", [])
    )

    overall_tamper_free = len(all_tampered) == 0
    total_records = att_res["count"] + gate_res["count"] + presence_res["count"]

    audit_log = AuditVerificationLog(
        verified_by_user_id=user_id,
        verification_type="CONSOLIDATED_FULL_AUDIT",
        attendance_chain_valid=att_res["valid"],
        gate_chain_valid=gate_res["valid"],
        presence_chain_valid=presence_res["valid"],
        overall_tamper_free=overall_tamper_free,
        total_records_audited=total_records,
        attendance_count=att_res["count"],
        gate_count=gate_res["count"],
        presence_count=presence_res["count"],
        tampered_records=all_tampered,
        details={
            "merkle_commitments_audited": merkle_res["count"],
            "merkle_commitments_valid": merkle_res["valid"],
            "latest_attendance_hash": att_res.get("latest_hash"),
            "latest_gate_hash": gate_res.get("latest_hash"),
            "latest_presence_hash": presence_res.get("latest_hash"),
            "verified_at": datetime.utcnow().isoformat()
        },
        created_at=datetime.utcnow()
    )

    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log
