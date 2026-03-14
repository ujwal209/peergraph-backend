from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_user
from app.db.supabase import get_supabase_admin
from pydantic import BaseModel
from typing import List, Optional, Any, Dict

router = APIRouter()

class CommentCreate(BaseModel):
    unitId: int
    content: str
    parentId: Optional[str] = None

class ReactionToggle(BaseModel):
    commentId: str
    emoji: str
    hasReacted: bool

class LikeToggle(BaseModel):
    commentId: str
    hasLiked: bool

@router.get("/channels")
async def get_discussion_channels(user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    
    response = supabase.table("subjects").select(
        "id, course_code, course_title, semester_id, semesters(semester_number), units(id, unit_number, unit_title)"
    ).order("course_code").execute()
    
    return {"channels": response.data}

@router.get("/comments/{unit_id}")
async def get_unit_comments(unit_id: int, user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    
    response = supabase.table("unit_comments").select(
        "*, unit_comment_likes(user_id), unit_comment_reactions(user_id, emoji)"
    ).eq("unit_id", unit_id).order("created_at").execute()
    
    formatted_data = []
    for comment in response.data:
        reaction_map: Dict[str, Dict] = {}
        for reaction in comment.get('unit_comment_reactions', []):
            emoji = reaction['emoji']
            if emoji not in reaction_map:
                reaction_map[emoji] = {"count": 0, "hasReacted": False}
            reaction_map[emoji]["count"] += 1
            if reaction['user_id'] == user.id:
                reaction_map[emoji]["hasReacted"] = True
                
        likes = comment.get('unit_comment_likes', [])
        
        formatted_data.append({
            **comment,
            "likesCount": len(likes),
            "hasLiked": any(l['user_id'] == user.id for l in likes),
            "reactions": [
                {"emoji": k, "count": v["count"], "hasReacted": v["hasReacted"]}
                for k, v in reaction_map.items()
            ],
            "unit_comment_likes": None,
            "unit_comment_reactions": None
        })
        
    return {"data": formatted_data, "currentUserId": user.id}

@router.post("/comments")
async def add_comment(req: CommentCreate, user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    
    response = supabase.table("unit_comments").insert({
        "unit_id": req.unitId,
        "user_id": user.id,
        "author_name": user.user_metadata.get("full_name", "Anonymous Peer"),
        "author_avatar": user.user_metadata.get("avatar_url"),
        "content": req.content,
        "parent_id": req.parentId
    }).execute()
    
    new_comment = response.data[0]
    return {
        "data": {
            **new_comment,
            "likesCount": 0,
            "hasLiked": False,
            "reactions": []
        }
    }

@router.post("/toggle-reaction")
async def toggle_reaction(req: ReactionToggle, user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    
    if req.hasReacted:
        supabase.table("unit_comment_reactions").delete().match({
            "comment_id": req.commentId,
            "user_id": user.id,
            "emoji": req.emoji
        }).execute()
    else:
        supabase.table("unit_comment_reactions").insert({
            "comment_id": req.commentId,
            "user_id": user.id,
            "emoji": req.emoji
        }).execute()
        
    return {"success": True}

@router.post("/toggle-like")
async def toggle_like(req: LikeToggle, user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    
    if req.hasLiked:
        supabase.table("unit_comment_likes").delete().match({
            "comment_id": req.commentId,
            "user_id": user.id
        }).execute()
    else:
        supabase.table("unit_comment_likes").insert({
            "comment_id": req.commentId,
            "user_id": user.id
        }).execute()
        
    return {"success": True}