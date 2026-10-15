import numpy as np
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, BiometricProfile
from ..schemas import BiometricEnrollResponse, BiometricRevokeResponse, WebcamEnrollResponse
from ..core.security import get_current_user, encrypt_embedding
from ..core.vision import vision_engine

router = APIRouter(prefix="/biometric", tags=["biometric"])

@router.post("/enroll", response_model=BiometricEnrollResponse)
async def enroll_biometrics(
    consent: bool = Form(...),
    front: UploadFile = File(...),
    left: UploadFile = File(...),
    right: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Biometric consent is mandatory for enrollment"
        )

    embeddings = []
    frames = [("front", front), ("left", left), ("right", right)]

    for name, file in frames:
        content = await file.read()
        img = vision_engine.decode_image(content)
        if img is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"BAD_IMAGE in {name} frame"
            )

        err, emb, yaw, score = vision_engine.detect_face_and_pose(img)
        if err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{err} in {name} frame"
            )

        embeddings.append(emb)

    # Average and L2-normalize embeddings for a robust template
    avg_emb = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(avg_emb)
    if norm > 0:
        avg_emb = avg_emb / norm

    # Encrypt embedding with Fernet
    encrypted = encrypt_embedding(avg_emb)

    # Privacy: Scrub in-memory raw frame and embedding allocations immediately
    from ..core.privacy_service import scrub_image_memory, log_biometric_access, PURPOSE_CAMPUS_ATTENDANCE, PURPOSE_ENROLLMENT, PURPOSE_CONSENT_REVOCATION
    for _, file_obj in frames:
        scrub_image_memory(getattr(file_obj, "_content", None))
    del embeddings

    now = datetime.utcnow()
    profile = db.query(BiometricProfile).filter(BiometricProfile.user_id == current_user.id).first()
    if not profile:
        profile = BiometricProfile(
            user_id=current_user.id,
            encrypted_embedding=encrypted,
            model_version="buffalo_l",
            consent_version="1.0",
            purpose_limitation=PURPOSE_CAMPUS_ATTENDANCE,
            storage_classification="RESTRICTED_SPECIAL_CATEGORY_PVI",
            encryption_algorithm="AES-256-GCM/FERNET",
            consent_status="CONSENT_GRANTED",
            consent_timestamp=now,
            raw_image_persisted=False,
            enrolled_at=now
        )
        db.add(profile)
    else:
        profile.encrypted_embedding = encrypted
        profile.model_version = "buffalo_l"
        profile.consent_version = "1.0"
        profile.purpose_limitation = PURPOSE_CAMPUS_ATTENDANCE
        profile.storage_classification = "RESTRICTED_SPECIAL_CATEGORY_PVI"
        profile.encryption_algorithm = "AES-256-GCM/FERNET"
        profile.consent_status = "CONSENT_GRANTED"
        profile.consent_timestamp = now
        profile.raw_image_persisted = False
        profile.enrolled_at = now
        profile.revoked_at = None
        profile.revoked_timestamp = None

    db.commit()

    log_biometric_access(
        db=db,
        accessor_id=current_user.id,
        target_user_id=current_user.id,
        purpose=PURPOSE_ENROLLMENT,
        action="WRITE_TEMPLATE",
        status_code="AUTHORIZED_SUCCESS"
    )

    return BiometricEnrollResponse(
        enrolled=True,
        model_version="buffalo_l"
    )

