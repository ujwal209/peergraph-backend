from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from app.api.deps import get_current_user
from app.db.supabase import get_supabase_admin
from app.core.pdf_utils import extract_text_from_pdf
from app.core.config import settings
import cloudinary
import cloudinary.uploader
import io
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class MaterialUpdate(BaseModel):
    file_name: str

try:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )
except Exception as e:
    logger.warning(f"Cloudinary config warning: {e}")

@router.post("/pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    branch_id: int = Form(1), # Defaulted to 1 to prevent 422 if missing
    semester_id: int = Form(...),
    subject_id: int = Form(...),
    unit_id: Optional[int] = Form(None),
    user=Depends(get_current_user)
):
    print(f"--- UPLOAD INITIATED --- File: {file.filename}, User: {user.id}")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    supabase = get_supabase_admin()
    
    try:
        content = await file.read()
        extracted_text = extract_text_from_pdf(content)
        print(f"Extracted {len(extracted_text)} characters.")
        
        upload_result = cloudinary.uploader.upload(
            io.BytesIO(content),
            resource_type="raw",
            folder="peergraph/materials",
            public_id=file.filename
        )
        cloudinary_url = upload_result.get("secure_url")

        response = supabase.table('personal_docs').insert({
            "file_name": file.filename,
            "cloudinary_url": cloudinary_url,
            "branch_id": branch_id,
            "semester_id": semester_id,
            "subject_id": subject_id,
            "unit_id": unit_id,
            "uploaded_by": user.id,
            "extracted_text": extracted_text 
        }).execute()
        
        print("--- UPLOAD SUCCESSFUL ---")
        return {
            "success": True, 
            "materialId": response.data[0]['id'],
            "cloudinaryUrl": cloudinary_url,
            "textLength": len(extracted_text)
        }
        
    except Exception as e:
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_materials(
    semester_id: int = None,
    subject_id: int = None,
    unit_id: int = None,
    user=Depends(get_current_user)
):
    supabase = get_supabase_admin()
    query = supabase.table('personal_docs').select('*').eq('uploaded_by', user.id)
    
    if semester_id:
        query = query.eq('semester_id', semester_id)
    if subject_id:
        query = query.eq('subject_id', subject_id)
    if unit_id:
        query = query.eq('unit_id', unit_id)
        
    response = query.order('created_at', desc=True).execute()
    return {"materials": response.data or []}

@router.patch("/pdf/{material_id}")
async def update_material(material_id: str, payload: MaterialUpdate, user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    res = supabase.table('personal_docs').update({"file_name": payload.file_name}).eq('id', material_id).eq('uploaded_by', user.id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"success": True, "material": res.data[0]}