from atlassian import Confluence
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)


def strip_html(html_content: str) -> str:
    """Strip HTML tags and clean up Confluence content for LLM consumption"""
    if not html_content:
        return ""

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for element in soup(['script', 'style', 'head', 'meta', 'link']):
            element.decompose()

        # Get text content
        text = soup.get_text(separator='\n')

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = '\n'.join(lines)

        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()
    except Exception as e:
        logger.error(f"Error stripping HTML: {e}")
        return html_content


class ConfluenceClient:
    """Client for interacting with Confluence API"""

    def __init__(self, url: str, username: str, api_token: str):
        # Normalize URL
        self.url = url.rstrip('/')

        self.confluence = Confluence(
            url=self.url,
            username=username,
            password=api_token,
            cloud=True
        )
        logger.info(f"Confluence client initialized for: {self.url}")

    def search_content(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Confluence content using CQL"""
        try:
            # Extract meaningful search terms (remove common words)
            stop_words = {'what', 'is', 'the', 'status', 'of', 'a', 'an', 'for', 'in', 'on', 'to', 'how', 'where', 'when', 'why', 'can', 'i', 'get', 'find', 'show', 'me', 'about'}
            words = query.lower().split()
            search_terms = [w for w in words if w not in stop_words and len(w) > 2]
            search_query = ' '.join(search_terms) if search_terms else query

            # Use CQL for text search
            cql_query = f'text ~ "{search_query}" ORDER BY lastmodified DESC'
            logger.info(f"Confluence CQL query: {cql_query}")

            results = self.confluence.cql(cql_query, limit=limit)
            pages = []

            for result in results.get('results', []):
                content = result.get('content', {})
                page_id = content.get('id')

                if page_id:
                    try:
                        # Fetch full page content
                        page = self.confluence.get_page_by_id(
                            page_id,
                            expand='body.storage,space,version'
                        )

                        # Extract and clean content
                        raw_html = page.get('body', {}).get('storage', {}).get('value', '')
                        clean_content = strip_html(raw_html)

                        # Get space key for URL
                        space_key = page.get('space', {}).get('key', '')

                        # Build proper Confluence Cloud URL
                        page_url = f"{self.url}/wiki/spaces/{space_key}/pages/{page_id}"

                        pages.append({
                            'id': page_id,
                            'title': page.get('title', ''),
                            'content': clean_content[:2000],  # Limit content length
                            'url': page_url,
                            'source': 'confluence',
                            'space': space_key,
                            'last_modified': page.get('version', {}).get('when', '')
                        })

                        logger.info(f"Fetched Confluence page: {page.get('title', '')} ({page_id})")

                    except Exception as page_error:
                        logger.error(f"Error fetching page {page_id}: {page_error}")
                        continue

            logger.info(f"Confluence search returned {len(pages)} pages for query: {query}")
            return pages

        except Exception as e:
            logger.error(f"Confluence search error: {e}")
            return []

    def get_page_content(self, page_id: str) -> Optional[Dict]:
        """Get specific page content by ID"""
        try:
            page = self.confluence.get_page_by_id(
                page_id,
                expand='body.storage,space,version'
            )

            raw_html = page.get('body', {}).get('storage', {}).get('value', '')
            clean_content = strip_html(raw_html)
            space_key = page.get('space', {}).get('key', '')

            return {
                'id': page_id,
                'title': page.get('title', ''),
                'content': clean_content,
                'url': f"{self.url}/wiki/spaces/{space_key}/pages/{page_id}",
                'source': 'confluence',
                'space': space_key
            }
        except Exception as e:
            logger.error(f"Error fetching page {page_id}: {e}")
            return None

    def get_spaces(self) -> List[Dict]:
        """Get list of accessible Confluence spaces"""
        try:
            spaces = self.confluence.get_all_spaces(limit=50)
            return [
                {
                    'key': space.get('key'),
                    'name': space.get('name'),
                    'type': space.get('type')
                }
                for space in spaces.get('results', [])
            ]
        except Exception as e:
            logger.error(f"Error fetching spaces: {e}")
            return []

    def search_in_space(self, query: str, space_key: str, limit: int = 10) -> List[Dict]:
        """Search within a specific Confluence space"""
        try:
            cql_query = f'space = "{space_key}" AND text ~ "{query}" ORDER BY lastmodified DESC'
            results = self.confluence.cql(cql_query, limit=limit)

            pages = []
            for result in results.get('results', []):
                content = result.get('content', {})
                page_id = content.get('id')
                if page_id:
                    page = self.get_page_content(page_id)
                    if page:
                        pages.append(page)

            return pages
        except Exception as e:
            logger.error(f"Error searching in space {space_key}: {e}")
            return []
