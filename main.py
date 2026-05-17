import os
import hashlib
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import LibreResponse

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
