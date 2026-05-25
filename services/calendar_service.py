import os
import logging
from datetime import datetime, timezone, timedelta
import google.auth
from googleapiclient.discovery import build

from models import CalendarEvent

_logger = logging.getLogger(__name__)

class CalendarService:
    """
    A service class to interact with the Google Calendar API using
    Google Application Default Credentials (ADC).
    """
    def __init__(self):
        self.scopes = ['https://www.googleapis.com/auth/calendar.readonly']
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
        self.creds = None
        self.service = None

    def _initialize_service(self):
        """
        Loads Google Application Default Credentials (ADC) and builds the calendar service.
        """
        if self.service:
            return

        try:
            self.creds, project = google.auth.default(scopes=self.scopes)
            self.service = build('calendar', 'v3', credentials=self.creds)
            _logger.info("Successfully initialized Google Calendar service.")
        except Exception as e:
            _logger.error(f"Failed to initialize Google Calendar client: {e}")
            raise RuntimeError(
                "Google Application Default Credentials (ADC) are not configured. "
                "If testing locally, please run 'gcloud auth application-default login' or "
                "set the GOOGLE_APPLICATION_CREDENTIALS environment variable to the path of your "
                "Service Account JSON key file. Details: " + str(e)
            )

    def _calculate_time_window(self, days_back: int, days_forward: int) -> tuple[str, str]:
        """
        Calculates the start and end boundary times in ISO format (RFC3339).
        """
        now = datetime.now(timezone.utc)
        time_min = (now - timedelta(days=days_back)).isoformat()
        time_max = (now + timedelta(days=days_forward)).isoformat()
        return time_min, time_max

    def _fetch_raw_events(self, calendar_id: str, time_min: str, time_max: str, max_results: int) -> list:
        """
        Calls the Google Calendar API directly to list events in the given time window.
        """
        self._initialize_service()
        try:
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            return events_result.get('items', [])
        except Exception as e:
            _logger.error(f"Failed to fetch events from Calendar API (ID: {calendar_id}): {e}")
            raise Exception(f"Failed to fetch calendar events from Google API: {e}")

    def _is_full_or_multi_day(self, event: dict) -> bool:
        """
        Determines whether a calendar event is an all-day or multi-day event.
        """
        start_obj = event.get('start', {})
        end_obj = event.get('end', {})

        if 'date' in start_obj:
            return True

        start_dt_str = start_obj.get('dateTime')
        end_dt_str = end_obj.get('dateTime')
        if start_dt_str and end_dt_str:
            try:
                s_dt = datetime.fromisoformat(start_dt_str.replace('Z', '+00:00'))
                e_dt = datetime.fromisoformat(end_dt_str.replace('Z', '+00:00'))
                if s_dt.date() != e_dt.date() or (e_dt - s_dt) >= timedelta(days=1):
                    return True
            except Exception as parse_err:
                _logger.warning(f"Error parsing date times for event {event.get('id', 'unknown')}: {parse_err}")
                
        return False

    def _format_event(self, event: dict) -> CalendarEvent:
        """
        Extracts and formats key event data into a CalendarEvent Pydantic model.
        """
        start_obj = event.get('start', {})
        end_obj = event.get('end', {})
        
        start = start_obj.get('dateTime') or start_obj.get('date')
        end = end_obj.get('dateTime') or end_obj.get('date')
        
        # Validates through Pydantic
        return CalendarEvent(
            id=event.get("id"),
            summary=event.get("summary", "(No Title)"),
            description=event.get("description") or "",
            start=start,
            end=end,
            location=event.get("location") or "",
            isAllDay='date' in start_obj
        )

    def get_upcoming_events(
        self, 
        days_back: int = 0, 
        days_forward: int = 7, 
        max_results: int = 250, 
        calendar_id: str = None
    ) -> list[CalendarEvent]:
        """
        High-level orchestrator method to get, filter, and format full-day/multi-day events.
        """
        if days_back < 0 or days_forward < 0:
            raise ValueError("days_back and days_forward parameters must be non-negative integers.")

        target_calendar_id = calendar_id or self.calendar_id
        if not target_calendar_id:
            raise ValueError("Calendar ID is not set. Specify it via parameters or GOOGLE_CALENDAR_ID in .env.")

        time_min, time_max = self._calculate_time_window(days_back, days_forward)
        
        _logger.info(
            f"Fetching events between {time_min} and {time_max} "
            f"for calendar: {target_calendar_id}"
        )

        raw_events = self._fetch_raw_events(
            calendar_id=target_calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results
        )

        filtered_events = [
            self._format_event(event)
            for event in raw_events
            if self._is_full_or_multi_day(event)
        ]

        return filtered_events

    def get_calendar_events(
        self,
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
            events = self.get_upcoming_events(
                days_back=days_back,
                days_forward=days_forward,
                max_results=max_results,
                calendar_id=calendar_id
            )
            import json
            return json.dumps([event.model_dump() for event in events], indent=2)
        except Exception as e:
            _logger.error(f"Error fetching calendar events for agent: {e}")
            return f"Error fetching calendar events: {str(e)}"

