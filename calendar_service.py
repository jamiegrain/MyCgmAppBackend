import os
import logging
from datetime import datetime, timezone, timedelta
import google.auth
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class CalendarService:
    """
    A service class to interact with the Google Calendar API using
    Google Application Default Credentials (ADC).
    """
    def __init__(self):
        # We only need read access for this test
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
            # Loads local credentials (from ADC login or GOOGLE_APPLICATION_CREDENTIALS)
            # or Google Cloud environment credentials when deployed.
            self.creds, project = google.auth.default(scopes=self.scopes)
            self.service = build('calendar', 'v3', credentials=self.creds)
            logger.info("Successfully initialized Google Calendar service.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar client: {e}")
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
            logger.error(f"Failed to fetch events from Calendar API (ID: {calendar_id}): {e}")
            raise Exception(f"Failed to fetch calendar events from Google API: {e}")

    def _is_full_or_multi_day(self, event: dict) -> bool:
        """
        Determines whether a calendar event is an all-day or multi-day event.
        """
        start_obj = event.get('start', {})
        end_obj = event.get('end', {})

        # Case 1: Standard All-Day event (defined by 'date' key instead of 'dateTime')
        if 'date' in start_obj:
            return True

        # Case 2: Timed event that spans across different calendar days or spans >= 24 hours
        start_dt_str = start_obj.get('dateTime')
        end_dt_str = end_obj.get('dateTime')
        if start_dt_str and end_dt_str:
            try:
                # Replace 'Z' suffix with standard '+00:00' to support older python versions
                s_dt = datetime.fromisoformat(start_dt_str.replace('Z', '+00:00'))
                e_dt = datetime.fromisoformat(end_dt_str.replace('Z', '+00:00'))
                
                # Check if starts on one day and ends on a different date, or spans a full day's duration
                if s_dt.date() != e_dt.date() or (e_dt - s_dt) >= timedelta(days=1):
                    return True
            except Exception as parse_err:
                logger.warning(f"Error parsing date times for event {event.get('id', 'unknown')}: {parse_err}")
                
        return False

    def _format_event(self, event: dict) -> dict:
        """
        Extracts and formats key event data into a clean structure for the endpoint response.
        """
        start_obj = event.get('start', {})
        end_obj = event.get('end', {})
        
        start = start_obj.get('dateTime') or start_obj.get('date')
        end = end_obj.get('dateTime') or end_obj.get('date')
        
        return {
            "id": event.get("id"),
            "summary": event.get("summary", "(No Title)"),
            "description": event.get("description", ""),
            "start": start,
            "end": end,
            "location": event.get("location", ""),
            "isAllDay": 'date' in start_obj
        }

    def get_upcoming_events(
        self, 
        days_back: int = 0, 
        days_forward: int = 7, 
        max_results: int = 250, 
        calendar_id: str = None
    ) -> list[dict]:
        """
        High-level orchestrator method to get, filter, and format full-day/multi-day events.
        """
        if days_back < 0 or days_forward < 0:
            raise ValueError("days_back and days_forward parameters must be non-negative integers.")

        target_calendar_id = calendar_id or self.calendar_id
        if not target_calendar_id:
            raise ValueError("Calendar ID is not set. Specify it via parameters or GOOGLE_CALENDAR_ID in .env.")

        # 1. Calculate the timeframe
        time_min, time_max = self._calculate_time_window(days_back, days_forward)
        
        logger.info(
            f"Fetching events between {time_min} and {time_max} "
            f"for calendar: {target_calendar_id}"
        )

        # 2. Fetch raw events
        raw_events = self._fetch_raw_events(
            calendar_id=target_calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results
        )

        # 3. Filter and format events
        filtered_events = [
            self._format_event(event)
            for event in raw_events
            if self._is_full_or_multi_day(event)
        ]

        return filtered_events
