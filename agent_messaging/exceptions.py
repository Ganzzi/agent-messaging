"""Custom exceptions for Agent Messaging Protocol SDK."""


class AgentMessagingError(Exception):
    """Base exception for all agent messaging errors."""

    pass


class ConfigurationError(AgentMessagingError):
    """Raised when configuration is invalid or missing."""

    pass


class DatabaseError(AgentMessagingError):
    """Raised when database operations fail."""

    pass


class AgentNotFoundError(AgentMessagingError):
    """Raised when an agent cannot be found."""

    pass


class OrganizationNotFoundError(AgentMessagingError):
    """Raised when an organization cannot be found."""

    pass


class NoHandlerRegisteredError(AgentMessagingError):
    """Raised when no handler is registered for an agent."""

    pass


class HandlerTimeoutError(AgentMessagingError):
    """Raised when a message handler times out."""

    pass


class SessionNotFoundError(AgentMessagingError):
    """Raised when a conversation session cannot be found."""

    pass


class MeetingNotFoundError(AgentMessagingError):
    """Raised when a meeting cannot be found."""

    pass


class MeetingNotActiveError(AgentMessagingError):
    """Raised when attempting to perform actions on an inactive meeting."""

    pass


class NotYourTurnError(AgentMessagingError):
    """Raised when an agent tries to speak out of turn in a meeting."""

    pass


class TurnTimeoutError(AgentMessagingError):
    """Raised when a meeting turn times out."""

    pass


class LockAcquisitionError(AgentMessagingError):
    """Raised when unable to acquire a coordination lock."""

    pass


class MessageValidationError(AgentMessagingError):
    """Raised when message validation fails."""

    pass


class TimeoutError(AgentMessagingError):
    """Raised when operations timeout."""

    pass
