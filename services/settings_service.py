import os
import logging
from pymongo import MongoClient
import certifi

_logger = logging.getLogger(__name__)

class SettingsService:
    def __init__(self):
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        
        conn_string = os.environ.get("FIRESTORE_CONN_STRING")
        if not conn_string:
            raise ValueError("FIRESTORE_CONN_STRING environment variable is not set!")

        client = MongoClient(
            conn_string, 
            tlsCAFile=certifi.where(),
            retryWrites=False
        )
        self._collection = client['cgm-settings-store']['settings']
        return self._collection

    def get_activity_status(self) -> bool:
        """Query: find the entry where name is 'isActivityInProgress'"""
        _logger.info("Fetching activity status from settings DB")
        try:
            collection = self._get_collection()
            doc = collection.find_one({"name": "isActivityInProgress"})
            if doc:
                return bool(doc.get('value'))
        except Exception as e:
            _logger.error(f"Error fetching activity status from DB: {e}")
        return False

    def set_activity_status(self, status: bool):
        """Query: set/update the value for 'isActivityInProgress'"""
        _logger.info(f"Setting activity status in settings DB to {status}")
        collection = self._get_collection()
        collection.update_one(
            {"name": "isActivityInProgress"},
            {"$set": {"value": status}},
            upsert=True
        )

    def get_garmin_tokens(self) -> str:
        """Query: find the entry where name is 'garmin_tokens'"""
        try:
            collection = self._get_collection()
            doc = collection.find_one({"name": "garmin_tokens"})
            if doc:
                return doc.get('value') if doc.get('value') else None
        except Exception as e:
            _logger.error(f"Error fetching Garmin tokens from DB: {e}")
        return None

    def save_garmin_tokens(self, token_str: str):
        """Query: set/update the value for 'garmin_tokens'"""
        collection = self._get_collection()
        collection.update_one(
            {"name": "garmin_tokens"},
            {"$set": {"value": token_str}},
            upsert=True
        )
