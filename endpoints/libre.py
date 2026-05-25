from fastapi import APIRouter, HTTPException, Depends
from services import LibreService

router = APIRouter()

def get_libre_service() -> LibreService:
    return LibreService()

@router.get("/")
def get_libre_data(service: LibreService = Depends(get_libre_service)):
    """HTTP FastAPI route to get CGM glucose data from LibreView."""
    try:
        libre_data = service.fetch_and_validate_glucose_data()
        return libre_data
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/libre/upload")
def upload_libre_to_bigquery(service: LibreService = Depends(get_libre_service)):
    """Trigger endpoint to push the last twelve hours of CGM data into BigQuery with deduplication."""
    try:
        rows_uploaded = service.upload_recent_to_bigquery(hours=12)
        return {
            "success": True,
            "records_uploaded": rows_uploaded,
            "message": f"Successfully processed and appended {rows_uploaded} new records to BigQuery."
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
