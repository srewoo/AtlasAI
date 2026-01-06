from typing import Dict, List, Optional, AsyncGenerator
import logging
from vector_store import VectorStore
from confluence_client import ConfluenceClient
from jira_client import JiraClient
from web_search import WebSearchClient
from llm_router import LLMRouter
from security import validate_query, get_security_enhanced_system_prompt, analyze_risk_level
from query_agent import QueryAgent, QueryAnalysis, DataSource, QueryIntent
import asyncio

logger = logging.getLogger(__name__)


class AgenticRAG:
    """Agentic RAG system with intelligent query routing"""

    def __init__(
        self,
        vector_store: VectorStore,
        llm_router: LLMRouter,
        confluence_client: Optional[ConfluenceClient] = None,
        jira_client: Optional[JiraClient] = None,
        slack_client=None,  # Optional SlackClient
        web_search_client: Optional[WebSearchClient] = None
    ):
        self.vector_store = vector_store
        self.llm_router = llm_router
        self.confluence = confluence_client
        self.jira = jira_client
        self.slack = slack_client
        self.web_search = web_search_client

        # Initialize the intelligent query agent
        self.query_agent = QueryAgent(llm_router)

    async def determine_source(self, query: str) -> tuple[List[str], QueryAnalysis]:
        """
        Determine which sources to query using the intelligent QueryAgent.
        Returns tuple of (source names list, analysis) for better handling.
        """
        try:
            # Use the intelligent agent to analyze the query
            analysis = await self.query_agent.analyze_query(query)

            # Convert DataSource enums to strings
            sources = [s.value for s in analysis.recommended_sources]

            # Filter by available clients
            available_sources = []
            if self.jira and 'jira' in sources:
                available_sources.append('jira')
            if self.confluence and 'confluence' in sources:
                available_sources.append('confluence')
            if self.slack and 'slack' in sources:
                available_sources.append('slack')
            if self.web_search and 'web' in sources:
                available_sources.append('web')

            logger.info(f"Query analysis: intent={analysis.intent.value}, confidence={analysis.confidence}")
            logger.info(f"Recommended sources: {sources}, available: {available_sources}")
            logger.info(f"Reasoning: {analysis.reasoning}")

            # Store analysis for later use
            self._last_analysis = analysis

            return available_sources if available_sources else ['vector_store'], analysis

        except Exception as e:
            logger.error(f"Query agent failed: {e}, using fallback routing")
            sources = self._fallback_determine_source(query)
            return sources, None

    def check_required_source_available(self, analysis: QueryAnalysis) -> tuple[bool, str]:
        """
        Check if the required source for a specific query type is available.
        Returns (is_available, message_if_not_available)
        """
        if not analysis:
            return True, ""

        # Map intents to required sources
        intent_required_source = {
            QueryIntent.TICKET_LOOKUP: ('jira', self.jira),
            QueryIntent.TEAM_COMMUNICATION: ('slack', self.slack),
        }

        if analysis.intent in intent_required_source:
            source_name, client = intent_required_source[analysis.intent]
            if not client:
                message = self.query_agent.get_required_source_message(analysis)
                return False, message

        return True, ""

    def _fallback_determine_source(self, query: str) -> List[str]:
        """Fallback keyword-based routing if agent fails"""
        import re
        query_lower = query.lower()
        sources = []

        # Check for specific Jira ticket ID
        jira_ticket_pattern = r'\b[A-Z]{2,10}-\d+\b'
        if re.search(jira_ticket_pattern, query, re.IGNORECASE):
            if self.jira:
                sources.append('jira')
            return sources if sources else ['jira']

        # Default: search internal sources first
        if self.jira:
            sources.append('jira')
        if self.confluence:
            sources.append('confluence')
        if self.slack:
            sources.append('slack')

        return sources if sources else ['vector_store']

    async def gather_context(self, query: str, sources: List[str]) -> List[Dict]:
        """Gather context from determined sources"""
        all_context = []

        # Fetch from live sources in parallel
        tasks = []

        if 'jira' in sources and self.jira:
            tasks.append(self._fetch_jira(query))

        if 'confluence' in sources and self.confluence:
            tasks.append(self._fetch_confluence(query))

        if 'slack' in sources and self.slack:
            tasks.append(self._fetch_slack(query))

        if 'web' in sources and self.web_search:
            tasks.append(self._fetch_web(query))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_context.extend(result)

        # Only search vector store if we didn't get enough results
        if len(all_context) < 2:
            vector_results = self.vector_store.search(query, n_results=3)
            # Filter to relevant sources only
            relevant_sources = set(sources + ['confluence', 'jira', 'slack'])
            filtered_vector = [
                doc for doc in vector_results
                if doc.get('source', 'unknown') in relevant_sources
            ]
            all_context.extend(filtered_vector)

        return all_context

    async def _fetch_jira(self, query: str) -> List[Dict]:
        """Fetch from Jira"""
        try:
            logger.info(f"Fetching Jira issues for query: {query}")
            issues = self.jira.search_issues(query, limit=5)
            logger.info(f"Jira returned {len(issues)} issues")
            if issues:
                self.vector_store.add_documents(issues, 'jira')
                for issue in issues:
                    logger.info(f"  - {issue.get('key')}: {issue.get('summary', '')[:50]}")
            return issues
        except Exception as e:
            logger.error(f"Jira fetch error: {e}", exc_info=True)
            return []

    async def _fetch_confluence(self, query: str) -> List[Dict]:
        """Fetch from Confluence"""
        try:
            logger.info(f"Fetching Confluence pages for query: {query}")
            pages = self.confluence.search_content(query, limit=5)
            logger.info(f"Confluence returned {len(pages)} pages")
            if pages:
                self.vector_store.add_documents(pages, 'confluence')
                for page in pages:
                    logger.info(f"  - {page.get('title', '')[:50]}")
            return pages
        except Exception as e:
            logger.error(f"Confluence fetch error: {e}", exc_info=True)
            return []

    async def _fetch_slack(self, query: str) -> List[Dict]:
        """Fetch from Slack"""
        try:
            logger.info(f"Fetching Slack messages for query: {query}")
            messages = await self.slack.search_messages(query, limit=5)
            logger.info(f"Slack returned {len(messages)} messages")
            if messages:
                self.vector_store.add_documents(messages, 'slack')
                for msg in messages:
                    logger.info(f"  - {msg.get('title', '')[:50]}")
            return messages
        except Exception as e:
            logger.error(f"Slack fetch error: {e}", exc_info=True)
            return []

    async def _fetch_web(self, query: str) -> List[Dict]:
        """Fetch from web - lowest priority"""
        try:
            logger.info(f"Fetching web results for query: {query}")
            results = await self.web_search.search(query, num_results=3)
            if results:
                self.vector_store.add_documents(results, 'web')
            return results
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return []

    async def generate_response(self, query: str, context: List[Dict], chat_history: List[Dict] = None) -> str:
        """Generate response using LLM with context and chat history"""
        # Validate and sanitize query for security
        is_valid, sanitized_query, error = validate_query(query)
        if not is_valid:
            logger.warning(f"Invalid query rejected: {error}")
            return f"I couldn't process that query. {error}"

        # Log risk level for monitoring
        risk = analyze_risk_level(query)
        if risk["risk_level"] in ["medium", "high"]:
            logger.warning(f"Query risk level: {risk['risk_level']}, flags: {risk['flags']}")

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

        base_system_message = """You are Atlas AI, an intelligent assistant with comprehensive access to organizational knowledge including Confluence documentation, Jira project management data, Slack communications, and real-time web information.

Your core capabilities:
- Access to internal documentation (Confluence wiki pages, guides, procedures)
- Project tracking and issue management (Jira tickets, sprints, epics)
- Team communications (Slack messages, discussions)
- Real-time information retrieval (web search, current events)
- Multi-turn conversation understanding with full context awareness

Guidelines for responses:
1. **Accuracy First**: Base answers strictly on provided context. If information is insufficient, clearly state limitations.
2. **Source Attribution**: Always cite specific sources (Confluence pages, Jira tickets, Slack messages, web articles) with titles and URLs when available.
3. **Context Awareness**: Consider the entire conversation history to provide coherent, contextually relevant responses.
4. **Structured Clarity**: Use markdown formatting for better readability (headings, lists, code blocks, tables).
5. **Actionable Insights**: When discussing tickets or tasks, provide actionable next steps or recommendations.
6. **Professional Tone**: Maintain a helpful, professional, and concise communication style.

When answering:
- Prioritize internal sources (Jira, Confluence, Slack) over web results
- Cross-reference information across sources when relevant
- Highlight any conflicts or inconsistencies in the data
- Suggest related resources or follow-up questions when appropriate"""

        # Apply security enhancements to system prompt
        system_message = get_security_enhanced_system_prompt(base_system_message)

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
        # Validate and sanitize query for security
        is_valid, sanitized_query, error = validate_query(query)
        if not is_valid:
            logger.warning(f"Invalid query rejected in stream: {error}")
            yield f"I couldn't process that query. {error}"
            return

        # Log risk level for monitoring
        risk = analyze_risk_level(query)
        if risk["risk_level"] in ["medium", "high"]:
            logger.warning(f"Query risk level: {risk['risk_level']}, flags: {risk['flags']}")

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

        base_system_message = """You are Atlas AI, an intelligent assistant with comprehensive access to organizational knowledge including Confluence documentation, Jira project management data, Slack communications, and real-time web information.

Your core capabilities:
- Access to internal documentation (Confluence wiki pages, guides, procedures)
- Project tracking and issue management (Jira tickets, sprints, epics)
- Team communications (Slack messages, discussions)
- Real-time information retrieval (web search, current events)
- Multi-turn conversation understanding with full context awareness

Guidelines for responses:
1. **Accuracy First**: Base answers strictly on provided context. If information is insufficient, clearly state limitations.
2. **Source Attribution**: Always cite specific sources (Confluence pages, Jira tickets, Slack messages, web articles) with titles and URLs when available.
3. **Context Awareness**: Consider the entire conversation history to provide coherent, contextually relevant responses.
4. **Structured Clarity**: Use markdown formatting for better readability (headings, lists, code blocks, tables).
5. **Actionable Insights**: When discussing tickets or tasks, provide actionable next steps or recommendations.
6. **Professional Tone**: Maintain a helpful, professional, and concise communication style.

When answering:
- Prioritize internal sources (Jira, Confluence, Slack) over web results
- Cross-reference information across sources when relevant
- Highlight any conflicts or inconsistencies in the data
- Suggest related resources or follow-up questions when appropriate"""

        # Apply security enhancements to system prompt
        system_message = get_security_enhanced_system_prompt(base_system_message)

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
            # Validate query for security
            is_valid, sanitized_query, error = validate_query(user_query)
            if not is_valid:
                logger.warning(f"Query validation failed: {error}")
                return {
                    'response': f"I couldn't process that query. {error}",
                    'sources': [],
                    'context': []
                }

            # Use sanitized query for processing
            user_query = sanitized_query

            # Determine sources using intelligent agent
            sources, analysis = await self.determine_source(user_query)
            logger.info(f"Query sources: {sources}")

            # Check if required source is available for this query type
            is_available, unavailable_message = self.check_required_source_available(analysis)
            if not is_available:
                logger.warning(f"Required source not available: {unavailable_message}")
                return {
                    'response': unavailable_message,
                    'sources': [],
                    'context': [],
                    'requires_setup': True
                }

            # Gather context
            context = await self.gather_context(user_query, sources)
            logger.info(f"Gathered {len(context)} context documents")

            # Generate response
            response = await self.generate_response(user_query, context)

            return {
                'response': response,
                'sources': sources,
                'context': context[:3]
            }
        except Exception as e:
            logger.error(f"Query error: {e}")
            return {
                'response': f"Sorry, I encountered an error: {str(e)}",
                'sources': [],
                'context': []
            }
