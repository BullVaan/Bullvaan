from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.supabase_client import supabase
from utils.auth import create_access_token
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(request: LoginRequest):
    result = supabase.table("users").select("id", "email", "is_approved").eq("email", request.email.lower().strip()).eq("password", request.password).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = result.data[0]
    
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

