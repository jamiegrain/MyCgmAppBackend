from fastapi import APIRouter, HTTPException, Depends
from services import CalendarService

router = APIRouter()

def get_calendar_service() -> CalendarService:
    return CalendarService()

@router.get("/calendar/events")
def get_calendar_events(
    days_back: int = 0,
    days_forward: int = 7,
    max_results: int = 250,
    service: CalendarService = Depends(get_calendar_service)
):
    """Fetch all-day and multi-day calendar events for a given time window."""
    try:
        events = service.get_upcoming_events(
            days_back=days_back,
            days_forward=days_forward,
            max_results=max_results
        )
        return events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
