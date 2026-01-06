"""
Google Workspace Integration Service
Search Drive, Docs, Sheets, Calendar, and Gmail
"""
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from ..base import (
    BaseIntegrationService,
    SearchResult,
    RateLimitConfig,
    CircuitBreakerConfig,
    ChunkConfig,
    create_service_app
)

logger = logging.getLogger(__name__)


class GoogleService(BaseIntegrationService):
    """
    Google Workspace integration

    Features:
    - Search Google Drive files
    - Read Google Docs content
    - Search Gmail messages
    - Access Calendar events
    """

    def __init__(
        self,
        credentials_file: Optional[str] = None,
        token_file: Optional[str] = None,
        redis_url: str = "redis://localhost:6379"
    ):
        super().__init__(
            service_name="google",
            version="1.0.0",
            rate_limit_config=RateLimitConfig(
                requests_per_window=100,
                window_seconds=100,
                burst_size=20
            ),
            circuit_config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout=60
            ),
            chunk_config=ChunkConfig(
                max_chunk_size=512,
                chunk_overlap=50
            ),
            redis_url=redis_url
        )
        self.credentials_file = credentials_file or os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        self.token_file = token_file or os.getenv("GOOGLE_TOKEN_FILE", "token.json")
        self._drive_service = None
        self._docs_service = None
        self._gmail_service = None
        self._calendar_service = None

    async def _init_client(self):
        """Initialize Google API clients"""
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            import pickle

            SCOPES = [
                'https://www.googleapis.com/auth/drive.readonly',
                'https://www.googleapis.com/auth/documents.readonly',
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/calendar.readonly'
            ]

            creds = None

            # Try to load existing token
            if os.path.exists(self.token_file):
                with open(self.token_file, 'rb') as token:
                    creds = pickle.load(token)

            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif os.path.exists(self.credentials_file):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                    # Save for future use
                    with open(self.token_file, 'wb') as token:
                        pickle.dump(creds, token)
                else:
                    logger.warning("Google credentials not configured")
                    return

            # Build service clients
            self._drive_service = build('drive', 'v3', credentials=creds)
            self._docs_service = build('docs', 'v1', credentials=creds)
            self._gmail_service = build('gmail', 'v1', credentials=creds)
            self._calendar_service = build('calendar', 'v3', credentials=creds)

            logger.info("Google services initialized")

        except ImportError:
            logger.error("Google API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib")
        except Exception as e:
            logger.error(f"Google init error: {e}")

    async def _health_check_impl(self) -> bool:
        """Check Google API connection"""
        if not self._drive_service:
            return False
        try:
            self._drive_service.about().get(fields="user").execute()
            return True
        except Exception as e:
            logger.error(f"Google health check failed: {e}")
            return False

    async def _search_impl(self, query: str, limit: int, **kwargs) -> List[Dict]:
        """Search across Google services"""
        search_type = kwargs.get("search_type", "drive")

        if search_type == "drive":
            return await self.search_drive(query, limit)
        elif search_type == "gmail":
            return await self.search_gmail(query, limit)
        elif search_type == "calendar":
            return await self.search_calendar(query, limit)

        return await self.search_drive(query, limit)

    async def search_drive(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Google Drive files"""
        if not self._drive_service:
            return []

        try:
            # Search query for Drive
            drive_query = f"fullText contains '{query}' and trashed = false"

            response = self._drive_service.files().list(
                q=drive_query,
                pageSize=limit,
                fields="files(id, name, mimeType, webViewLink, modifiedTime, owners, description)",
                orderBy="modifiedTime desc"
            ).execute()

            files = response.get("files", [])
            results = []

            for file in files:
                mime_type = file.get("mimeType", "")
                file_type = self._get_file_type(mime_type)

                # Get content preview for docs
                content = file.get("description", "") or ""
                if mime_type == "application/vnd.google-apps.document":
                    doc_content = await self.get_doc_content(file.get("id"))
                    if doc_content:
                        content = doc_content[:500]

                results.append({
                    "id": file.get("id"),
                    "title": file.get("name"),
                    "content": content,
                    "url": file.get("webViewLink"),
                    "source": "google",
                    "metadata": {
                        "type": file_type,
                        "mime_type": mime_type,
                        "modified": file.get("modifiedTime"),
                        "owners": [o.get("displayName") for o in file.get("owners", [])]
                    }
                })

            return results

        except Exception as e:
            logger.error(f"Google Drive search error: {e}")
            return []

    async def get_doc_content(self, doc_id: str) -> Optional[str]:
        """Get content from a Google Doc"""
        if not self._docs_service:
            return None

        try:
            doc = self._docs_service.documents().get(documentId=doc_id).execute()
            content = self._extract_doc_text(doc)
            return content
        except Exception as e:
            logger.error(f"Google Doc fetch error: {e}")
            return None

    def _extract_doc_text(self, doc: Dict) -> str:
        """Extract plain text from Google Doc"""
        text_parts = []

        def extract_text(element):
            if 'paragraph' in element:
                for elem in element['paragraph'].get('elements', []):
                    if 'textRun' in elem:
                        text_parts.append(elem['textRun'].get('content', ''))
            if 'table' in element:
                for row in element['table'].get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        for content in cell.get('content', []):
                            extract_text(content)

        body = doc.get('body', {})
        for content in body.get('content', []):
            extract_text(content)

        return ''.join(text_parts)

    async def search_gmail(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Gmail messages"""
        if not self._gmail_service:
            return []

        try:
            response = self._gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=limit
            ).execute()

            messages = response.get("messages", [])
            results = []

            for msg_ref in messages[:limit]:
                msg = self._gmail_service.users().messages().get(
                    userId='me',
                    id=msg_ref['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date']
                ).execute()

                headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}

                results.append({
                    "id": msg.get("id"),
                    "title": headers.get("Subject", "No Subject"),
                    "content": msg.get("snippet", ""),
                    "url": f"https://mail.google.com/mail/u/0/#inbox/{msg.get('id')}",
                    "source": "google",
                    "metadata": {
                        "type": "email",
                        "from": headers.get("From"),
                        "date": headers.get("Date"),
                        "labels": msg.get("labelIds", [])
                    }
                })

            return results

        except Exception as e:
            logger.error(f"Gmail search error: {e}")
            return []

    async def search_calendar(self, query: str, limit: int = 10) -> List[Dict]:
        """Search calendar events"""
        if not self._calendar_service:
            return []

        try:
            # Search in next 30 days
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=30)).isoformat() + 'Z'

            response = self._calendar_service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=limit,
                singleEvents=True,
                orderBy='startTime',
                q=query
            ).execute()

            events = response.get("items", [])
            results = []

            for event in events:
                start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date'))

                results.append({
                    "id": event.get("id"),
                    "title": event.get("summary", "No Title"),
                    "content": event.get("description", ""),
                    "url": event.get("htmlLink"),
                    "source": "google",
                    "metadata": {
                        "type": "calendar_event",
                        "start": start,
                        "end": event.get('end', {}).get('dateTime'),
                        "location": event.get("location"),
                        "attendees": [a.get("email") for a in event.get("attendees", [])]
                    }
                })

            return results

        except Exception as e:
            logger.error(f"Calendar search error: {e}")
            return []

    def _get_file_type(self, mime_type: str) -> str:
        """Map MIME type to friendly file type"""
        type_map = {
            "application/vnd.google-apps.document": "doc",
            "application/vnd.google-apps.spreadsheet": "spreadsheet",
            "application/vnd.google-apps.presentation": "presentation",
            "application/vnd.google-apps.folder": "folder",
            "application/pdf": "pdf",
            "image/": "image",
            "video/": "video"
        }

        for key, value in type_map.items():
            if key in mime_type:
                return value
        return "file"


# Create FastAPI app
def create_app() -> "FastAPI":
    service = GoogleService()
    app = create_service_app(
        service,
        title="Google Workspace Integration Service",
        description="Search Google Drive, Docs, Gmail, and Calendar"
    )

    # Add custom endpoints
    @app.get("/drive")
    async def search_drive(query: str, limit: int = 10):
        return await service.search_drive(query, limit)

    @app.get("/gmail")
    async def search_gmail(query: str, limit: int = 10):
        return await service.search_gmail(query, limit)

    @app.get("/calendar")
    async def search_calendar(query: str, limit: int = 10):
        return await service.search_calendar(query, limit)

    @app.get("/doc/{doc_id}")
    async def get_doc(doc_id: str):
        content = await service.get_doc_content(doc_id)
        return {"id": doc_id, "content": content}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)
