import os
import logging
from datetime import datetime, timezone
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
        # Default fallback to the provided decoded calendar ID
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
        self.creds = None
        self.service = None

    def _initialize_service(self):
        if not self.service:
            try:
                # google.auth.default() automatically loads credentials:
                # 1. GOOGLE_APPLICATION_CREDENTIALS env var (path to a service account JSON file)
                # 2. Inside Google Cloud (Cloud Run, Cloud Functions, GCE), it uses the attached Service Account
                # 3. Locally, if run: gcloud auth application-default login
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

    def get_upcoming_events(self, max_results: int = 10, calendar_id: str = None) -> list:
        """
        Retrieves upcoming events from the specified calendar.
        """
        self._initialize_service()
        target_calendar_id = calendar_id or self.calendar_id
        
        # Format "now" in RFC3339 format with Z timezone offset
        now = datetime.now(timezone.utc).isoformat()
        logger.info(f"Fetching up to {max_results} upcoming events from calendar: {target_calendar_id}")
        
        try:
            events_result = self.service.events().list(
                calendarId=target_calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Formulate a simplified structure for the test endpoint output
            formatted_events = []
            for event in events:
                start = event.get('start', {}).get('dateTime') or event.get('start', {}).get('date')
                end = event.get('end', {}).get('dateTime') or event.get('end', {}).get('date')
                formatted_events.append({
                    "id": event.get("id"),
                    "summary": event.get("summary", "(No Title)"),
                    "description": event.get("description", ""),
                    "start": start,
                    "end": end,
                    "location": event.get("location", "")
                })
                
            return formatted_events
        except Exception as e:
            logger.error(f"Error fetching events from calendar {target_calendar_id}: {e}")
            raise Exception(f"Failed to fetch calendar events: {e}")
