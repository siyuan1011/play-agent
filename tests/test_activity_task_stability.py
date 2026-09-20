from __future__ import annotations

import pytest

from ymjh_bot.task.BPRW_task import BPRWTask
from ymjh_bot.task.RCFB_task import RCFBTask
from ymjh_bot.task.XSRW_task import XSRWTask
from ymjh_bot.ym_game_task import YmGameTask


def test_bangpai_transition_drains_residual_npc_dialogue() -> None:
    task = BPRWTask()
    events: list[str] = []
    task.wait_auto_pathfinding = lambda **_kwargs: True  # type: ignore[method-assign]
    task.drain_dialog_next = lambda: events.append("dialog") or 1  # type: ignore[method-assign]

    task.wait_bangpai_task_transition("测试")

    assert events == ["dialog"]


def test_daily_dungeon_team_step_only_creates_team() -> None:
    task = RCFBTask()
    events: list[str] = []
    task.create_team = lambda *_args, **_kwargs: events.append("create-team")  # type: ignore[method-assign]

    task.ensure_daily_team()

    assert events == ["create-team"]


def test_task_start_strictly_leaves_team_before_final_panel_close() -> None:
    task = YmGameTask()
    task.LEAVE_TEAM_ON_START = True
    events: list[object] = []
    task._log = lambda _message: None  # type: ignore[method-assign]
    task.close_all_panels = lambda **kwargs: events.append(  # type: ignore[method-assign]
        ("close", kwargs.get("timeout_ms"))
    )
    task.after_startup_panel_close = lambda: None  # type: ignore[method-assign]
    task.wake_from_power_saving_if_needed = lambda: False  # type: ignore[method-assign]
    task.leave_team = lambda **kwargs: events.append(("leave", kwargs)) or False  # type: ignore[method-assign]
    task._run_health_precheck = lambda context: events.append(("health", context))  # type: ignore[method-assign]

    task.on_start()

    assert events == [
        ("close", None),
        ("leave", {"timeout_ms": 5000, "wait_after_click_ms": 1000}),
        ("close", task.STARTUP_FINAL_CLOSE_TIMEOUT_MS),
        ("health", "任务启动"),
    ]


def test_task_start_propagates_leave_team_failure() -> None:
    task = YmGameTask()
    task.LEAVE_TEAM_ON_START = True
    task._log = lambda _message: None  # type: ignore[method-assign]
    task.close_all_panels = lambda **_kwargs: None  # type: ignore[method-assign]
    task.after_startup_panel_close = lambda: None  # type: ignore[method-assign]
    task.wake_from_power_saving_if_needed = lambda: False  # type: ignore[method-assign]
    task.leave_team = lambda **_kwargs: (_ for _ in ()).throw(  # type: ignore[method-assign]
        RuntimeError("退队失败")
    )

    with pytest.raises(RuntimeError, match="退队失败"):
        task.on_start()


def test_team_tasks_use_shared_strict_startup_leave() -> None:
    assert RCFBTask.LEAVE_TEAM_ON_START
    assert XSRWTask.LEAVE_TEAM_ON_START
    assert "leave_team_if_present" not in RCFBTask.__dict__
    assert "leave_team_if_present" not in XSRWTask.__dict__
    assert "is_daily_dungeon_panel_visible" not in RCFBTask.__dict__


def test_daily_dungeon_panel_retry_step_never_creates_team() -> None:
    task = RCFBTask()
    events: list[str] = []
    task.close_all_panels = lambda **_kwargs: events.append("close")  # type: ignore[method-assign]
    task.open_daily_dungeon_panel = lambda: events.append("open-panel")  # type: ignore[method-assign]
    task.enter_daily_dungeon_challenge = lambda: events.append("challenge")  # type: ignore[method-assign]

    task.start_daily_match()

    assert events == ["close", "open-panel", "challenge"]
