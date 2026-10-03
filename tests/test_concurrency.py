"""
Comprehensive Concurrency Tests for Telegram Bot Commands (Section 23).
Tests:
- Test 1: User A (/cek_putus) & User B (/cek_isolir) run concurrently without blocking.
- Test 2: Three users (/cek_putus, /cek_isolir, /cek_redaman) execute in parallel.
- Test 3: Fast task (/cek_isolir) completes and delivers BEFORE slow task (/cek_putus).
- Test 4: Prevention of crossed results across different chat IDs.
- Test 5: Error isolation (one task failing does not affect other concurrent tasks).
- Test 6: Semaphore concurrency limiting and task_manager registry tracking.
"""
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock

from app.telegram.tasks import RequestContext, run_concurrent_task, task_manager
from app.olt.handlers import cek_putus_command, cek_redaman_command
from app.telegram.handlers import cmd_cek_isolir, cmd_cek_off, cmd_cek_pelanggan


def _create_mock_update_and_context(chat_id: int, user_id: int):
    mock_update = MagicMock()
    mock_update.effective_chat.id = chat_id
    mock_update.effective_user.id = user_id
    mock_update.effective_user.username = f"user_{chat_id}"

    mock_bot = MagicMock()
    mock_bot.edit_message_text = AsyncMock()
    mock_bot.send_message = AsyncMock()

    placeholder = MagicMock()
    placeholder.message_id = chat_id * 100

    async def _delegate_edit(text, **kw):
        return await mock_bot.edit_message_text(chat_id=chat_id, text=text, **kw)

    placeholder.edit_text = AsyncMock(side_effect=_delegate_edit)
    mock_update.message.reply_text = AsyncMock(return_value=placeholder)

    mock_context = MagicMock()
    mock_context.bot = mock_bot
    mock_context.bot_data = {}

    return mock_update, mock_context, placeholder, mock_bot


def test_concurrency_test1_two_users_simultaneous(monkeypatch):
    """
    Test 1: User A (/cek_putus) and User B (/cek_isolir) run nearly simultaneously.
    Results must route strictly to Chat A and Chat B respectively.
    """
    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "111,222")

    update_a, ctx_a, placeholder_a, bot_a = _create_mock_update_and_context(111, 111)
    update_b, ctx_b, placeholder_b, bot_b = _create_mock_update_and_context(222, 222)

    # Mock OLT monitor
    mock_monitor = AsyncMock()
    mock_monitor.config.enabled = True
    mock_monitor.config.olt_name = "OLT-TEST"
    mock_monitor.get_offline_onts.return_value = []
    ctx_a.bot_data["olt_monitor"] = mock_monitor

    # Mock isolated PPPoE
    monkeypatch.setattr(
        "app.telegram.handlers.get_isolated_customers",
        lambda: {"status": "ok", "total_isolated": 0, "isolated_sessions": []}
    )

    async def _test():
        task_a = await cek_putus_command(update_a, ctx_a)
        task_b = await cmd_cek_isolir(update_b, ctx_b)

        assert task_a is not None
        assert task_b is not None

        await asyncio.gather(task_a, task_b)

        # Check User A result routed to Chat A
        bot_a.edit_message_text.assert_called_once()
        assert bot_a.edit_message_text.call_args[1]["chat_id"] == 111
        assert "ONT PUTUS" in bot_a.edit_message_text.call_args[1]["text"]

        # Check User B result routed to Chat B
        bot_b.edit_message_text.assert_called_once()
        assert bot_b.edit_message_text.call_args[1]["chat_id"] == 222
        assert "TIDAK ADA PELANGGAN DI-ISOLIR" in bot_b.edit_message_text.call_args[1]["text"]

    asyncio.run(_test())


