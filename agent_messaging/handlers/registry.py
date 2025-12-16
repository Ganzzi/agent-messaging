"""Global handler registry for message handlers."""

import asyncio
import logging
from typing import Any, Dict, Optional

from .types import HandlerContext, MessageContext, AnyHandler

logger = logging.getLogger(__name__)

_handlers: Dict[HandlerContext, AnyHandler] = {}
_background_tasks: set = set()
_handler_timeout: float = 30.0


def set_handler_timeout(timeout: float) -> None:
    """Set the default handler timeout."""
    global _handler_timeout
    _handler_timeout = timeout


def get_handler_timeout() -> float:
    """Get the current handler timeout setting."""
    return _handler_timeout


def register_one_way_handler(handler: AnyHandler) -> AnyHandler:
    """Register a handler for one-way messages."""
    _handlers[HandlerContext.ONE_WAY] = handler
    logger.info(f"Registered one-way handler: {handler.__name__}")
    return handler


def register_conversation_handler(handler: AnyHandler) -> AnyHandler:
    """Register a handler for conversation messages."""
    _handlers[HandlerContext.CONVERSATION] = handler
    logger.info(f"Registered conversation handler: {handler.__name__}")
    return handler


def register_meeting_handler(handler: AnyHandler) -> AnyHandler:
    """Register a handler for meeting messages."""
    _handlers[HandlerContext.MEETING] = handler
    logger.info(f"Registered meeting handler: {handler.__name__}")
    return handler


def register_system_handler(handler: AnyHandler) -> AnyHandler:
    """Register a handler for system messages."""
    _handlers[HandlerContext.SYSTEM] = handler
    logger.info(f"Registered system handler: {handler.__name__}")
    return handler


def get_handler(context: HandlerContext) -> Optional[AnyHandler]:
    """Get the handler for a specific context type."""
    return _handlers.get(context)


def has_handler(context: HandlerContext) -> bool:
    """Check if a handler is registered for a specific context type."""
    return context in _handlers


def list_handlers() -> dict:
    """List all registered handlers."""
    return {ctx.value: h.__name__ for ctx, h in _handlers.items()}


async def invoke_handler_async(
    handler_context: HandlerContext,
    message: Any,
    context: MessageContext,
    timeout: Optional[float] = None,
) -> Optional[Any]:
    """Invoke a handler asynchronously."""
    from ..exceptions import HandlerTimeoutError, NoHandlerRegisteredError

    handler = get_handler(handler_context)
    if not handler:
        raise NoHandlerRegisteredError(
            f"No handler registered for context '{handler_context.value}'"
        )

    effective_timeout = timeout if timeout is not None else _handler_timeout

    try:
        if asyncio.iscoroutinefunction(handler):
            result = await asyncio.wait_for(handler(message, context), timeout=effective_timeout)
        else:
            result = handler(message, context)
        return result
    except asyncio.TimeoutError:
        raise HandlerTimeoutError(f"Handler timed out after {effective_timeout}s")


def invoke_handler(
    handler_context: HandlerContext,
    message: Any,
    context: MessageContext,
    timeout: Optional[float] = None,
) -> Optional[Any]:
    """Invoke a handler synchronously (blocking)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                invoke_handler_async(handler_context, message, context, timeout),
            )
            return future.result()
    else:
        return asyncio.run(invoke_handler_async(handler_context, message, context, timeout))


def clear_handlers() -> None:
    """Clear all registered handlers."""
    _handlers.clear()
    logger.debug("Cleared all handlers")


async def shutdown() -> None:
    """Shutdown the handler registry cleanly."""
    for task in _background_tasks:
        if not task.done():
            task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()
    logger.info("Handler registry shutdown complete")
