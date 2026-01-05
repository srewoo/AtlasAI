"""
Lightweight Vector Store - Optimized for Render.com free tier (512MB RAM)
Uses simple in-memory storage instead of ChromaDB to save memory
"""

from typing import List, Dict
import logging
import hashlib

logger = logging.getLogger(__name__)


class VectorStore:
    """Lightweight in-memory vector store - no heavy ML models needed"""
    
    def __init__(self, collection_name: str = "chatbot_knowledge"):
        # Simple in-memory storage
        self.documents = []
        self.collection_name = collection_name
        logger.info(f"Initialized lightweight vector store: {collection_name}")
        
    def add_documents(self, documents: List[Dict], source: str):
        """Add documents to in-memory store"""
        try:
            for i, doc in enumerate(documents):
                doc_id = f"{source}_{doc.get('id', i)}"
                text = f"{doc.get('title', '')} {doc.get('content', '')} {doc.get('snippet', '')}"
                
                self.documents.append({
                    'id': doc_id,
                    'text': text.lower(),  # lowercase for simple matching
                    'source': source,
                    'title': doc.get('title', ''),
                    'url': doc.get('url', ''),
                    'content': text[:500]  # Keep first 500 chars
                })
                
            logger.info(f"Added {len(documents)} documents from {source}")
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
    
    def search(self, query: str, n_results: int = 5, source_filter: str = None) -> List[Dict]:
        """Simple keyword-based search (no ML embeddings needed)"""
        try:
            query_lower = query.lower()
            query_words = set(query_lower.split())
            
            # Score documents by keyword matches
            scored_docs = []
            for doc in self.documents:
                # Filter by source if specified
                if source_filter and doc['source'] != source_filter:
                    continue
                
                # Count matching words
                doc_words = set(doc['text'].split())
                matches = len(query_words & doc_words)
                
                if matches > 0:
                    scored_docs.append((matches, doc))
            
            # Sort by score and return top n
            scored_docs.sort(reverse=True, key=lambda x: x[0])
            results = [doc for score, doc in scored_docs[:n_results]]
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []
    
    def clear_collection(self):
        """Clear all documents"""
        try:
            self.documents = []
            logger.info("Collection cleared")
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
