import os
import hashlib
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from typing import Optional
from models import LibreResponse
from settings.settings import (
    get_activity_status, 
    set_activity_status
)
from vertex_service import VertexService
from calendar_service import CalendarService

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://api-eu2.libreview.io/"
HEADERS = {
    "accept-encoding": "gzip",
    "cache-control": "no-cache",
    "connection": "Keep-Alive",
    "product": "llu.android",
    "version": "4.16.0",
    "priority": "u=1, i",
}

@app.get("/")
def get_libre_data():
    """HTTP FastAPI route using Pydantic models."""
    username = os.environ.get("LIBRE_USER")
    password = os.environ.get("LIBRE_PASS")

    if not username or not password:
        raise HTTPException(status_code=401, detail="Missing Libre credentials in environment variables.")

    try:
        login_details = login(username, password)
        graph_text = fetch_glucose_data(login_details)
        
        # Validate and serialize using Pydantic
        libre_data = LibreResponse.model_validate_json(graph_text)
        
        return libre_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ActivityStatusRequest(BaseModel):
    isActivityInProgress: bool

@app.get("/settings/activity")
def get_activity():
    try:
        status = get_activity_status()
        return {"isActivityInProgress": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/settings/activity")
def set_activity(request: ActivityStatusRequest):
    try:
        set_activity_status(request.isActivityInProgress)
        return {"success": True, "isActivityInProgress": request.isActivityInProgress}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class VertexQueryRequest(BaseModel):
    text: str
    sessionId: Optional[str] = None

@app.post("/vertex/query")
def query_vertex(request: VertexQueryRequest):
    try:
        service = VertexService()
        if not service.project_id or not service.agent_id:
            raise HTTPException(
                status_code=400,
                detail="Vertex AI Agent is not configured. Please set environment variables (VERTEX_PROJECT_ID, VERTEX_AGENT_ID) or configure them via settings."
            )
        import uuid
        active_session_id = request.sessionId or str(uuid.uuid4())
        response_text = service.ask(text=request.text, session_id=active_session_id)
        return {"response": response_text, "sessionId": active_session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/calendar/events")
def get_calendar_events(max_results: int = 10, calendar_id: Optional[str] = None):
    try:
        service = CalendarService()
        events = service.get_upcoming_events(max_results=max_results, calendar_id=calendar_id)
        return {"success": True, "calendarId": calendar_id or service.calendar_id, "events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



def login(username, password):
    url = f"{BASE_URL}llu/auth/login"
    payload = {"email": username, "password": password}
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if not response.ok:
        raise Exception(f"Failed to login to LibreView: {response.text}")
    
    data = response.json()
    user_id = data.get("data", {}).get("user", {}).get("id")
    token = data.get("data", {}).get("authTicket", {}).get("token")
    
    if not user_id or not token:
        raise Exception("Invalid login response format")

    account_id = hashlib.sha256(user_id.encode('utf-8')).hexdigest().lower()

    return {
        "patientId": user_id,
        "token": token,
        "accountId": account_id
    }

def fetch_glucose_data(login_details):
    url = f"{BASE_URL}llu/connections/{login_details['patientId']}/graph"
    req_headers = HEADERS.copy()
    req_headers.update({
        "Authorization": f"Bearer {login_details['token']}",
        "account-id": login_details['accountId']
    })
    
    response = requests.get(url, headers=req_headers)
    
    if not response.ok:
        raise Exception(f"Failed to fetch graph data: {response.text}")
        
    return response.text
