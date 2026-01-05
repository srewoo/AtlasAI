"""
LLM Router - Direct API calls to OpenAI, Anthropic, and Google Gemini
No third-party tracking or proprietary libraries
"""

from typing import AsyncGenerator, Optional
import os
from dotenv import load_dotenv

load_dotenv()


class LLMRouter:
    """Routes LLM requests to different providers using native APIs"""
    
    def __init__(self, provider: str, model: str, api_key: str, session_id: str = "default"):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key
        self.session_id = session_id
        
    async def chat(self, user_message: str, system_message: str = "You are a helpful assistant.") -> str:
        """Send a chat message and get response from the appropriate provider"""
        
        if self.provider == "openai":
            return await self._chat_openai(user_message, system_message)
        elif self.provider == "anthropic":
            return await self._chat_anthropic(user_message, system_message)
        elif self.provider in ["gemini", "google"]:
            return await self._chat_gemini(user_message, system_message)
        elif self.provider == "ollama":
            return await self._chat_ollama(user_message, system_message)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def _chat_openai(self, user_message: str, system_message: str) -> str:
        """OpenAI API call"""
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=self.api_key)
        
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    
    async def _chat_anthropic(self, user_message: str, system_message: str) -> str:
        """Anthropic Claude API call"""
        from anthropic import AsyncAnthropic
        
        client = AsyncAnthropic(api_key=self.api_key)
        
        response = await client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_message,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        return response.content[0].text
    
    async def _chat_gemini(self, user_message: str, system_message: str) -> str:
        """Google Gemini API call"""
        import google.generativeai as genai
        
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        
        # Combine system and user messages for Gemini
        full_prompt = f"{system_message}\n\nUser: {user_message}"
        
        response = await model.generate_content_async(full_prompt)
        return response.text
    
    async def _chat_ollama(self, user_message: str, system_message: str) -> str:
        """Ollama local model API call"""
        import aiohttp
        
        # Default Ollama endpoint
        ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"{system_message}\n\nUser: {user_message}",
                    "stream": False
                }
            ) as response:
                data = await response.json()
                return data.get('response', '')
    
    async def stream_chat(self, user_message: str, system_message: str = "You are a helpful assistant.") -> AsyncGenerator[str, None]:
        """Stream chat responses"""
        # For now, return full response (can be enhanced for true streaming)
        response = await self.chat(user_message, system_message)
        
        # Yield in chunks to simulate streaming
        chunk_size = 10
        for i in range(0, len(response), chunk_size):
            yield response[i:i+chunk_size]
