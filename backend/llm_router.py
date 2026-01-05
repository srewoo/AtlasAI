from emergentintegrations.llm.chat import LlmChat, UserMessage
from typing import AsyncGenerator, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class LLMRouter:
    """Routes LLM requests to different providers based on configuration"""
    
    def __init__(self, provider: str, model: str, api_key: str, session_id: str = "default"):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key
        self.session_id = session_id
        
    async def chat(self, user_message: str, system_message: str = "You are a helpful assistant.") -> str:
        """Send a chat message and get response"""
        chat = LlmChat(
            api_key=self.api_key,
            session_id=self.session_id,
            system_message=system_message
        ).with_model(self.provider, self.model)
        
        message = UserMessage(text=user_message)
        response = await chat.send_message(message)
        return response
    
    async def stream_chat(self, user_message: str, system_message: str = "You are a helpful assistant.") -> AsyncGenerator[str, None]:
        """Stream chat responses (simulated for now)"""
        # Note: emergentintegrations doesn't support streaming yet, so we'll return full response
        # In a real implementation, this would yield chunks
        response = await self.chat(user_message, system_message)
        
        # Simulate streaming by yielding in chunks
        chunk_size = 10
        for i in range(0, len(response), chunk_size):
            yield response[i:i+chunk_size]
