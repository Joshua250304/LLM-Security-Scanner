"""
llm_client.py
-------------
A thin, provider-agnostic client so scan modules never need to know whether
they are talking to Anthropic, OpenAI, or an arbitrary HTTP endpoint. Add a
new provider by implementing `LLMClient` and registering it in `get_client`.
"""

from __future__ import annotations

import time
import abc
from typing import Optional

import requests

from core.config import settings


class LLMClientError(Exception):
    """Raised when the target model cannot be reached or errors out."""


class LLMClient(abc.ABC):
    """Common interface every provider adapter must implement."""

    provider_name: str = "base"

    def __init__(self, model: str):
        self.model = model

    @abc.abstractmethod
    def send(self, system_prompt: Optional[str], user_prompt: str) -> str:
        """Send a single-turn prompt and return the model's text response."""
        raise NotImplementedError

    def send_with_retries(self, system_prompt: Optional[str], user_prompt: str) -> str:
        last_err = None
        for attempt in range(settings.max_retries + 1):
            try:
                return self.send(system_prompt, user_prompt)
            except Exception as exc:  # noqa: BLE001 - surfaced to caller
                last_err = exc
                time.sleep(min(2 ** attempt, 8))
        raise LLMClientError(f"{self.provider_name} request failed: {last_err}")


class AnthropicClient(LLMClient):
    provider_name = "anthropic"
    ENDPOINT = "https://api.anthropic.com/v1/messages"

    def __init__(self, model: str):
        super().__init__(model)
        if not settings.anthropic_api_key:
            raise LLMClientError("ANTHROPIC_API_KEY is not set")

    def send(self, system_prompt: Optional[str], user_prompt: str) -> str:
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        resp = requests.post(
            self.ENDPOINT, headers=headers, json=payload, timeout=settings.request_timeout
        )
        if resp.status_code != 200:
            raise LLMClientError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        return "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        )


class OpenAIClient(LLMClient):
    provider_name = "openai"
    ENDPOINT = "https://api.openai.com/v1/chat/completions"

    def __init__(self, model: str):
        super().__init__(model)
        if not settings.openai_api_key:
            raise LLMClientError("OPENAI_API_KEY is not set")

    def send(self, system_prompt: Optional[str], user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "content-type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload = {"model": self.model, "messages": messages, "max_tokens": 1024}
        resp = requests.post(
            self.ENDPOINT, headers=headers, json=payload, timeout=settings.request_timeout
        )
        if resp.status_code != 200:
            raise LLMClientError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        return data["choices"][0]["message"]["content"]


class CustomEndpointClient(LLMClient):
    """
    Generic adapter for a self-hosted or third-party model that exposes a
    simple JSON endpoint: POST {"prompt": "..."} -> {"response": "..."}.
    Adjust `send()` to match your actual endpoint's contract.
    """

    provider_name = "custom"

    def __init__(self, model: str):
        super().__init__(model)
        if not settings.custom_endpoint_url:
            raise LLMClientError("CUSTOM_LLM_ENDPOINT is not set")

    def send(self, system_prompt: Optional[str], user_prompt: str) -> str:
        headers = {"content-type": "application/json"}
        if settings.custom_endpoint_key:
            headers["Authorization"] = f"Bearer {settings.custom_endpoint_key}"

        full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
        resp = requests.post(
            settings.custom_endpoint_url,
            headers=headers,
            json={"prompt": full_prompt, "model": self.model},
            timeout=settings.request_timeout,
        )
        if resp.status_code != 200:
            raise LLMClientError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json().get("response", "")


_PROVIDERS = {
    "anthropic": AnthropicClient,
    "openai": OpenAIClient,
    "custom": CustomEndpointClient,
}


def get_client(provider: str, model: str) -> LLMClient:
    if provider not in _PROVIDERS:
        raise LLMClientError(
            f"Unknown provider '{provider}'. Choose from: {', '.join(_PROVIDERS)}"
        )
    return _PROVIDERS[provider](model)
