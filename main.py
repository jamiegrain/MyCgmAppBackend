import os

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from endpoints import (
    libre_router,
    garmin_router,
    calendar_router,
    settings_router,
    vertex_router
)

API_KEY_HEADER = APIKeyHeader(name="X-Secret-Key", auto_error=False)

async def verify_secret_key(secret_key: str = Security(API_KEY_HEADER)):
    if secret_key != os.environ.get("APP_SECRET"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized"
        )

app = FastAPI(title="MyCGM App Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers with authentication dependency
app.include_router(libre_router, dependencies=[Depends(verify_secret_key)])
app.include_router(garmin_router, dependencies=[Depends(verify_secret_key)])
app.include_router(calendar_router, dependencies=[Depends(verify_secret_key)])
app.include_router(settings_router, dependencies=[Depends(verify_secret_key)])
app.include_router(vertex_router, dependencies=[Depends(verify_secret_key)])

