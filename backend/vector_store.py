import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict
import logging
import os

logger = logging.getLogger(__name__)

class VectorStore:
    """ChromaDB vector store for RAG"""
    
    def __init__(self, collection_name: str = "chatbot_knowledge"):
        # Initialize ChromaDB with persistent storage
        db_path = os.path.join(os.path.dirname(__file__), "chroma_db")
        os.makedirs(db_path, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
    def add_documents(self, documents: List[Dict], source: str):
        """Add documents to vector store"""
        try:
            ids = []
            texts = []
            metadatas = []
            
            for i, doc in enumerate(documents):
                doc_id = f"{source}_{doc.get('id', i)}"
                text = f"{doc.get('title', '')} {doc.get('content', '')} {doc.get('snippet', '')}"
                
                ids.append(doc_id)
                texts.append(text)
                metadatas.append({
                    'source': source,
                    'title': doc.get('title', ''),
                    'url': doc.get('url', '')
                })
            
            if texts:
                # Generate embeddings
                embeddings = self.embedding_model.encode(texts).tolist()
                
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas
                )
                logger.info(f"Added {len(texts)} documents from {source}")
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
    
    def search(self, query: str, n_results: int = 5, source_filter: str = None) -> List[Dict]:
        """Search vector store"""
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode([query])[0].tolist()
            
            # Build where filter
            where = None
            if source_filter:
                where = {"source": source_filter}
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )
            
            # Format results
            documents = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    documents.append({
                        'content': doc,
                        'title': metadata.get('title', ''),
                        'url': metadata.get('url', ''),
                        'source': metadata.get('source', '')
                    })
            
            return documents
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []
    
    def clear_collection(self):
        """Clear all documents from collection"""
        try:
            self.client.delete_collection(self.collection.name)
            self.collection = self.client.create_collection(
                name=self.collection.name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Collection cleared")
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
