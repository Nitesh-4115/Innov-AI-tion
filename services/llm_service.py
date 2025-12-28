"""
LLM Service
Centralized service for all LLM interactions using Cerebras
"""

import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
import json
import re
import asyncio
from datetime import datetime

import requests

from config import settings


logger = logging.getLogger(__name__)


class LLMService:
    """
    Service for interacting with Cerebras LLM
    Handles all AI model calls for the application
    """
    
    def __init__(self):
        self.model_name = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.provider = "cerebras"  # Cerebras only
        
        # Provider state
        self._configured = False
        
        # Usage tracking
        self._total_tokens_used = 0
        self._request_count = 0
        
        # Configure on init
        self._configure()
    
    def _configure(self):
        """Configure the Cerebras LLM provider"""
        if self._configured:
            return

        if not settings.CEREBRAS_API_KEY:
            logger.warning("CEREBRAS_API_KEY not configured")
            return
        # No client configuration required; just mark configured
        self._configured = True
        logger.info(f"Cerebras API configured with model: {self.model_name}")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """
        Generate a response from the LLM
        
        Args:
            prompt: User prompt/message
            system_prompt: System instructions
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum response tokens
            stop_sequences: Sequences that stop generation
            
        Returns:
            Generated text response
        """
        return await self._generate_cerebras(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stop_sequences=stop_sequences,
        )
    
    async def generate_with_context(
        self,
        prompt: str,
        context: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate response with additional context (for RAG)
        
        Args:
            prompt: User question/request
            context: Retrieved context to include
            system_prompt: System instructions
            
        Returns:
            Generated response
        """
        augmented_prompt = f"""Context information:
{context}

---

Based on the context above, please answer the following:
{prompt}"""
        
        return await self.generate(
            prompt=augmented_prompt,
            system_prompt=system_prompt,
            **kwargs
        )
    
    async def generate_json(
        self,
        prompt: str,
        schema_hint: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a JSON response from the LLM
        
        Args:
            prompt: User prompt
            schema_hint: Example of expected JSON structure
            system_prompt: System instructions
            
        Returns:
            Parsed JSON response
        """
        json_system = system_prompt or ""
        json_system += "\n\nYou must respond with valid JSON only. No additional text, no markdown code blocks, just pure JSON."
        
        if schema_hint:
            json_system += f"\n\nExpected JSON structure:\n{json.dumps(schema_hint, indent=2)}"
        
        response = await self.generate(
            prompt=prompt,
            system_prompt=json_system,
            **kwargs
        )
        
        return self.parse_json_response(response)

    async def _generate_cerebras(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> str:
        """Generate via Cerebras (OpenAI-compatible chat API)."""
        if not self._configured:
            self._configure()
        if not self._configured:
            raise RuntimeError("Cerebras is not configured. Set CEREBRAS_API_KEY.")

        headers = {
            "Authorization": f"Bearer {settings.CEREBRAS_API_KEY}",
            "Content-Type": "application/json",
        }

        # Inject time context into system prompt so models receive current time
        def _time_context() -> str:
            now_local = datetime.now().astimezone()
            now_utc = datetime.utcnow().replace(tzinfo=None)
            return (
                f"Time Context:\n"
                f"- UTC: {now_utc.isoformat()}Z\n"
                f"- Local: {now_local.isoformat()} ({now_local.tzname() or 'local'})\n"
            )

        if system_prompt:
            system_prompt = f"{system_prompt}\n\n{_time_context()}"
        else:
            system_prompt = _time_context()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }
        if stop_sequences:
            payload["stop"] = stop_sequences

        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: requests.post(
                    f"{settings.CEREBRAS_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30,
                ),
            )

            if resp.status_code != 200:
                logger.error("Cerebras API error %s: %s", resp.status_code, resp.text)
                raise RuntimeError(f"Cerebras API error: {resp.status_code}")

            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                return ""
            text = choices[0].get("message", {}).get("content", "")

            usage = data.get("usage") or {}
            self._total_tokens_used += usage.get("total_tokens", 0)
            self._request_count += 1

            return text
        except Exception as e:
            logger.error("Cerebras generation error: %s", e)
            raise


    
    def parse_json_response(
        self,
        response: str,
        default: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse JSON from LLM response, handling common issues
        
        Args:
            response: Raw LLM response
            default: Default value if parsing fails
            
        Returns:
            Parsed JSON dictionary
        """
        if default is None:
            default = {}
        
        if not response:
            return default
        
        # Clean up the response
        response = response.strip()
        
        try:
            # Try direct parsing first
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'\{[\s\S]*\}',
            r'\[[\s\S]*\]'
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, response)
            if match:
                try:
                    json_str = match.group(1) if '```' in pattern else match.group(0)
                    return json.loads(json_str.strip())
                except json.JSONDecodeError:
                    continue
        
        logger.warning(f"Failed to parse JSON from response: {response[:200]}...")
        return default
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Multi-turn conversation
        
        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            system_prompt: System instructions
            
        Returns:
            Assistant's response
        """
        try:
            if not self._configured:
                self._configure()
            if not self._configured:
                raise RuntimeError("Cerebras is not configured. Set CEREBRAS_API_KEY.")

            headers = {
                "Authorization": f"Bearer {settings.CEREBRAS_API_KEY}",
                "Content-Type": "application/json",
            }

            # Build messages list for Cerebras
            api_messages = []
            # Inject time context for chat-style calls as well
            def _time_context() -> str:
                now_local = datetime.now().astimezone()
                now_utc = datetime.utcnow().replace(tzinfo=None)
                return (
                    f"Time Context:\n"
                    f"- UTC: {now_utc.isoformat()}Z\n"
                    f"- Local: {now_local.isoformat()} ({now_local.tzname() or 'local'})\n"
                )

            if system_prompt:
                system_prompt = f"{system_prompt}\n\n{_time_context()}"
            else:
                system_prompt = _time_context()

            if system_prompt:
                api_messages.append({"role": "system", "content": system_prompt})
            for msg in messages:
                role = "assistant" if msg["role"] == "assistant" else "user"
                api_messages.append({"role": role, "content": msg["content"]})

            payload = {
                "model": self.model_name,
                "messages": api_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: requests.post(
                    f"{settings.CEREBRAS_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30,
                ),
            )

            if resp.status_code != 200:
                logger.error("Cerebras API error %s: %s", resp.status_code, resp.text)
                raise RuntimeError(f"Cerebras API error: {resp.status_code}")

            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                return ""
            text = choices[0].get("message", {}).get("content", "")

            usage = data.get("usage") or {}
            self._total_tokens_used += usage.get("total_tokens", 0)
            self._request_count += 1

            return text
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise
    
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream generated response (Cerebras streaming)
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            
        Yields:
            Text chunks as they're generated
        """
        try:
            if not self._configured:
                self._configure()
            if not self._configured:
                raise RuntimeError("Cerebras is not configured. Set CEREBRAS_API_KEY.")

            headers = {
                "Authorization": f"Bearer {settings.CEREBRAS_API_KEY}",
                "Content-Type": "application/json",
            }

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
            }

            # Use synchronous streaming in executor
            def _stream():
                with requests.post(
                    f"{settings.CEREBRAS_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60,
                    stream=True,
                ) as resp:
                    if resp.status_code != 200:
                        raise RuntimeError(f"Cerebras API error: {resp.status_code}")
                    for line in resp.iter_lines():
                        if line:
                            line_str = line.decode("utf-8")
                            if line_str.startswith("data: "):
                                data_str = line_str[6:]
                                if data_str.strip() == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_str)
                                    delta = data.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                                except json.JSONDecodeError:
                                    pass

            loop = asyncio.get_event_loop()
            for chunk in await loop.run_in_executor(None, lambda: list(_stream())):
                yield chunk
                    
        except Exception as e:
            logger.error(f"Stream error: {e}")
            raise
    
    async def analyze_text(
        self,
        text: str,
        analysis_type: str,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze text for specific purposes
        
        Args:
            text: Text to analyze
            analysis_type: Type of analysis (sentiment, entities, summary, etc.)
            system_prompt: Custom system prompt
            
        Returns:
            Analysis results
        """
        analysis_prompts = {
            "sentiment": "Analyze the sentiment of this text. Return JSON with 'sentiment' (positive/negative/neutral), 'confidence' (0-1), and 'explanation'.",
            "entities": "Extract named entities from this text. Return JSON with 'entities' list containing objects with 'text', 'type', and 'relevance'.",
            "summary": "Summarize this text. Return JSON with 'summary' (2-3 sentences) and 'key_points' (list of main points).",
            "medical": "Analyze this text for medical/health information. Return JSON with 'symptoms', 'medications', 'concerns', and 'recommendations'."
        }
        
        prompt = f"{analysis_prompts.get(analysis_type, 'Analyze this text.')}\n\nText:\n{text}"
        
        return await self.generate_json(prompt, system_prompt=system_prompt)
    
    async def classify(
        self,
        text: str,
        categories: List[str],
        allow_multiple: bool = False
    ) -> Dict[str, Any]:
        """
        Classify text into categories
        
        Args:
            text: Text to classify
            categories: List of possible categories
            allow_multiple: Whether to allow multiple categories
            
        Returns:
            Classification result
        """
        mode = "one or more categories" if allow_multiple else "exactly one category"
        prompt = f"""Classify the following text into {mode} from this list: {', '.join(categories)}

Text: {text}

Return JSON with 'categories' (list), 'confidence' (0-1 for primary), and 'reasoning'."""
        
        return await self.generate_json(prompt)
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "total_tokens": self._total_tokens_used,
            "request_count": self._request_count,
            "model": self.model_name,
            "provider": self.provider
        }
    
    def reset_usage_stats(self):
        """Reset usage tracking"""
        self._total_tokens_used = 0
        self._request_count = 0


# Singleton instance
llm_service = LLMService()


async def generate(prompt: str, system_prompt: Optional[str] = None) -> str:
    """Convenience function for text generation"""
    return await llm_service.generate(prompt, system_prompt)


async def generate_json(prompt: str, schema: Optional[Dict] = None) -> Dict[str, Any]:
    """Convenience function for JSON generation"""
    return await llm_service.generate_json(prompt, schema)
