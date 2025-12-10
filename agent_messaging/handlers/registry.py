"""Handler registry for message handlers."""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from ..models import MessageContext
from .types import (
    HandlerContext,
    OneWayHandler,
    ConversationHandler,
    MeetingHandler,
    SystemHandler,
    AnyHandler,
)

logger = logging.getLogger(__name__)

# Type for message handler: async def handler(message: T, context: MessageContext) -> Optional[T]
MessageHandler = Callable[[Any, MessageContext], Any]


class HandlerRegistry:
    """Registry for agent message handlers.

    Handlers can be registered globally (deprecated) or per-agent per-context.
    Supports type-based routing for different messaging patterns.

    New API (Phase 3+):
    - register_one_way_handler(agent_id, handler)
    - register_conversation_handler(agent_id, handler)
    - register_meeting_handler(agent_id, handler)
    - register_system_handler(handler)

    Deprecated API (still supported for backward compatibility):
    - register(handler)  # Global handler for all agents
    """

    def __init__(self, handler_timeout: float = 30.0):
        """Initialize the handler registry.

        Args:
            handler_timeout: Timeout for handler execution in seconds
        """
        # Legacy global handler (deprecated in Phase 3)
        self._handler: Optional[MessageHandler] = None
        self._handler_timeout = handler_timeout
        self._background_tasks: set = set()

        # New storage structure (Phase 3+):
        # Maps: agent_external_id -> {handler_context -> handler}
        self._agent_handlers: Dict[str, Dict[HandlerContext, AnyHandler]] = {}

        # Global system handler (not agent-specific)
        self._system_handler: Optional[SystemHandler] = None

    # ========================================================================
    # Legacy API (Deprecated, kept for backward compatibility)
    # ========================================================================

    def register(self, handler: MessageHandler) -> MessageHandler:
        """Register a global message handler (DEPRECATED).

        .. deprecated:: 2.0.0
            Use register_one_way_handler(), register_conversation_handler(), etc.

        This registers a single global handler that handles all messages for all agents.
        Only one global handler can be registered at a time.

        Args:
            handler: Message handler function

        Returns:
            Handler function (for decorator use)

        Example:
            @registry.register
            async def my_handler(message: T, context: MessageContext) -> Optional[T]:
                return None
        """
        logger.warning(
            "register() is deprecated in Phase 2+. "
            "Use register_one_way_handler(), register_conversation_handler(), "
            "or register_meeting_handler() instead."
        )
        self._handler = handler
        logger.info(f"Registered global handler: {handler.__name__}")
        return handler

    def get_handler(self) -> Optional[MessageHandler]:
        """Get the registered global handler (DEPRECATED).

        .. deprecated:: 2.0.0
            Use get_handler_for_agent() instead.

        Returns:
            Global handler function if registered, None otherwise
        """
        return self._handler

    def has_handler(self) -> bool:
        """Check if a global handler is registered (DEPRECATED).

        .. deprecated:: 2.0.0
            Use has_handler_for_agent() instead.

        Returns:
            True if global handler is registered
        """
        return self._handler is not None

    # ========================================================================
    # Phase 3+ API: Type-Safe Registration Methods
    # ========================================================================

    def register_one_way_handler(
        self,
        agent_external_id: str,
        handler: OneWayHandler,
    ) -> OneWayHandler:
        """Register a one-way message handler for an agent.

        One-way handlers process fire-and-forget messages. The handler is invoked
        asynchronously and the sender does not wait for or expect a response.

        Args:
            agent_external_id: The agent's external ID
            handler: Handler function with OneWayHandler signature

        Returns:
            Handler function (for decorator use)

        Example:
            @registry.register_one_way_handler("agent_001")
            async def handle_notification(msg: str, ctx: MessageContext) -> None:
                print(f"Notification: {msg}")
        """
        if agent_external_id not in self._agent_handlers:
            self._agent_handlers[agent_external_id] = {}

        self._agent_handlers[agent_external_id][HandlerContext.ONE_WAY] = handler
        logger.info(
            f"Registered one-way handler for agent '{agent_external_id}': " f"{handler.__name__}"
        )
        return handler

    def register_conversation_handler(
        self,
        agent_external_id: str,
        handler: ConversationHandler,
    ) -> ConversationHandler:
        """Register a synchronous conversation handler for an agent.

        Conversation handlers process request-response messages. The sender blocks
        and waits for the handler's response with a configurable timeout.

        Args:
            agent_external_id: The agent's external ID
            handler: Handler function with ConversationHandler signature

        Returns:
            Handler function (for decorator use)

        Example:
            @registry.register_conversation_handler("agent_001")
            async def handle_query(msg: str, ctx: MessageContext) -> str:
                return "response"
        """
        if agent_external_id not in self._agent_handlers:
            self._agent_handlers[agent_external_id] = {}

        self._agent_handlers[agent_external_id][HandlerContext.CONVERSATION] = handler
        logger.info(
            f"Registered conversation handler for agent '{agent_external_id}': "
            f"{handler.__name__}"
        )
        return handler

    def register_meeting_handler(
        self,
        agent_external_id: str,
        handler: MeetingHandler,
    ) -> MeetingHandler:
        """Register a meeting message handler for an agent.

        Meeting handlers process messages during active meetings. The handler is invoked
        when the agent has the speaking turn.

        Args:
            agent_external_id: The agent's external ID
            handler: Handler function with MeetingHandler signature

        Returns:
            Handler function (for decorator use)

        Example:
            @registry.register_meeting_handler("agent_001")
            async def handle_meeting_turn(msg: str, ctx: MessageContext) -> str:
                return "my contribution"
        """
        if agent_external_id not in self._agent_handlers:
            self._agent_handlers[agent_external_id] = {}

        self._agent_handlers[agent_external_id][HandlerContext.MEETING] = handler
        logger.info(
            f"Registered meeting handler for agent '{agent_external_id}': " f"{handler.__name__}"
        )
        return handler

    def register_system_handler(
        self,
        handler: SystemHandler,
    ) -> SystemHandler:
        """Register a global system message handler.

        System handlers process internal messages like timeouts, events, etc.
        This is a global handler (not agent-specific).

        Args:
            handler: Handler function with SystemHandler signature

        Returns:
            Handler function (for decorator use)

        Example:
            @registry.register_system_handler()
            async def handle_system_message(msg: dict, ctx: MessageContext) -> None:
                logger.info(f"System event: {msg}")
        """
        self._system_handler = handler
        logger.info(f"Registered global system handler: {handler.__name__}")
        return handler

    # ========================================================================
    # Phase 3+ API: Handler Selection and Lookup
    # ========================================================================

    def get_handler_for_agent(
        self,
        agent_external_id: str,
        context: HandlerContext = HandlerContext.ONE_WAY,
    ) -> Optional[AnyHandler]:
        """Get handler for an agent with specified context.

        Args:
            agent_external_id: The agent's external ID
            context: The type of handler context (one_way, conversation, meeting)

        Returns:
            Handler function if registered, None otherwise
        """
        if agent_external_id not in self._agent_handlers:
            # Fallback to global handler for backward compatibility
            return self._handler

        agent_contexts = self._agent_handlers[agent_external_id]
        if context not in agent_contexts:
            # Fallback to global handler if context-specific handler not found
            return self._handler

        return agent_contexts[context]

    def get_system_handler(self) -> Optional[SystemHandler]:
        """Get the global system message handler.

        Returns:
            System handler if registered, None otherwise
        """
        return self._system_handler

    def has_handler_for_agent(
        self,
        agent_external_id: str,
        context: HandlerContext = HandlerContext.ONE_WAY,
    ) -> bool:
        """Check if handler exists for agent with specified context.

        Args:
            agent_external_id: The agent's external ID
            context: The type of handler context

        Returns:
            True if handler is registered for the agent/context combo
        """
        if agent_external_id not in self._agent_handlers:
            return self._handler is not None

        agent_contexts = self._agent_handlers[agent_external_id]
        if context not in agent_contexts:
            return self._handler is not None

        return True

    def list_handlers(self) -> Dict[str, Dict[str, str]]:
        """List all registered handlers for debugging/introspection.

        Returns:
            Dict mapping agent_external_id -> {context_name -> handler_name}
        """
        result = {}
        for agent_id, contexts in self._agent_handlers.items():
            result[agent_id] = {ctx.value: handler.__name__ for ctx, handler in contexts.items()}
        return result

    # ========================================================================
    # Handler Invocation (Support both APIs)
    # ========================================================================

    async def invoke_handler(
        self,
        message: Any,
        context: MessageContext,
        agent_external_id: Optional[str] = None,
        handler_context: HandlerContext = HandlerContext.ONE_WAY,
    ) -> Optional[Any]:
        """Invoke handler synchronously (blocking).

        Supports both legacy and Phase 3+ APIs:
        - If agent_external_id is provided: uses type-based routing
        - If agent_external_id is None: uses global handler (legacy)

        Args:
            message: Message content
            context: Message context
            agent_external_id: Agent's external ID (optional, for type-based routing)
            handler_context: Type of handler context (one_way, conversation, meeting)

        Returns:
            Handler response if available

        Raises:
            NoHandlerRegisteredError: If no handler is registered
            HandlerTimeoutError: If handler execution times out
        """
        from ..exceptions import HandlerTimeoutError, NoHandlerRegisteredError

        # Select appropriate handler
        if agent_external_id:
            handler = self.get_handler_for_agent(agent_external_id, handler_context)
        else:
            handler = self._handler

        if not handler:
            raise NoHandlerRegisteredError(
                f"No handler registered for agent '{agent_external_id}' "
                f"with context '{handler_context.value}'"
                if agent_external_id
                else "No handler registered"
            )

        try:
            result = await asyncio.wait_for(
                handler(message, context),
                timeout=self._handler_timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Handler timeout for agent '{agent_external_id}'")
            raise HandlerTimeoutError(f"Handler timed out after {self._handler_timeout}s")
        except Exception as e:
            logger.error(f"Handler error: {e}", exc_info=True)
            raise

    def invoke_handler_async(
        self,
        message: Any,
        context: MessageContext,
        agent_external_id: Optional[str] = None,
        handler_context: HandlerContext = HandlerContext.ONE_WAY,
    ) -> asyncio.Task:
        """Invoke handler asynchronously (fire-and-forget).

        Args:
            message: Message content
            context: Message context
            agent_external_id: Agent's external ID (optional, for type-based routing)
            handler_context: Type of handler context (one_way, conversation, meeting)

        Returns:
            asyncio.Task for the handler execution

        Raises:
            NoHandlerRegisteredError: If no handler is registered
        """
        from ..exceptions import NoHandlerRegisteredError

        # Select appropriate handler
        if agent_external_id:
            handler = self.get_handler_for_agent(agent_external_id, handler_context)
        else:
            handler = self._handler

        if not handler:
            raise NoHandlerRegisteredError(
                f"No handler registered for agent '{agent_external_id}' "
                f"with context '{handler_context.value}'"
                if agent_external_id
                else "No handler registered"
            )

        # Create task with error handling
        task = asyncio.create_task(self._safe_handler_invoke(handler, message, context))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        return task

    async def _safe_handler_invoke(
        self,
        handler: MessageHandler,
        message: Any,
        context: MessageContext,
    ) -> None:
        """Safely invoke handler with error handling.

        Args:
            handler: Handler function
            message: Message content
            context: Message context
        """
        try:
            await asyncio.wait_for(handler(message, context), timeout=self._handler_timeout)
        except asyncio.TimeoutError:
            logger.error(f"Background handler timeout: {handler.__name__}")
        except Exception as e:
            logger.error(f"Background handler error: {e}", exc_info=True)

    async def shutdown(self) -> None:
        """Shutdown handler registry and cancel pending tasks."""
        logger.info("Shutting down handler registry")
        # Wait for background tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        logger.info("Handler registry shutdown complete")
