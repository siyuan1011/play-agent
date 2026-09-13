from __future__ import annotations

from ymjh_bot.task.BPRW_task import BPRWTask
from ymjh_bot.task.RCFB_task import RCFBTask


def test_bangpai_transition_drains_residual_npc_dialogue() -> None:
    task = BPRWTask()
    events: list[str] = []
    task.wait_auto_pathfinding = lambda **_kwargs: True  # type: ignore[method-assign]
    task.drain_dialog_next = lambda: events.append("dialog") or 1  # type: ignore[method-assign]

    task.wait_bangpai_task_transition("测试")

    assert events == ["dialog"]


def test_daily_dungeon_reuses_existing_team_without_recreating() -> None:
    task = RCFBTask()
    events: list[str] = []
    task.open_team_panel = lambda **_kwargs: events.append("open-team")  # type: ignore[method-assign]
    task.is_in_team = lambda: True  # type: ignore[method-assign]
    task.create_team = lambda *_args, **_kwargs: events.append("create-team")  # type: ignore[method-assign]
    task.close_all_panels = lambda **_kwargs: events.append("close")  # type: ignore[method-assign]
    task._log = lambda _message: None  # type: ignore[method-assign]

    task.ensure_daily_team()

    assert events == ["open-team", "close"]


def test_daily_dungeon_panel_retry_step_never_creates_team() -> None:
    task = RCFBTask()
    events: list[str] = []
    task.close_all_panels = lambda **_kwargs: events.append("close")  # type: ignore[method-assign]
    task.open_daily_dungeon_panel = lambda: events.append("open-panel")  # type: ignore[method-assign]
    task.enter_daily_dungeon_challenge = lambda: events.append("challenge")  # type: ignore[method-assign]

    task.start_daily_match()

    assert events == ["close", "open-panel", "challenge"]
