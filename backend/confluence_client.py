from atlassian import Confluence
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ConfluenceClient:
    """Client for interacting with Confluence API"""
    
    def __init__(self, url: str, username: str, api_token: str):
        self.confluence = Confluence(
            url=url,
            username=username,
            password=api_token,
            cloud=True
        )
        self.url = url
        
    def search_content(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Confluence content"""
        try:
            results = self.confluence.cql(f'text ~ "{query}"', limit=limit)
            pages = []
            
            for result in results.get('results', []):
                page_id = result.get('content', {}).get('id')
                if page_id:
                    page = self.confluence.get_page_by_id(page_id, expand='body.storage')
                    pages.append({
                        'id': page_id,
                        'title': page.get('title', ''),
                        'content': page.get('body', {}).get('storage', {}).get('value', ''),
                        'url': f"{self.url}/wiki/spaces/{page.get('space', {}).get('key', '')}/pages/{page_id}"
                    })
            
            return pages
        except Exception as e:
            logger.error(f"Confluence search error: {e}")
            return []
    
    def get_page_content(self, page_id: str) -> Optional[Dict]:
        """Get specific page content"""
        try:
            page = self.confluence.get_page_by_id(page_id, expand='body.storage')
            return {
                'id': page_id,
                'title': page.get('title', ''),
                'content': page.get('body', {}).get('storage', {}).get('value', ''),
                'url': f"{self.url}/wiki/pages/{page_id}"
            }
        except Exception as e:
            logger.error(f"Error fetching page {page_id}: {e}")
            return None
