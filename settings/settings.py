import os

from pymongo import MongoClient
import certifi

def get_activity_status():
    """Query: find the entry where name is 'isActivityInProgress'"""
    
    collection = _get_collection()

    doc = collection.find_one({"name": "isActivityInProgress"})
    
    if doc:
        print(f"Status: {doc.get('value')}")
        return doc.get('value')
    return None

def set_activity_status(status: bool):
    """Query: set/update the value for 'isActivityInProgress'"""
    collection = _get_collection()
    collection.update_one(
        {"name": "isActivityInProgress"},
        {"$set": {"value": status}},
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

