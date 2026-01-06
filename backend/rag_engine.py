from typing import Dict, List, Optional, AsyncGenerator
import logging
from vector_store import VectorStore
from confluence_client import ConfluenceClient
from jira_client import JiraClient
from web_search import WebSearchClient
from llm_router import LLMRouter
import asyncio

logger = logging.getLogger(__name__)

class AgenticRAG:
    """Agentic RAG system that routes queries to appropriate sources"""
    
    def __init__(
        self,
        vector_store: VectorStore,
        llm_router: LLMRouter,
        confluence_client: Optional[ConfluenceClient] = None,
        jira_client: Optional[JiraClient] = None,
        web_search_client: Optional[WebSearchClient] = None
    ):
        self.vector_store = vector_store
        self.llm_router = llm_router
        self.confluence = confluence_client
        self.jira = jira_client
        self.web_search = web_search_client
        
    async def determine_source(self, query: str) -> List[str]:
        """Determine which sources to query based on the question
        Priority order: Confluence → Jira → Web
        Always searches all available sources for comprehensive results"""
        query_lower = query.lower()
        sources = []

        # Check for specific keyword hints to prioritize certain sources
        confluence_keywords = ['document', 'documentation', 'wiki', 'page', 'confluence', 'article', 'guide', 'tutorial', 'how-to', 'procedure']
        jira_keywords = ['issue', 'ticket', 'bug', 'task', 'story', 'epic', 'jira', 'sprint', 'backlog', 'feature']
        web_keywords = ['latest', 'news', 'current', 'today', 'recent', 'what is', 'who is', 'when', 'where']

        has_confluence_keywords = any(keyword in query_lower for keyword in confluence_keywords)
        has_jira_keywords = any(keyword in query_lower for keyword in jira_keywords)
        has_web_keywords = any(keyword in query_lower for keyword in web_keywords)

        # Build sources list in priority order
        # If specific keywords detected, prioritize that source but still search others
        if has_confluence_keywords and self.confluence:
            sources.append('confluence')
            logger.info(f"Confluence keywords detected in query")

        if has_jira_keywords and self.jira:
            if 'jira' not in sources:
                sources.append('jira')
            logger.info(f"Jira keywords detected in query")

        # Add remaining sources in priority order
        if self.confluence and 'confluence' not in sources:
            sources.append('confluence')

        if self.jira and 'jira' not in sources:
            sources.append('jira')

        # Add web search if:
        # 1. Web keywords are present, OR
        # 2. No other sources are available, OR
        # 3. As fallback for comprehensive search
        if self.web_search:
            if has_web_keywords or len(sources) == 0:
                sources.append('web')
            elif len(sources) > 0:
                # Add web as additional source for comprehensive results
                sources.append('web')

        logger.info(f"Determined sources for query: {sources}")
        return sources if sources else ['vector_store']
    
    async def gather_context(self, query: str, sources: List[str]) -> List[Dict]:
        """Gather context from determined sources"""
        all_context = []
        
        # First, always search vector store for existing knowledge
        vector_results = self.vector_store.search(query, n_results=3)
        all_context.extend(vector_results)
        
        # Fetch from sources in parallel
        tasks = []
        
        if 'confluence' in sources and self.confluence:
            tasks.append(self._fetch_confluence(query))
        
        if 'jira' in sources and self.jira:
            tasks.append(self._fetch_jira(query))
        
        if 'web' in sources and self.web_search:
            tasks.append(self._fetch_web(query))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_context.extend(result)
        
        return all_context
    
    async def _fetch_confluence(self, query: str) -> List[Dict]:
        """Fetch from Confluence"""
        try:
            logger.info(f"Fetching Confluence pages for query: {query}")
            pages = self.confluence.search_content(query, limit=5)
            logger.info(f"Confluence returned {len(pages)} pages")
            # Add to vector store for future queries
            if pages:
                self.vector_store.add_documents(pages, 'confluence')
                for page in pages:
                    logger.info(f"  - {page.get('title', '')[:50]}")
            else:
                logger.warning("Confluence search returned no results")
            return pages
        except Exception as e:
            logger.error(f"Confluence fetch error: {e}", exc_info=True)
            return []
    
    async def _fetch_jira(self, query: str) -> List[Dict]:
        """Fetch from Jira"""
        try:
            logger.info(f"Fetching Jira issues for query: {query}")
            issues = self.jira.search_issues(query, limit=5)
            logger.info(f"Jira returned {len(issues)} issues")
            # Add to vector store
            if issues:
                self.vector_store.add_documents(issues, 'jira')
                for issue in issues:
                    logger.info(f"  - {issue.get('key')}: {issue.get('summary', '')[:50]}")
            else:
                logger.warning("Jira search returned no results")
            return issues
        except Exception as e:
            logger.error(f"Jira fetch error: {e}", exc_info=True)
            return []
    
    async def _fetch_web(self, query: str) -> List[Dict]:
        """Fetch from web"""
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
            for msg in chat_history[-5:]:  # Last 5 messages
                history_items.append(f"User: {msg.get('user_message', '')}\nAssistant: {msg.get('bot_response', '')}")
            history_str = "\n\n".join(history_items)

        system_message = """You are Atlas AI, an intelligent assistant with comprehensive access to organizational knowledge including Confluence documentation, Jira project management data, and real-time web information.

Your core capabilities:
- Access to internal documentation (Confluence wiki pages, guides, procedures)
- Project tracking and issue management (Jira tickets, sprints, epics)
- Real-time information retrieval (web search, current events)
- Multi-turn conversation understanding with full context awareness

Guidelines for responses:
1. **Accuracy First**: Base answers strictly on provided context. If information is insufficient, clearly state limitations.
2. **Source Attribution**: Always cite specific sources (Confluence pages, Jira tickets, web articles) with titles and URLs when available.
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
            for msg in chat_history[-5:]:  # Last 5 messages
                history_items.append(f"User: {msg.get('user_message', '')}\nAssistant: {msg.get('bot_response', '')}")
            history_str = "\n\n".join(history_items)

        system_message = """You are Atlas AI, an intelligent assistant with comprehensive access to organizational knowledge including Confluence documentation, Jira project management data, and real-time web information.

Your core capabilities:
- Access to internal documentation (Confluence wiki pages, guides, procedures)
- Project tracking and issue management (Jira tickets, sprints, epics)
- Real-time information retrieval (web search, current events)
- Multi-turn conversation understanding with full context awareness

Guidelines for responses:
1. **Accuracy First**: Base answers strictly on provided context. If information is insufficient, clearly state limitations.
2. **Source Attribution**: Always cite specific sources (Confluence pages, Jira tickets, web articles) with titles and URLs when available.
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
