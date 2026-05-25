import os
import hashlib
import requests
import logging
from models import LibreResponse

_logger = logging.getLogger(__name__)

class LibreService:
    BASE_URL = "https://api-eu2.libreview.io/"
    HEADERS = {
        "accept-encoding": "gzip",
        "cache-control": "no-cache",
        "connection": "Keep-Alive",
        "product": "llu.android",
        "version": "4.16.0",
        "priority": "u=1, i",
    }

    def login(self, username, password) -> dict:
        _logger.info(f"Attempting to login to LibreView for user '{username}'")
        url = f"{self.BASE_URL}llu/auth/login"
        payload = {"email": username, "password": password}
        
        try:
            response = requests.post(url, headers=self.HEADERS, json=payload)
            if not response.ok:
                _logger.error(f"Failed to login to LibreView. Status code: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to login to LibreView: {response.text}")
            
            data = response.json()
            user_id = data.get("data", {}).get("user", {}).get("id")
            token = data.get("data", {}).get("authTicket", {}).get("token")
            
            if not user_id or not token:
                _logger.error("Invalid login response format from LibreView API: user_id or token is missing.")
                raise Exception("Invalid login response format")

            account_id = hashlib.sha256(user_id.encode('utf-8')).hexdigest().lower()
            _logger.info("Successfully logged in to LibreView and generated credentials.")
            
            return {
                "patientId": user_id,
                "token": token,
                "accountId": account_id
            }
        except Exception as e:
            _logger.error(f"Exception during LibreView login flow: {e}")
            raise

    def fetch_glucose_data(self, login_details: dict) -> str:
        patient_id = login_details.get("patientId")
        _logger.info(f"Fetching glucose graph data for patient ID: '{patient_id}'")
        
        url = f"{self.BASE_URL}llu/connections/{patient_id}/graph"
        req_headers = self.HEADERS.copy()
        req_headers.update({
            "Authorization": f"Bearer {login_details['token']}",
            "account-id": login_details['accountId']
        })
        
        try:
            response = requests.get(url, headers=req_headers)
            if not response.ok:
                _logger.error(f"Failed to fetch graph data for patient {patient_id}. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to fetch graph data: {response.text}")
                
            _logger.info(f"Successfully retrieved raw glucose data stream for patient {patient_id}.")
            return response.text
        except Exception as e:
            _logger.error(f"Exception during LibreView glucose data fetch: {e}")
            raise

    def get_glucose_data(self) -> LibreResponse:
        _logger.info("Initiating high-level LibreView glucose data retrieval...")
        username = os.environ.get("LIBRE_USER")
        password = os.environ.get("LIBRE_PASS")

        if not username or not password:
            _logger.error("Missing environment variables LIBRE_USER or LIBRE_PASS.")
            raise ValueError("Missing Libre credentials in environment variables (LIBRE_USER, LIBRE_PASS).")

        try:
            login_details = self.login(username, password)
            graph_text = self.fetch_glucose_data(login_details)
            
            _logger.info("Parsing and validating raw glucose data against LibreResponse Pydantic model...")
            libre_data = LibreResponse.model_validate_json(graph_text)
            
            _logger.info("LibreView glucose data retrieval, validation, and serialization completed successfully.")
            return libre_data
        except Exception as e:
            _logger.error(f"LibreView high-level glucose data fetch failed: {e}")
            raise

    def get_libre_glucose_data(self) -> str:
        """Fetch current CGM glucose data from LibreView."""
        try:
            libre_data = self.get_glucose_data()
            return libre_data.model_dump_json(indent=2)
        except Exception as e:
            _logger.error(f"Error fetching Libre glucose data for agent: {e}")
            return f"Error fetching Libre glucose data: {str(e)}"

