from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from endpoints import (
    libre_router,
    garmin_router,
    calendar_router,
    settings_router,
    vertex_router
)

app = FastAPI(title="MyCGM App Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(libre_router)
app.include_router(garmin_router)
app.include_router(calendar_router)
app.include_router(settings_router)
app.include_router(vertex_router)