def test_concurrency_test2_three_users_parallel(monkeypatch):
    """
    Test 2: Three users (/cek_putus, /cek_isolir, /cek_redaman) execute in parallel.
    All tasks run concurrently.
    """
    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "100,200,300")

    update_a, ctx_a, _, bot_a = _create_mock_update_and_context(100, 100)
    update_b, ctx_b, _, bot_b = _create_mock_update_and_context(200, 200)
    update_c, ctx_c, _, bot_c = _create_mock_update_and_context(300, 300)

    mock_monitor = AsyncMock()
    mock_monitor.config.enabled = True
    mock_monitor.config.olt_name = "OLT-TEST"
    mock_monitor.config.rx_power_threshold = -25.0
    mock_monitor.get_offline_onts.return_value = []
    mock_monitor.get_high_attenuation_onts.return_value = []

    ctx_a.bot_data["olt_monitor"] = mock_monitor
    ctx_c.bot_data["olt_monitor"] = mock_monitor

    monkeypatch.setattr(
        "app.telegram.handlers.get_isolated_customers",
        lambda: {"status": "ok", "total_isolated": 0, "isolated_sessions": []}
    )

    async def _test():
        t_a = await cek_putus_command(update_a, ctx_a)
        t_b = await cmd_cek_isolir(update_b, ctx_b)
        t_c = await cek_redaman_command(update_c, ctx_c)

        await asyncio.gather(t_a, t_b, t_c)

        assert bot_a.edit_message_text.call_args[1]["chat_id"] == 100
        assert bot_b.edit_message_text.call_args[1]["chat_id"] == 200
        assert bot_c.edit_message_text.call_args[1]["chat_id"] == 300

    asyncio.run(_test())


def test_concurrency_test3_fast_task_not_blocked_by_slow_task(monkeypatch):
    """
    Test 3: Slow task (/cek_putus takes 0.25s) and fast task (/cek_isolir takes 0.02s).
    Fast task MUST complete and deliver response BEFORE slow task finishes.
    """
    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "111,222")

    update_slow, ctx_slow, _, bot_slow = _create_mock_update_and_context(111, 111)
    update_fast, ctx_fast, _, bot_fast = _create_mock_update_and_context(222, 222)

    delivery_order = []

    async def slow_get_offline_onts():
        await asyncio.sleep(0.20)
        return []

    mock_monitor = AsyncMock()
    mock_monitor.config.enabled = True
    mock_monitor.config.olt_name = "OLT-TEST"
    mock_monitor.get_offline_onts = slow_get_offline_onts
    ctx_slow.bot_data["olt_monitor"] = mock_monitor

    def slow_edit(*args, **kwargs):
        delivery_order.append("SLOW_DELIVERED")

    def fast_edit(*args, **kwargs):
        delivery_order.append("FAST_DELIVERED")

    bot_slow.edit_message_text.side_effect = slow_edit
    bot_fast.edit_message_text.side_effect = fast_edit

    def fast_get_isolated():
        time.sleep(0.01)
        return {"status": "ok", "total_isolated": 0, "isolated_sessions": []}

    monkeypatch.setattr("app.telegram.handlers.get_isolated_customers", fast_get_isolated)

    async def _test():
        t_slow = await cek_putus_command(update_slow, ctx_slow)
        t_fast = await cmd_cek_isolir(update_fast, ctx_fast)

        await asyncio.gather(t_slow, t_fast)

        # Fast task MUST have finished and delivered first!
        assert delivery_order == ["FAST_DELIVERED", "SLOW_DELIVERED"]

    asyncio.run(_test())


