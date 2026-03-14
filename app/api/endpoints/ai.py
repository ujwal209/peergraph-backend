import random
import logging
from fastapi import APIRouter, Depends, HTTPException
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import Annotated, TypedDict, Optional
from pydantic import BaseModel
from app.core.config import settings
from app.db.supabase import get_supabase_admin
from app.api.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

class PDFChatRequest(BaseModel):
    material_id: str
    message: str
    session_id: Optional[str] = None

class SessionUpdate(BaseModel):
    title: str

# --- LangGraph Setup & Load Balancing ---
class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    context: str

def get_api_keys() -> list[str]:
    """Extracts a list of API keys from the environment variables."""
    # Checks for GROQ_API_KEYS list, or falls back to splitting GROQ_API_KEY by comma
    raw_keys = getattr(settings, "GROQ_API_KEYS", getattr(settings, "GROQ_API_KEY", ""))
    if isinstance(raw_keys, list):
        return [k.strip() for k in raw_keys if k.strip()]
    return [k.strip() for k in raw_keys.split(",") if k.strip()]

def invoke_with_fallback(messages: list) -> AIMessage:
    # Use the helper method to get clean, stripped keys
    keys = settings.get_groq_keys()
    
    if not keys:
        raise ValueError("No Groq API keys found. Check GROQ_API_KEYS in .env")
        
    random.shuffle(keys)
    
    last_exception = None
    for key in keys:
        try:
            # Important: Print for debugging (remove in production)
            # print(f"Attempting with key: {key[:10]}...") 
            llm = ChatGroq(
                groq_api_key=key,
                model_name=settings.GROQ_LLM_MODEL
            )
            return llm.invoke(messages)
        except Exception as e:
            logger.warning(f"Key failure: {str(e)}")
            last_exception = e
            continue
            
    raise HTTPException(status_code=503, detail=f"All AI nodes exhausted: {str(last_exception)}")
    """
    Attempts to invoke the LLM using a pool of API keys.
    Provides load balancing (random start) and fallback on failures (rate limits, etc.).
    """
    keys = get_api_keys()
    if not keys:
        raise ValueError("No Groq API keys configured in environment variables.")
        
    # Shuffle keys to distribute load evenly across the pool (Round-Robin style)
    random.shuffle(keys)
    
    last_exception = None
    
    for key in keys:
        try:
            llm = ChatGroq(
                groq_api_key=key,
                model_name=settings.GROQ_LLM_MODEL
            )
            # If successful, return the response immediately
            return llm.invoke(messages)
        except Exception as e:
            # Log the failure and try the next key in the loop
            logger.warning(f"Groq API key starting with {key[:8]}... failed. Error: {str(e)}")
            last_exception = e
            continue
            
    # If we exit the loop, all keys have failed
    logger.error("All Groq API keys failed.")
    raise Exception(f"AI Provider Error. All fallback keys exhausted. Last error: {last_exception}")

def call_model(state: GraphState):
    system_prompt = SystemMessage(
        content=(
            "You are an intelligent academic assistant. Answer strictly based on the provided document context. "
            "If the context lacks the answer, state that, but you may provide general knowledge if relevant. "
            "Use Markdown and LaTeX for math.\n\n"
            f"DOCUMENT CONTEXT:\n{state['context']}"
        )
    )
    
    # Pass system prompt + history + current message to our load-balanced invoker
    messages_to_pass = [system_prompt] + state["messages"]
    response = invoke_with_fallback(messages_to_pass)
    
    return {"messages": [response]}

workflow = StateGraph(GraphState)
workflow.add_node("agent", call_model)
workflow.add_edge(START, "agent")
workflow.add_edge("agent", END)
app_graph = workflow.compile()
# -----------------------

@router.post("/pdf-chat")
async def chat_with_pdf(req: PDFChatRequest, user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    
    # 1. Fetch PDF Context
    material_res = supabase.table('personal_docs').select('*').eq('id', req.material_id).eq('uploaded_by', user.id).single().execute()
    if not material_res.data:
        raise HTTPException(status_code=404, detail="Material not found")
        
    material = material_res.data
    # Safely handle null text
    raw_text = material.get('extracted_text')
    context_text = (raw_text if raw_text else "No text could be extracted.")[:12000]
    
    # 2. Manage Chat Session
    session_id = req.session_id
    if not session_id:
        session_res = supabase.table('chat_sessions').insert({
            "user_id": user.id,
            "title": f"Analysis: {material.get('file_name', 'Document')}"
        }).execute()
        session_id = session_res.data[0]['id']
        
    # 3. Save incoming user message
    supabase.table('chat_messages').insert({
        "session_id": session_id,
        "role": "user",
        "content": req.message
    }).execute()
    
    # 4. Fetch history for the LangGraph
    history_res = supabase.table('chat_messages').select('*').eq('session_id', session_id).order('created_at').execute()
    
    langchain_messages = []
    if history_res.data:
        for msg in history_res.data:
            if msg['role'] == 'user':
                langchain_messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                langchain_messages.append(AIMessage(content=msg['content']))

    # 5. Invoke LangGraph (which now safely uses load-balancing fallback)
    try:
        final_state = app_graph.invoke({
            "messages": langchain_messages,
            "context": context_text
        })
        
        ai_response_content = final_state["messages"][-1].content
        
        # 6. Save AI Response
        supabase.table('chat_messages').insert({
            "session_id": session_id,
            "role": "assistant",
            "content": ai_response_content
        }).execute()
        
        return {
            "response": ai_response_content,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Session Management Endpoints ---

@router.get("/sessions")
async def get_sessions(user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    # Fetch all chat sessions for the current user
    res = supabase.table('chat_sessions').select('*').eq('user_id', user.id).order('created_at', desc=True).execute()
    return {"sessions": res.data or []}

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    
    # Verify the session belongs to the user
    session_res = supabase.table('chat_sessions').select('*').eq('id', session_id).eq('user_id', user.id).single().execute()
    if not session_res.data:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Fetch messages
    res = supabase.table('chat_messages').select('*').eq('session_id', session_id).order('created_at').execute()
    return {"messages": res.data or []}

@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, payload: SessionUpdate, user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    res = supabase.table('chat_sessions').update({"title": payload.title}).eq('id', session_id).eq('user_id', user.id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": res.data[0]}

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user=Depends(get_current_user)):
    supabase = get_supabase_admin()
    supabase.table('chat_sessions').delete().eq('id', session_id).eq('user_id', user.id).execute()
    return {"success": True}