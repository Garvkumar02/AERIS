import time
import os
import hmac
import hashlib
import base64
import json
from typing import Tuple, Optional, Dict, Any

# 12-second rotating QR token constants
ROTATION_INTERVAL_SECONDS = 12
GRACE_PERIOD_SECONDS = 6  # Allow slight clock skew or transmission latency

# In-memory single-use anti-replay nonce storage
# nonce -> timestamp of consumption
CONSUMED_LECTURE_NONCES: Dict[str, float] = {}

def cleanup_old_nonces():
    """Purge consumed nonces older than 5 minutes to prevent memory leaks."""
    cutoff = time.time() - 300
    expired = [n for n, ts in CONSUMED_LECTURE_NONCES.items() if ts < cutoff]
    for n in expired:
        CONSUMED_LECTURE_NONCES.pop(n, None)

def generate_lecture_qr_token(
    lecture_id: str,
    room_id: str,
    subject_code: str,
    secret_key: str
) -> Dict[str, Any]:
    """
    Generates a cryptographically signed dynamic QR token rotating every 12 seconds.
    Payload: AERIS-LEC:{lecture_id}:{room_id}:{subject_code}:{epoch}:{nonce}
    HMAC-SHA256 signature guarantees token authenticity.
    """
    now = time.time()
    current_epoch = int(now // ROTATION_INTERVAL_SECONDS)
    seconds_remaining = ROTATION_INTERVAL_SECONDS - int(now % ROTATION_INTERVAL_SECONDS)
    if seconds_remaining == 0:
        seconds_remaining = ROTATION_INTERVAL_SECONDS

    # 16-byte cryptographically secure random single-use nonce
    nonce = os.urandom(16).hex()

    payload_data = {
        "ver": "AERIS-LEC-v1",
        "lecture_id": lecture_id,
        "room_id": room_id,
        "subject_code": subject_code,
        "epoch": current_epoch,
        "nonce": nonce,
        "iat": int(now)
    }

    payload_json = json.dumps(payload_data, separators=(',', ':'), sort_keys=True)
    b64_payload = base64.urlsafe_b64encode(payload_json.encode('utf-8')).decode('utf-8').rstrip('=')

    # HMAC-SHA256 signature
    signature = hmac.new(
        secret_key.encode('utf-8'),
        b64_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    token = f"{b64_payload}.{signature}"
    expires_at = (current_epoch + 1) * ROTATION_INTERVAL_SECONDS

    return {
        "token": token,
        "seconds_remaining": seconds_remaining,
        "rotation_interval": ROTATION_INTERVAL_SECONDS,
        "expires_at": expires_at,
        "nonce": nonce,
        "lecture_id": lecture_id,
        "room_id": room_id,
        "subject_code": subject_code
    }

def verify_lecture_qr_token(
    token_str: str,
    expected_lecture_id: str,
    expected_room_id: Optional[str],
    secret_key: str
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Verifies a dynamic 12-second lecture QR token:
    1. Cryptographic HMAC-SHA256 signature validation
    2. Lecture ID & Room ID matching
    3. Rotation epoch freshness (12s window with 6s grace) -> "QR_EXPIRED"
    4. Single-use nonce consumption -> "QR_REPLAYED"
    """
    cleanup_old_nonces()

    if not token_str or "." not in token_str:
        return False, "QR_MALFORMED", None

    parts = token_str.strip().split(".")
    if len(parts) != 2:
        return False, "QR_MALFORMED", None

    b64_payload, signature = parts

    # 1. Cryptographic signature verification
    expected_sig = hmac.new(
        secret_key.encode('utf-8'),
        b64_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        return False, "QR_INVALID_SIGNATURE", None

    # Decode JSON payload
    try:
        padding = '=' * (-len(b64_payload) % 4)
        raw_json = base64.urlsafe_b64decode((b64_payload + padding).encode('utf-8')).decode('utf-8')
        payload = json.loads(raw_json)
    except Exception:
        return False, "QR_DECODE_ERROR", None

    # 2. Check Lecture and Room binding
    if payload.get("lecture_id") != expected_lecture_id:
        return False, "QR_LECTURE_MISMATCH", None

    if expected_room_id and payload.get("room_id") != expected_room_id:
        return False, "QR_ROOM_MISMATCH", None

    # 3. Check Expiration & Time Window
    now = time.time()
    current_epoch = int(now // ROTATION_INTERVAL_SECONDS)
    token_epoch = payload.get("epoch", 0)

    # Valid if token is from current epoch or immediately previous epoch within grace window
    time_delta = now - (token_epoch * ROTATION_INTERVAL_SECONDS)
    max_allowed_age = ROTATION_INTERVAL_SECONDS + GRACE_PERIOD_SECONDS

    if time_delta < -GRACE_PERIOD_SECONDS or time_delta > max_allowed_age:
        return False, "QR_EXPIRED", None

    # 4. Anti-Replay Nonce Check
    nonce = payload.get("nonce")
    if not nonce:
        return False, "QR_MISSING_NONCE", None

    if nonce in CONSUMED_LECTURE_NONCES:
        return False, "QR_REPLAYED", None

    # Atomically mark nonce as consumed
    CONSUMED_LECTURE_NONCES[nonce] = now

    return True, None, payload
