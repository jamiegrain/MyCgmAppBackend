import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.adk.cli.fast_api import get_fast_api_app

from endpoints import (
    libre_router,
    garmin_router,
    calendar_router,
    settings_router,
    vertex_router
)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(CURRENT_DIR, "agents")

# Module-level environment constant (True if running locally on your Mac, False if deployed on Cloud Run)
IS_LOCAL = "K_SERVICE" not in os.environ

# Automatically determine session persistence based on environment:
default_db_url = f"sqlite:///{os.path.join(BASE_DIR, 'sessions.db')}" if IS_LOCAL else "firestore://"
SESSION_DB_URL = os.getenv("SESSION_DB_URL", default_db_url)

app: FastAPI = get_fast_api_app(
    agents_dir=BASE_DIR,
    session_service_uri=SESSION_DB_URL,
    allow_origins=["*"],  # In production, restrict this
    web=IS_LOCAL,  # Enable the ADK Web UI only for local development
)

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
