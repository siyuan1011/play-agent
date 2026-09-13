from __future__ import annotations

import pytest

from ymjh_bot.task.KYRW_task import KYRWTask


def _task() -> KYRWTask:
    task = KYRWTask()
    task._log = lambda _message: None  # type: ignore[method-assign]
    task.wait = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    return task


def test_purchase_settlement_skips_cleanup_when_already_main_scene() -> None:
    task = _task()
    task.is_game_main_ready = lambda **_kwargs: True  # type: ignore[method-assign]
    task.close_all_panels = lambda **_kwargs: pytest.fail("主界面不应关闭面板")  # type: ignore[method-assign]

    task.settle_purchase_to_main_scene("商城购买")


def test_purchase_settlement_closes_panels_until_main_scene_returns() -> None:
    task = _task()
    main_scene_states = iter((False, True))
    closed: list[dict[str, object]] = []
    task.is_game_main_ready = lambda **_kwargs: next(main_scene_states)  # type: ignore[method-assign]
    task.close_all_panels = lambda **kwargs: closed.append(kwargs)  # type: ignore[method-assign]

    task.settle_purchase_to_main_scene("摆摊购买")

    assert closed == [{"timeout_ms": 5000}]


def test_purchase_settlement_fails_when_cleanup_does_not_restore_main_scene() -> None:
    task = _task()
    closed: list[dict[str, object]] = []
    task.is_game_main_ready = lambda **_kwargs: False  # type: ignore[method-assign]
    task.close_all_panels = lambda **kwargs: closed.append(kwargs)  # type: ignore[method-assign]
    task.save_debug_screenshot = lambda _prefix: "purchase-not-closed.png"  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="关闭面板仍未回到主界面"):
        task.settle_purchase_to_main_scene("商城购买")

    assert closed == [{"timeout_ms": 5000}]


def test_acquire_route_does_not_submit_until_the_next_task_sidebar_click() -> None:
    task = _task()
    events: list[str] = []
    task.is_acquire_route_panel_visible = lambda: True  # type: ignore[method-assign]
    task.try_mall_route = lambda: events.append("mall") or True  # type: ignore[method-assign]
    task.handle_submit_panel_if_visible = lambda **_kwargs: events.append("submit") or True  # type: ignore[method-assign]

    assert task.handle_acquire_route_panel_if_visible()
    assert events == ["mall"]


def test_mall_purchase_uses_shared_main_scene_settlement() -> None:
    task = _task()
    events: list[str] = []
    task.ensure_acquire_route_panel_open = lambda: True  # type: ignore[method-assign]
    task.click_template_if_available = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    task.buy_from_mall_default_quantity = lambda: events.append("buy") or True  # type: ignore[method-assign]
    task.settle_purchase_to_main_scene = lambda description: events.append(description)  # type: ignore[method-assign]

    assert task.try_mall_route()
    assert events == ["buy", "商城购买"]


def test_trade_purchase_uses_shared_main_scene_settlement() -> None:
    task = _task()
    events: list[str] = []
    task.click_template_if_available = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    task.confirm_purchase_if_needed = lambda: True  # type: ignore[method-assign]
    task.settle_purchase_to_main_scene = lambda description: events.append(description)  # type: ignore[method-assign]

    assert task.buy_from_current_trade_panel("摆摊购买按钮", timeout_ms=1)
    assert events == ["摆摊购买按钮"]
