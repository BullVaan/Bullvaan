from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.supabase_client import supabase
import secrets
from datetime import datetime

router = APIRouter()

class SignupRequest(BaseModel):
    email: str

@router.post("/signup")
def signup(request: SignupRequest):
    # Check if email already exists
    existing = supabase.table("users").select("id").eq("email", request.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered.")
    # Generate random password
    password = secrets.token_urlsafe(12)
    # Insert user
    result = supabase.table("users").insert({
        "email": request.email,
        "password": password,
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Signup failed: " + str(result.__dict__))
    return {"message": "Signup successful. Admin will share your password."}
