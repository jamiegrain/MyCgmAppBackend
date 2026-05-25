import os
import time
import uuid
import logging
from typing import Any, Optional
from google.cloud import firestore
from google.adk.sessions.base_session_service import BaseSessionService, GetSessionConfig, ListSessionsResponse
from google.adk.sessions.session import Session
from google.adk.events.event import Event
from google.adk.cli.service_registry import get_service_registry

logger = logging.getLogger("google_adk.firestore_sessions")

class FirestoreSessionService(BaseSessionService):
    """
    A custom ADK Session Service that uses Google Cloud Firestore for serverless,
    highly available chat session persistence in Cloud Run.
    """

    def __init__(self, uri: str, **kwargs: Any):
        """
        Initializes the Firestore Session Service.
        The URI scheme is expected to be 'firestore://' or 'firestore://project-id'
        """
        # Parse project ID if provided in the URI, otherwise fall back to environment/ADC default
        project = None
        if "://" in uri:
            parts = uri.split("://", 1)
            if parts[1]:
                project = parts[1].strip("/")
        
        # Initialize standard Async Firestore Client (non-blocking for FastAPI!)
        self.db = firestore.AsyncClient(project=project)
        self.collection_name = "adk_sessions"
        self.sessions_ref = self.db.collection(self.collection_name)
        logger.info(f"Initialized FirestoreSessionService targeting collection '{self.collection_name}' (Project: {project or 'default'})")

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        session_id = session_id or str(uuid.uuid4())
        doc_id = f"{app_name}:{user_id}:{session_id}"
        
        initial_state = state or {}
        now = time.time()
        
        doc_ref = self.sessions_ref.document(doc_id)
        await doc_ref.set({
            "app_name": app_name,
            "user_id": user_id,
            "session_id": session_id,
            "state": initial_state,
            "events": [],
            "last_update_time": now
        })
        
        logger.info(f"Created new Firestore session: {doc_id}")
        return Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            state=initial_state,
            events=[],
            last_update_time=now
        )

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:
        doc_id = f"{app_name}:{user_id}:{session_id}"
        doc_ref = self.sessions_ref.document(doc_id)
        doc = await doc_ref.get()
        
        if not doc.exists:
            logger.debug(f"Firestore session {doc_id} not found.")
            return None
            
        data = doc.to_dict()
        events_data = data.get("events", [])
        
        # Deserialize events back into Pydantic models
        events = []
        for e in events_data:
            try:
                events.append(Event.model_validate(e))
            except Exception as ex:
                logger.error(f"Error deserializing event: {ex}")
                
        # Apply standard filters if provided by ADK
        if config:
            if config.after_timestamp:
                events = [e for e in events if e.timestamp >= config.after_timestamp]
            if config.num_recent_events:
                events = events[-config.num_recent_events:]
                
        logger.info(f"Retrieved Firestore session {doc_id} with {len(events)} events.")
        return Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            state=data.get("state", {}),
            events=events,
            last_update_time=data.get("last_update_time", 0.0)
        )

    async def list_sessions(
        self, *, app_name: str, user_id: Optional[str] = None
    ) -> ListSessionsResponse:
        query = self.sessions_ref.where("app_name", "==", app_name)
        if user_id is not None:
            query = query.where("user_id", "==", user_id)
            
        sessions = []
        async for doc in query.stream():
            data = doc.to_dict()
            sessions.append(Session(
                id=data.get("session_id"),
                app_name=app_name,
                user_id=data.get("user_id"),
                state=data.get("state", {}),
                events=[], # list_sessions does not populate event list
                last_update_time=data.get("last_update_time", 0.0)
            ))
            
        return ListSessionsResponse(sessions=sessions)

    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        doc_id = f"{app_name}:{user_id}:{session_id}"
        await self.sessions_ref.document(doc_id).delete()
        logger.info(f"Deleted Firestore session: {doc_id}")

    async def append_event(self, session: Session, event: Event) -> Event:
        # 1. Update in-memory session (temp delta states, merges, local lists)
        await super().append_event(session=session, event=event)
        
        # 2. Write to Firestore database
        doc_id = f"{session.app_name}:{session.user_id}:{session.id}"
        doc_ref = self.sessions_ref.document(doc_id)
        
        # Serialize the event using mode='json' (converts Pydantic to pure dict)
        serialized_event = event.model_dump(mode="json", exclude_none=True)
        
        await doc_ref.update({
            "state": session.state,
            "events": firestore.ArrayUnion([serialized_event]),
            "last_update_time": event.timestamp
        })
        
        logger.info(f"Appended event to Firestore session {doc_id}")
        return event

def firestore_session_factory(uri: str, **kwargs: Any) -> BaseSessionService:
    return FirestoreSessionService(uri, **kwargs)

# Register the firestore:// scheme in the singleton ADK registry
registry = get_service_registry()
registry.register_session_service("firestore", firestore_session_factory)
logger.info("Successfully registered custom 'firestore' session service scheme with ADK!")
