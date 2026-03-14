from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os

# Get the base directory of the backend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Settings(BaseSettings):
    PROJECT_NAME: str = "PeerGraph API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    
    # Groq Logic
    GROQ_API_KEY: str  # Kept for backward compatibility
    GROQ_API_KEYS: Optional[str] = None # Our comma-separated list
    GROQ_LLM_MODEL: str = "llama-3.3-70b-versatile"
    
    # SMTP
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_SECURE: bool = False
    SMTP_USER: str
    SMTP_PASS: str
    SMTP_FROM: Optional[str] = None

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    
    GEMINI_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_groq_keys(self) -> List[str]:
        """Helper to parse keys safely and remove newlines/whitespace"""
        source = self.GROQ_API_KEYS or self.GROQ_API_KEY
        if not source:
            return []
        # Split by comma, then strip all whitespace and newlines from each key
        return [k.strip().replace("\n", "").replace("\r", "") for k in source.split(",") if k.strip()]

settings = Settings()