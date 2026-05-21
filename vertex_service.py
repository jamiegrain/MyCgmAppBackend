import os
import uuid
import logging
import requests
import google.auth
import google.auth.transport.requests

logger = logging.getLogger(__name__)

class VertexService:
    """
    A service to interact with Vertex AI Agents (CES / Gen AI Playbooks) via the runSession REST API.
    """
    def __init__(self):
        self.project_id = os.getenv("VERTEX_PROJECT_ID")
        self.location = os.getenv("VERTEX_LOCATION", "us")
        self.agent_id = os.getenv("VERTEX_AGENT_ID")
        self.app_version = os.getenv("VERTEX_APP_VERSION")
        self.deployment = os.getenv("VERTEX_DEPLOYMENT")
        self.creds = None

    def ask(self, text: str, session_id: str = None) -> str:
        """
        Sends a query to the Vertex CES Playbook agent and returns the text response.
        """
        if not self.project_id or not self.agent_id:
            raise ValueError(
                "Vertex Agent is not configured. Please set VERTEX_PROJECT_ID and VERTEX_AGENT_ID in .env."
            )

        # Get Google Application Default Credentials (ADC)
        if self.creds is None:
            self.creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            
        # Refresh the credentials to get a fresh access token
        auth_req = google.auth.transport.requests.Request()
        self.creds.refresh(auth_req)

        # Use or generate a transient session ID
        active_session_id = session_id or str(uuid.uuid4())
        
        # Build the session path
        session_path = f"projects/{self.project_id}/locations/{self.location}/apps/{self.agent_id}/sessions/{active_session_id}"
        url = f"https://ces.googleapis.com/v1beta/{session_path}:runSession"
        
        headers = {
            "Authorization": f"Bearer {self.creds.token}",
            "Content-Type": "application/json"
        }

        # Build request payload
        config = {
            "session": session_path
        }
        if self.app_version:
            config["app_version"] = self.app_version
        if self.deployment:
            config["deployment"] = self.deployment

        payload = {
            "config": config,
            "inputs": [
                {
                    "text": text
                }
            ]
        }

        logger.info(f"Querying CES agent runSession: {url}")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if not response.ok:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
            res_json = response.json()
            logger.info("Successfully received response from CES runSession API.")
            
            # CES runSession returns a structured JSON payload containing the conversation turns/outputs.
            # Let's extract the textual response from the payload dynamically.
            text_outputs = []
            
            def extract_text(data):
                if isinstance(data, dict):
                    for k, v in data.items():
                        if k == "text" and isinstance(v, str):
                            text_outputs.append(v)
                        else:
                            extract_text(v)
                elif isinstance(data, list):
                    for item in data:
                        extract_text(item)
                        
            extract_text(res_json)
            
            if text_outputs:
                # Deduplicate and filter out reflected user query if present
                unique_outputs = list(dict.fromkeys(t.strip() for t in text_outputs if t.strip().lower() != text.strip().lower()))
                if unique_outputs:
                    return "\n\n".join(unique_outputs)
                return "\n\n".join(list(dict.fromkeys(t.strip() for t in text_outputs)))
                
            return str(res_json)
            
        except Exception as e:
            logger.error(f"Error querying CES runSession: {e}")
            raise e
