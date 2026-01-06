"""
Personal Productivity Integration Service
Search local files, notes, and browser bookmarks
"""
import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import mimetypes
from datetime import datetime

from ..base import (
    BaseIntegrationService,
    SearchResult,
    RateLimitConfig,
    CircuitBreakerConfig,
    ChunkConfig,
    create_service_app
)

logger = logging.getLogger(__name__)


class ProductivityService(BaseIntegrationService):
    """
    Personal Productivity integration

    Features:
    - Local file search
    - Notes search (various formats)
    - Browser bookmarks (received from extension)
    - Clipboard history (received from extension)
    """

    def __init__(
        self,
        search_paths: Optional[List[str]] = None,
        redis_url: str = "redis://localhost:6379"
    ):
        super().__init__(
            service_name="productivity",
            version="1.0.0",
            rate_limit_config=RateLimitConfig(
                requests_per_window=1000,  # Local operations
                window_seconds=60,
                burst_size=100
            ),
            circuit_config=CircuitBreakerConfig(
                failure_threshold=10,
                timeout=30
            ),
            chunk_config=ChunkConfig(
                max_chunk_size=512,
                chunk_overlap=50
            ),
            redis_url=redis_url
        )

        # Default search paths
        home = Path.home()
        self.search_paths = search_paths or [
            str(home / "Documents"),
            str(home / "Desktop"),
            str(home / "Downloads"),
            str(home / "Notes"),
        ]

        # Supported file extensions for content search
        self.text_extensions = {
            '.txt', '.md', '.markdown', '.rst', '.org',
            '.json', '.yaml', '.yml', '.toml', '.xml',
            '.csv', '.tsv',
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.rb',
            '.html', '.css', '.scss', '.less',
            '.sh', '.bash', '.zsh',
            '.sql', '.graphql',
            '.env', '.ini', '.conf', '.cfg'
        }

        # In-memory storage for bookmarks and clipboard (sent from extension)
        self._bookmarks: List[Dict] = []
        self._clipboard_history: List[Dict] = []

    async def _init_client(self):
        """Initialize file search"""
        # Verify search paths exist
        valid_paths = []
        for path in self.search_paths:
            if os.path.exists(path):
                valid_paths.append(path)
            else:
                logger.debug(f"Search path does not exist: {path}")

        self.search_paths = valid_paths
        logger.info(f"Productivity service initialized with {len(valid_paths)} search paths")

    async def _health_check_impl(self) -> bool:
        """Check service health"""
        return len(self.search_paths) > 0

    async def _search_impl(self, query: str, limit: int, **kwargs) -> List[Dict]:
        """Search across productivity sources"""
        search_type = kwargs.get("search_type", "all")
        results = []

        if search_type in ["all", "files"]:
            file_results = await self.search_files(query, limit)
            results.extend(file_results)

        if search_type in ["all", "bookmarks"]:
            bookmark_results = await self.search_bookmarks(query, limit)
            results.extend(bookmark_results)

        if search_type in ["all", "clipboard"]:
            clipboard_results = await self.search_clipboard(query, limit)
            results.extend(clipboard_results)

        return results[:limit]

    async def search_files(self, query: str, limit: int = 10) -> List[Dict]:
        """Search local files by name and content"""
        results = []
        query_lower = query.lower()
        query_terms = query_lower.split()

        for search_path in self.search_paths:
            try:
                for root, dirs, files in os.walk(search_path):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith('.')]

                    for filename in files:
                        if filename.startswith('.'):
                            continue

                        filepath = os.path.join(root, filename)

                        try:
                            # Check filename match
                            filename_lower = filename.lower()
                            name_match = any(term in filename_lower for term in query_terms)

                            # Check content match for text files
                            content_match = False
                            content_preview = ""

                            ext = os.path.splitext(filename)[1].lower()
                            if ext in self.text_extensions and os.path.getsize(filepath) < 1_000_000:  # <1MB
                                try:
                                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                        content = f.read(50000)  # First 50KB
                                        content_lower = content.lower()

                                        if any(term in content_lower for term in query_terms):
                                            content_match = True
                                            # Find relevant snippet
                                            for term in query_terms:
                                                idx = content_lower.find(term)
                                                if idx != -1:
                                                    start = max(0, idx - 100)
                                                    end = min(len(content), idx + 200)
                                                    content_preview = "..." + content[start:end] + "..."
                                                    break
                                except:
                                    pass

                            if name_match or content_match:
                                stat = os.stat(filepath)
                                results.append({
                                    "id": filepath,
                                    "title": filename,
                                    "content": content_preview or f"File: {filename}",
                                    "url": f"file://{filepath}",
                                    "source": "productivity",
                                    "metadata": {
                                        "type": "local_file",
                                        "path": filepath,
                                        "extension": ext,
                                        "size": stat.st_size,
                                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                        "match_type": "content" if content_match else "filename"
                                    },
                                    "score": 2 if content_match else 1
                                })

                                if len(results) >= limit * 3:  # Collect more, then sort
                                    break

                        except (PermissionError, OSError) as e:
                            logger.debug(f"Cannot access file {filepath}: {e}")
                            continue

                    if len(results) >= limit * 3:
                        break

            except Exception as e:
                logger.error(f"Error searching path {search_path}: {e}")

        # Sort by score and return top results
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:limit]

    async def search_bookmarks(self, query: str, limit: int = 10) -> List[Dict]:
        """Search browser bookmarks (stored from extension)"""
        query_lower = query.lower()
        results = []

        for bookmark in self._bookmarks:
            title = bookmark.get("title", "").lower()
            url = bookmark.get("url", "").lower()

            if query_lower in title or query_lower in url:
                results.append({
                    "id": bookmark.get("id", ""),
                    "title": bookmark.get("title", ""),
                    "content": f"Bookmark: {bookmark.get('title', '')}\nURL: {bookmark.get('url', '')}",
                    "url": bookmark.get("url", ""),
                    "source": "productivity",
                    "metadata": {
                        "type": "bookmark",
                        "folder": bookmark.get("folder", ""),
                        "date_added": bookmark.get("dateAdded")
                    }
                })

                if len(results) >= limit:
                    break

        return results

    async def search_clipboard(self, query: str, limit: int = 10) -> List[Dict]:
        """Search clipboard history (stored from extension)"""
        query_lower = query.lower()
        results = []

        for idx, clip in enumerate(self._clipboard_history):
            content = clip.get("content", "")

            if query_lower in content.lower():
                results.append({
                    "id": f"clip_{idx}",
                    "title": f"Clipboard ({clip.get('timestamp', '')})",
                    "content": content[:500],
                    "url": "",
                    "source": "productivity",
                    "metadata": {
                        "type": "clipboard",
                        "timestamp": clip.get("timestamp"),
                        "content_type": clip.get("type", "text")
                    }
                })

                if len(results) >= limit:
                    break

        return results

    async def sync_bookmarks(self, bookmarks: List[Dict]) -> Dict:
        """Sync bookmarks from browser extension"""
        self._bookmarks = bookmarks
        logger.info(f"Synced {len(bookmarks)} bookmarks")

        # Also cache in Redis for persistence
        if self.cache:
            await self.cache.set("bookmarks", bookmarks, l2_ttl=86400)  # 24 hours

        return {"status": "synced", "count": len(bookmarks)}

    async def add_clipboard(self, content: str, content_type: str = "text") -> Dict:
        """Add item to clipboard history"""
        clip = {
            "content": content,
            "type": content_type,
            "timestamp": datetime.now().isoformat()
        }

        self._clipboard_history.insert(0, clip)

        # Keep only last 100 items
        self._clipboard_history = self._clipboard_history[:100]

        return {"status": "added"}

    async def get_recent_files(self, limit: int = 20) -> List[Dict]:
        """Get recently modified files"""
        files = []

        for search_path in self.search_paths:
            try:
                for root, dirs, filenames in os.walk(search_path):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]

                    for filename in filenames:
                        if filename.startswith('.'):
                            continue

                        filepath = os.path.join(root, filename)
                        try:
                            stat = os.stat(filepath)
                            files.append({
                                "path": filepath,
                                "name": filename,
                                "modified": stat.st_mtime,
                                "size": stat.st_size
                            })
                        except:
                            continue

            except Exception as e:
                logger.error(f"Error scanning {search_path}: {e}")

        # Sort by modification time
        files.sort(key=lambda x: x["modified"], reverse=True)

        results = []
        for f in files[:limit]:
            results.append({
                "id": f["path"],
                "title": f["name"],
                "content": f"File: {f['name']}",
                "url": f"file://{f['path']}",
                "source": "productivity",
                "metadata": {
                    "type": "recent_file",
                    "path": f["path"],
                    "size": f["size"],
                    "modified": datetime.fromtimestamp(f["modified"]).isoformat()
                }
            })

        return results

    async def search_notes(self, query: str, limit: int = 10) -> List[Dict]:
        """Search specifically in notes folders"""
        # Common notes locations
        home = Path.home()
        notes_paths = [
            home / "Notes",
            home / "Documents" / "Notes",
            home / "Obsidian",
            home / "Documents" / "Obsidian",
            home / "Logseq",
            home / ".logseq",
        ]

        # Temporarily set search paths to notes folders
        original_paths = self.search_paths
        self.search_paths = [str(p) for p in notes_paths if p.exists()]

        results = await self.search_files(query, limit)

        # Restore original paths
        self.search_paths = original_paths

        # Update metadata type
        for r in results:
            r["metadata"]["type"] = "note"

        return results


