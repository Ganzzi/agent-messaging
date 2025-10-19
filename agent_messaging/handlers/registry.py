"""Handler registry for message handlers."""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from ..models import MessageContext

logger = logging.getLogger(__name__)

# Type for message handler: async def handler(message: T, context: MessageContext) -> Optional[T]
MessageHandler = Callable[[Any, MessageContext], Any]


class HandlerRegistry:
    """Registry for agent message handlers."""

    def __init__(self, handler_timeout: float = 30.0):
        """Initialize the handler registry.

        Args:
            handler_timeout: Timeout for handler execution in seconds
        """
        self._handlers: Dict[str, MessageHandler] = {}
        self._handler_timeout = handler_timeout
        self._background_tasks: set = set()

    def register(self, agent_external_id: str) -> Callable:
        """Decorator to register a message handler for an agent.

        Args:
            agent_external_id: External ID of the agent

        Returns:
            Decorator function

        Example:
            @registry.register("alice")
            async def alice_handler(message: T, context: MessageContext) -> Optional[T]:
                return None
        """

        def decorator(handler: MessageHandler) -> MessageHandler:
            self._handlers[agent_external_id] = handler
            logger.info(f"Registered handler for agent: {agent_external_id}")
            return handler

        return decorator

    def get_handler(self, agent_external_id: str) -> Optional[MessageHandler]:
        """Get registered handler for an agent.

        Args:
            agent_external_id: External ID of the agent

        Returns:
            Handler function if registered, None otherwise
        """
        return self._handlers.get(agent_external_id)

    def has_handler(self, agent_external_id: str) -> bool:
        """Check if a handler is registered for an agent.

        Args:
            agent_external_id: External ID of the agent

        Returns:
            True if handler is registered
        """
        return agent_external_id in self._handlers

    async def invoke_handler(
        self,
        agent_external_id: str,
        message: Any,
        context: MessageContext,
    ) -> Optional[Any]:
        """Invoke handler for an agent synchronously.

        Args:
            agent_external_id: External ID of the agent
            message: Message content
            context: Message context

        Returns:
            Handler response if available

        Raises:
            NoHandlerRegisteredError: If no handler is registered
            HandlerTimeoutError: If handler execution times out
        """
        from ..exceptions import HandlerTimeoutError, NoHandlerRegisteredError

        handler = self.get_handler(agent_external_id)
        if not handler:
            raise NoHandlerRegisteredError(f"No handler registered for agent: {agent_external_id}")

        try:
            result = await asyncio.wait_for(
                handler(message, context),
                timeout=self._handler_timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Handler timeout for agent {agent_external_id}")
            raise HandlerTimeoutError(
                f"Handler for agent {agent_external_id} timed out after {self._handler_timeout}s"
            )
        except Exception as e:
            logger.error(f"Handler error for agent {agent_external_id}: {e}", exc_info=True)
            raise

    def invoke_handler_async(
        self,
        agent_external_id: str,
        message: Any,
        context: MessageContext,
    ) -> asyncio.Task:
        """Invoke handler for an agent asynchronously (fire-and-forget).

        Args:
            agent_external_id: External ID of the agent
            message: Message content
            context: Message context

        Returns:
            asyncio.Task for the handler execution

        Raises:
            NoHandlerRegisteredError: If no handler is registered
        """
        from ..exceptions import NoHandlerRegisteredError

        handler = self.get_handler(agent_external_id)
        if not handler:
            raise NoHandlerRegisteredError(f"No handler registered for agent: {agent_external_id}")

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
