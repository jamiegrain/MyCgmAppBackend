import os
import json
import logging
from fastmcp import FastMCP
from fastapi import FastAPI

# Import existing backend logic
from main import login, fetch_glucose_data
from models import LibreResponse
from garmin_service import GarminService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP Server
mcp = FastMCP(
    "MyCgmApp MCP Server"
)

@mcp.tool()
def get_libre_glucose_data() -> str:
    """Fetch current CGM glucose data from LibreView."""
    username = os.environ.get("LIBRE_USER")
    password = os.environ.get("LIBRE_PASS")

    if not username or not password:
        return "Error: Missing Libre credentials in environment variables."

    try:
        login_details = login(username, password)
        graph_text = fetch_glucose_data(login_details)
        libre_data = LibreResponse.model_validate_json(graph_text)
        return libre_data.model_dump_json(indent=2)
    except Exception as e:
        return f"Error fetching Libre glucose data: {str(e)}"

@mcp.tool()
def get_garmin_activities() -> str:
    """Fetch recent Garmin activities for the last week."""
    try:
        service = GarminService()
        activities = service.get_activities_last_week()
        return json.dumps(activities, indent=2, default=str)
    except Exception as e:
        return f"Error fetching Garmin activities: {str(e)}"

# FastMCP v3.3.1 provides an ASGI application via http_app()
# that handles streamable-http connections at the root.
mcp_sub_app = mcp.http_app(path="/", transport="streamable-http")

# Pass the lifespan of the FastMCP sub-app to the parent FastAPI application
# so that background task groups are properly initialized.
app = FastAPI(lifespan=mcp_sub_app.lifespan)

# Mount it so your endpoints are clearly mapped to the root
app.mount("/", mcp_sub_app)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Production FastMCP Server via Uvicorn on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
