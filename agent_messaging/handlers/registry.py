"""Handler registry for message handlers."""

import asyncio
import logging
from typing import Any, Callable, Optional

from ..models import MessageContext

logger = logging.getLogger(__name__)

# Type for message handler: async def handler(message: T, context: MessageContext) -> Optional[T]
MessageHandler = Callable[[Any, MessageContext], Any]


class HandlerRegistry:
    """Registry for agent message handlers.

    Handlers are registered globally and shared across all agents.
    Only one handler can be registered at a time.
    """

    def __init__(self, handler_timeout: float = 30.0):
        """Initialize the handler registry.

        Args:
            handler_timeout: Timeout for handler execution in seconds
        """
        self._handler: Optional[MessageHandler] = None
        self._handler_timeout = handler_timeout
        self._background_tasks: set = set()

    def register(self, handler: MessageHandler) -> MessageHandler:
        """Register a message handler (decorator or direct call).

        Args:
            handler: Message handler function

        Returns:
            Handler function (for decorator use)

        Example:
            @registry.register
            async def my_handler(message: T, context: MessageContext) -> Optional[T]:
                return None

            # Or direct:
            registry.register(my_handler)
        """
        self._handler = handler
        logger.info(f"Registered global handler: {handler.__name__}")
        return handler

    def get_handler(self) -> Optional[MessageHandler]:
        """Get the registered handler.

        Returns:
            Handler function if registered, None otherwise
        """
        return self._handler

    def has_handler(self) -> bool:
        """Check if a handler is registered.

        Returns:
            True if handler is registered
        """
        return self._handler is not None

    async def invoke_handler(
        self,
        message: Any,
        context: MessageContext,
    ) -> Optional[Any]:
        """Invoke the registered handler synchronously.

        Args:
            message: Message content
            context: Message context

        Returns:
            Handler response if available

        Raises:
            NoHandlerRegisteredError: If no handler is registered
            HandlerTimeoutError: If handler execution times out
        """
        from ..exceptions import HandlerTimeoutError, NoHandlerRegisteredError

        if not self._handler:
            raise NoHandlerRegisteredError("No handler registered")

        try:
            result = await asyncio.wait_for(
                self._handler(message, context),
                timeout=self._handler_timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Handler timeout")
            raise HandlerTimeoutError(f"Handler timed out after {self._handler_timeout}s")
        except Exception as e:
            logger.error(f"Handler error: {e}", exc_info=True)
            raise

    def invoke_handler_async(
        self,
        message: Any,
        context: MessageContext,
    ) -> asyncio.Task:
        """Invoke handler asynchronously (fire-and-forget).

        Args:
            message: Message content
            context: Message context

        Returns:
            asyncio.Task for the handler execution

        Raises:
            NoHandlerRegisteredError: If no handler is registered
        """
        from ..exceptions import NoHandlerRegisteredError

        if not self._handler:
            raise NoHandlerRegisteredError("No handler registered")

        # Create task with error handling
        task = asyncio.create_task(self._safe_handler_invoke(self._handler, message, context))
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
