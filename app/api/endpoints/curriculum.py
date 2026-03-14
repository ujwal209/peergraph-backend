from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_user
from app.db.supabase import get_supabase_admin
from pydantic import BaseModel
import datetime

router = APIRouter()

# FIXED: Schema matches the frontend exactly
class TopicToggle(BaseModel):
    unit_id: int
    topic_index: int
    status: bool

@router.get("/taxonomy")
async def get_taxonomy():
    supabase = get_supabase_admin()
    
    branches = supabase.table('branches').select('*').order('id').execute()
    semesters = supabase.table('semesters').select('*').order('semester_number').execute()
    subjects = supabase.table('subjects').select('*, units(*)').order('course_title').execute()
    units = supabase.table('units').select('id, unit_number, unit_title, subject_id, unit_content').order('unit_number').execute()
    
    return {
        "branches": branches.data or [],
        "semesters": semesters.data or [],
        "subjects": subjects.data or [],
        "units": units.data or []
    }

@router.get("/data")
async def get_curriculum_data(user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    
    # Fetch subjects and units
    subjects_res = supabase.table('subjects').select(
        "id, course_code, course_title, branch_id, semester_id, units(id, unit_number, unit_title, unit_content)"
    ).order('course_title').execute()
    
    if not subjects_res.data:
        return {"data": []}
        
    # Fetch progress
    progress_res = supabase.table('user_topic_progress')\
        .select('unit_id, topic_index')\
        .eq('user_id', user.id)\
        .eq('is_completed', True)\
        .execute()
        
    completed_set = {f"{p['unit_id']}-{p['topic_index']}" for p in progress_res.data}
    
    formatted_data = []
    for sub in subjects_res.data:
        total_sub_topics = 0
        completed_sub_topics = 0
        
        units = sorted(sub.get('units', []), key=lambda x: x['unit_number'])
        formatted_units = []
        
        for u in units:
            unit_content = u.get('unit_content', '')
            import re
            
            raw_topics = [t.strip() for t in re.split(r'\r?\n|,', unit_content) if t.strip()]
            raw_topics = [re.sub(r'^[-*•\d.]+\s*', '', t) for t in raw_topics if t]
            
            topics = []
            for idx, title in enumerate(raw_topics):
                is_comp = f"{u['id']}-{idx}" in completed_set
                total_sub_topics += 1
                if is_comp:
                    completed_sub_topics += 1
                topics.append({"id": idx, "title": title, "completed": is_comp})
                
            formatted_units.append({
                "id": u['id'],
                "title": u['unit_title'],
                "number": u['unit_number'],
                "topics": topics,
                "totalTopics": len(topics),
                "completedTopics": sum(1 for t in topics if t['completed'])
            })
            
        progress_pct = 0
        if total_sub_topics > 0:
            progress_pct = int((completed_sub_topics / total_sub_topics) * 100)
            
        formatted_data.append({
            "id": str(sub['id']),
            "rawId": sub['id'],
            "title": sub['course_title'],
            "code": sub['course_code'],
            "branch_id": sub['branch_id'],
            "semester_id": sub['semester_id'],
            "progress": progress_pct,
            "totalSubjectTopics": total_sub_topics,
            "completedSubjectTopics": completed_sub_topics,
            "units": formatted_units
        })
        
    return {"data": formatted_data}

@router.post("/toggle-topic")
async def toggle_topic(req: TopicToggle, user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    
    try:
        supabase.table('user_topic_progress').upsert({
            "user_id": user.id,
            "unit_id": req.unit_id,
            "topic_index": req.topic_index,
            "is_completed": req.status,
            "completed_at": datetime.datetime.now().isoformat()
        }).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))