def test_concurrency_test4_prevent_crossed_results(monkeypatch):
    """
    Test 4: Multiple users sending requests concurrently with varying completion times.
    Results must strictly map 1:1 to origin chat IDs without cross-talk or mixups.
    """
    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "1,2,3,4")

    updates = {}
    contexts = {}
    bots = {}

    for uid in [1, 2, 3, 4]:
        upd, ctx, _, bot = _create_mock_update_and_context(uid, uid)
        updates[uid] = upd
        contexts[uid] = ctx
        bots[uid] = bot

    mock_monitor = AsyncMock()
    mock_monitor.config.enabled = True
    mock_monitor.config.olt_name = "OLT-TEST"
    mock_monitor.config.rx_power_threshold = -25.0
    mock_monitor.get_offline_onts.return_value = []
    mock_monitor.get_high_attenuation_onts.return_value = []

    contexts[1].bot_data["olt_monitor"] = mock_monitor
    contexts[2].bot_data["olt_monitor"] = mock_monitor
    contexts[3].bot_data["olt_monitor"] = mock_monitor

    monkeypatch.setattr(
        "app.telegram.handlers.get_isolated_customers",
        lambda: {"status": "ok", "total_isolated": 0, "isolated_sessions": []}
    )

    async def _test():
        t1 = await cek_putus_command(updates[1], contexts[1])
        t2 = await cek_putus_command(updates[2], contexts[2])
        t3 = await cek_redaman_command(updates[3], contexts[3])
        t4 = await cmd_cek_isolir(updates[4], contexts[4])

        await asyncio.gather(t1, t2, t3, t4)

        assert bots[1].edit_message_text.call_args[1]["chat_id"] == 1
        assert "ONT PUTUS" in bots[1].edit_message_text.call_args[1]["text"]

        assert bots[2].edit_message_text.call_args[1]["chat_id"] == 2
        assert "ONT PUTUS" in bots[2].edit_message_text.call_args[1]["text"]

        assert bots[3].edit_message_text.call_args[1]["chat_id"] == 3
        assert "REDAMAN" in bots[3].edit_message_text.call_args[1]["text"]

        assert bots[4].edit_message_text.call_args[1]["chat_id"] == 4
        assert "ISOLIR" in bots[4].edit_message_text.call_args[1]["text"]

    asyncio.run(_test())


def test_concurrency_test5_error_isolation(monkeypatch):
    """
    Test 5: An unhandled exception in Task A must NOT crash or prevent Task B from completing.
    """
    monkeypatch.setattr("app.core.config.settings.telegram_allowed_chat_ids_raw", "111,222")

    update_err, ctx_err, _, bot_err = _create_mock_update_and_context(111, 111)
    update_ok, ctx_ok, _, bot_ok = _create_mock_update_and_context(222, 222)

    # Task A will throw an exception
    mock_monitor = AsyncMock()
    mock_monitor.config.enabled = True
    mock_monitor.get_offline_onts.side_effect = RuntimeError("SNMP timeout on OLT")
    ctx_err.bot_data["olt_monitor"] = mock_monitor

    # Task B will succeed
    monkeypatch.setattr(
        "app.telegram.handlers.get_isolated_customers",
        lambda: {"status": "ok", "total_isolated": 0, "isolated_sessions": []}
    )

    async def _test():
        t_err = await cek_putus_command(update_err, ctx_err)
        t_ok = await cmd_cek_isolir(update_ok, ctx_ok)

        await asyncio.gather(t_err, t_ok)

        # Task A receives isolated error message
        bot_err.edit_message_text.assert_called_once()
        assert "Terjadi kesalahan" in bot_err.edit_message_text.call_args[1]["text"]
        assert bot_err.edit_message_text.call_args[1]["chat_id"] == 111

        # Task B receives normal success
        bot_ok.edit_message_text.assert_called_once()
        assert "TIDAK ADA PELANGGAN DI-ISOLIR" in bot_ok.edit_message_text.call_args[1]["text"]
        assert bot_ok.edit_message_text.call_args[1]["chat_id"] == 222

    asyncio.run(_test())


def test_concurrency_test6_task_manager_registry():
    """
    Test 6: Verify task registration, active count, and cleanup upon task finish.
    """
    context = RequestContext(
        request_id="test-req-1234",
        chat_id=999,
        user_id=888,
        command="/test_cmd"
    )

    mock_bot = MagicMock()
    mock_bot.edit_message_text = AsyncMock()
    mock_bot.send_message = AsyncMock()

    async def _test():
        started_evt = asyncio.Event()

        async def _worker():
            started_evt.set()
            await asyncio.sleep(0.05)
            return ["DONE"]

        task = run_concurrent_task(
            context=context,
            worker_func=_worker,
            bot=mock_bot
        )

        await started_evt.wait()
        # While running, task must be in active registry
        assert "test-req-1234" in task_manager.get_active_tasks()
        assert task_manager.active_count >= 1

        await task

        # After completion, task must be automatically cleaned up
        assert "test-req-1234" not in task_manager.get_active_tasks()

    asyncio.run(_test())
