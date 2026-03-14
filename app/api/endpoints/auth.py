from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from app.db.supabase import get_supabase, get_supabase_admin
from app.core.mailer import send_otp_email
import random
import datetime

router = APIRouter()

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserSignup(BaseModel):
    email: EmailStr
    password: str
    name: str

class OTPVerify(BaseModel):
    email: EmailStr
    token: str

@router.post("/login")
async def login(user_data: UserLogin):
    supabase = get_supabase()
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user_data.email,
            "password": user_data.password
        })
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/signup")
async def signup(user_data: UserSignup, background_tasks: BackgroundTasks):
    supabase_admin = get_supabase_admin()
    
    # 1. Create user in Supabase Auth via Admin Client
    try:
        user = supabase_admin.auth.admin.create_user({
            "email": user_data.email,
            "password": user_data.password,
            "email_confirm": False,
            "user_metadata": {"full_name": user_data.name}
        })
    except Exception as e:
        # Fall through if user already exists
        if "already registered" not in str(e).lower():
            raise HTTPException(status_code=400, detail=str(e))

    # 2. Generate OTP
    otp_code = str(random.randint(100000, 999999))
    expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()

    # 3. Store OTP in database
    try:
        supabase_admin.table("otps").insert({
            "email": user_data.email,
            "code": otp_code,
            "type": "signup",
            "expires_at": expires_at
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate security sequence")

    # 4. Send Email (Background Task)
    background_tasks.add_task(send_otp_email, user_data.email, otp_code, "signup")

    return {"message": "Initialization Sequence Started. Check your institutional node."}

@router.post("/verify-otp")
async def verify_otp(data: OTPVerify):
    supabase_admin = get_supabase_admin()
    
    # 1. Check OTP
    now = datetime.datetime.now().isoformat()
    try:
        otp_query = supabase_admin.table("otps")\
            .select("*")\
            .eq("email", data.email)\
            .eq("code", data.token)\
            .eq("type", "signup")\
            .eq("used", False)\
            .gt("expires_at", now)\
            .execute()
        
        if not otp_query.data:
            raise HTTPException(status_code=400, detail="Invalid or expired verification sequence")
        
        otp_id = otp_query.data[0]['id']
        
        # 2. Mark as used
        supabase_admin.table("otps").update({"used": True}).eq("id", otp_id).execute()
        
        # 3. Confirm user
        # In python, we list users or just find by email
        users = supabase_admin.auth.admin.list_users()
        target_user = next((u for u in users if u.email == data.email), None)
        
        if target_user:
            supabase_admin.auth.admin.update_user_by_id(target_user.id, {"email_confirm": True})
            
        return {"message": "Identity verified. You may now resume session."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send-reset-otp")
async def send_reset_otp(email: EmailStr, background_tasks: BackgroundTasks):
    supabase_admin = get_supabase_admin()
    
    # Check if user exists
    users = supabase_admin.auth.admin.list_users()
    target_user = next((u for u in users if u.email == email), None)
    
    if not target_user:
        raise HTTPException(status_code=404, detail="Identity not found in network registry")

    otp_code = str(random.randint(100000, 999999))
    expires_at = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()

    try:
        supabase_admin.table("otps").insert({
            "email": email,
            "code": otp_code,
            "type": "recovery",
            "expires_at": expires_at
        }).execute()
        
        background_tasks.add_task(send_otp_email, email, otp_code, "recovery")
        return {"message": "Recovery sequence initiated. Check your node."}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to dispatch recovery sequence")

@router.post("/verify-reset-otp")
async def verify_reset_otp(data: OTPVerify):
    supabase_admin = get_supabase_admin()
    
    # 1. Check OTP
    now = datetime.datetime.now().isoformat()
    try:
        otp_query = supabase_admin.table("otps")\
            .select("*")\
            .eq("email", data.email)\
            .eq("code", data.token)\
            .eq("type", "recovery")\
            .eq("used", False)\
            .gt("expires_at", now)\
            .execute()
        
        if not otp_query.data:
            raise HTTPException(status_code=400, detail="Invalid or expired recovery sequence")
        
        otp_id = otp_query.data[0]['id']
        
        # 2. Mark as used
        supabase_admin.table("otps").update({"used": True}).eq("id", otp_id).execute()
        
        return {"message": "Recovery sequence verified. You may now update your identity key."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PasswordUpdate(BaseModel):
    email: EmailStr
    password: str

@router.post("/update-password")
async def update_password(data: PasswordUpdate):
    supabase_admin = get_supabase_admin()
    try:
        # Find user
        users = supabase_admin.auth.admin.list_users()
        target_user = next((u for u in users if u.email == data.email), None)
        
        if not target_user:
            raise HTTPException(status_code=404, detail="Identity not found in network registry")
        
        # Update password
        supabase_admin.auth.admin.update_user_by_id(target_user.id, {"password": data.password})
        
        return {"message": "Identity key updated successfully. Security layers established."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
