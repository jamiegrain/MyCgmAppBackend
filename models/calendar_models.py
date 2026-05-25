from pydantic import BaseModel
from typing import Optional

class CalendarEvent(BaseModel):
    id: Optional[str] = None
    summary: str
    description: Optional[str] = ""
    start: str
    end: str
    location: Optional[str] = ""
    isAllDay: bool
