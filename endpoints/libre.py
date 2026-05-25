from fastapi import APIRouter, HTTPException, Depends
from services import LibreService
from models import LibreResponse

router = APIRouter()

def get_libre_service() -> LibreService:
    return LibreService()

@router.get("/")
def get_libre_data(service: LibreService = Depends(get_libre_service)):
    """HTTP FastAPI route to get CGM glucose data from LibreView."""
    try:
        libre_data = service.get_glucose_data()
        return libre_data
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
