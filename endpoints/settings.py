from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from services import GarminService

router = APIRouter()

class ActivityStatusRequest(BaseModel):
    isActivityInProgress: bool

def get_garmin_service() -> GarminService:
    return GarminService()

@router.get("/settings/activity")
def get_activity(service: GarminService = Depends(get_garmin_service)):
    """Get the current physical activity in progress status."""
    try:
        status = service.get_activity_status()
        return {"isActivityInProgress": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/settings/activity")
def set_activity(request: ActivityStatusRequest, service: GarminService = Depends(get_garmin_service)):
    """Set the physical activity in progress status."""
    try:
        service.set_activity_status(request.isActivityInProgress)
        return {"success": True, "isActivityInProgress": request.isActivityInProgress}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
