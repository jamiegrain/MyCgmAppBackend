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
            libre_service.get_glucose_statistics,
            libre_service.get_time_in_range,
            libre_service.get_hourly_glucose_patterns,
            libre_service.get_glucose_extreme_events,
            garmin_service.get_garmin_activities,
            garmin_service.get_garmin_daily_steps,
            garmin_service.get_garmin_daily_stress,
            garmin_service.get_garmin_daily_sleep_and_recovery,
            calendar_service.get_calendar_events
        ]

        # Instruct the model on how to act, retrieve data, and present its findings
        system_instruction = (
            "You are an encouraging, friendly personal health data analyst and educational fitness companion. "
            "While you can't provide medical advice, you can provide informational and educational insights and suggestions. "
            "You have access to the user's LibreView Continuous Glucose Monitor (CGM) data (both current stream and rich historical BigQuery stats), "
            "Garmin activity/fitness logs, daily steps, stress levels, sleep scores, overnight HRV recovery data, and Google Calendar schedules. "
            "Use these tools to fetch data and analyze historical trends or relationships between physical activity (Garmin) and glucose patterns (CGM). "
            "Present your findings as correlation insights, data summaries, and educational observations.\n\n"
            "CRITICAL GUIDANCE FOR INSULIN AND RATIO INQUIRIES:\n"
            "- If the user asks about their insulin ratio, insulin-to-carb ratio, correction factor, active insulin, or dosing:\n"
            "  1. State clearly that you cannot calculate, suggest, or recommend insulin dosing or adjust clinical ratios, as this must be done with their physician.\n"
            "  2. Pivot immediately to a retrospective, mathematical analysis of historical data. Review glucose levels 2-4 hours after logged meals or exercise to identify patterns (e.g., 'Historically, after high-carb meals, glucose remains above target for 3 hours, or drops below target').\n"
            "  3. Frame these as retrospective observations (e.g., 'This historical pattern is something you can share with your healthcare team to discuss whether your current ratio is optimal').\n"
            "- All measures are in mmol/L. "
            "- We are in debug mode, so any errors should be reported back to the user."
        )

        config = types.GenerateContentConfig(
            tools=tools,
            system_instruction=system_instruction,
            temperature=0.3
        )

        try:
            # We use gemini-2.5-flash as the default model
            response = self.client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=text,
                config=config
            )
            logger.info("Successfully received response from local Gemini 2.5 Agent.")
            return response.text
        except Exception as e:
            logger.error(f"Gemini local agent query failed: {e}")
            raise e
