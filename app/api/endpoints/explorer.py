from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_user
from app.db.supabase import get_supabase_admin
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class FolderCreate(BaseModel):
    name: str
    branchId: int
    semesterId: int
    subjectId: int
    parentId: Optional[str] = None

class FilesMove(BaseModel):
    fileIds: List[str]
    newSubjectId: int
    newFolderId: Optional[str] = None

class FileRename(BaseModel):
    fileId: str
    newName: str

@router.get("/directory")
async def get_directory(subjectId: int, folderId: Optional[str] = None):
    supabase = get_supabase_admin()
    
    # Folders
    f_q = supabase.table('folders').select('*').eq('subject_id', subjectId)
    if folderId:
        f_q = f_q.eq('parent_id', folderId)
    else:
        f_q = f_q.is_('parent_id', 'null')
    folders = f_q.execute()
    
    # Files
    m_q = supabase.table('study_materials').select('*').eq('subject_id', subjectId)
    if folderId:
        m_q = m_q.eq('folder_id', folderId)
    else:
        m_q = m_q.is_('folder_id', 'null')
    files = m_q.execute()
    
    return {"folders": folders.data or [], "files": files.data or []}

@router.post("/folders")
async def create_folder(req: FolderCreate):
    supabase = get_supabase_admin()
    response = supabase.table('folders').insert({
        "name": req.name,
        "branch_id": req.branchId,
        "semester_id": req.semesterId,
        "subject_id": req.subjectId,
        "parent_id": req.parentId
    }).execute()
    return {"success": True}

@router.post("/files/move")
async def move_files(req: FilesMove):
    supabase = get_supabase_admin()
    subject_info = supabase.table('subjects').select('branch_id, semester_id').eq('id', req.newSubjectId).single().execute()
    if not subject_info.data:
        raise HTTPException(status_code=404, detail="Subject not found")
        
    supabase.table('study_materials').update({
        "subject_id": req.newSubjectId,
        "branch_id": subject_info.data['branch_id'],
        "semester_id": subject_info.data['semester_id'],
        "folder_id": req.newFolderId
    }).in_('id', req.fileIds).execute()
    
    return {"success": True}

@router.delete("/files")
async def delete_files(fileIds: List[str]):
    supabase = get_supabase_admin()
    supabase.table('study_materials').delete().in_('id', fileIds).execute()
    return {"success": True}

@router.patch("/files/rename")
async def rename_file(req: FileRename):
    supabase = get_supabase_admin()
    supabase.table('study_materials').update({"file_name": req.newName}).eq('id', req.fileId).execute()
    return {"success": True}
