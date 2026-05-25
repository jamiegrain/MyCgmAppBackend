from fastapi import APIRouter, HTTPException, Depends
from services import GarminService

router = APIRouter()

def get_garmin_service() -> GarminService:
    return GarminService()

@router.get("/garmin/activities")
def get_garmin_activities(service: GarminService = Depends(get_garmin_service)):
    """Fetch Garmin activities for the last week."""
    try:
        activities = service.get_activities_last_week()
        return activities
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
