"""
Document Chunking and Token Management
Handles splitting large documents into optimal chunks for LLM processing
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChunkConfig:
    """Configuration for chunking"""
    max_chunk_size: int = 512       # tokens
    chunk_overlap: int = 50         # tokens
    min_chunk_size: int = 100       # tokens
    max_chunks_per_doc: int = 20
    separator_priority: List[str] = None  # Custom separators

    def __post_init__(self):
        if self.separator_priority is None:
            self.separator_priority = [
                "\n\n\n",    # Triple newline (section breaks)
                "\n\n",      # Paragraph breaks
                "\n",        # Line breaks
                ". ",        # Sentences
                "! ",
                "? ",
                "; ",        # Semi-colons
                ", ",        # Commas
                " ",         # Words
            ]


class TokenCounter:
    """
    Token counter for different models
    Uses simple estimation for speed, with option for precise counting
    """

    # Average characters per token for different models
    CHARS_PER_TOKEN = {
        "gpt-4": 4.0,
        "gpt-3.5-turbo": 4.0,
        "claude": 3.5,
        "gemini": 4.0,
        "default": 4.0
    }

    def __init__(self, model: str = "default"):
        self.model = model
        self.chars_per_token = self.CHARS_PER_TOKEN.get(model, self.CHARS_PER_TOKEN["default"])
        self._tokenizer = None

    def count(self, text: str) -> int:
        """
        Count tokens in text

        Args:
            text: Text to count tokens in

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        # Fast estimation
        return int(len(text) / self.chars_per_token)

    def count_precise(self, text: str) -> int:
        """
        Count tokens precisely using tiktoken (if available)
        Falls back to estimation if tiktoken not available
        """
        try:
            if self._tokenizer is None:
                import tiktoken
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            return len(self._tokenizer.encode(text))
        except ImportError:
            return self.count(text)

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to approximately max_tokens"""
        max_chars = int(max_tokens * self.chars_per_token)
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."


class DocumentChunker:
    """
    Intelligent document chunker with multiple strategies
    """

    def __init__(self, config: Optional[ChunkConfig] = None, model: str = "default"):
        self.config = config or ChunkConfig()
        self.token_counter = TokenCounter(model)

    def chunk_text(self, text: str, metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks optimized for LLM processing

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text:
            return []

        # If text is small enough, return as single chunk
        token_count = self.token_counter.count(text)
        if token_count <= self.config.max_chunk_size:
            return [self._create_chunk(text, 0, metadata)]

        # Split into chunks
        chunks = self._recursive_split(text)

        # Limit number of chunks
        if len(chunks) > self.config.max_chunks_per_doc:
            logger.warning(
                f"Document has {len(chunks)} chunks, limiting to {self.config.max_chunks_per_doc}"
            )
            chunks = chunks[:self.config.max_chunks_per_doc]

        # Create chunk objects with metadata
        result = []
        for i, chunk_text in enumerate(chunks):
            result.append(self._create_chunk(chunk_text, i, metadata))

        return result

    def _recursive_split(self, text: str, depth: int = 0) -> List[str]:
        """
        Recursively split text using separator hierarchy
        """
        if depth >= len(self.config.separator_priority):
            # No more separators, force split by characters
            return self._force_split(text)

        separator = self.config.separator_priority[depth]
        parts = text.split(separator)

        # If only one part, try next separator
        if len(parts) == 1:
            return self._recursive_split(text, depth + 1)

        chunks = []
        current_chunk = ""

        for part in parts:
            # Check if adding this part would exceed limit
            potential_chunk = current_chunk + separator + part if current_chunk else part
            potential_tokens = self.token_counter.count(potential_chunk)

            if potential_tokens <= self.config.max_chunk_size:
                current_chunk = potential_chunk
            else:
                # Save current chunk if it meets minimum size
                if current_chunk and self.token_counter.count(current_chunk) >= self.config.min_chunk_size:
                    chunks.append(current_chunk)

                # Check if this part alone is too large
                part_tokens = self.token_counter.count(part)
                if part_tokens > self.config.max_chunk_size:
                    # Recursively split this part
                    sub_chunks = self._recursive_split(part, depth + 1)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = part

        # Don't forget the last chunk
        if current_chunk and self.token_counter.count(current_chunk) >= self.config.min_chunk_size:
            chunks.append(current_chunk)

        return chunks

    def _force_split(self, text: str) -> List[str]:
        """Force split text by character count when no separators work"""
        chunks = []
        chars_per_chunk = int(self.config.max_chunk_size * self.token_counter.chars_per_token)
        overlap_chars = int(self.config.chunk_overlap * self.token_counter.chars_per_token)

        start = 0
        while start < len(text):
            end = start + chars_per_chunk
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap_chars

        return chunks

    def _create_chunk(self, text: str, index: int, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a chunk object with metadata"""
        chunk = {
            "text": text.strip(),
            "chunk_index": index,
            "token_count": self.token_counter.count(text),
            "char_count": len(text)
        }

        if metadata:
            chunk["metadata"] = metadata

        return chunk

    def chunk_with_overlap(self, text: str, metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Create overlapping chunks for better context preservation
        """
        chunks = self.chunk_text(text, metadata)

        if len(chunks) <= 1:
            return chunks

        # Add overlap text to each chunk
        result = []
        for i, chunk in enumerate(chunks):
            chunk_text = chunk["text"]

            # Add previous chunk overlap
            if i > 0:
                prev_text = chunks[i-1]["text"]
                overlap = self._get_tail(prev_text, self.config.chunk_overlap)
                chunk_text = overlap + " ... " + chunk_text

            # Add next chunk overlap
            if i < len(chunks) - 1:
                next_text = chunks[i+1]["text"]
                overlap = self._get_head(next_text, self.config.chunk_overlap)
                chunk_text = chunk_text + " ... " + overlap

            result.append({
                **chunk,
                "text": chunk_text,
                "token_count": self.token_counter.count(chunk_text)
            })

        return result

    def _get_tail(self, text: str, tokens: int) -> str:
        """Get approximately the last N tokens of text"""
        chars = int(tokens * self.token_counter.chars_per_token)
        if len(text) <= chars:
            return text
        return "..." + text[-chars:]

    def _get_head(self, text: str, tokens: int) -> str:
        """Get approximately the first N tokens of text"""
        chars = int(tokens * self.token_counter.chars_per_token)
        if len(text) <= chars:
            return text
        return text[:chars] + "..."


class ParallelChunkProcessor:
    """
    Process chunks in parallel for faster embedding and analysis
    """

    def __init__(self, max_parallel: int = 5):
        self.max_parallel = max_parallel

    async def process_chunks(
        self,
        chunks: List[Dict],
        processor: callable,
        *args,
        **kwargs
    ) -> List[Any]:
        """
        Process chunks in parallel batches

        Args:
            chunks: List of chunks to process
            processor: Async function to process each chunk
            *args, **kwargs: Additional arguments for processor

        Returns:
            List of processed results
        """
        import asyncio

        results = []
        for i in range(0, len(chunks), self.max_parallel):
            batch = chunks[i:i + self.max_parallel]
            batch_tasks = [
                processor(chunk, *args, **kwargs)
                for chunk in batch
            ]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Chunk processing error: {result}")
                    results.append(None)
                else:
                    results.append(result)

        return results


def estimate_context_tokens(documents: List[Dict], max_tokens: int = 4096) -> Tuple[List[Dict], int]:
    """
    Estimate and limit documents to fit within context window

    Args:
        documents: List of document dictionaries with 'content' field
        max_tokens: Maximum tokens for context

    Returns:
        Tuple of (limited documents, total tokens)
    """
    counter = TokenCounter()
    total_tokens = 0
    result = []

    for doc in documents:
        content = doc.get('content', '')
        tokens = counter.count(content)

        if total_tokens + tokens <= max_tokens:
            result.append(doc)
            total_tokens += tokens
        else:
            # Try to fit partial content
            remaining = max_tokens - total_tokens
            if remaining > 100:  # Minimum useful content
                truncated_content = counter.truncate_to_tokens(content, remaining)
                result.append({**doc, 'content': truncated_content})
                total_tokens = max_tokens
            break

    return result, total_tokens
