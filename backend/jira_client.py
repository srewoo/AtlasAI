from atlassian import Jira
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class JiraClient:
    """Client for interacting with Jira API"""
    
    def __init__(self, url: str, username: str, api_token: str):
        self.jira = Jira(
            url=url,
            username=username,
            password=api_token,
            cloud=True
        )
        self.url = url
        
    def search_issues(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Jira issues"""
        try:
            jql = f'text ~ "{query}" ORDER BY updated DESC'
            results = self.jira.jql(jql, limit=limit)
            
            issues = []
            for issue in results.get('issues', []):
                issues.append(self._format_issue(issue))
            
            return issues
        except Exception as e:
            logger.error(f"Jira search error: {e}")
            return []
    
    def get_issue(self, issue_key: str) -> Optional[Dict]:
        """Get specific Jira issue"""
        try:
            issue = self.jira.issue(issue_key)
            return self._format_issue(issue)
        except Exception as e:
            logger.error(f"Error fetching issue {issue_key}: {e}")
            return None
    
    def _format_issue(self, issue: Dict) -> Dict:
        """Format Jira issue data"""
        fields = issue.get('fields', {})
        return {
            'key': issue.get('key', ''),
            'summary': fields.get('summary', ''),
            'description': fields.get('description', ''),
            'status': fields.get('status', {}).get('name', ''),
            'assignee': fields.get('assignee', {}).get('displayName', 'Unassigned') if fields.get('assignee') else 'Unassigned',
            'priority': fields.get('priority', {}).get('name', ''),
            'url': f"{self.url}/browse/{issue.get('key', '')}"
        }
