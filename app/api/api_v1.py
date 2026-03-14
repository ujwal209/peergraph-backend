from fastapi import APIRouter
from app.api.endpoints import health, ai, auth, learning, curriculum, discussions, upload, explorer

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"])
api_router.include_router(curriculum.router, prefix="/curriculum", tags=["curriculum"])
api_router.include_router(discussions.router, prefix="/discussions", tags=["discussions"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(explorer.router, prefix="/explorer", tags=["explorer"])
