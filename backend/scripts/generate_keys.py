#!/usr/bin/env python3
"""
AERIS Key Generation Utility.
Generates cryptographically secure 256-bit secrets for JWT authentication
and Fernet symmetric biometric encryption.
"""
import secrets
from cryptography.fernet import Fernet

def generate_keys():
    jwt_secret = secrets.token_urlsafe(64)
    fernet_key = Fernet.generate_key().decode('utf-8')
    
    print("=" * 60)
    print("AERIS CRYPTOGRAPHIC KEY GENERATOR (PHASE 1)")
    print("=" * 60)
    print("\n# Copy these values into your backend .env file:\n")
    print(f"SECRET_KEY=\"{jwt_secret}\"")
    print(f"FERNET_KEY=\"{fernet_key}\"")
    print("\n" + "=" * 60)
    print("Keep these keys confidential! Never commit production keys to git.")
    print("=" * 60)
    return jwt_secret, fernet_key

if __name__ == "__main__":
    generate_keys()
