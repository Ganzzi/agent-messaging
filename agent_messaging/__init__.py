# Agent Messaging Protocol
# A Python SDK for AI agent communication

__version__ = "0.3.0"
__author__ = "Ganzzi"
__email__ = "boinguyen9701@gmail.com"
__license__ = "MIT"

from .client import AgentMessaging
from .config import Config, DatabaseConfig, MessagingConfig
from .exceptions import (
    AgentMessagingError,
    AgentNotFoundError,
    OrganizationNotFoundError,
    NoHandlerRegisteredError,
    HandlerTimeoutError,
    MeetingNotFoundError,
    MeetingError,
    TimeoutError,
)
from .messaging import OneWayMessenger, Conversation, MeetingManager
from .utils import MeetingTimeoutManager
from .handlers import (
    # Generic type variables
    T_OneWay,
    T_Conversation,
    T_Meeting,
    # Context types
    HandlerContext,
    MessageContext,
    # Handler protocols
    OneWayHandler,
    ConversationHandler,
    # Registration decorators
    register_one_way_handler,
    register_conversation_handler,
    register_message_notification_handler,
    # Lookup and management
    get_handler,
    has_handler,
    clear_handlers,
)

__all__ = [
    # Main SDK class
    "AgentMessaging",
    "Config",
    # Messaging classes
    "OneWayMessenger",
    "Conversation",
    "MeetingManager",
    "MeetingTimeoutManager",
    # Exceptions
    "AgentMessagingError",
    "AgentNotFoundError",
    "OrganizationNotFoundError",
    "NoHandlerRegisteredError",
    "HandlerTimeoutError",
    "MeetingNotFoundError",
    "MeetingError",
    "TimeoutError",
    # Generic type variables
    "T_OneWay",
    "T_Conversation",
    "T_Meeting",
    # Handler types
    "HandlerContext",
    "MessageContext",
    "OneWayHandler",
    "ConversationHandler",
    # Handler registration
    "register_one_way_handler",
    "register_conversation_handler",
    "register_message_notification_handler",
    # Handler management
    "get_handler",
    "has_handler",
    "clear_handlers",
]
