from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from utils.auth import get_current_user
from utils.supabase_client import supabase

router = APIRouter()

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    mobile: Optional[str] = None

@router.get("/user/profile")
def get_profile(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    result = supabase.table("users").select("full_name, mobile, email").eq("id", user_id).single().execute()
    if not result.data:
        return {"full_name": None, "mobile": None, "email": None}
    return result.data

@router.patch("/user/profile")
def update_profile(payload: ProfileUpdate, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    update_data = {}
    if payload.full_name is not None:
        update_data["full_name"] = payload.full_name
    if payload.mobile is not None:
        update_data["mobile"] = payload.mobile
    if not update_data:
        return {"status": "ok", "message": "Nothing to update"}
    supabase.table("users").update(update_data).eq("id", user_id).execute()
    return {"status": "ok"}
