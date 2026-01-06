"""
Agentic RAG Engine for Gateway
Uses orchestrator service for distributed context gathering
"""
from typing import Dict, List, Optional, AsyncGenerator
import logging
from vector_store import VectorStore
from web_search import WebSearchClient
from llm_router import LLMRouter
from orchestrator_client import OrchestratorClient, get_orchestrator_client
import asyncio

logger = logging.getLogger(__name__)


class AgenticRAG:
    """Agentic RAG system that routes queries to appropriate sources via orchestrator"""

    def __init__(
        self,
        vector_store: VectorStore,
        llm_router: LLMRouter,
        orchestrator_client: Optional[OrchestratorClient] = None,
        web_search_client: Optional[WebSearchClient] = None,
        enabled_services: Optional[List[str]] = None
    ):
        self.vector_store = vector_store
        self.llm_router = llm_router
        self.orchestrator = orchestrator_client or get_orchestrator_client()
        self.web_search = web_search_client
        # Services enabled for this user (from settings)
        self.enabled_services = enabled_services or ['confluence', 'jira']

    async def determine_source(self, query: str) -> List[str]:
        """Determine which sources to query based on the question"""
        query_lower = query.lower()
        sources = []

        # Service keyword mappings
        service_keywords = {
            'confluence': ['document', 'documentation', 'wiki', 'page', 'confluence', 'article', 'guide', 'tutorial', 'how-to', 'procedure'],
            'jira': ['issue', 'ticket', 'bug', 'task', 'story', 'epic', 'jira', 'sprint', 'backlog', 'feature'],
            'slack': ['slack', 'message', 'chat', 'channel', 'thread', 'dm'],
            'github': ['github', 'code', 'repository', 'commit', 'pr', 'pull request', 'branch', 'merge'],
            'google': ['drive', 'doc', 'sheet', 'gmail', 'email', 'calendar', 'meeting'],
            'notion': ['notion', 'note', 'database'],
            'linear': ['linear', 'issue', 'project', 'cycle', 'roadmap'],
            'figma': ['figma', 'design', 'prototype', 'component', 'frame', 'ui', 'ux'],
            'microsoft365': ['teams', 'sharepoint', 'outlook', 'onedrive', 'office', 'microsoft'],
            'devtools': ['stackoverflow', 'npm', 'pypi', 'package', 'library', 'mdn', 'how to', 'error'],
            'productivity': ['file', 'local', 'bookmark', 'notes', 'clipboard'],
            'web': ['latest', 'news', 'current', 'today', 'recent', 'what is', 'who is', 'when', 'where']
        }

        # Check keywords and build prioritized list
        keyword_matches = []
        for service, keywords in service_keywords.items():
            if service in self.enabled_services or service == 'web':
                if any(kw in query_lower for kw in keywords):
                    keyword_matches.append(service)
                    logger.info(f"Keywords detected for: {service}")

        # If specific keywords matched, use those services
        if keyword_matches:
            sources = keyword_matches
        else:
            # Default: use all enabled services
            sources = [s for s in self.enabled_services if s != 'web']

        # Add web search if enabled
        if self.web_search and 'web' not in sources:
            sources.append('web')

        logger.info(f"Determined sources for query: {sources}")
        return sources if sources else ['vector_store']

    async def gather_context(self, query: str, sources: List[str]) -> List[Dict]:
        """Gather context from determined sources via orchestrator"""
        all_context = []

        # First, always search vector store for existing knowledge
        vector_results = self.vector_store.search(query, n_results=3)
        all_context.extend(vector_results)

        # Separate web from orchestrator services
        orchestrator_services = [s for s in sources if s not in ['web', 'vector_store']]
        include_web = 'web' in sources

        # Fetch from orchestrator (all services in parallel)
        tasks = []

        if orchestrator_services:
            tasks.append(self._fetch_from_orchestrator(query, orchestrator_services))

        if include_web and self.web_search:
            tasks.append(self._fetch_web(query))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_context.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Context fetch error: {result}")

        return all_context

    async def _fetch_from_orchestrator(self, query: str, services: List[str]) -> List[Dict]:
        """Fetch context from multiple services via orchestrator"""
        try:
            logger.info(f"Fetching from orchestrator for services: {services}")
            results = await self.orchestrator.search(query, services=services, limit=5)

            # Transform orchestrator results to context format
            context = []
            for result in results:
                doc = {
                    'id': result.get('id', ''),
                    'title': result.get('title', ''),
                    'content': result.get('content', ''),
                    'url': result.get('url', ''),
                    'source': result.get('source', 'unknown'),
                    'metadata': result.get('metadata', {})
                }
                context.append(doc)

                # Add to vector store for future queries
                self.vector_store.add_documents([doc], doc['source'])

            logger.info(f"Orchestrator returned {len(context)} results")
            return context

        except Exception as e:
            logger.error(f"Orchestrator fetch error: {e}", exc_info=True)
            return []

    async def _fetch_web(self, query: str) -> List[Dict]:
        """Fetch from web search"""
        try:
            results = await self.web_search.search(query, num_results=3)
            # Add to vector store
            if results:
                self.vector_store.add_documents(results, 'web')
            return results
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return []

    async def generate_response(self, query: str, context: List[Dict], chat_history: List[Dict] = None) -> str:
        """Generate response using LLM with context and chat history"""
        # Build context string from retrieved documents
        context_str = "\n\n".join([
            f"Source: {doc.get('source', 'unknown')}\nTitle: {doc.get('title', 'N/A')}\nURL: {doc.get('url', 'N/A')}\nContent: {doc.get('content', '')[:500]}"
            for doc in context[:5]
        ])

        # Build chat history string (last 5 messages)
        history_str = ""
        if chat_history and len(chat_history) > 0:
            history_items = []
            for msg in chat_history[-5:]:
                history_items.append(f"User: {msg.get('user_message', '')}\nAssistant: {msg.get('bot_response', '')}")
            history_str = "\n\n".join(history_items)

        system_message = """You are Atlas AI, an intelligent assistant with comprehensive access to organizational knowledge including Confluence documentation, Jira project management data, Slack messages, GitHub code, and many other integrations.

Your core capabilities:
- Access to internal documentation (Confluence wiki pages, guides, procedures)
- Project tracking and issue management (Jira tickets, sprints, epics)
- Communication history (Slack messages, Teams chats)
- Code repositories (GitHub repos, PRs, issues)
- Design assets (Figma files, components)
- Real-time information retrieval (web search, current events)
- Multi-turn conversation understanding with full context awareness

Guidelines for responses:
1. **Accuracy First**: Base answers strictly on provided context. If information is insufficient, clearly state limitations.
2. **Source Attribution**: Always cite specific sources with titles and URLs when available.
3. **Context Awareness**: Consider the entire conversation history to provide coherent, contextually relevant responses.
4. **Structured Clarity**: Use markdown formatting for better readability (headings, lists, code blocks, tables).
5. **Actionable Insights**: When discussing tickets or tasks, provide actionable next steps or recommendations.
6. **Professional Tone**: Maintain a helpful, professional, and concise communication style.

When answering:
- Prioritize recent conversation context to understand user intent
- Cross-reference information across sources when relevant
- Highlight any conflicts or inconsistencies in the data
- Suggest related resources or follow-up questions when appropriate"""

        user_message_parts = []

        if history_str:
            user_message_parts.append(f"**Previous Conversation:**\n{history_str}\n")

        if context_str:
            user_message_parts.append(f"**Retrieved Context:**\n{context_str}\n")

        user_message_parts.append(f"**Current Question:** {query}\n")
        user_message_parts.append("Please provide a comprehensive, well-structured answer based on the conversation history and retrieved context. Include source citations where applicable.")

        user_message = "\n".join(user_message_parts)

        response = await self.llm_router.chat(user_message, system_message)
        return response

    async def stream_response(self, query: str, context: List[Dict], chat_history: List[Dict] = None) -> AsyncGenerator[str, None]:
        """Generate streaming response using LLM with context and chat history"""
        # Build context string from retrieved documents
        context_str = "\n\n".join([
            f"Source: {doc.get('source', 'unknown')}\nTitle: {doc.get('title', 'N/A')}\nURL: {doc.get('url', 'N/A')}\nContent: {doc.get('content', '')[:500]}"
            for doc in context[:5]
        ])

        # Build chat history string (last 5 messages)
        history_str = ""
        if chat_history and len(chat_history) > 0:
            history_items = []
            for msg in chat_history[-5:]:
                history_items.append(f"User: {msg.get('user_message', '')}\nAssistant: {msg.get('bot_response', '')}")
            history_str = "\n\n".join(history_items)

        system_message = """You are Atlas AI, an intelligent assistant with comprehensive access to organizational knowledge including Confluence documentation, Jira project management data, Slack messages, GitHub code, and many other integrations.

Your core capabilities:
- Access to internal documentation (Confluence wiki pages, guides, procedures)
- Project tracking and issue management (Jira tickets, sprints, epics)
- Communication history (Slack messages, Teams chats)
- Code repositories (GitHub repos, PRs, issues)
- Design assets (Figma files, components)
- Real-time information retrieval (web search, current events)
- Multi-turn conversation understanding with full context awareness

Guidelines for responses:
1. **Accuracy First**: Base answers strictly on provided context. If information is insufficient, clearly state limitations.
2. **Source Attribution**: Always cite specific sources with titles and URLs when available.
3. **Context Awareness**: Consider the entire conversation history to provide coherent, contextually relevant responses.
4. **Structured Clarity**: Use markdown formatting for better readability (headings, lists, code blocks, tables).
5. **Actionable Insights**: When discussing tickets or tasks, provide actionable next steps or recommendations.
6. **Professional Tone**: Maintain a helpful, professional, and concise communication style.

When answering:
- Prioritize recent conversation context to understand user intent
- Cross-reference information across sources when relevant
- Highlight any conflicts or inconsistencies in the data
- Suggest related resources or follow-up questions when appropriate"""

        user_message_parts = []

        if history_str:
            user_message_parts.append(f"**Previous Conversation:**\n{history_str}\n")

        if context_str:
            user_message_parts.append(f"**Retrieved Context:**\n{context_str}\n")

        user_message_parts.append(f"**Current Question:** {query}\n")
        user_message_parts.append("Please provide a comprehensive, well-structured answer based on the conversation history and retrieved context. Include source citations where applicable.")

        user_message = "\n".join(user_message_parts)

        async for chunk in self.llm_router.stream_chat(user_message, system_message):
            yield chunk

    async def query(self, user_query: str) -> Dict:
        """Main query method"""
        try:
            # Determine sources
            sources = await self.determine_source(user_query)
            logger.info(f"Query sources: {sources}")

            # Gather context
            context = await self.gather_context(user_query, sources)
            logger.info(f"Gathered {len(context)} context documents")

            # Generate response
            response = await self.generate_response(user_query, context)

            return {
                'response': response,
                'sources': sources,
                'context': context[:3]  # Return top 3 for reference
            }
        except Exception as e:
            logger.error(f"Query error: {e}")
            return {
                'response': f"Sorry, I encountered an error: {str(e)}",
                'sources': [],
                'context': []
            }
