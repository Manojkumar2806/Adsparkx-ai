class SupportAgentError(Exception):
    """Base exception class for the Persona-Adaptive Support Agent."""
    pass

class ConfigurationError(SupportAgentError):
    """Raised when application setup or configuration is invalid."""
    pass

class VectorDBError(SupportAgentError):
    """Raised when there is an issue interacting with ChromaDB (Cloud or Local)."""
    pass

class LLMCallError(SupportAgentError):
    """Raised when a request to Gemini API or embedding generation fails."""
    pass

class IngestionError(SupportAgentError):
    """Raised when document parsing, chunking, or indexing fails."""
    pass
