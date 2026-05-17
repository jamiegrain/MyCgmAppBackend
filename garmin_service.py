import os
import logging
from datetime import date
from pathlib import Path
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

logger = logging.getLogger(__name__)

class GarminService:
    def __init__(self, email=None, password=None, token_path=None):
        self.email = email or os.getenv("GARMIN_USER")
        self.password = password or os.getenv("GARMIN_PASS")
        self.token_path = token_path or os.getenv("GARMIN_TOKEN_PATH", "~/.garminconnect")
        self.garmin = None

    def login(self):
        """Initialise Garmin API, restoring saved tokens or logging in fresh."""
        token_path = str(Path(self.token_path).expanduser())
        
        try:
            # Try to restore saved tokens
            self.garmin = Garmin()
            self.garmin.login(token_path)
            logger.info("Logged in to Garmin using saved tokens.")
            return True
        except (GarminConnectAuthenticationError, GarminConnectConnectionError):
            logger.info("No valid Garmin tokens found or expired — attempting fresh login.")
        except Exception as e:
            logger.error(f"Unexpected error during token login: {e}")

        # Fresh credential login
        if not self.email or not self.password:
            raise ValueError("Garmin credentials (email/password) not provided and not found in environment.")

        try:
            self.garmin = Garmin(email=self.email, password=self.password)
            self.garmin.login(token_path)
            logger.info(f"Garmin login successful. Tokens saved to: {token_path}")
            return True
        except GarminConnectAuthenticationError as e:
            logger.error(f"Garmin authentication failed: {e}")
            raise
        except GarminConnectTooManyRequestsError as e:
            logger.error(f"Garmin rate limit exceeded: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Garmin login: {e}")
            raise

    def get_activities_last_30_days(self):
        """Fetch activities for the last 30 days."""
        if not self.garmin:
            self.login()

        end_date = date.today()
        start_date = date(2026,1,1)
        
        logger.info(f"Fetching Garmin activities from {start_date} to {end_date}")
        
        try:
            activities = self.garmin.get_activities_by_date(
                start_date.isoformat(), 
                end_date.isoformat()
            )
            return activities
        except Exception as e:
            logger.error(f"Failed to fetch Garmin activities: {e}")
            raise
