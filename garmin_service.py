from datetime import timedelta
import os
import logging
from datetime import date
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

# Import the MongoDB token helpers
from settings.settings import get_garmin_tokens, save_garmin_tokens

logger = logging.getLogger(__name__)

class GarminService:
    def __init__(self, email=None, password=None):
        self.email = email or os.getenv("GARMIN_USER")
        self.password = password or os.getenv("GARMIN_PASS")
        self.garmin = None

    def login(self):
        """Initialise Garmin API, restoring saved tokens from DB or logging in fresh."""
        db_tokens = None
        try:
            db_tokens = get_garmin_tokens()
        except Exception as e:
            logger.error(f"Failed to fetch Garmin tokens from settings DB: {e}")

        if db_tokens:
            try:
                # Try to restore saved tokens from DB string
                self.garmin = Garmin()
                self.garmin.login(db_tokens)
                logger.info("Logged in to Garmin using tokens loaded from DB.")
                
                # Check if session was updated/refreshed during login and save back if so
                try:
                    updated_tokens = self.garmin.dumps()
                    if updated_tokens != db_tokens:
                        save_garmin_tokens(updated_tokens)
                        logger.info("Garmin tokens refreshed and updated in settings DB.")
                except Exception as e:
                    logger.error(f"Failed to dump/save refreshed Garmin tokens: {e}")
                    
                return True
            except (GarminConnectAuthenticationError, GarminConnectConnectionError) as e:
                logger.info(f"Garmin tokens in DB are expired or invalid ({e}) — attempting fresh login.")
            except Exception as e:
                logger.error(f"Unexpected error during DB token login: {e}")

        # Fresh credential login
        if not self.email or not self.password:
            raise ValueError("Garmin credentials (email/password) not provided and not found in environment.")

        try:
            self.garmin = Garmin(email=self.email, password=self.password)
            self.garmin.login()
            logger.info("Garmin login successful using fresh credentials.")
            
            # Save the fresh tokens to settings DB
            try:
                token_str = self.garmin.dumps()
                save_garmin_tokens(token_str)
                logger.info("Garmin tokens successfully saved to settings DB.")
            except Exception as e:
                logger.error(f"Failed to save fresh Garmin tokens to DB: {e}")
                
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

    def get_activities_last_week(self):
        """Fetch activities for the last week."""
        if not self.garmin:
            self.login()

        end_date = date.today()
        start_date = date.today() - timedelta(days=7)
        
        logger.info(f"Fetching Garmin activities from {start_date} to {end_date}")
        
        try:
            activities = self.garmin.get_activities_by_date(
                start_date.isoformat(), 
                end_date.isoformat()
            )
            
            # Save any auto-rotated/refreshed tokens back to DB
            try:
                current_tokens = self.garmin.dumps()
                save_garmin_tokens(current_tokens)
            except Exception as e:
                logger.error(f"Failed to save possibly refreshed tokens to settings DB: {e}")
                
            return activities
        except Exception as e:
            logger.error(f"Failed to fetch Garmin activities: {e}")
            raise
