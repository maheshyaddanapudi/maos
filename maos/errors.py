"""MAOS custom exceptions."""


class MAOSError(Exception):
    """Base exception for MAOS."""

    pass


class MAOSConfigError(MAOSError):
    """Configuration error."""

    pass


class MAOSToolError(MAOSError):
    """Tool execution error."""

    pass


class MAOSToolTimeoutError(MAOSToolError):
    """Tool execution timed out."""

    def __init__(self, tool_id: str, timeout_seconds: int):
        self.tool_id = tool_id
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Tool {tool_id} timed out after {timeout_seconds}s")


class MAOSLLMError(MAOSError):
    """LLM invocation error."""

    pass


class MAOSAgentError(MAOSError):
    """Agent execution error."""

    pass


class MAOSCircuitBreakerError(MAOSError):
    """Circuit breaker is open."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Circuit breaker '{name}' is open")


class MAOSA2AError(MAOSError):
    """A2A communication error."""

    pass


class MAOSAuthError(MAOSError):
    """Authentication/authorization error."""

    pass


class MAOSRateLimitError(MAOSError):
    """Rate limit exceeded."""

    pass
