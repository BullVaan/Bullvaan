"""
Authentication utilities for Bullvaan
Includes password hashing, JWT token handling, and encryption
"""
import os
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
import secrets
from fastapi import HTTPException, status, Depends, Header

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Encryption Configuration
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


# ==================== PASSWORD HASHING ====================

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


# ==================== JWT TOKEN HANDLING ====================

def create_access_token(user_id: str, email: str) -> str:
    """Create JWT access token"""
    payload = {
        "user_id": user_id,
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token expired
    except jwt.InvalidTokenError:
        return None  # Invalid token


# ==================== ENCRYPTION ====================

def encrypt_credential(credential: str) -> str:
    """Encrypt sensitive credential (API key, access token)"""
    return cipher.encrypt(credential.encode()).decode()


def decrypt_credential(encrypted_credential: str) -> str:
    """Decrypt sensitive credential"""
    try:
        return cipher.decrypt(encrypted_credential.encode()).decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt credential: {str(e)}")


# ==================== TOKEN EXTRACTION ====================

def extract_token_from_header(auth_header: Optional[str]) -> Optional[str]:
    """Extract JWT token from Authorization header"""
    if not auth_header:
        return None
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    
    return parts[1]


# ==================== FASTAPI DEPENDENCY ====================

async def get_current_user(authorization: Optional[str] = Header(None), x_session_id: Optional[str] = Header(None)) -> Dict[str, Any]:
    """FastAPI dependency to extract and validate current user from JWT token
    
    Also extracts X-Session-ID header for multi-session auto-trading support.
    Each session (user/browser/device) can run independent auto-traders.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = extract_token_from_header(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("user_id")
    email = payload.get("email")
    
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    # Generate default session ID if not provided
    # This allows clients to send X-Session-ID header for multi-session support
    if not x_session_id:
        x_session_id = f"session_default_{user_id}"
    
    return {
        "user_id": user_id,
        "email": email,
        "session_id": x_session_id
    }