@router.post("/revoke", response_model=BiometricRevokeResponse)
def revoke_biometrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GDPR & DPDP compliance: Revokes biometric consent, deletes/zeroes encrypted embedding,
    and records revocation audit entry. Biometric attendance check-ins will immediately be rejected.
    """
    from ..core.privacy_service import revoke_biometric_consent
    res = revoke_biometric_consent(db=db, user=current_user)

    return BiometricRevokeResponse(
        revoked=True,
        user_id=current_user.id,
        revoked_at=res["revoked_at"],
        message=res["message"]
    )

@router.get("/status")
def get_biometric_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(BiometricProfile).filter(
        BiometricProfile.user_id == current_user.id,
        BiometricProfile.revoked_at.is_(None)
    ).first()
    return {
        "enrolled": profile is not None and bool(profile.encrypted_embedding),
        "model_version": profile.model_version if profile else None,
        "enrolled_at": profile.enrolled_at.isoformat() if profile and profile.enrolled_at else None
    }

@router.post("/webcam-enroll", response_model=WebcamEnrollResponse)
async def webcam_enroll_biometrics(
    user_id: str = Form(...),
    frame: UploadFile = File(...),
    consent: bool = Form(True),
    db: Session = Depends(get_db)
):
    """
    Direct webcam facial enrolment:
    1. Decodes single high-resolution frontal frame captured from the webcam.
    2. Detects face and extracts 512-d feature descriptor.
    3. Encrypts template via Fernet (AES-256) and stores with zero raw image persistence.
    """
    from sqlalchemy import or_, func
    from ..core.privacy_service import scrub_image_memory, log_biometric_access, PURPOSE_ENROLLMENT, PURPOSE_CAMPUS_ATTENDANCE

    clean_uid = user_id.strip()
    user = db.query(User).filter(
        or_(
            User.id == clean_uid,
            User.employee_id == clean_uid,
            func.lower(User.name) == clean_uid.lower(),
            func.lower(User.email) == clean_uid.lower()
        )
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found in campus directory"
        )

    content = await frame.read()
    img = vision_engine.decode_image(content)
    if img is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decode webcam frame. Check camera stream."
        )

    err, emb, yaw, score, mesh_info = vision_engine.detect_face_and_mesh(img)
    if err:
        scrub_image_memory(content, img)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Face detection error: {err}. Please ensure face is centered and well-lit."
        )

    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = emb / norm

    encrypted = encrypt_embedding(emb)
    now = datetime.utcnow()

    profile = db.query(BiometricProfile).filter(BiometricProfile.user_id == user.id).first()
    if not profile:
        profile = BiometricProfile(
            user_id=user.id,
            encrypted_embedding=encrypted,
            model_version="buffalo_l",
            consent_version="1.0",
            purpose_limitation=PURPOSE_CAMPUS_ATTENDANCE,
            storage_classification="RESTRICTED_SPECIAL_CATEGORY_PVI",
            encryption_algorithm="AES-256-GCM/FERNET",
            consent_status="CONSENT_GRANTED",
            consent_timestamp=now,
            raw_image_persisted=False,
            enrolled_at=now
        )
        db.add(profile)
    else:
        profile.encrypted_embedding = encrypted
        profile.model_version = "buffalo_l"
        profile.consent_version = "1.0"
        profile.purpose_limitation = PURPOSE_CAMPUS_ATTENDANCE
        profile.storage_classification = "RESTRICTED_SPECIAL_CATEGORY_PVI"
        profile.encryption_algorithm = "AES-256-GCM/FERNET"
        profile.consent_status = "CONSENT_GRANTED"
        profile.consent_timestamp = now
        profile.raw_image_persisted = False
        profile.enrolled_at = now
        profile.revoked_at = None
        profile.revoked_timestamp = None

    db.commit()

    log_biometric_access(
        db=db,
        accessor_id=user.id,
        target_user_id=user.id,
        purpose=PURPOSE_ENROLLMENT,
        action="WEBCAM_ENROLLMENT",
        status_code="AUTHORIZED_SUCCESS"
    )

    scrub_image_memory(content, img)

    return WebcamEnrollResponse(
        status="ENROLLED",
        user_id=user.id,
        name=user.name,
        employee_id=user.employee_id,
        model_version="buffalo_l",
        message=f"Facial biometrics enrolled successfully for {user.name} ({user.employee_id}) via live webcam with 68 mesh vertices.",
        vertices_count=mesh_info.get("vertices_count") if mesh_info else 68,
        yaw_deg=mesh_info.get("yaw_deg") if mesh_info else None,
        bbox=mesh_info.get("bbox") if mesh_info else None,
        landmarks=mesh_info.get("landmarks") if mesh_info else None,
        key_vertices=mesh_info.get("key_vertices") if mesh_info else None
    )




