import os
import uuid
import logging
from google import genai
from google.genai import types

from services import LibreService, GarminService, CalendarService

logger = logging.getLogger(__name__)

class VertexService:
    """
    A service that runs your Gemini 2.5 Agent directly inside your existing backend.
    It utilizes the new google-genai SDK with automatic function calling on your tools.
    """
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.agent_id = os.getenv("VERTEX_AGENT_ID")
        self.client = genai.Client()

    def ask(self, text: str, session_id: str = None) -> str:
        """
        Queries Gemini 2.5 with automatic function calling over your LibreView, Garmin, and Calendar tools.
        """
        active_session_id = session_id or str(uuid.uuid4())
        logger.info(f"Querying Gemini 2.5 local agent (Session: {active_session_id})")

        # Instantiate services dynamically
        libre_service = LibreService()
        garmin_service = GarminService()
        calendar_service = CalendarService()

        # Configure the tools available to the model using bound service methods
        tools = [
            libre_service.get_libre_glucose_data,
            garmin_service.get_garmin_activities,
            calendar_service.get_calendar_events
        ]

        # Instruct the model on how to act, retrieve data, and present its findings
        system_instruction = (
            "You are an encouraging, highly professional personal health and fitness AI assistant. "
            "You have access to the user's LibreView Continuous Glucose Monitor (CGM) data, "
            "recent Garmin activity/fitness logs, and Google Calendar schedules. "
            "Use these tools to fetch real-time or historical data when asked questions about the user's health. "
            "Analyze relationships between physical activity (Garmin) and glucose patterns (CGM), "
            "and suggest correlation insights. "
            "All measures are in mmol/L."
            "We are in debug mode, so any errors should be reported back to the user."
        )

        config = types.GenerateContentConfig(
            tools=tools,
            system_instruction=system_instruction,
            temperature=0.2  # Low temperature for precise analytical insights
        )

        try:
            # We use gemini-2.5-flash as the default model
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=text,
                config=config
            )
            logger.info("Successfully received response from local Gemini 2.5 Agent.")
            return response.text
        except Exception as e:
            logger.error(f"Gemini local agent query failed: {e}")
            raise e
