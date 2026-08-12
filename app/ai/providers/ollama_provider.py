import requests

from app.ai.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """
    Ollama LLM Provider

    Uses a locally running Ollama server.

    Default URL:
    http://localhost:11434
    """

    def __init__(
        self,
        model: str = "llama3.2:latest",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def chat(
        self,
        messages: list,
        tools: list | None = None,
    ):
        """
        Send chat messages to Ollama.
        """

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        # Future support for function calling
        if tools:
            payload["tools"] = tools

        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=(3, 10),
        )

        response.raise_for_status()

        data = response.json()

        return {
            "content": data["message"]["content"],
            "raw": data,
        }