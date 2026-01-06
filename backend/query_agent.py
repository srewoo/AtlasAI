"""
Query Agent - Intelligent query routing using LLM understanding
Routes queries to the most appropriate sources based on intent analysis.
"""

import logging
import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Types of query intents"""
    TICKET_LOOKUP = "ticket_lookup"          # Specific ticket/issue lookup
    TICKET_SEARCH = "ticket_search"          # Search for tickets matching criteria
    DOCUMENTATION = "documentation"           # Looking for docs/guides/procedures
    PROJECT_STATUS = "project_status"         # Project/sprint/release status
    TEAM_COMMUNICATION = "team_communication" # Slack messages, discussions
    PERSON_LOOKUP = "person_lookup"           # Who is responsible, contact info
    GENERAL_KNOWLEDGE = "general_knowledge"   # General/external information
    CODE_RELATED = "code_related"             # Code, technical implementation
    UNKNOWN = "unknown"


class DataSource(Enum):
    """Available data sources in priority order"""
    JIRA = "jira"
    CONFLUENCE = "confluence"
    SLACK = "slack"
    VECTOR_STORE = "vector_store"
    WEB = "web"  # Lowest priority


@dataclass
class QueryAnalysis:
    """Result of query analysis"""
    original_query: str
    intent: QueryIntent
    entities: Dict[str, str]  # Extracted entities (ticket IDs, project names, etc.)
    recommended_sources: List[DataSource]
    search_queries: Dict[str, str]  # Optimized query for each source
    confidence: float
    reasoning: str


class QueryAgent:
    """
    Intelligent agent that understands queries and routes them to appropriate sources.
    Uses LLM for intent classification and entity extraction.
    """

    # Source priority (lower = higher priority)
    SOURCE_PRIORITY = {
        DataSource.JIRA: 1,
        DataSource.CONFLUENCE: 2,
        DataSource.SLACK: 3,
        DataSource.VECTOR_STORE: 4,
        DataSource.WEB: 5,  # Lowest priority
    }

    # Intent to source mapping
    INTENT_SOURCE_MAP = {
        QueryIntent.TICKET_LOOKUP: [DataSource.JIRA],
        QueryIntent.TICKET_SEARCH: [DataSource.JIRA, DataSource.CONFLUENCE],
        QueryIntent.DOCUMENTATION: [DataSource.CONFLUENCE, DataSource.JIRA],
        QueryIntent.PROJECT_STATUS: [DataSource.JIRA, DataSource.CONFLUENCE, DataSource.SLACK],
        QueryIntent.TEAM_COMMUNICATION: [DataSource.SLACK, DataSource.JIRA],
        QueryIntent.PERSON_LOOKUP: [DataSource.JIRA, DataSource.SLACK, DataSource.CONFLUENCE],
        QueryIntent.CODE_RELATED: [DataSource.CONFLUENCE, DataSource.JIRA, DataSource.WEB],
        QueryIntent.GENERAL_KNOWLEDGE: [DataSource.WEB],
        QueryIntent.UNKNOWN: [DataSource.JIRA, DataSource.CONFLUENCE, DataSource.SLACK],
    }

    def __init__(self, llm_router):
        self.llm_router = llm_router

    async def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Analyze the query using LLM to understand intent and extract entities.
        """
        # First, do quick pattern-based analysis
        quick_analysis = self._quick_pattern_analysis(query)
        if quick_analysis and quick_analysis.confidence > 0.9:
            logger.info(f"Quick analysis matched: {quick_analysis.intent.value}")
            return quick_analysis

        # Use LLM for deeper understanding
        try:
            llm_analysis = await self._llm_analyze(query)
            return llm_analysis
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}, falling back to pattern analysis")
            return quick_analysis or self._fallback_analysis(query)

    def _quick_pattern_analysis(self, query: str) -> Optional[QueryAnalysis]:
        """
        Quick pattern-based analysis for common query types.
        Faster than LLM and handles obvious cases.
        """
        query_lower = query.lower()
        entities = {}

        # Pattern 1: Specific Jira ticket ID (CTT-21761, PROJ-123, etc.)
        ticket_pattern = r'\b([A-Z]{2,10}-\d+)\b'
        ticket_matches = re.findall(ticket_pattern, query, re.IGNORECASE)
        if ticket_matches:
            entities['ticket_ids'] = [t.upper() for t in ticket_matches]
            return QueryAnalysis(
                original_query=query,
                intent=QueryIntent.TICKET_LOOKUP,
                entities=entities,
                recommended_sources=[DataSource.JIRA],
                search_queries={DataSource.JIRA.value: query},
                confidence=0.95,
                reasoning=f"Detected specific Jira ticket ID(s): {entities['ticket_ids']}"
            )

        # Pattern 2: Documentation/guide requests
        doc_patterns = [
            r'(how (do|to|can) (i|we)|guide|tutorial|documentation|docs|procedure|process|steps)',
            r'(where (can i|do i|is)|find .*(document|guide|page|wiki))',
            r'(runbook|playbook|handbook|manual)',
        ]
        for pattern in doc_patterns:
            if re.search(pattern, query_lower):
                return QueryAnalysis(
                    original_query=query,
                    intent=QueryIntent.DOCUMENTATION,
                    entities=entities,
                    recommended_sources=[DataSource.CONFLUENCE, DataSource.JIRA],
                    search_queries={
                        DataSource.CONFLUENCE.value: query,
                        DataSource.JIRA.value: query
                    },
                    confidence=0.85,
                    reasoning="Query appears to be looking for documentation or guides"
                )

        # Pattern 3: Project/Sprint status
        status_patterns = [
            r'(status|progress|update) (of|on|for)',
            r'(sprint|release|milestone|roadmap)',
            r'(what.*(happening|going on|progress))',
        ]
        for pattern in status_patterns:
            if re.search(pattern, query_lower):
                return QueryAnalysis(
                    original_query=query,
                    intent=QueryIntent.PROJECT_STATUS,
                    entities=entities,
                    recommended_sources=[DataSource.JIRA, DataSource.CONFLUENCE, DataSource.SLACK],
                    search_queries={
                        DataSource.JIRA.value: query,
                        DataSource.CONFLUENCE.value: query,
                        DataSource.SLACK.value: query
                    },
                    confidence=0.8,
                    reasoning="Query appears to be about project or sprint status"
                )

        # Pattern 4: Team/Slack communication
        comm_patterns = [
            r'(slack|message|chat|discussion|thread)',
            r'(did (anyone|someone)|who said|was there)',
            r'(meeting|standup|sync|call) (notes|summary)',
        ]
        for pattern in comm_patterns:
            if re.search(pattern, query_lower):
                return QueryAnalysis(
                    original_query=query,
                    intent=QueryIntent.TEAM_COMMUNICATION,
                    entities=entities,
                    recommended_sources=[DataSource.SLACK, DataSource.CONFLUENCE],
                    search_queries={
                        DataSource.SLACK.value: query,
                        DataSource.CONFLUENCE.value: query
                    },
                    confidence=0.85,
                    reasoning="Query appears to be about team communications"
                )

        # Pattern 5: Person lookup
        person_patterns = [
            r'(who (is|are|was)|contact|owner|assignee|responsible)',
            r'(team|person|people|member)',
        ]
        for pattern in person_patterns:
            if re.search(pattern, query_lower):
                return QueryAnalysis(
                    original_query=query,
                    intent=QueryIntent.PERSON_LOOKUP,
                    entities=entities,
                    recommended_sources=[DataSource.JIRA, DataSource.SLACK, DataSource.CONFLUENCE],
                    search_queries={
                        DataSource.JIRA.value: query,
                        DataSource.SLACK.value: query,
                        DataSource.CONFLUENCE.value: query
                    },
                    confidence=0.75,
                    reasoning="Query appears to be looking for person/team information"
                )

        # Pattern 6: Bug/Issue search
        issue_patterns = [
            r'(bug|issue|error|problem|fix|broken)',
            r'(tickets?|issues?) (about|related|for|with)',
        ]
        for pattern in issue_patterns:
            if re.search(pattern, query_lower):
                return QueryAnalysis(
                    original_query=query,
                    intent=QueryIntent.TICKET_SEARCH,
                    entities=entities,
                    recommended_sources=[DataSource.JIRA, DataSource.CONFLUENCE],
                    search_queries={
                        DataSource.JIRA.value: query,
                        DataSource.CONFLUENCE.value: query
                    },
                    confidence=0.8,
                    reasoning="Query appears to be searching for bugs or issues"
                )

        return None

    async def _llm_analyze(self, query: str) -> QueryAnalysis:
        """
        Use LLM to analyze the query for deeper understanding.
        """
        analysis_prompt = f"""Analyze this user query and determine the best way to answer it.

Query: "{query}"

Respond in JSON format with:
{{
    "intent": "<one of: ticket_lookup, ticket_search, documentation, project_status, team_communication, person_lookup, general_knowledge, code_related, unknown>",
    "entities": {{
        "ticket_ids": ["list of any ticket IDs like CTT-123"],
        "project_names": ["list of project names mentioned"],
        "person_names": ["list of person names mentioned"],
        "keywords": ["important search keywords"]
    }},
    "sources": ["ordered list of best sources: jira, confluence, slack, web"],
    "optimized_queries": {{
        "jira": "optimized search query for Jira",
        "confluence": "optimized search query for Confluence",
        "slack": "optimized search query for Slack"
    }},
    "confidence": <0.0 to 1.0>,
    "reasoning": "brief explanation of your analysis"
}}

Important:
- For internal/organizational queries, do NOT include "web" in sources
- "web" should only be included for general knowledge questions about external topics
- Prioritize: jira > confluence > slack > web
"""

        system_prompt = "You are a query analysis assistant. Analyze queries and return structured JSON responses. Be concise and accurate."

        try:
            response = await self.llm_router.chat(analysis_prompt, system_prompt)

            # Parse JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())

                # Map intent string to enum
                intent_map = {
                    'ticket_lookup': QueryIntent.TICKET_LOOKUP,
                    'ticket_search': QueryIntent.TICKET_SEARCH,
                    'documentation': QueryIntent.DOCUMENTATION,
                    'project_status': QueryIntent.PROJECT_STATUS,
                    'team_communication': QueryIntent.TEAM_COMMUNICATION,
                    'person_lookup': QueryIntent.PERSON_LOOKUP,
                    'general_knowledge': QueryIntent.GENERAL_KNOWLEDGE,
                    'code_related': QueryIntent.CODE_RELATED,
                }
                intent = intent_map.get(data.get('intent', 'unknown'), QueryIntent.UNKNOWN)

                # Map sources
                source_map = {
                    'jira': DataSource.JIRA,
                    'confluence': DataSource.CONFLUENCE,
                    'slack': DataSource.SLACK,
                    'web': DataSource.WEB,
                    'vector_store': DataSource.VECTOR_STORE,
                }
                sources = []
                for s in data.get('sources', []):
                    if s.lower() in source_map:
                        sources.append(source_map[s.lower()])

                # Ensure web is last if present
                if DataSource.WEB in sources:
                    sources.remove(DataSource.WEB)
                    sources.append(DataSource.WEB)

                # Build search queries
                search_queries = {}
                opt_queries = data.get('optimized_queries', {})
                for source in sources:
                    if source.value in opt_queries:
                        search_queries[source.value] = opt_queries[source.value]
                    else:
                        search_queries[source.value] = query

                return QueryAnalysis(
                    original_query=query,
                    intent=intent,
                    entities=data.get('entities', {}),
                    recommended_sources=sources if sources else [DataSource.JIRA, DataSource.CONFLUENCE],
                    search_queries=search_queries,
                    confidence=data.get('confidence', 0.7),
                    reasoning=data.get('reasoning', 'LLM analysis')
                )

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")

        return self._fallback_analysis(query)

    def _fallback_analysis(self, query: str) -> QueryAnalysis:
        """
        Fallback analysis when pattern and LLM analysis fail.
        Default to searching internal sources first.
        """
        return QueryAnalysis(
            original_query=query,
            intent=QueryIntent.UNKNOWN,
            entities={},
            recommended_sources=[DataSource.JIRA, DataSource.CONFLUENCE, DataSource.SLACK],
            search_queries={
                DataSource.JIRA.value: query,
                DataSource.CONFLUENCE.value: query,
                DataSource.SLACK.value: query
            },
            confidence=0.5,
            reasoning="Fallback analysis - searching all internal sources"
        )

    def is_source_specific_query(self, analysis: QueryAnalysis) -> bool:
        """Check if the query specifically requires a particular source"""
        source_specific_intents = [
            QueryIntent.TICKET_LOOKUP,      # Requires Jira
            QueryIntent.TEAM_COMMUNICATION, # Requires Slack
        ]
        return analysis.intent in source_specific_intents

    def get_required_source_message(self, analysis: QueryAnalysis) -> str:
        """Get a message about required but unavailable source"""
        messages = {
            QueryIntent.TICKET_LOOKUP: "This query requires Jira access. Please configure your Jira credentials in Settings.",
            QueryIntent.TEAM_COMMUNICATION: "This query requires Slack access. Please configure your Slack Bot Token in Settings to search Slack messages.",
        }
        return messages.get(analysis.intent, "")

    def get_sources_for_intent(self, intent: QueryIntent, available_sources: List[str]) -> List[DataSource]:
        """
        Get recommended sources for an intent, filtered by what's available.
        """
        recommended = self.INTENT_SOURCE_MAP.get(intent, [DataSource.JIRA, DataSource.CONFLUENCE])

        # Filter by available sources
        available_set = set(available_sources)
        filtered = [s for s in recommended if s.value in available_set]

        # Sort by priority
        filtered.sort(key=lambda s: self.SOURCE_PRIORITY.get(s, 99))

        return filtered

    async def route_and_search(
        self,
        query: str,
        jira_client=None,
        confluence_client=None,
        slack_client=None,
        web_client=None,
        vector_store=None
    ) -> Tuple[QueryAnalysis, List[Dict]]:
        """
        Analyze the query and search appropriate sources.
        Returns analysis and results.
        """
        # Analyze the query
        analysis = await self.analyze_query(query)
        logger.info(f"Query analysis: intent={analysis.intent.value}, sources={[s.value for s in analysis.recommended_sources]}")

        all_results = []

        # Search each recommended source in priority order
        for source in analysis.recommended_sources:
            search_query = analysis.search_queries.get(source.value, query)

            try:
                if source == DataSource.JIRA and jira_client:
                    results = jira_client.search_issues(search_query, limit=5)
                    for r in results:
                        r['source'] = 'jira'
                    all_results.extend(results)
                    logger.info(f"Jira returned {len(results)} results")

                elif source == DataSource.CONFLUENCE and confluence_client:
                    results = confluence_client.search_content(search_query, limit=5)
                    for r in results:
                        r['source'] = 'confluence'
                    all_results.extend(results)
                    logger.info(f"Confluence returned {len(results)} results")

                elif source == DataSource.SLACK and slack_client:
                    results = await slack_client.search_messages(search_query, limit=5)
                    for r in results:
                        r['source'] = 'slack'
                    all_results.extend(results)
                    logger.info(f"Slack returned {len(results)} results")

                elif source == DataSource.WEB and web_client:
                    # Only search web if we don't have enough results from internal sources
                    if len(all_results) < 2:
                        results = await web_client.search(search_query, num_results=3)
                        for r in results:
                            r['source'] = 'web'
                        all_results.extend(results)
                        logger.info(f"Web returned {len(results)} results")
                    else:
                        logger.info("Skipping web search - enough internal results")

                elif source == DataSource.VECTOR_STORE and vector_store:
                    results = vector_store.search(search_query, n_results=3)
                    all_results.extend(results)
                    logger.info(f"Vector store returned {len(results)} results")

            except Exception as e:
                logger.error(f"Error searching {source.value}: {e}")

            # Early exit if we have enough good results
            if len(all_results) >= 5 and source != DataSource.WEB:
                break

        return analysis, all_results
