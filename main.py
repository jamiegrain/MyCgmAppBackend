import os
import hashlib
import requests
import functions_framework
from flask import jsonify

BASE_URL = "https://api-eu2.libreview.io/"
HEADERS = {
    "accept-encoding": "gzip",
    "cache-control": "no-cache",
    "connection": "Keep-Alive",
    "product": "llu.android",
    "version": "4.16.0",
    "priority": "u=1, i",
}

@functions_framework.http
def hello_http(request):
    """HTTP Cloud Function replacing the C# logic."""
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    username = os.environ.get("LIBRE_USER")
    password = os.environ.get("LIBRE_PASS")

    cors_headers = {'Access-Control-Allow-Origin': '*'}

    if not username or not password:
        return jsonify({"error": "Missing Libre credentials in environment variables."}), 401, cors_headers

    try:
        login_details = login(username, password)
        graph_text = fetch_glucose_data(login_details)
        
        headers = {**cors_headers, 'Content-Type': 'application/json'}
        return graph_text, 200, headers
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500, cors_headers

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
