import os
import base64
from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AERIS"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    API_V1_STR: str = ""
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./aeris.db")
    
    # JWT Authentication & Token Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", os.getenv("JWT_SECRET", "super-secret-aeris-campusproof-jwt-key-2026"))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    JWT_ISSUER: str = "aeris"
    JWT_AUDIENCE: str = "aeris-app"
    
    # Biometric Fernet Symmetric Encryption Keys (32 url-safe base64-encoded bytes)
    # Primary key used for all new encryptions
    FERNET_KEY: str = os.getenv("FERNET_KEY", "uK23mP7q8Wv1Xz9N4bE6sY0tL5cR8aF2mG7hJ9kQ3v8=")
    # Optional comma-separated previous keys to enable zero-downtime key rotation
    FERNET_KEYS_FALLBACK: str = os.getenv("FERNET_KEYS_FALLBACK", "")
    
    # Biometric & Verification Calibration Thresholds (per docs/results.md & docs/decisions.md)
    FACE_MATCH_THRESHOLD: float = 0.450
    YAW_DELTA_THRESHOLD_DEG: float = 15.0
    MIN_FACE_SCORE: float = 0.50
    BLUR_LAPLACIAN_THRESHOLD: float = 40.0
    MAX_GPS_ACCURACY_M: float = 100.0
    
    # Session
    SESSION_EXPIRY_SECONDS: int = 60

    # Rate Limiting (slowapi limit strings — override via .env in production)
    RATE_LIMIT_LOGIN: str = "10 per minute"
    RATE_LIMIT_VERIFY: str = "5 per minute"
    RATE_LIMIT_ENROLL: str = "5 per minute"

    # Port & HTTPS configuration
    PORT: int = int(os.getenv("PORT", 8000))
    ENABLE_HSTS: bool = True
    HSTS_MAX_AGE_SECONDS: int = 63072000
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

    def get_allowed_origins(self) -> List[str]:
        if self.ALLOWED_ORIGINS and self.ALLOWED_ORIGINS.strip() != "*":
            return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        return ["*"]

    def get_all_fernet_keys(self) -> List[bytes]:
        """Returns ordered list of Fernet keys (primary first, then fallbacks)."""
        keys = [self.FERNET_KEY.strip()]
        if self.FERNET_KEYS_FALLBACK:
            for k in self.FERNET_KEYS_FALLBACK.split(","):
                k = k.strip()
                if k and k not in keys:
                    keys.append(k)
        
        # Validate that each key is a valid 32-byte url-safe base64 key
        validated = []
        for key_str in keys:
            key_bytes = key_str.encode("utf-8")
            try:
                decoded = base64.urlsafe_b64decode(key_bytes)
                if len(decoded) != 32:
                    raise ValueError(f"Fernet key must decode to exactly 32 bytes, got {len(decoded)}")
                validated.append(key_bytes)
            except Exception as e:
                raise ValueError(f"Invalid Fernet key in configuration: {e}")
        return validated

    def validate_production_secrets(self):
        """Enforces that non-default secrets are used in production; auto-generates if missing."""
        default_secret = "super-secret-aeris-campusproof-jwt-key-2026"
        default_fernet = "uK23mP7q8Wv1Xz9N4bE6sY0tL5cR8aF2mG7hJ9kQ3v8="
        
        if self.SECRET_KEY == default_secret:
            jwt_sec = os.getenv("JWT_SECRET")
            if jwt_sec and jwt_sec != default_secret:
                self.SECRET_KEY = jwt_sec
            else:
                import secrets
                self.SECRET_KEY = secrets.token_urlsafe(32)
                
        if self.FERNET_KEY == default_fernet:
            from cryptography.fernet import Fernet
            self.FERNET_KEY = Fernet.generate_key().decode()

settings = Settings()
