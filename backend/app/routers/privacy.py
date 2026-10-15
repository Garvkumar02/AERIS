from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, BiometricProfile, BiometricAccessLog
from ..schemas import (
    PrivacyConsentStatusResponse,
    GrantConsentRequest,
    RevokeConsentRequest,
    ErasureReceiptResponse,
    BiometricAccessLogResponse,
    RetentionStatusResponse,
    RetentionCleanupResponse,
    BackupRecordResponse,
    RecoveryTestReportResponse
)
from ..core.security import get_current_user
from ..core.privacy_service import (
    get_user_consent_status,
    grant_biometric_consent,
    revoke_biometric_consent,
    cryptographic_biometric_erasure,
    PURPOSE_CAMPUS_ATTENDANCE
)
from ..core.retention_service import get_retention_overview, execute_retention_cleanup
from ..core.backup_service import (
    create_encrypted_backup,
    cleanup_expired_backups,
    test_backup_recovery,
    list_all_backups
)

router = APIRouter(prefix="/privacy", tags=["privacy"])

@router.get("/consent", response_model=PrivacyConsentStatusResponse)
def get_my_consent_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns authenticated user's biometric consent status, encryption cipher,
    purpose limitations, and retention policies.
    """
    return get_user_consent_status(db, current_user)

@router.get("/user/{user_id}/consent", response_model=PrivacyConsentStatusResponse)
def get_user_consent_status_by_id(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Admin & Faculty lookup of user consent record.
    """
    if current_user.role not in ["admin", "faculty"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access.")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return get_user_consent_status(db, target)

@router.post("/consent/grant")
def grant_consent(
    payload: GrantConsentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Grants or renews biometric consent.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    return grant_biometric_consent(
        db=db,
        user=current_user,
        consent_version=payload.consent_version or "1.0",
        client_ip=client_ip
    )

@router.post("/consent/revoke")
def revoke_consent(
    payload: RevokeConsentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revokes biometric consent, cryptographic zeroing of face embedding vector,
    and falls back to non-biometric credentials.
    """
    target = current_user
    if payload.target_user_id and payload.target_user_id != current_user.id:
        if current_user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authorization required to revoke other users' consent.")
        target = db.query(User).filter(User.id == payload.target_user_id).first()
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    client_ip = request.client.host if request.client else "127.0.0.1"
    return revoke_biometric_consent(
        db=db,
        user=target,
        reason=payload.reason or "User self-revocation",
        client_ip=client_ip
    )

@router.post("/delete-biometric-data", response_model=ErasureReceiptResponse)
def delete_biometric_data(
    target_user_id: Optional[str] = None,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    'Right to be Forgotten' Permanent Erasure Workflow (GDPR Article 17 / DPDP Section 12).
    Permanently purges the biometric profile from primary storage and issues a verifiable SHA-256 deletion confirmation receipt hash.
    Students can request deletion of their own biometric profile. Admins can execute for any user.
    """
    target = current_user
    if target_user_id and target_user_id != current_user.id:
        if current_user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can delete other users' biometric profiles.")
        target = db.query(User).filter(User.id == target_user_id).first()
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    client_ip = request.client.host if request and request.client else "127.0.0.1"
    return cryptographic_biometric_erasure(
        db=db,
        target_user=target,
        requested_by=current_user,
        client_ip=client_ip
    )

@router.get("/access-logs", response_model=List[BiometricAccessLogResponse])
def get_biometric_access_logs(
    target_user_id: Optional[str] = None,
    purpose: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Audit log of who accessed biometric templates, for what purpose, and confirms zero raw-image persistence.
    Regular users see accesses to their own templates; admins see campus-wide logs.
    """
    query = db.query(BiometricAccessLog)
    if current_user.role != "admin":
        query = query.filter(BiometricAccessLog.target_user_id == current_user.id)
    else:
        if target_user_id:
            query = query.filter(BiometricAccessLog.target_user_id == target_user_id)

    if purpose:
        query = query.filter(BiometricAccessLog.purpose == purpose)

    logs = query.order_by(BiometricAccessLog.accessed_at.desc()).limit(limit).all()

    return [
        BiometricAccessLogResponse(
            id=log.id,
            accessor_id=log.accessor_id,
            target_user_id=log.target_user_id,
            purpose=log.purpose,
            action=log.action,
            status=log.status,
            client_ip=log.client_ip,
            user_agent=log.user_agent,
            raw_image_persisted=log.raw_image_persisted,
            accessed_at=log.accessed_at.isoformat()
        )
        for log in logs
    ]

# ==========================================
# 90-Day Operational Retention Endpoints
# ==========================================

@router.get("/retention/status", response_model=RetentionStatusResponse)
def get_retention_status(
    retention_days: int = Query(90, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns current status of 90-day operational data retention policy and eligible records.
    """
    if current_user.role not in ["admin", "faculty"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authorization required.")
    return get_retention_overview(db, retention_days)

@router.post("/retention/run-cleanup", response_model=RetentionCleanupResponse)
def run_retention_cleanup(
    retention_days: int = Query(90, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers scheduled operational data cleanup: purges verification attempts, delivered notification logs,
    and stale access logs older than retention threshold (default 90 days).
    Generates a cryptographically signed Retention Compliance Certificate.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authorization required.")
    return execute_retention_cleanup(db, retention_days, current_user.id)

# ==========================================
# Backup Expiry & Disaster Recovery Endpoints
# ==========================================

@router.post("/backups/create", response_model=Dict[str, Any])
def create_backup(
    retention_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates an AES-256 encrypted snapshot backup with an expiry lifecycle.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authorization required.")
    return create_encrypted_backup(db, retention_days)

@router.get("/backups", response_model=List[BackupRecordResponse])
def get_backups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists all encrypted backups in catalog with expiration and recovery status.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authorization required.")
    return list_all_backups(db)

@router.post("/backups/cleanup-expired")
def cleanup_backups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Scans and purges backups past their expiry window.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authorization required.")
    return cleanup_expired_backups(db)

@router.post("/backups/test-recovery", response_model=RecoveryTestReportResponse)
def run_recovery_test(
    backup_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes an automated disaster recovery drill: decrypts backup into a sandboxed environment,
    executes SQLite 'PRAGMA integrity_check;', audits row count parity across core tables,
    and certifies recovery readiness.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authorization required.")
    return test_backup_recovery(db, backup_id)
