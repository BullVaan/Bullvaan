from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.supabase_client import supabase
from datetime import datetime

router = APIRouter()

class SignupRequest(BaseModel):
    email: str
    password: str

@router.post("/signup")
def signup(request: SignupRequest):
    # Check if email already exists
    existing = supabase.table("users").select("id").eq("email", request.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered.")
    
    # Use the password provided by the user (not a random one)
    password = request.password
    
    # Insert user with is_approved = false (requires admin approval)
    result = supabase.table("users").insert({
        "email": request.email,
        "password": password,
        "is_approved": False,  # New user is not approved by default
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Signup failed: " + str(result.__dict__))
    
    return {
        "message": "Signup successful! Your account is pending admin approval. You will receive an email once approved.",
        "email": request.email,
        "id": result.data[0].get("id") if result.data else None
    }
