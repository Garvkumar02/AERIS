import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from ..models import (
    User,
    VerificationAttempt,
    Notification,
    BiometricAccessLog,
    RetentionRunLog
)

DEFAULT_RETENTION_DAYS = 90

def get_retention_overview(db: Session, retention_days: int = DEFAULT_RETENTION_DAYS) -> Dict[str, Any]:
    """
    Scans the database and returns counts of operational records eligible for 90-day cleanup.
    """
    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    attempts_count = db.query(VerificationAttempt).filter(VerificationAttempt.created_at < cutoff).count()
    notifs_count = db.query(Notification).filter(
        Notification.created_at < cutoff,
        Notification.delivery_status.in_(["DELIVERED", "SUPPRESSED_DUPLICATE"])
    ).count()
    access_logs_count = db.query(BiometricAccessLog).filter(BiometricAccessLog.accessed_at < cutoff).count()

    last_run = db.query(RetentionRunLog).order_by(RetentionRunLog.executed_at.desc()).first()

    return {
        "retention_policy_days": retention_days,
        "cutoff_date": cutoff.isoformat(),
        "eligible_records": {
            "verification_attempts": attempts_count,
            "operational_notifications": notifs_count,
            "biometric_access_logs": access_logs_count,
            "total_eligible": attempts_count + notifs_count + access_logs_count
        },
        "last_retention_run": {
            "id": last_run.id if last_run else None,
            "executed_at": last_run.executed_at.isoformat() if last_run else None,
            "total_purged": last_run.total_records_purged if last_run else 0,
            "compliance_cert_hash": last_run.compliance_cert_hash if last_run else None,
            "status": last_run.status if last_run else "IDLE"
        } if last_run else None,
        "policy_description": "Operational logs exceeding 90 days are purged according to data minimization principles (DPDP & GDPR Article 5(1)(e))."
    }

def execute_retention_cleanup(
    db: Session,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    run_by_user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the 90-day operational retention purge.
    Removes ephemeral verification attempts, delivered notification logs, and stale access records.
    Generates a cryptographically verifiable Retention Compliance Certificate.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=retention_days)

    # 1. Purge ephemeral verification attempts
    attempts_deleted = db.query(VerificationAttempt).filter(
        VerificationAttempt.created_at < cutoff
    ).delete(synchronize_session=False)

    # 2. Purge delivered notifications & duplicate suppression markers past 90 days
    notifs_deleted = db.query(Notification).filter(
        Notification.created_at < cutoff,
        Notification.delivery_status.in_(["DELIVERED", "SUPPRESSED_DUPLICATE"])
    ).delete(synchronize_session=False)

    # 3. Purge biometric access logs past 90 days
    access_logs_deleted = db.query(BiometricAccessLog).filter(
        BiometricAccessLog.accessed_at < cutoff
    ).delete(synchronize_session=False)

    total_purged = attempts_deleted + notifs_deleted + access_logs_deleted

    # 4. Generate SHA-256 Retention Compliance Certificate Hash
    cert_raw = f"{cutoff.isoformat()}:{total_purged}:{now.isoformat()}:AERIS_RETENTION_90D_COMPLIANCE"
    cert_hash = hashlib.sha256(cert_raw.encode("utf-8")).hexdigest()

    # 5. Record retention run in database audit table
    run_log = RetentionRunLog(
        run_by_user_id=run_by_user_id,
        retention_threshold_days=retention_days,
        cutoff_date=cutoff,
        verification_attempts_purged=attempts_deleted,
        notifications_purged=notifs_deleted,
        access_logs_purged=access_logs_deleted,
        total_records_purged=total_purged,
        compliance_cert_hash=cert_hash,
        status="COMPLETED",
        executed_at=now
    )
    db.add(run_log)
    db.commit()
    db.refresh(run_log)

    return {
        "status": "success",
        "retention_run_id": run_log.id,
        "retention_threshold_days": retention_days,
        "cutoff_date": cutoff.isoformat(),
        "executed_at": now.isoformat(),
        "records_purged": {
            "verification_attempts": attempts_deleted,
            "notifications": notifs_deleted,
            "biometric_access_logs": access_logs_deleted,
            "total_purged": total_purged
        },
        "compliance_certificate": {
            "hash": cert_hash,
            "standard": "DPDP / GDPR Article 5(1)(e) Storage Limitation",
            "certified_by": "AERIS Retention Automation Engine"
        }
    }