# Create FastAPI app
def create_app() -> "FastAPI":
    service = ProductivityService()
    app = create_service_app(
        service,
        title="Personal Productivity Integration Service",
        description="Search local files, notes, and bookmarks"
    )

    from pydantic import BaseModel
    from typing import List as PyList

    class BookmarkSync(BaseModel):
        bookmarks: PyList[Dict[str, Any]]

    class ClipboardAdd(BaseModel):
        content: str
        content_type: str = "text"

    # Add custom endpoints
    @app.get("/files")
    async def search_files(query: str, limit: int = 10):
        return await service.search_files(query, limit)

    @app.get("/files/recent")
    async def get_recent_files(limit: int = 20):
        return await service.get_recent_files(limit)

    @app.get("/notes")
    async def search_notes(query: str, limit: int = 10):
        return await service.search_notes(query, limit)

    @app.get("/bookmarks")
    async def search_bookmarks(query: str, limit: int = 10):
        return await service.search_bookmarks(query, limit)

    @app.post("/bookmarks/sync")
    async def sync_bookmarks(data: BookmarkSync):
        return await service.sync_bookmarks(data.bookmarks)

    @app.get("/clipboard")
    async def search_clipboard(query: str, limit: int = 10):
        return await service.search_clipboard(query, limit)

    @app.post("/clipboard")
    async def add_clipboard(data: ClipboardAdd):
        return await service.add_clipboard(data.content, data.content_type)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8026)
