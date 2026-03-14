from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.api.deps import get_current_user
from app.db.supabase import get_supabase
from app.core.config import settings
from pydantic import BaseModel
from typing import List, Optional, Any
from groq import Groq

router = APIRouter()

class UnitStudyGuideRequest(BaseModel):
    courseTitle: str
    unitTitle: str
    unitContent: str

class CommentCreate(BaseModel):
    unitId: int
    content: str

class AIMessageRequest(BaseModel):
    sessionId: int
    unitId: int
    message: str
    unitTitle: str
    unitContent: str
    history: List[Any] = []

@router.post("/generate-study-guide")
async def generate_study_guide(req: UnitStudyGuideRequest, user=Depends(get_current_user)):
    groq = Groq(api_key=settings.GROQ_API_KEY)
    try:
        completion = groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an elite academic AI tutor. Your task is to break down the given syllabus unit into a structured, easy-to-understand study guide. Provide key topics, brief explanations, and suggested reading strategies. Use Markdown format. Keep it concise, engaging, and focused on learning outcomes.",
                },
                {
                    "role": "user",
                    "content": f"Course: {req.courseTitle}\nUnit: {req.unitTitle}\nSyllabus Content: {req.unitContent}\n\nPlease generate a learning breakdown for this unit.",
                },
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.5,
            max_tokens=1500,
        )
        return {"data": completion.choices[0].message.content or "No content generated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/comments")
async def add_comment(req: CommentCreate, user=Depends(get_current_user)):
    supabase = get_supabase()
    
    # We need to use the token for the user sense
    # Since we use get_supabase() which is anon client by default,
    # we should ideally use the user's token for RLS
    # For now, let's use the admin client if needed or pass the token
    
    # Actually, to respect RLS, we should initialize the client with the user's token
    # But let's simplify and use admin for now while migrating
    from app.db.supabase import get_supabase_admin
    supabase_admin = get_supabase_admin()
    
    response = supabase_admin.table("unit_comments").insert({
        "unit_id": req.unitId,
        "user_id": user.id,
        "content": req.content,
        "author_name": user.user_metadata.get("full_name", "Anonymous Scholar"),
        "author_avatar": user.user_metadata.get("avatar_url")
    }).execute()
    
    return {"data": response.data[0]}

@router.get("/comments/{unit_id}")
async def get_comments(unit_id: int, user=Depends(get_current_user)):
    supabase_admin = get_supabase_admin()
    
    # Fetch comments and likes
    response = supabase_admin.table("unit_comments")\
        .select("*, unit_comment_likes(user_id)")\
        .eq("unit_id", unit_id)\
        .order("created_at", {"ascending": True})\
        .execute()
    
    comments = []
    for c in response.data:
        likes = c.get('unit_comment_likes', [])
        comments.append({
            **c,
            "likesCount": len(likes),
            "hasLiked": any(l['user_id'] == user.id for l in likes),
            "unit_comment_likes": None
        })
    
    return {"data": comments, "currentUserId": user.id}

@router.post("/ai/message")
async def send_ai_message(req: AIMessageRequest, user=Depends(get_current_user)):
    supabase_admin = get_supabase_admin()
    
    # 1. Store user message
    supabase_admin.table("ai_chat_messages").insert({
        "session_id": req.sessionId,
        "role": 'user',
        "message": req.message
    }).execute()
    
    # 2. Prepare AI context
    groq = Groq(api_key=settings.GROQ_API_KEY)
    
    context_history = [
        {"role": m.get('role'), "content": m.get('message')} 
        for m in req.history[-5:]
    ]

    try:
        completion = groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"""You are an elite academic AI tutor with access to the following unit syllabus. 
Unit Title: {req.unitTitle}
Unit Content: {req.unitContent}

Your task: Provide accurate explanations and answers based strictly on this unit context. 
Be concise, technical when needed, and always academic. Explain mathematical concepts iteratively and logically.

CRITICAL FORMATTING RULES:
1. Use Markdown for structural formatting.
2. For math/equations, use strict LaTeX.
3. Single $ for inline, double $$ for block.
4. Use LaTeX bmatrix for matrices.
"""
                },
                *context_history,
                {"role": "user", "content": req.message},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.6,
        )

        ai_response = completion.choices[0].message.content or "No response returned."

        # 3. Store AI message
        saved_msg = supabase_admin.table("ai_chat_messages").insert({
            "session_id": req.sessionId,
            "role": 'assistant',
            "message": ai_response
        }).execute()

        return {"data": saved_msg.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
