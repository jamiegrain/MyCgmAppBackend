import os
import json
import logging

# Import existing backend logic
from main import login, fetch_glucose_data
from models import LibreResponse
from garmin_service import GarminService
from calendar_service import CalendarService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_libre_glucose_data() -> str:
    """Fetch current CGM glucose data from LibreView."""
    username = os.environ.get("LIBRE_USER")
    password = os.environ.get("LIBRE_PASS")

    if not username or not password:
        return "Error: Missing Libre credentials in environment variables."

    try:
        login_details = login(username, password)
        graph_text = fetch_glucose_data(login_details)
        libre_data = LibreResponse.model_validate_json(graph_text)
        return libre_data.model_dump_json(indent=2)
    except Exception as e:
        return f"Error fetching Libre glucose data: {str(e)}"


def get_garmin_activities() -> str:
    """Fetch recent Garmin activities for the last week."""
    try:
        service = GarminService()
        activities = service.get_activities_last_week()
        return json.dumps(activities, indent=2, default=str)
    except Exception as e:
        return f"Error fetching Garmin activities: {str(e)}"


def get_calendar_events(
    days_back: int = 0,
    days_forward: int = 7,
    max_results: int = 250,
    calendar_id: str = None
) -> str:
    """
    Fetch all-day and multi-day calendar events for a given time window.
    
    Args:
        days_back: Number of days to search backwards (must be non-negative).
        days_forward: Number of days to search forwards (must be non-negative).
        max_results: Maximum number of raw events to retrieve from the Google API before filtering.
        calendar_id: Optional Google Calendar ID. Defaults to the configured main calendar.
    """
    if days_back < 0 or days_forward < 0:
        return "Error: days_back and days_forward parameters must be non-negative integers."
        
    try:
        service = CalendarService()
        events = service.get_upcoming_events(
            days_back=days_back,
            days_forward=days_forward,
            max_results=max_results,
            calendar_id=calendar_id
        )
        return json.dumps(events, indent=2)
    except Exception as e:
        return f"Error fetching calendar events: {str(e)}"


