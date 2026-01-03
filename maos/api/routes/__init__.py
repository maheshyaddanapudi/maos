"""API route handlers."""

from maos.api.routes.chat import router as chat_router
from maos.api.routes.agents import router as agents_router
from maos.api.routes.health import router as health_router
from maos.api.routes.openai_compat import router as openai_router

__all__ = [
    "chat_router",
    "agents_router",
    "health_router",
    "openai_router",
]
