from atlassian import Jira
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)


def extract_text_from_adf(adf_content) -> str:
    """Extract plain text from Atlassian Document Format (ADF)"""
    if not adf_content:
        return ""

    # If it's already a string, return it
    if isinstance(adf_content, str):
        return adf_content

    # If it's ADF (dict format), extract text
    if isinstance(adf_content, dict):
        text_parts = []

        def extract_text(node):
            if isinstance(node, dict):
                # Text node
                if node.get('type') == 'text':
                    text_parts.append(node.get('text', ''))
                # Recurse into content
                if 'content' in node:
                    for child in node.get('content', []):
                        extract_text(child)
            elif isinstance(node, list):
                for item in node:
                    extract_text(item)

        extract_text(adf_content)
        return '\n'.join(text_parts)

    return str(adf_content)


class JiraClient:
    """Client for interacting with Jira API"""

    def __init__(self, url: str, username: str, api_token: str):
        # Normalize URL
        self.url = url.rstrip('/')

        self.jira = Jira(
            url=self.url,
            username=username,
            password=api_token,
            cloud=True
        )
        logger.info(f"Jira client initialized for: {self.url}")

    def search_issues(self, query: str, limit: int = 10) -> List[Dict]:
        """Search Jira issues using JQL"""
        try:
            # Check if query contains a Jira issue key (e.g., CTT-21761, PROJ-123)
            issue_key_match = re.search(r'\b([A-Z]+-\d+)\b', query.upper())

            if issue_key_match:
                # Direct issue key search
                issue_key = issue_key_match.group(1)
                logger.info(f"Detected Jira issue key: {issue_key}")
                jql = f'key = "{issue_key}" OR text ~ "{issue_key}"'
            else:
                # Extract meaningful search terms (remove common words)
                stop_words = {'what', 'is', 'the', 'status', 'of', 'a', 'an', 'for', 'in', 'on', 'to', 'how', 'where', 'when', 'why', 'can', 'i', 'get', 'find', 'show', 'me', 'about'}
                words = query.lower().split()
                search_terms = [w for w in words if w not in stop_words and len(w) > 2]
                search_query = ' '.join(search_terms) if search_terms else query
                jql = f'text ~ "{search_query}" ORDER BY updated DESC'

            logger.info(f"Jira JQL query: {jql}")

            results = self.jira.jql(jql, limit=limit)

            issues = []
            for issue in results.get('issues', []):
                formatted = self._format_issue(issue)
                if formatted:
                    issues.append(formatted)
                    logger.info(f"Fetched Jira issue: {formatted.get('key')} - {formatted.get('title')}")

            logger.info(f"Jira search returned {len(issues)} issues for query: {query}")
            return issues

        except Exception as e:
            logger.error(f"Jira search error: {e}")
            return []

    def get_issue(self, issue_key: str, include_comments: bool = True) -> Optional[Dict]:
        """Get specific Jira issue with optional comments"""
        try:
            issue = self.jira.issue(issue_key, expand='renderedFields')
            formatted = self._format_issue(issue)

            if formatted and include_comments:
                comments = self.get_issue_comments(issue_key)
                if comments:
                    formatted['comments'] = comments
                    # Append comments to content
                    comment_text = '\n\nComments:\n' + '\n'.join([
                        f"- {c.get('author', 'Unknown')}: {c.get('body', '')}"
                        for c in comments[:5]  # Limit to 5 most recent comments
                    ])
                    formatted['content'] = formatted.get('content', '') + comment_text

            return formatted
        except Exception as e:
            logger.error(f"Error fetching issue {issue_key}: {e}")
            return None

    def get_issue_comments(self, issue_key: str, limit: int = 5) -> List[Dict]:
        """Get comments for a Jira issue"""
        try:
            comments_data = self.jira.issue_get_comments(issue_key)
            comments = []

            for comment in comments_data.get('comments', [])[-limit:]:
                body = comment.get('body', '')
                # Handle ADF format
                if isinstance(body, dict):
                    body = extract_text_from_adf(body)

                comments.append({
                    'id': comment.get('id', ''),
                    'author': comment.get('author', {}).get('displayName', 'Unknown'),
                    'body': body[:500] if body else '',  # Limit comment length
                    'created': comment.get('created', '')
                })

            return comments
        except Exception as e:
            logger.error(f"Error fetching comments for {issue_key}: {e}")
            return []

    def _format_issue(self, issue: Dict) -> Dict:
        """Format Jira issue data with proper content field for RAG"""
        try:
            fields = issue.get('fields', {})
            key = issue.get('key', '')

            # Extract description - handle both plain text and ADF format
            description = fields.get('description', '')
            if isinstance(description, dict):
                description = extract_text_from_adf(description)
            elif description is None:
                description = ''

            # Get other fields
            summary = fields.get('summary', '')
            status = fields.get('status', {}).get('name', '') if fields.get('status') else ''
            priority = fields.get('priority', {}).get('name', '') if fields.get('priority') else ''
            issue_type = fields.get('issuetype', {}).get('name', '') if fields.get('issuetype') else ''
            assignee = fields.get('assignee', {}).get('displayName', 'Unassigned') if fields.get('assignee') else 'Unassigned'
            reporter = fields.get('reporter', {}).get('displayName', 'Unknown') if fields.get('reporter') else 'Unknown'
            created = fields.get('created', '')
            updated = fields.get('updated', '')

            # Get labels and components
            labels = [label for label in fields.get('labels', [])]
            components = [comp.get('name', '') for comp in fields.get('components', [])]

            # Build comprehensive content for RAG
            content_parts = [
                f"Issue: {key}",
                f"Summary: {summary}",
                f"Type: {issue_type}",
                f"Status: {status}",
                f"Priority: {priority}",
                f"Assignee: {assignee}",
                f"Reporter: {reporter}",
            ]

            if labels:
                content_parts.append(f"Labels: {', '.join(labels)}")
            if components:
                content_parts.append(f"Components: {', '.join(components)}")

            content_parts.append(f"\nDescription:\n{description}")

            content = '\n'.join(content_parts)

            return {
                'id': key,
                'key': key,
                'title': f"[{key}] {summary}",
                'summary': summary,
                'description': description,
                'content': content[:2000],  # Limit content for RAG
                'status': status,
                'priority': priority,
                'type': issue_type,
                'assignee': assignee,
                'reporter': reporter,
                'labels': labels,
                'components': components,
                'url': f"{self.url}/browse/{key}",
                'source': 'jira',
                'created': created,
                'updated': updated
            }

        except Exception as e:
            logger.error(f"Error formatting issue: {e}")
            return None

    def search_by_project(self, project_key: str, query: str = "", limit: int = 10) -> List[Dict]:
        """Search issues within a specific project"""
        try:
            if query:
                jql = f'project = "{project_key}" AND text ~ "{query}" ORDER BY updated DESC'
            else:
                jql = f'project = "{project_key}" ORDER BY updated DESC'

            results = self.jira.jql(jql, limit=limit)

            issues = []
            for issue in results.get('issues', []):
                formatted = self._format_issue(issue)
                if formatted:
                    issues.append(formatted)

            return issues
        except Exception as e:
            logger.error(f"Error searching project {project_key}: {e}")
            return []

    def get_projects(self) -> List[Dict]:
        """Get list of accessible Jira projects"""
        try:
            projects = self.jira.projects()
            return [
                {
                    'key': project.get('key'),
                    'name': project.get('name'),
                    'type': project.get('projectTypeKey', 'software')
                }
                for project in projects
            ]
        except Exception as e:
            logger.error(f"Error fetching projects: {e}")
            return []
