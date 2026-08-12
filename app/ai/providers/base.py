from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """
    Base interface for every Large Language Model provider.

    All providers (OpenAI, Groq, Ollama, Gemini, DeepSeek...)
    must inherit from this class.
    """

    @abstractmethod
    def chat(
        self,
        messages: list,
        tools: list | None = None,
    ):
        """
        Send a conversation to the LLM.

        Parameters
        ----------
        messages : list
            Chat history in OpenAI format.

        tools : list | None
            Optional function/tool definitions.

        Returns
        -------
        dict
            Standardized AI response.
        """
        pass