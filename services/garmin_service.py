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

    def get_garmin_daily_steps(self, days: int = 7) -> str:
        """
        Fetch daily step counts and active/resting distance metrics for the last N days.
        Use this tool when the user asks questions about their daily step counts, passive physical activity levels, or general movement trends.
        """
        if not self.garmin:
            _logger.info("Garmin client not authenticated. Authenticating now...")
            self.login()

        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        _logger.info(f"Querying Garmin daily steps from {start_date} to {end_date}")
        
        try:
            steps_data = self.garmin.get_daily_steps(
                start_date.isoformat(),
                end_date.isoformat()
            )
            
            if not steps_data:
                return f"No daily step data found from {start_date} to {end_date}."
                
            lines = [
                f"🚶 **Garmin Daily Steps & Distance (Last {days} Days)**\n",
                "| Date | Steps | Distance (km) | Target Steps | % of Goal |",
                "| :---: | :---: | :---: | :---: | :---: |"
            ]
            
            for entry in steps_data:
                dt_str = entry.get("calendarDate", "N/A")
                steps = entry.get("totalSteps", 0)
                dist_m = entry.get("totalDistance", 0)
                dist_km = dist_m / 1000.0 if dist_m else 0.0
                goal = entry.get("stepGoal", 10000)
                pct = (steps / goal * 100) if goal else 0
                lines.append(f"| {dt_str} | {steps:,} | {dist_km:.2f} | {goal:,} | {pct:.1f}% |")
                
            return "\n".join(lines)
        except Exception as e:
            _logger.error(f"Failed to fetch Garmin daily steps: {e}")
            return f"Error fetching Garmin daily steps: {str(e)}"

    def get_garmin_daily_stress(self, days: int = 5) -> str:
        """
        Fetch daily stress statistics (average stress score, time in high/medium stress states) for the last N days.
        Use this tool when the user asks questions like: 'Have I been stressed lately?' or 'Could stress be driving my blood sugar spikes?'
        """
        if not self.garmin:
            _logger.info("Garmin client not authenticated. Authenticating now...")
            self.login()

        end_date = date.today()
        lines = [
            f"🧘 **Garmin Daily Stress Summary (Last {days} Days)**\n",
            "| Date | Avg Stress Score | Stress State | Rest Time | Medium/High Stress Time |",
            "| :---: | :---: | :--- | :---: | :---: |"
        ]
        
        found_data = False
        for i in range(days):
            target_date = end_date - timedelta(days=i)
            date_str = target_date.isoformat()
            
            try:
                stress_data = self.garmin.get_all_day_stress(date_str)
                if not stress_data or "avgStressLevel" not in stress_data:
                    continue
                
                avg_stress = stress_data.get("avgStressLevel", 0)
                if avg_stress <= 25:
                    state = "🟢 Rest/Low"
                elif avg_stress <= 50:
                    state = "🟡 Mild Stress"
                elif avg_stress <= 75:
                    state = "orange Medium Stress"
                else:
                    state = "🔴 High Stress"
                    
                rest_sec = stress_data.get("restStressDurationInSeconds", 0)
                med_sec = stress_data.get("mediumStressDurationInSeconds", 0)
                high_sec = stress_data.get("highStressDurationInSeconds", 0)
                
                rest_hours = rest_sec / 3600.0 if rest_sec else 0.0
                stress_hours = (med_sec + high_sec) / 3600.0 if (med_sec or high_sec) else 0.0
                
                lines.append(f"| {date_str} | {avg_stress} | {state} | {rest_hours:.1f} hrs | {stress_hours:.1f} hrs |")
                found_data = True
            except Exception as e:
                _logger.warning(f"Failed to fetch stress for {date_str}: {e}")
                continue
                
        if not found_data:
            return f"No Garmin stress data found for the requested period."
            
        return "\n".join(lines)

    def get_garmin_daily_sleep_and_recovery(self, days: int = 5) -> str:
        """
        Fetch daily sleep quality scores, sleep phase durations, and overnight Heart Rate Variability (HRV) recovery metrics for the last N days.
        Use this tool when the user asks questions about sleep duration, sleep quality, or autonomic recovery (HRV status).
        """
        if not self.garmin:
            _logger.info("Garmin client not authenticated. Authenticating now...")
            self.login()

        end_date = date.today()
        lines = [
            f"💤 **Garmin Sleep & HRV Recovery (Last {days} Days)**\n",
            "| Date | Sleep Duration | Sleep Score | Quality | Overnight Avg HRV (ms) | HRV Status |",
            "| :---: | :---: | :---: | :--- | :---: | :--- |"
        ]
        
        found_data = False
        for i in range(days):
            target_date = end_date - timedelta(days=i)
            date_str = target_date.isoformat()
            
            try:
                sleep = self.garmin.get_sleep_data(date_str)
                sleep_summary = sleep.get("dailySleepDTO", {}) if sleep else {}
                
                hrv = None
                try:
                    hrv = self.garmin.get_hrv_data(date_str)
                except Exception:
                    pass
                
                if not sleep_summary:
                    continue
                    
                dur_sec = sleep_summary.get("sleepTimeSeconds", 0)
                dur_hrs = dur_sec / 3600.0 if dur_sec else 0.0
                score = sleep_summary.get("sleepScore", "N/A")
                
                raw_quality = sleep_summary.get("sleepQualityType", "N/A")
                quality = "N/A"
                if raw_quality == "POOR":
                    quality = "🔴 Poor"
                elif raw_quality == "FAIR":
                    quality = "🟡 Fair"
                elif raw_quality == "GOOD":
                    quality = "🟢 Good"
                elif raw_quality == "EXCELLENT":
                    quality = "✨ Excellent"
                else:
                    quality = str(raw_quality).capitalize()
                
                hrv_avg = "N/A"
                hrv_status = "N/A"
                if hrv and isinstance(hrv, dict):
                    hrv_summary = hrv.get("hrvSummary", {})
                    if hrv_summary:
                        hrv_avg = hrv_summary.get("lastNightAvg", "N/A")
                        raw_status = hrv_summary.get("status", "N/A")
                        if raw_status == "BALANCED":
                            hrv_status = "🟢 Balanced"
                        elif raw_status == "UNBALANCED":
                            hrv_status = "🟡 Unbalanced"
                        else:
                            hrv_status = str(raw_status).capitalize()
                
                lines.append(f"| {date_str} | {dur_hrs:.1f} hrs | {score} | {quality} | {hrv_avg} | {hrv_status} |")
                found_data = True
            except Exception as e:
                _logger.warning(f"Failed to fetch sleep/HRV for {date_str}: {e}")
                continue
                
        if not found_data:
            return "No Garmin sleep or HRV data found for the requested period."
            
        return "\n".join(lines)

