import requests
from typing import List, Dict, Optional
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class WebSearchClient:
    """Client for web search and scraping"""
    
    def __init__(self, firecrawl_api_key: Optional[str] = None):
        self.firecrawl_api_key = firecrawl_api_key
        
    async def search(self, query: str, num_results: int = 5) -> List[Dict]:
        """Search the web and return results"""
        # Using DuckDuckGo HTML search as a free alternative
        try:
            results = []
            url = "https://html.duckduckgo.com/html/"
            params = {'q': query}
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.post(url, data=params, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for result in soup.find_all('div', class_='result')[:num_results]:
                title_elem = result.find('a', class_='result__a')
                snippet_elem = result.find('a', class_='result__snippet')
                
                if title_elem:
                    results.append({
                        'title': title_elem.get_text(strip=True),
                        'url': title_elem.get('href', ''),
                        'snippet': snippet_elem.get_text(strip=True) if snippet_elem else ''
                    })
            
            return results
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return []
    
    async def scrape_url(self, url: str) -> str:
        """Scrape content from a URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:5000]  # Limit to first 5000 chars
        except Exception as e:
            logger.error(f"Scraping error for {url}: {e}")
            return ""
