"""Custom exceptions for Agent Messaging Protocol SDK."""


# Base exception
class AgentMessagingError(Exception):
    """Base exception for all agent messaging errors."""

    pass


# Agent and Organization errors
class AgentNotFoundError(AgentMessagingError):
    """Raised when an agent cannot be found."""

    pass


class OrganizationNotFoundError(AgentMessagingError):
    """Raised when an organization cannot be found."""

    pass


# Session-related errors
class SessionError(AgentMessagingError):
    """Base class for session-related errors."""

    pass


class SessionStateError(SessionError):
    """Raised when a session is in an invalid state for the requested operation."""

    pass


class SessionLockError(SessionError):
    """Raised when unable to acquire or release session locks."""

    pass


# Meeting-related errors
class MeetingError(AgentMessagingError):
    """Base class for meeting-related errors."""

    pass


class MeetingNotFoundError(MeetingError):
    """Raised when a meeting cannot be found."""

    pass


class MeetingNotActiveError(MeetingError):
    """Raised when attempting to perform actions on an inactive meeting."""

    pass


class MeetingStateError(MeetingError):
    """Raised when a meeting is in an invalid state for the requested operation."""

    pass


class NotYourTurnError(MeetingError):
    """Raised when an agent tries to speak out of turn in a meeting."""

    pass


class MeetingPermissionError(MeetingError):
    """Raised when an agent lacks permission to perform a meeting operation."""

    pass


# Handler-related errors
class HandlerError(AgentMessagingError):
    """Base class for handler-related errors."""

    pass


class NoHandlerRegisteredError(HandlerError):
    """Raised when no handler is registered for an agent."""

    pass


class HandlerTimeoutError(HandlerError):
    """Raised when a message handler times out."""

    pass


# Timeout-related errors
class TimeoutError(AgentMessagingError):
    """Raised when an operation times out."""

    pass


# Database and connection errors
class DatabaseError(AgentMessagingError):
    """Raised when database operations fail."""

    pass
