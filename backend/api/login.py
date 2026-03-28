from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from utils.supabase_client import supabase
from utils.auth import create_access_token, hash_password, verify_password
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, login_data: LoginRequest):
    # Fetch user by email only — never compare passwords in SQL
    result = supabase.table("users").select("id", "email", "password", "is_approved").eq("email", login_data.email.lower().strip()).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = result.data[0]
    stored_password = user.get("password", "")

    # Seamless migration: if password is still plaintext (legacy), verify directly
    # then immediately re-hash and update in DB so it's secure going forward
    if stored_password.startswith("$2b$") or stored_password.startswith("$2a$"):
        # Already hashed — normal bcrypt verify
        if not verify_password(login_data.password, stored_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        # Legacy plaintext password — verify directly
        if login_data.password != stored_password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        # Re-hash and update in DB silently
        new_hash = hash_password(login_data.password)
        supabase.table("users").update({"password": new_hash}).eq("id", user["id"]).execute()
    
    # Check if user is approved by admin
    if not user.get("is_approved", False):
        raise HTTPException(status_code=403, detail="Your account is pending admin approval. Please wait for confirmation email.")
    
    # Generate JWT token
    user_id = str(user.get("id", ""))
    email = user.get("email", "")
    
    try:
        access_token = create_access_token(user_id, email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create token: {str(e)}")
    
    return {
        "message": "Login successful",
        "access_token": access_token,
        "user_id": user_id,
        "email": email,
        "token_type": "bearer"
    }

@router.post("/refresh-token")
def refresh_token():
    """Refresh access token - currently just returns success.
    In production, validate refresh token and return new access token.
    """
    return {"message": "Token refresh successful"}

