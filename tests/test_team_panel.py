from __future__ import annotations

import numpy as np
import pytest

from botCore import ImageMatchResult
from ymjh_bot.ym_game_task import YmGameTask


def make_match(found: bool, template: str, score: float = 0.99) -> ImageMatchResult:
    return ImageMatchResult(
        found=found,
        score=score if found else 0.1,
        center=(100, 100) if found else None,
        bbox=(90, 90, 110, 110) if found else None,
        template_path=template,
    )


@pytest.mark.parametrize(
    ("visible_template", "expected_open", "expected_in_team"),
    [
        (YmGameTask.TEXT_TEAM_PANEL_TITLE, True, False),
        (YmGameTask.BTN_TEAM_QUICK, True, False),
        (YmGameTask.BTN_TEAM_LEAVE, True, True),
        (None, False, False),
    ],
)
def test_normal_team_panel_state_uses_trusted_markers(
    monkeypatch: pytest.MonkeyPatch,
    visible_template: str | None,
    expected_open: bool,
    expected_in_team: bool,
) -> None:
    task = YmGameTask()
    screenshot = np.zeros((720, 1280, 3), dtype=np.uint8)
    monkeypatch.setattr(task, "screenshot", lambda: screenshot)
    monkeypatch.setattr(
        task,
        "_match_team_template",
        lambda screen, template, **kwargs: make_match(template == visible_template, template),
    )

    assert task.is_team_panel_open() is expected_open
    assert task.is_in_team() is expected_in_team


def test_open_team_panel_wakes_then_retries_only_correct_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = YmGameTask()
    events: list[object] = []
    panel_waits = iter((False, True))
    initial_panel_checks = iter((False,))

    monkeypatch.setattr(
        task,
        "wake_from_power_saving_if_needed",
        lambda: events.append("wake") or True,
    )
    monkeypatch.setattr(task, "is_quick_team_panel_open", lambda: False)
    monkeypatch.setattr(task, "is_team_panel_open", lambda: next(initial_panel_checks))
    monkeypatch.setattr(task, "collapse_chat_if_open", lambda: events.append("chat") or False)
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, *, offset: events.append(("click", x, y, offset)),
    )
    monkeypatch.setattr(task, "wait", lambda wait_ms: events.append(("wait", wait_ms)))
    monkeypatch.setattr(
        task,
        "wait_for_team_panel_open",
        lambda *, timeout_ms: events.append(("verify", timeout_ms)) or next(panel_waits),
    )

    task.open_team_panel(timeout_ms=2500, wait_after_click_ms=800)

    team_clicks = [event for event in events if isinstance(event, tuple) and event[0] == "click"]
    assert events[0] == "wake"
    assert team_clicks == [
        ("click", task.POINT_MAIN_TEAM[0], task.POINT_MAIN_TEAM[1], 0),
        ("click", task.POINT_MAIN_TEAM[0], task.POINT_MAIN_TEAM[1], 0),
    ]
    assert all(event[2] != 420 for event in team_clicks)


def test_open_team_panel_failure_saves_score_and_screenshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = YmGameTask()
    clicks: list[tuple[int, int]] = []
    task._last_match_score = 0.42
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(task, "is_quick_team_panel_open", lambda: False)
    monkeypatch.setattr(task, "is_team_panel_open", lambda: False)
    monkeypatch.setattr(task, "collapse_chat_if_open", lambda: False)
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, *, offset: clicks.append((x, y)),
    )
    monkeypatch.setattr(task, "wait", lambda wait_ms: None)
    monkeypatch.setattr(task, "wait_for_team_panel_open", lambda **kwargs: False)
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: "team-failed.png")

    with pytest.raises(RuntimeError, match=r"0\.420.*team-failed\.png"):
        task.open_team_panel()

    assert clicks == [task.POINT_MAIN_TEAM] * task.TEAM_PANEL_OPEN_ATTEMPTS
    assert not hasattr(task, "POINT_MAIN_TEAM_WHEN_TASK_PANEL_OPEN")


def test_create_team_with_one_member_never_starts_public_matching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = YmGameTask()
    events: list[object] = []
    monkeypatch.setattr(task, "open_team_panel", lambda **kwargs: events.append("open"))
    monkeypatch.setattr(task, "is_in_team", lambda: False)
    monkeypatch.setattr(
        task,
        "open_quick_team_panel",
        lambda **kwargs: events.append("quick"),
    )
    monkeypatch.setattr(
        task,
        "select_quick_team_target",
        lambda target, **kwargs: events.append(("target", target)),
    )
    monkeypatch.setattr(
        task,
        "click_template_if_available",
        lambda *args, **kwargs: events.append("create") or True,
    )
    monkeypatch.setattr(
        task,
        "wait_for_normal_team_state",
        lambda **kwargs: events.append("verified") or True,
    )
    monkeypatch.setattr(
        task,
        "click_point",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("人数要求为 1 时不应点击开始匹配")
        ),
    )
    monkeypatch.setattr(
        task,
        "wait_for_team_members",
        lambda count: (_ for _ in ()).throw(
            AssertionError("人数要求为 1 时不应进入招募等待")
        ),
    )

    task.create_team("日常", min_member_count=1)

    assert events == [
        "open",
        "quick",
        ("target", task.TEAM_TARGET_JIANGHU_DAILY),
        "create",
        "verified",
    ]
