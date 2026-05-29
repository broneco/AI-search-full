from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, List, Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM interactions should be routed through implementations of this interface
    to prevent provider/library lock-in across the rest of the application layers.
    """

    @abstractmethod
    async def generate(
        self,
        messages: List[ChatMessage],
        model_profile: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a complete text response from the model.

        Args:
            messages: List of chat messages representing the prompt and conversation.
            model_profile: The target model profile ('flash' or 'thinking').
            temperature: LLM temperature parameter.
            max_tokens: Limit on maximum tokens generated.
            **kwargs: Provider-specific generation arguments.
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[ChatMessage],
        model_profile: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a text response from the model as it becomes available.

        Args:
            messages: List of chat messages representing the prompt and conversation.
            model_profile: The target model profile ('flash' or 'thinking').
            temperature: LLM temperature parameter.
            max_tokens: Limit on maximum tokens generated.
            **kwargs: Provider-specific generation arguments.
        """
        # Serve as a signature definition for async generator
        yield ""
