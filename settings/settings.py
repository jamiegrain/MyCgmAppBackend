import logging
import os

from pymongo import MongoClient
import certifi

_logger = logging.getLogger(__name__)

def get_activity_status():
    """Query: find the entry where name is 'isActivityInProgress'"""

    _logger.info("Fetching activity status from settings DB")
    
    collection = _get_collection()

    doc = collection.find_one({"name": "isActivityInProgress"})
    
    if doc:
        return doc.get('value')
    return None

def set_activity_status(status: bool):
    """Query: set/update the value for 'isActivityInProgress'"""
    _logger.info("Setting activity status in settings DB")
    collection = _get_collection()
    collection.update_one(
        {"name": "isActivityInProgress"},
        {"$set": {"value": status}},
        upsert=True
    )

def get_garmin_tokens() -> str:
    """Query: find the entry where name is 'garmin_tokens'"""
    collection = _get_collection()
    doc = collection.find_one({"name": "garmin_tokens"})
    if doc:
        return doc.get('value') if doc.get('value') else None
    return None

def save_garmin_tokens(token_str: str):
    """Query: set/update the value for 'garmin_tokens'"""
    collection = _get_collection()
    collection.update_one(
        {"name": "garmin_tokens"},
        {"$set": {"value": token_str}},
        upsert=True
    )

def _get_collection():
    conn_string = os.environ.get("FIRESTORE_CONN_STRING")
    
    if not conn_string:
        raise ValueError("FIRESTORE_CONN_STRING environment variable is not set!")

    client = MongoClient(
        conn_string, 
        tlsCAFile=certifi.where(),
        retryWrites=False
    )

    return client['cgm-settings-store']['settings']

