"""
Concurrent Telegram Request Processing & Task Registry Module.
Manages asynchronous tasks, request contexts, concurrency semaphores, and worker execution.
Ensures zero global blocking, strict chat_id isolation, and structured logging.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Awaitable
from telegram import Bot, InlineKeyboardMarkup

from app.core.config import settings
from app.core.logging import logger


async def _maybe_await(res: Any) -> Any:
    """Helper to safely await coroutines or return sync mock results in tests."""
    if hasattr(res, "__await__"):
        return await res
    return res


@dataclass
class RequestContext:
    """
    Carries request-scoped metadata for strict routing isolation.
    Guarantees no reliance on global chat/user state.
    """
    request_id: str
    chat_id: int
    user_id: int
    command: str
    username: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "username": self.username,
            "command": self.command,
            "created_at": self.created_at,
        }


class TaskManager:
    """
    Active task registry and concurrency limiter.
    """
    def __init__(self):
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._active_contexts: Dict[str, RequestContext] = {}
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """
        Lazily creates Semaphore bound to current active event loop.
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._semaphore is None or (current_loop and self._loop != current_loop):
            self._semaphore = asyncio.Semaphore(settings.max_concurrent_tasks)
            self._loop = current_loop
        return self._semaphore

    def register_task(self, context: RequestContext, task: asyncio.Task) -> None:
        self._active_tasks[context.request_id] = task
        self._active_contexts[context.request_id] = context

    def unregister_task(self, request_id: str) -> None:
        self._active_tasks.pop(request_id, None)
        self._active_contexts.pop(request_id, None)

    def cancel_task(self, request_id: str) -> bool:
        task = self._active_tasks.get(request_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        return {
            req_id: ctx.to_dict()
            for req_id, ctx in self._active_contexts.items()
        }

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)


# Global singleton task manager
task_manager = TaskManager()


async def send_or_edit_response(
    bot: Optional[Bot],
    chat_id: int,
    message_id: Optional[int],
    messages: List[str],
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = None,
    query: Optional[Any] = None,
    placeholder: Optional[Any] = None
) -> None:
    """
    Dispatches result directly to designated chat_id.
    Attempts editing existing placeholder or query first; falls back to send_message.
    """
    if not messages:
        return

    first_msg = messages[0]
    edited = False

    # 1. Try editing via placeholder message object if available
    if placeholder and hasattr(placeholder, "edit_text"):
        try:
            await _maybe_await(placeholder.edit_text(
                first_msg,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            ))
            edited = True
        except Exception as e:
            logger.debug(f"Could not edit via placeholder: {e}")

    # 2. Try editing via callback query object if present
    if not edited and query and hasattr(query, "edit_message_text"):
        try:
            await _maybe_await(query.edit_message_text(
                text=first_msg,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            ))
            edited = True
        except Exception as e:
            logger.debug(f"Could not edit via callback query: {e}")

    # 3. Fallback to bot.edit_message_text
    if not edited and bot and message_id:
        try:
            await _maybe_await(bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=first_msg,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            ))
            edited = True
        except Exception as e:
            logger.debug(f"Could not edit placeholder message {message_id} in chat {chat_id}: {e}. Sending new message.")

    # 4. Fallback to bot.send_message
    if not edited and bot:
        try:
            await _maybe_await(bot.send_message(
                chat_id=chat_id,
                text=first_msg,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            ))
        except Exception as e:
            logger.error(f"Failed to send message to chat_id {chat_id}: {e}")

    # Send any subsequent pages to chat_id
    for extra_msg in messages[1:]:
        if bot:
            try:
                await _maybe_await(bot.send_message(
                    chat_id=chat_id,
                    text=extra_msg,
                    parse_mode=parse_mode
                ))
            except Exception as e:
                logger.error(f"Failed to send paginated message to chat_id {chat_id}: {e}")
        elif query and getattr(query, "message", None):
            try:
                await _maybe_await(query.message.reply_text(
                    text=extra_msg,
                    parse_mode=parse_mode
                ))
            except Exception as e:
                logger.error(f"Failed to send extra message via query: {e}")


async def execute_worker_task(
    context: RequestContext,
    worker_func: Callable[[], Awaitable[List[str]]],
    bot: Optional[Bot],
    message_id: Optional[int] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = None,
    query: Optional[Any] = None,
    placeholder: Optional[Any] = None
) -> None:
    """
    Executes worker with concurrency semaphore, logs lifecycle with request_id,
    and isolates errors to prevent affecting other tasks.
    """
    short_req = context.request_id[:8]
    cmd_name = context.command.lstrip("/")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info(f"[{now_str}] [REQ:{short_req}] [CHAT:{context.chat_id}] [{cmd_name}] START")

    try:
        async with task_manager.semaphore:
            messages = await worker_func()

        await send_or_edit_response(
            bot=bot,
            chat_id=context.chat_id,
            message_id=message_id,
            messages=messages,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            query=query,
            placeholder=placeholder
        )
        now_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{now_end}] [REQ:{short_req}] [CHAT:{context.chat_id}] [{cmd_name}] SUCCESS")

    except asyncio.CancelledError:
        now_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.warning(f"[{now_end}] [REQ:{short_req}] [CHAT:{context.chat_id}] [{cmd_name}] CANCELLED")
        await send_or_edit_response(
            bot=bot,
            chat_id=context.chat_id,
            message_id=message_id,
            messages=[f"⚠️ Permintaan {context.command} (REQ:{short_req}) dibatalkan."],
            reply_markup=reply_markup,
            query=query,
            placeholder=placeholder
        )
    except Exception as e:
        now_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.error(f"[{now_end}] [REQ:{short_req}] [CHAT:{context.chat_id}] [{cmd_name}] ERROR: {e}", exc_info=True)
        err_msg = f"❌ Terjadi kesalahan saat memproses permintaan {context.command}.\n\nError: {e}\nRequest ID: {short_req}"
        await send_or_edit_response(
            bot=bot,
            chat_id=context.chat_id,
            message_id=message_id,
            messages=[err_msg],
            reply_markup=reply_markup,
            query=query,
            placeholder=placeholder
        )
    finally:
        task_manager.unregister_task(context.request_id)


def run_concurrent_task(
    context: RequestContext,
    worker_func: Callable[[], Awaitable[List[str]]],
    bot: Optional[Bot] = None,
    message_id: Optional[int] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = None,
    query: Optional[Any] = None,
    placeholder: Optional[Any] = None
) -> asyncio.Task:
    """
    Schedules worker as an asynchronous task, registers it, and returns the Task.
    """
    task = asyncio.create_task(
        execute_worker_task(
            context=context,
            worker_func=worker_func,
            bot=bot,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            query=query,
            placeholder=placeholder
        )
    )
    task_manager.register_task(context, task)
    return task
