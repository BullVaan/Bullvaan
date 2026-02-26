from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.supabase_client import supabase

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(request: LoginRequest):
    result = supabase.table("users").select("id", "email").eq("email", request.email).eq("password", request.password).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"message": "Login successful", "user": result.data[0]}
