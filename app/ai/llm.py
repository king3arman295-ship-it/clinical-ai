from app.ai.providers.ollama_provider import OllamaProvider


class LLM:
    """
    Central LLM Manager.

    This class hides the actual AI provider from the rest
    of the application.

    Later you can switch to:
        - OpenAI
        - Groq
        - Gemini
        - DeepSeek
        - Ollama

    without changing any other code.
    """

    def __init__(self):
        # Current Provider
        self.provider = OllamaProvider(
            model="llama3.2:latest"
        )

    def chat(
        self,
        messages: list,
        tools: list | None = None,
    ):
        """
        Forward chat requests to the active provider.
        """

        return self.provider.chat(
            messages=messages,
            tools=tools,
        )