import time
import hmac
import hashlib
import base64
import uuid
import json
from typing import Tuple, Optional, Dict
from ..config import settings

QR_ROTATION_INTERVAL_SECONDS = 12
DRIFT_TOLERANCE_WINDOWS = 1  # Allows +/- 1 window (12 seconds) for slight clock skew

# In-memory consumed token replay cache: nonce -> consumption_timestamp
CONSUMED_NONCES: Dict[str, float] = {}

def get_current_window(offset: int = 0) -> int:
    return int((time.time() + offset) // QR_ROTATION_INTERVAL_SECONDS)

def get_window_expiry(window: int) -> int:
    """Returns unix epoch seconds when this window expires."""
    return int((window + 1) * QR_ROTATION_INTERVAL_SECONDS)

def generate_dynamic_qr_token(user_id: str, role: str) -> Dict[str, any]:
    """
    Generates a cryptographically signed, 12-second rotating dynamic QR token.
    Contains user identity, current time window, single-use nonce, and HMAC-SHA256 signature.
    """
    current_time = time.time()
    window = int(current_time // QR_ROTATION_INTERVAL_SECONDS)
    seconds_remaining = int(((window + 1) * QR_ROTATION_INTERVAL_SECONDS) - current_time)
    nonce = uuid.uuid4().hex[:12]

    payload = f"{user_id}|{role}|{window}|{nonce}"
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()[:24]

    raw_token = f"{payload}|{sig}"
    encoded_token = base64.urlsafe_b64encode(raw_token.encode("utf-8")).decode("utf-8").rstrip("=")

    return {
        "token": encoded_token,
        "seconds_remaining": max(1, seconds_remaining),
        "rotation_interval": QR_ROTATION_INTERVAL_SECONDS,
        "expires_at": get_window_expiry(window),
        "nonce": nonce
    }

def verify_dynamic_qr_token(encoded_token: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Validates dynamic QR token:
    1. Base64 decode and payload formatting.
    2. HMAC-SHA256 cryptographic signature match.
    3. Expiration window check (12 seconds rotation with 1 window drift tolerance).
    4. Anti-Replay: Verifies nonce was never consumed before, then consumes it atomically.
    Returns: (is_valid, user_id, role, error_reason)
    """
    _cleanup_consumed_nonces()

    # Padding restore
    pad_len = (4 - len(encoded_token) % 4) % 4
    padded = encoded_token + ("=" * pad_len)

    try:
        raw_str = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        parts = raw_str.split("|")
        if len(parts) != 5:
            return False, None, None, "MALFORMED_QR_TOKEN"
        
        user_id, role, window_str, nonce, signature = parts
        token_window = int(window_str)
    except Exception:
        return False, None, None, "INVALID_QR_ENCODING"

    # 1. Cryptographic Signature Verification
    expected_payload = f"{user_id}|{role}|{token_window}|{nonce}"
    expected_sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        expected_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()[:24]

    if not hmac.compare_digest(signature, expected_sig):
        return False, None, None, "INVALID_QR_SIGNATURE"

    # 2. Time Window & Expiry Check (12-second interval)
    current_window = int(time.time() // QR_ROTATION_INTERVAL_SECONDS)
    window_diff = abs(current_window - token_window)
    if window_diff > DRIFT_TOLERANCE_WINDOWS:
        return False, None, None, "QR_TOKEN_EXPIRED"

    # 3. Anti-Replay Check (Single-use nonce)
    if nonce in CONSUMED_NONCES:
        return False, None, None, "QR_TOKEN_ALREADY_USED"

    # 4. Atomically consume nonce
    CONSUMED_NONCES[nonce] = time.time()
    return True, user_id, role, None

def _cleanup_consumed_nonces():
    """Purges nonces older than 3 rotation windows to bound memory usage."""
    now = time.time()
    cutoff = now - (QR_ROTATION_INTERVAL_SECONDS * 4)
    expired_keys = [k for k, t in CONSUMED_NONCES.items() if t < cutoff]
    for k in expired_keys:
        CONSUMED_NONCES.pop(k, None)
