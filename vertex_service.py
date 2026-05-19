import os
import uuid
import logging
from google.cloud import dialogflowcx_v3 as dialogflow

logger = logging.getLogger(__name__)

class VertexService:
    """
    A simplified service to interact with Vertex AI Agents in a stateless, 
    single ask-and-response fashion.
    """
    def __init__(self):
        self.project_id = os.getenv("VERTEX_PROJECT_ID")
        self.location = os.getenv("VERTEX_LOCATION", "global")
        self.agent_id = os.getenv("VERTEX_AGENT_ID")
        self.client = None

    def ask(self, text: str, session_id: str = None) -> str:
        """
        Sends a query to the Vertex agent and returns the text response directly.
        If a session_id is provided, it maintains state across queries.
        """
        if not self.project_id or not self.agent_id:
            raise ValueError(
                "Vertex Agent is not configured. Please set the environment variables "
                "VERTEX_PROJECT_ID and VERTEX_AGENT_ID, or save them in settings."
            )

        # Lazy initialize client
        if self.client is None:
            if self.location and self.location.lower() != "global":
                api_endpoint = f"{self.location.lower()}-dialogflow.googleapis.com:443"
            else:
                api_endpoint = "dialogflow.googleapis.com:443"

            self.client = dialogflow.SessionsClient(client_options={"api_endpoint": api_endpoint})
            logger.info(f"Initialized SessionsClient on endpoint: {api_endpoint}")

        # Use provided session_id or generate transient session ID
        active_session_id = session_id or str(uuid.uuid4())
        session_path = self.client.session_path(
            project=self.project_id,
            location=self.location,
            agent=self.agent_id,
            session=active_session_id
        )

        logger.info(f"Querying agent in project {self.project_id} (session: {active_session_id})")

        # Construct request
        text_input = dialogflow.TextInput(text=text)
        query_input = dialogflow.QueryInput(text=text_input, language_code="en")
        request = dialogflow.DetectIntentRequest(
            session=session_path,
            query_input=query_input
        )

        # Query the agent
        response = self.client.detect_intent(request=request)

        # Extract text response parts
        text_responses = []
        for message in response.query_result.response_messages:
            if message.text:
                text_responses.extend(message.text.text)

        # Return concatenated string
        if text_responses:
            return " ".join(text_responses)
        
        return "No text response received from agent."
