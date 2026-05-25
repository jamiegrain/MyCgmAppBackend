import os
import hashlib
import requests
import logging
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional
from models import LibreResponse

_logger = logging.getLogger(__name__)

class LibreService:
    BASE_URL = "https://api-eu2.libreview.io/"
    HEADERS = {
        "accept-encoding": "gzip",
        "cache-control": "no-cache",
        "connection": "Keep-Alive",
        "product": "llu.android",
        "version": "4.16.0",
        "priority": "u=1, i",
    }

    def login(self, username, password) -> dict:
        _logger.info(f"Attempting to login to LibreView for user '{username}'")
        url = f"{self.BASE_URL}llu/auth/login"
        payload = {"email": username, "password": password}
        
        try:
            response = requests.post(url, headers=self.HEADERS, json=payload)
            if not response.ok:
                _logger.error(f"Failed to login to LibreView. Status code: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to login to LibreView: {response.text}")
            
            data = response.json()
            user_id = data.get("data", {}).get("user", {}).get("id")
            token = data.get("data", {}).get("authTicket", {}).get("token")
            
            if not user_id or not token:
                _logger.error("Invalid login response format from LibreView API: user_id or token is missing.")
                raise Exception("Invalid login response format")

            account_id = hashlib.sha256(user_id.encode('utf-8')).hexdigest().lower()
            _logger.info("Successfully logged in to LibreView and generated credentials.")
            
            return {
                "patientId": user_id,
                "token": token,
                "accountId": account_id
            }
        except Exception as e:
            _logger.error(f"Exception during LibreView login flow: {e}")
            raise

    def fetch_glucose_data(self, login_details: dict) -> str:
        patient_id = login_details.get("patientId")
        _logger.info(f"Fetching glucose graph data for patient ID: '{patient_id}'")
        
        url = f"{self.BASE_URL}llu/connections/{patient_id}/graph"
        req_headers = self.HEADERS.copy()
        req_headers.update({
            "Authorization": f"Bearer {login_details['token']}",
            "account-id": login_details['accountId']
        })
        
        try:
            response = requests.get(url, headers=req_headers)
            if not response.ok:
                _logger.error(f"Failed to fetch graph data for patient {patient_id}. Status: {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to fetch graph data: {response.text}")
                
            _logger.info(f"Successfully retrieved raw glucose data stream for patient {patient_id}.")
            return response.text
        except Exception as e:
            _logger.error(f"Exception during LibreView glucose data fetch: {e}")
            raise

    def fetch_and_validate_glucose_data(self) -> LibreResponse:
        _logger.info("Initiating high-level LibreView glucose data retrieval...")
        username = os.environ.get("LIBRE_USER")
        password = os.environ.get("LIBRE_PASS")

        if not username or not password:
            _logger.error("Missing environment variables LIBRE_USER or LIBRE_PASS.")
            raise ValueError("Missing Libre credentials in environment variables (LIBRE_USER, LIBRE_PASS).")

        try:
            login_details = self.login(username, password)
            graph_text = self.fetch_glucose_data(login_details)
            
            _logger.info("Parsing and validating raw glucose data against LibreResponse Pydantic model...")
            libre_data = LibreResponse.model_validate_json(graph_text)
            
            _logger.info("LibreView glucose data retrieval, validation, and serialization completed successfully.")
            return libre_data
        except Exception as e:
            _logger.error(f"LibreView high-level glucose data fetch failed: {e}")
            raise

    def get_libre_glucose_data(self) -> str:
        """Fetch current CGM glucose data from LibreView."""
        try:
            libre_data = self.fetch_and_validate_glucose_data()
            return libre_data.model_dump_json(indent=2)
        except Exception as e:
            _logger.error(f"Error fetching Libre glucose data for agent: {e}")
            return f"Error fetching Libre glucose data: {str(e)}"

    def upload_recent_to_bigquery(self, hours: int = 12, dataset_id: str = "my_cgm_dataset", table_id: str = "glucose_records") -> int:
        """Fetch latest glucose data from LibreView, filter for recent hours, and upload new delta records to BigQuery."""
        _logger.info(f"Running scheduled recent upload to BigQuery (last {hours} hours)...")
        libre_data = self.fetch_and_validate_glucose_data()
        
        records = []
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours)
        
        for entry in libre_data.data.graphData:
            # Parse timestamp
            ts = pd.to_datetime(entry.Timestamp)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            else:
                ts = ts.tz_convert("UTC")
                
            # Filter for the last twelve hours
            if ts < cutoff_time:
                continue
                
            record_type = int(entry.type)
            val = float(entry.Value)
            
            records.append({
                "device_timestamp": ts,
                "record_type": record_type,
                "historic_glucose": val if record_type == 0 else None,
                "scan_glucose": val if record_type == 1 else None,
                "rapid_acting_insulin": None
            })
            
        if not records:
            _logger.info(f"No records found matching the last {hours} hours window.")
            return 0
            
        df = pd.DataFrame(records)
        df["record_type"] = df["record_type"].astype(int)
        df["historic_glucose"] = pd.to_numeric(df["historic_glucose"], errors="coerce")
        df["scan_glucose"] = pd.to_numeric(df["scan_glucose"], errors="coerce")
        df["rapid_acting_insulin"] = pd.to_numeric(df["rapid_acting_insulin"], errors="coerce")
        
        # Perform incremental upload
        uploaded_df = self._upload_incremental_to_bigquery(df, dataset_id, table_id)
        return len(uploaded_df) if uploaded_df is not None else 0

    def get_glucose_statistics(self, days: int = 7) -> str:
        """
        Get high-level summary statistics (average, standard deviation, range, estimated GMI) for the last N days.
        Use this tool when the user asks questions like: 'What was my average glucose last week?' or 'How stable was my blood sugar?'
        """
        try:
            from google.cloud import bigquery
            full_table_id = self._get_full_table_id()
            _logger.info(f"Computing glucose statistics over the last {days} days from BigQuery...")
            
            query = f"""
                SELECT 
                    ROUND(AVG(historic_glucose), 2) as avg_glucose,
                    ROUND(STDDEV(historic_glucose), 2) as std_glucose,
                    ROUND(MIN(historic_glucose), 1) as min_glucose,
                    ROUND(MAX(historic_glucose), 1) as max_glucose,
                    COUNT(historic_glucose) as total_readings
                FROM `{full_table_id}`
                WHERE device_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            """
            params = [bigquery.ScalarQueryParameter("days", "INT64", days)]
            df = self._run_bigquery_query(query, params)
            
            if df.empty or df["avg_glucose"].iloc[0] is None:
                return f"No glucose data found in BigQuery for the last {days} days."
                
            row = df.iloc[0]
            avg_mmol = float(row["avg_glucose"])
            # Estimate GMI (Glucose Management Indicator) which approximates HbA1c
            avg_mgdl = avg_mmol * 18.0182
            gmi = 3.31 + (0.02392 * avg_mgdl)
            
            summary = (
                f"📈 **Glucose Statistics (Last {days} Days)**\n"
                f"- **Average Glucose**: {avg_mmol:.2f} mmol/L\n"
                f"- **Standard Deviation (Variability)**: {float(row['std_glucose']):.2f} mmol/L\n"
                f"- **Glucose Range**: {float(row['min_glucose']):.1f} - {float(row['max_glucose']):.1f} mmol/L\n"
                f"- **Estimated GMI (HbA1c Equivalent)**: {gmi:.2f}%\n"
                f"- **Total Automatic Readings**: {int(row['total_readings']):,}\n"
            )
            return summary
        except Exception as e:
            _logger.error(f"Failed to fetch glucose statistics: {e}")
            return f"Error retrieving glucose statistics: {str(e)}"

    def get_time_in_range(self, days: int = 7, target_low: float = 3.9, target_high: float = 10.0) -> str:
        """
        Calculate percentage of time spent in range (TIR), below range (hypoglycemia), and above range (hyperglycemia) for the last N days.
        Use this tool when the user asks questions like: 'What was my time in range last week?' or 'How often was I low?'
        """
        try:
            from google.cloud import bigquery
            full_table_id = self._get_full_table_id()
            _logger.info(f"Computing Time in Range over the last {days} days from BigQuery...")
            
            query = f"""
                SELECT 
                    ROUND(COUNTIF(historic_glucose >= @low AND historic_glucose <= @high) / COUNT(historic_glucose) * 100, 1) as in_range_pct,
                    ROUND(COUNTIF(historic_glucose < @low) / COUNT(historic_glucose) * 100, 1) as below_range_pct,
                    ROUND(COUNTIF(historic_glucose > @high) / COUNT(historic_glucose) * 100, 1) as above_range_pct,
                    COUNT(historic_glucose) as total_readings
                FROM `{full_table_id}`
                WHERE device_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            """
            params = [
                bigquery.ScalarQueryParameter("days", "INT64", days),
                bigquery.ScalarQueryParameter("low", "FLOAT64", target_low),
                bigquery.ScalarQueryParameter("high", "FLOAT64", target_high)
            ]
            df = self._run_bigquery_query(query, params)
            
            if df.empty or df["total_readings"].iloc[0] == 0 or df["in_range_pct"].iloc[0] is None:
                return f"No glucose data found in BigQuery for the last {days} days."
                
            row = df.iloc[0]
            summary = (
                f"🎯 **Time in Range (Last {days} Days, Target: {target_low} - {target_high} mmol/L)**\n"
                f"- **Time in Range (TIR)**: {float(row['in_range_pct']):.1f}%\n"
                f"- **Time Below Range (TBR - Hypo)**: {float(row['below_range_pct']):.1f}%\n"
                f"- **Time Above Range (TAR - Hyper)**: {float(row['above_range_pct']):.1f}%\n"
                f"- **Total Readings Evaluated**: {int(row['total_readings']):,}\n"
            )
            return summary
        except Exception as e:
            _logger.error(f"Failed to fetch Time in Range: {e}")
            return f"Error retrieving Time in Range: {str(e)}"

    def get_hourly_glucose_patterns(self, days: int = 14) -> str:
        """
        Get hourly average glucose patterns (diurnal profile) over the last N days to identify daily trends (e.g. dawn phenomenon, spikes after certain meal hours).
        Use this tool when the user asks questions like: 'Do I tend to spike in the mornings?' or 'What is my average daily diurnal pattern?'
        """
        try:
            from google.cloud import bigquery
            full_table_id = self._get_full_table_id()
            _logger.info(f"Computing hourly glucose patterns over the last {days} days from BigQuery...")
            
            query = f"""
                SELECT 
                    EXTRACT(HOUR FROM device_timestamp AT TIME ZONE "UTC") as hour_of_day,
                    ROUND(AVG(historic_glucose), 2) as avg_glucose,
                    ROUND(STDDEV(historic_glucose), 2) as std_glucose,
                    COUNT(*) as readings_count
                FROM `{full_table_id}`
                WHERE device_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
                GROUP BY hour_of_day
                ORDER BY hour_of_day
            """
            params = [bigquery.ScalarQueryParameter("days", "INT64", days)]
            df = self._run_bigquery_query(query, params)
            
            if df.empty:
                return f"No hourly data patterns found for the last {days} days."
                
            lines = [
                f"📅 **Hourly Glucose Diurnal Patterns (Last {days} Days, UTC hour)**\n", 
                "| Hour | Avg Glucose (mmol/L) | Variability (StdDev) |", 
                "| :---: | :---: | :---: |"
            ]
            for _, row in df.iterrows():
                hour = int(row["hour_of_day"])
                avg = float(row["avg_glucose"])
                std = float(row["std_glucose"])
                lines.append(f"| {hour:02d}:00 | {avg:.2f} | {std:.2f} |")
                
            return "\n".join(lines)
        except Exception as e:
            _logger.error(f"Failed to fetch hourly glucose patterns: {e}")
            return f"Error retrieving hourly glucose patterns: {str(e)}"

    def get_glucose_extreme_events(self, days: int = 7, threshold_low: float = 3.9, threshold_high: float = 10.0) -> str:
        """
        Retrieve recent extreme glucose events (hypoglycemia < 3.9 mmol/L and hyperglycemia > 10.0 mmol/L) to diagnose spikes/dips.
        Use this tool when the user asks questions like: 'Did I have any spikes yesterday?' or 'How many low events did I experience last week?'
        """
        try:
            from google.cloud import bigquery
            full_table_id = self._get_full_table_id()
            _logger.info(f"Fetching recent extreme glucose events over the last {days} days from BigQuery...")
            
            query = f"""
                SELECT 
                    FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S UTC', device_timestamp) as formatted_time,
                    record_type,
                    historic_glucose,
                    scan_glucose
                FROM `{full_table_id}`
                WHERE device_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
                  AND (historic_glucose < @low OR historic_glucose > @high OR scan_glucose < @low OR scan_glucose > @high)
                ORDER BY device_timestamp DESC
                LIMIT 30
            """
            params = [
                bigquery.ScalarQueryParameter("days", "INT64", days),
                bigquery.ScalarQueryParameter("low", "FLOAT64", threshold_low),
                bigquery.ScalarQueryParameter("high", "FLOAT64", threshold_high)
            ]
            df = self._run_bigquery_query(query, params)
            
            if df.empty:
                return f"✨ Outstanding! No extreme low (< {threshold_low} mmol/L) or high (> {threshold_high} mmol/L) events found in the last {days} days."
                
            lines = [
                f"🚨 **Extreme Glucose Events (Last {days} Days)**\n", 
                "| Timestamp | Type | Value (mmol/L) | Severity |", 
                "| :--- | :---: | :---: | :--- |"
            ]
            for _, row in df.iterrows():
                ts_str = str(row["formatted_time"])
                rec_type = int(row["record_type"])
                hist_val = row["historic_glucose"]
                scan_val = row["scan_glucose"]
                
                val = float(hist_val if pd.notnull(hist_val) else scan_val)
                type_label = "Auto-recorded" if rec_type == 0 else "Active Scan"
                
                if val < threshold_low:
                    severity = "🔴 Low (Hypoglycemia)"
                else:
                    severity = "🟡 High (Hyperglycemia)"
                    
                lines.append(f"| {ts_str} | {type_label} | {val:.1f} | {severity} |")
                
            return "\n".join(lines)
        except Exception as e:
            _logger.error(f"Failed to fetch extreme glucose events: {e}")
            return f"Error retrieving extreme events: {str(e)}"

    def _get_latest_bigquery_timestamp(self, client, full_table_id: str) -> Optional[datetime]:
        """Query BigQuery to find the latest timestamp we have successfully uploaded."""
        try:
            query = f"SELECT MAX(device_timestamp) as max_ts FROM `{full_table_id}`"
            query_job = client.query(query)
            results = query_job.result()
            for row in results:
                return row.max_ts  # Returns timezone-aware datetime or None
        except Exception as e:
            _logger.warning(f"Could not fetch BigQuery watermark (table may not exist yet): {e}")
            return None

    def _upload_incremental_to_bigquery(self, df: pd.DataFrame, dataset_id: str, table_id: str, project_id: str = None) -> pd.DataFrame:
        """Fetch watermark from BigQuery, filter for new data, and append only delta rows."""
        try:
            from google.cloud import bigquery
            _logger.info(f"Preparing incremental upload to BigQuery ({dataset_id}.{table_id})...")
            
            client = bigquery.Client(project=project_id)
            full_table_id = f"{client.project}.{dataset_id}.{table_id}"
            
            # 1. Fetch watermark
            max_ts = self._get_latest_bigquery_timestamp(client, full_table_id)
            
            if max_ts is not None:
                _logger.info(f"Found existing BigQuery watermark: {max_ts}")
                if df["device_timestamp"].dt.tz is None:
                    df["device_timestamp"] = df["device_timestamp"].dt.tz_localize("UTC")
                df = df[df["device_timestamp"] > max_ts]
            else:
                _logger.info("No watermark found. Initiating full table load/creation...")

            if df.empty:
                _logger.info("BigQuery is already up to date. No new records to upload.")
                return df

            # Define table schema configuration
            job_config = bigquery.LoadJobConfig(
                schema=[
                    bigquery.SchemaField("device_timestamp", "TIMESTAMP", mode="REQUIRED"),
                    bigquery.SchemaField("record_type", "INTEGER", mode="REQUIRED"),
                    bigquery.SchemaField("historic_glucose", "FLOAT", mode="NULLABLE"),
                    bigquery.SchemaField("scan_glucose", "FLOAT", mode="NULLABLE"),
                    bigquery.SchemaField("rapid_acting_insulin", "FLOAT", mode="NULLABLE"),
                ],
                time_partitioning=bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY,
                    field="device_timestamp"
                ),
                clustering_fields=["record_type"],
                write_disposition="WRITE_APPEND"
            )
            
            _logger.info(f"Appending {len(df):,} new records directly to BigQuery (Table: {full_table_id})...")
            job = client.load_table_from_dataframe(df, full_table_id, job_config=job_config)
            job.result()
            _logger.info(f"Success! Appended {len(df):,} rows directly into partitioned table '{full_table_id}'!")
            return df
            
        except Exception as e:
            _logger.error(f"Error uploading incrementally to BigQuery: {e}")
            raise e

    def _get_full_table_id(self, dataset_id: str = "my_cgm_dataset", table_id: str = "glucose_records") -> str:
        """Helper to dynamically fetch and build the full BigQuery table identifier."""
        try:
            from google.cloud import bigquery
            client = bigquery.Client()
            return f"{client.project}.{dataset_id}.{table_id}"
        except Exception:
            # Fallback using standard configured project ID if client bootstrap fails before setting credentials
            return f"my-cgm-494710.{dataset_id}.{table_id}"

    def _run_bigquery_query(self, query: str, query_parameters: list = None) -> pd.DataFrame:
        """Private helper to run a parameter-parameterized query on BigQuery and return a pandas DataFrame."""
        try:
            from google.cloud import bigquery
            client = bigquery.Client()
            job_config = bigquery.QueryJobConfig(query_parameters=query_parameters) if query_parameters else None
            query_job = client.query(query, job_config=job_config)
            return query_job.to_dataframe()
        except Exception as e:
            _logger.error(f"Error executing BigQuery query: {e}")
            raise e
