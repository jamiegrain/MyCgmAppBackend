from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import uuid
from vertex_service import VertexService

router = APIRouter()

class VertexQueryRequest(BaseModel):
    text: str
    sessionId: Optional[str] = None

def get_vertex_service() -> VertexService:
    return VertexService()

@router.post("/vertex/query")
def query_vertex(request: VertexQueryRequest, service: VertexService = Depends(get_vertex_service)):
    """Query the local Gemini/Vertex AI agent with automatic tool calling."""
    try:
        if not service.project_id or not service.agent_id:
            raise HTTPException(
                status_code=400,
                detail="Vertex AI Agent is not configured. Please set environment variables (GOOGLE_CLOUD_PROJECT, VERTEX_AGENT_ID)."
            )
        active_session_id = request.sessionId or str(uuid.uuid4())
        response_text = service.ask(text=request.text, session_id=active_session_id)
        return {"response": response_text, "sessionId": active_session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
