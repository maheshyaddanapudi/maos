"""
MAOS - Multi-Agent Orchestration System

A config-driven multi-agent orchestration system combining:
- LangGraph Supervisor for intelligent routing
- Any-Agent for framework-agnostic worker execution
- MCP (Model Context Protocol) for tool integration
- A2A (Agent-to-Agent) for external agent communication
"""

__version__ = "0.1.0"

from maos.main import main, initialize_system, shutdown_system

__all__ = [
    "__version__",
    "main",
    "initialize_system",
    "shutdown_system",
]
