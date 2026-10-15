import os
import uuid
import hashlib
import base64
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from jose import JWTError, jwt
import bcrypt
from cryptography.fernet import Fernet, MultiFernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..models import User

# ==========================================
# 1. Password Hashing (bcrypt, rounds=12)
# ==========================================

BCRYPT_ROUNDS = 12

def hash_password(password: str) -> str:
    """Hashes a password with bcrypt using 12 salt rounds. Enforces 72-byte max limit."""
    pwd_bytes = password.encode('utf-8')
    if len(pwd_bytes) > 72:
        raise ValueError("Password must not exceed 72 bytes")
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification of password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

# ==========================================
# 2. JWT Tokens (with JTI, ISS, AUD, EXP)
# ==========================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generates a cryptographically signed JWT with expiration, issuer, audience, and unique token ID."""
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + (expires_delta if expires_delta else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    
    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid.uuid4())
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates JWT claims including expiration, issuer, and audience."""
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE
    )

# ==========================================
# 3. Biometric Encryption (MultiFernet with Key Rotation)
# ==========================================

def _get_fernet() -> MultiFernet:
    """Instantiates a MultiFernet instance supporting primary key encryption and zero-downtime key rotation."""
    keys = settings.get_all_fernet_keys()
    fernet_instances = [Fernet(k) for k in keys]
    return MultiFernet(fernet_instances)

def encrypt_embedding(embedding: np.ndarray) -> bytes:
    """Serializes a 512-d float32 numpy vector and encrypts it with the primary Fernet key."""
    f = _get_fernet()
    raw_bytes = embedding.astype(np.float32).tobytes()
    return f.encrypt(raw_bytes)

def decrypt_embedding(encrypted_data: bytes) -> np.ndarray:
    """Decrypts Fernet ciphertext using MultiFernet (supports current or any valid previous fallback key)."""
    f = _get_fernet()
    raw_bytes = f.decrypt(encrypted_data)
    return np.frombuffer(raw_bytes, dtype=np.float32)

def rotate_encrypted_embedding(encrypted_data: bytes) -> bytes:
    """Re-encrypts ciphertext to use the latest primary Fernet key without changing plain payload."""
    f = _get_fernet()
    return f.rotate(encrypted_data)

# ==========================================
# 4. Cryptographic Hash Chaining (Audit Integrity)
# ==========================================

GENESIS_HASH = "0" * 64

def compute_attendance_event_hash(
    prev_hash: str,
    attendance_id: str,
    user_id: str,
    campus_id: Optional[str],
    day_str: str,
    checked_in_at_str: str,
    risk_score: Optional[int],
    device_id: Optional[str]
) -> str:
    """
    Computes a deterministic SHA-256 hash chaining this attendance event to the previous record.
    Any tampering with timestamp, user, location, or past event breaks the entire hash chain.
    """
    canonical_payload = (
        f"{prev_hash}|"
        f"{attendance_id}|"
        f"{user_id}|"
        f"{campus_id or ''}|"
        f"{day_str}|"
        f"{checked_in_at_str}|"
        f"{risk_score if risk_score is not None else ''}|"
        f"{device_id or ''}"
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

def compute_audit_log_hash(
    prev_hash: str,
    log_id: int,
    actor_id: Optional[str],
    action: str,
    entity: Optional[str],
    entity_id: Optional[str],
    created_at_str: str
) -> str:
    """Computes a tamper-proof SHA-256 hash for an administrative audit log entry."""
    canonical_payload = (
        f"{prev_hash}|"
        f"{log_id}|"
        f"{actor_id or ''}|"
        f"{action}|"
        f"{entity or ''}|"
        f"{entity_id or ''}|"
        f"{created_at_str}"
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

def compute_gate_event_hash(
    prev_hash: str,
    event_id: str,
    user_id: str,
    gate_id: str,
    direction: str,
    event_type: str,
    device_id: str,
    timestamp_str: str,
    synced_offline: bool
) -> str:
    """Computes a tamper-proof SHA-256 hash chaining this gate access event."""
    canonical_payload = (
        f"{prev_hash}|"
        f"{event_id}|"
        f"{user_id}|"
        f"{gate_id}|"
        f"{direction}|"
        f"{event_type}|"
        f"{device_id}|"
        f"{timestamp_str}|"
        f"{'1' if synced_offline else '0'}"
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

def compute_room_presence_hash(
    prev_hash: str,
    presence_id: str,
    user_id: str,
    room_id: str,
    verification_method: str,
    check_in_at_str: str
) -> str:
    """Computes a tamper-proof SHA-256 hash chaining this indoor room presence event."""
    canonical_payload = (
        f"{prev_hash}|"
        f"{presence_id}|"
        f"{user_id}|"
        f"{room_id}|"
        f"{verification_method}|"
        f"{check_in_at_str}"
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

# ==========================================
# 5. FastAPI Authentication Dependencies
# ==========================================

security_bearer = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.status == "active").first()
    if user is None:
        raise credentials_exception
    return user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

def get_current_guard_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "guard"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guard or Admin privileges required for gate operation"
        )
    return current_user

