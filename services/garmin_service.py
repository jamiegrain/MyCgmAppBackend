from datetime import timedelta, date
import os
import logging
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from services.settings_service import SettingsService

_logger = logging.getLogger(__name__)

class GarminService:
    def __init__(self, email=None, password=None):
        self.email = email or os.getenv("GARMIN_USER")
        self.password = password or os.getenv("GARMIN_PASS")
        self.garmin = None
        self.settings_service = SettingsService()
        _logger.info("Initializing GarminService with configured SettingsService.")

    def get_activity_status(self) -> bool:
        """Fetch activity in progress status from database settings."""
        _logger.info("Fetching Garmin physical activity status from database...")
        status = self.settings_service.get_activity_status()
        _logger.info(f"Retrieved Garmin physical activity status: isActivityInProgress = {status}")
        return status

    def set_activity_status(self, status: bool):
        """Update activity in progress status in database settings."""
        _logger.info(f"Setting Garmin physical activity status to: isActivityInProgress = {status}")
        self.settings_service.set_activity_status(status)
        _logger.info("Garmin physical activity status updated successfully.")

    def login(self):
        """Initialise Garmin API, restoring saved tokens from DB or logging in fresh."""
        _logger.info("Initiating Garmin Service login sequence...")
        db_tokens = None
        try:
            _logger.info("Checking for cached Garmin authentication tokens in settings store...")
            db_tokens = self.settings_service.get_garmin_tokens()
        except Exception as e:
            _logger.error(f"Failed to fetch Garmin tokens from settings DB: {e}")

        if db_tokens:
            try:
                _logger.info("Cached Garmin tokens found in settings store. Attempting token-based authentication restore...")
                self.garmin = Garmin()
                self.garmin.login(db_tokens)
                _logger.info("Garmin token-based authentication restore successful.")
                
                # Check if session was updated/refreshed during login and save back if so
                try:
                    updated_tokens = self.garmin.client.dumps()
                    if updated_tokens != db_tokens:
                        _logger.info("Garmin tokens refreshed during session validation. Saving updated tokens to DB...")
                        self.settings_service.save_garmin_tokens(updated_tokens)
                        _logger.info("Refreshed Garmin tokens saved successfully.")
                except Exception as e:
                    _logger.error(f"Failed to dump/save refreshed Garmin tokens: {e}")
                    
                return True
            except (GarminConnectAuthenticationError, GarminConnectConnectionError) as e:
                _logger.warning(f"Garmin tokens in DB are expired or invalid ({e}) — fallback to fresh login.")
            except Exception as e:
                _logger.error(f"Unexpected error during token restoration: {e}")

        # Fresh credential login
        _logger.info("Performing fresh credential-based login to Garmin Connect...")
        if not self.email or not self.password:
            _logger.error("Garmin credentials (email/password) not provided and not found in environment.")
            raise ValueError("Garmin credentials (email/password) not provided and not found in environment.")

        try:
            self.garmin = Garmin(email=self.email, password=self.password)
            self.garmin.login()
            _logger.info("Garmin Connect credential authentication successful.")
            
            # Save the fresh tokens to settings DB
            try:
                _logger.info("Serializing and caching new Garmin authentication tokens...")
                token_str = self.garmin.client.dumps()
                self.settings_service.save_garmin_tokens(token_str)
                _logger.info("New Garmin tokens successfully cached in settings store.")
            except Exception as e:
                _logger.error(f"Failed to save fresh Garmin tokens to DB: {e}")
                
            return True
        except GarminConnectAuthenticationError as e:
            _logger.error(f"Garmin authentication credentials rejected: {e}")
            raise
        except GarminConnectTooManyRequestsError as e:
            _logger.error(f"Garmin rate limits exceeded for fresh logins: {e}")
            raise
        except Exception as e:
            _logger.error(f"Unexpected error during Garmin Connect login flow: {e}")
            raise

    def get_activities_last_week(self):
        """Fetch activities for the last week."""
        _logger.info("Requesting Garmin activity list for the past week...")
        if not self.garmin:
            _logger.info("Garmin client not authenticated. Authenticating now...")
            self.login()

        end_date = date.today()
        start_date = date.today() - timedelta(days=7)
        
        _logger.info(f"Querying Garmin activities from {start_date} to {end_date}")
        
        try:
            activities = self.garmin.get_activities_by_date(
                start_date.isoformat(), 
                end_date.isoformat()
            )
            _logger.info(f"Successfully retrieved {len(activities)} activities from Garmin Connect API.")
            
            # Save any auto-rotated/refreshed tokens back to DB
            try:
                _logger.info("Checking if Garmin Connect auto-rotated session tokens during query...")
                current_tokens = self.garmin.client.dumps()
                self.settings_service.save_garmin_tokens(current_tokens)
                _logger.info("Rotated Garmin session tokens stored successfully.")
            except Exception as e:
                _logger.error(f"Failed to save possibly refreshed tokens to settings DB: {e}")
                
            return activities
        except Exception as e:
            _logger.error(f"Failed to query activities from Garmin Connect API: {e}")
            raise

    def get_garmin_activities(self) -> str:
        """Fetch recent Garmin activities for the last week."""
        try:
            activities = self.get_activities_last_week()
            import json
            return json.dumps(activities, indent=2, default=str)
        except Exception as e:
            _logger.error(f"Error fetching Garmin activities for agent: {e}")
            return f"Error fetching Garmin activities: {str(e)}"

