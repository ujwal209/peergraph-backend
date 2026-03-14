from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.supabase import get_supabase
from app.core.config import settings

security = HTTPBearer()

async def get_current_user(auth: HTTPAuthorizationCredentials = Security(security)):
    token = auth.credentials
    supabase = get_supabase()
    
    # Verify token with Supabase
    try:
        user_response = supabase.auth.get_user(token)
        if not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return user_response.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

async def get_optional_user(auth: HTTPAuthorizationCredentials = Security(security)):
    if not auth:
        return None
    try:
        return await get_current_user(auth)
    except:
        return None
