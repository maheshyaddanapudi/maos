"""Title Generator external A2A agent.

This agent generates concise titles for conversations based on
the conversation content. It's typically used by UI clients to
generate thread titles after the first exchange.
"""

from typing import Any

import structlog

from maos.a2a.agents.base import ExternalAgentServer

logger = structlog.get_logger()


class TitleGeneratorAgent(ExternalAgentServer):
    """External agent that generates titles for conversations.

    This agent:
    1. Receives conversation content (typically user's first message + assistant response)
    2. Uses an LLM to generate a concise, descriptive title
    3. Returns the title (5-8 words max)

    It runs as an A2A-compliant server and can be called by the supervisor
    or directly by clients that need to generate thread titles.
    """

    # Default system prompt for title generation
    DEFAULT_SYSTEM_PROMPT = """You are a title generator. Given a conversation or message, generate a concise, descriptive title.

Rules:
- Maximum 5-8 words
- Be specific about the topic
- Don't use phrases like "Discussion about" or "Help with"
- Don't use quotes around the title
- Use title case
- Output ONLY the title, nothing else

Examples:
- Input: "How do I sort a list in Python?"
  Title: Python List Sorting Methods

- Input: "Can you explain what machine learning is?"
  Title: Machine Learning Fundamentals Overview

- Input: "I need to fix a bug in my React component"
  Title: React Component Bug Fix"""

    def __init__(
        self,
        name: str = "title_generator",
        description: str = "Generates concise titles for conversations",
        host: str = "127.0.0.1",
        port: int | None = None,
        llm_adapter: Any | None = None,
        system_prompt: str | None = None,
    ):
        """
        Initialize the title generator agent.

        Args:
            name: Agent name.
            description: Agent description.
            host: Host to bind to.
            port: Port to listen on (None = find free port).
            llm_adapter: LLM adapter for generating titles.
            system_prompt: Custom system prompt for title generation.
        """
        skills = [
            {
                "id": "generate_title",
                "name": "Generate Title",
                "description": "Generate a concise title for a conversation"
            }
        ]
        super().__init__(name, description, host, port, skills)
        self._llm = llm_adapter
        self._system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

    def set_llm(self, llm_adapter: Any) -> None:
        """Set the LLM adapter after initialization."""
        self._llm = llm_adapter

    async def _process(self, task: str, context: dict[str, Any] | None = None) -> str:
        """
        Generate a title for the given conversation content.

        Args:
            task: The conversation content to generate a title for.
            context: Optional context (not used for title generation).

        Returns:
            A concise title string.
        """
        if not task or not task.strip():
            return "New Conversation"

        # If no LLM configured, use a simple fallback
        if self._llm is None:
            return self._generate_fallback_title(task)

        try:
            # Use LLM to generate title
            title = await self._generate_with_llm(task)
            return title.strip()
        except Exception as e:
            logger.warning(
                "title_generation_failed",
                error=str(e),
                falling_back=True
            )
            return self._generate_fallback_title(task)

    async def _generate_with_llm(self, content: str) -> str:
        """Generate title using LLM."""
        from maos.llm.base import Message

        messages = [
            Message(role="system", content=self._system_prompt),
            Message(role="user", content=f"Generate a title for this conversation:\n\n{content[:2000]}")
        ]

        response = await self._llm.invoke(messages)
        return response.content.strip().strip('"').strip("'")

    def _generate_fallback_title(self, content: str) -> str:
        """Generate a simple fallback title without LLM."""
        # Take first line or first 50 chars
        first_line = content.split("\n")[0].strip()
        if len(first_line) <= 50:
            return first_line[:50]

        # Truncate at word boundary
        words = first_line[:50].split()
        if len(words) > 1:
            return " ".join(words[:-1]) + "..."
        return first_line[:47] + "..."


class TitleGeneratorFactory:
    """Factory for creating TitleGeneratorAgent instances."""

    @staticmethod
    def create(
        config: dict[str, Any],
        llm_adapter: Any | None = None
    ) -> TitleGeneratorAgent:
        """
        Create a TitleGeneratorAgent from configuration.

        Args:
            config: Configuration dict with keys:
                - name: Agent name (optional)
                - description: Agent description (optional)
                - host: Server host (optional)
                - port: Server port (optional, None for random)
                - system_prompt: Custom system prompt (optional)
            llm_adapter: LLM adapter for generating titles.

        Returns:
            Configured TitleGeneratorAgent instance.
        """
        return TitleGeneratorAgent(
            name=config.get("name", "title_generator"),
            description=config.get("description", "Generates concise titles for conversations"),
            host=config.get("host", "127.0.0.1"),
            port=config.get("port"),
            llm_adapter=llm_adapter,
            system_prompt=config.get("system_prompt"),
        )
