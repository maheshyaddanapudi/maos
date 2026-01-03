"""
MAOS - Multi-Agent Orchestration System

A config-driven multi-agent orchestration system that combines:
- LangGraph Supervisor for intelligent routing
- Framework-agnostic worker execution
- MCP (Model Context Protocol) for tool integration
- A2A (Agent-to-Agent) for external agent communication
"""

__version__ = "0.1.0"
__author__ = "MAOS Team"

from maos.config.loader import ConfigLoader
from maos.config.models import Config

__all__ = [
    "__version__",
    "Config",
    "ConfigLoader",
]
