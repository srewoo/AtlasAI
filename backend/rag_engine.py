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
        """Determine which sources to query based on the question"""
        # Simple keyword-based routing (can be enhanced with LLM-based classification)
        query_lower = query.lower()
        sources = []
        
        # Check for Confluence-related keywords
        confluence_keywords = ['document', 'documentation', 'wiki', 'page', 'confluence', 'article']
        if any(keyword in query_lower for keyword in confluence_keywords) and self.confluence:
            sources.append('confluence')
        
        # Check for Jira-related keywords
        jira_keywords = ['issue', 'ticket', 'bug', 'task', 'story', 'epic', 'jira', 'sprint']
        if any(keyword in query_lower for keyword in jira_keywords) and self.jira:
            sources.append('jira')
        
        # Check for web search keywords or if no specific source matched
        web_keywords = ['latest', 'news', 'current', 'today', 'recent', 'how to', 'what is']
        if any(keyword in query_lower for keyword in web_keywords) or not sources:
            if self.web_search:
                sources.append('web')
        
        # If no sources determined, use all available
        if not sources:
            if self.confluence:
                sources.append('confluence')
            if self.jira:
                sources.append('jira')
        
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
            pages = self.confluence.search_content(query, limit=3)
            # Add to vector store for future queries
            if pages:
                self.vector_store.add_documents(pages, 'confluence')
            return pages
        except Exception as e:
            logger.error(f"Confluence fetch error: {e}")
            return []
    
    async def _fetch_jira(self, query: str) -> List[Dict]:
        """Fetch from Jira"""
        try:
            issues = self.jira.search_issues(query, limit=3)
            # Add to vector store
            if issues:
                self.vector_store.add_documents(issues, 'jira')
            return issues
        except Exception as e:
            logger.error(f"Jira fetch error: {e}")
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
    
    async def generate_response(self, query: str, context: List[Dict]) -> str:
        """Generate response using LLM with context"""
        # Build context string
        context_str = "\n\n".join([
            f"Source: {doc.get('source', 'unknown')}\nTitle: {doc.get('title', 'N/A')}\nURL: {doc.get('url', 'N/A')}\nContent: {doc.get('content', '')[:500]}"
            for doc in context[:5]
        ])
        
        system_message = """You are a helpful assistant with access to Confluence, Jira, and web information. 
        Use the provided context to answer questions accurately. If the context doesn't contain relevant information, 
        say so and provide a general answer if possible. Always cite your sources when using information from the context."""
        
        user_message = f"""Context:
{context_str}

Question: {query}

Please provide a comprehensive answer based on the context above."""
        
        response = await self.llm_router.chat(user_message, system_message)
        return response
    
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
