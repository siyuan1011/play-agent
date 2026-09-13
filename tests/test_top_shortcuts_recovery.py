from __future__ import annotations

from pathlib import Path

import pytest

from botCore import VisionEngine
from botCore.vision import load_image
from ymjh_bot.ym_game_task import (
    ActivityEntryUnavailableError,
    LoginState,
    YmGameTask,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "top_shortcuts"


class _ShortcutTask(YmGameTask):
    task_name = "顶部快捷栏测试"


def _visual_task(image_path: Path) -> _ShortcutTask:
    task = _ShortcutTask()
    task._vision = VisionEngine()  # type: ignore[assignment]
    image = load_image(image_path)
    task.screenshot = lambda: image  # type: ignore[method-assign]
    return task


def test_visual_regression_distinguishes_expanded_and_collapsed_shortcuts() -> None:
    collapsed = _visual_task(FIXTURE_DIR / "collapsed.png")
    expanded = _visual_task(FIXTURE_DIR / "expanded.png")

    collapsed_state = collapsed.detect_login_state()
    expanded_state = expanded.detect_login_state()

    assert collapsed_state is not None
    assert collapsed_state.name == collapsed.LOGIN_STATE_MAIN_SHORTCUTS_COLLAPSED
    assert expanded_state is not None
    assert expanded_state.name == expanded.LOGIN_STATE_MAIN


def test_shortcut_arrow_is_not_detected_on_expanded_fixture() -> None:
    expanded = _visual_task(FIXTURE_DIR / "expanded.png")

    assert not expanded.find_image(
        expanded.BTN_TOP_SHORTCUTS_EXPAND,
        threshold=expanded.TOP_SHORTCUTS_EXPAND_THRESHOLD,
        roi=expanded.scale_roi(expanded.ROI_TOP_SHORTCUTS_CONTROL),
    )


def test_ensure_top_shortcuts_expanded_clicks_only_matched_arrow() -> None:
    task = _ShortcutTask()
    clicks: list[tuple[int, int, int]] = []
    logs: list[str] = []

    def find(template: str, **_kwargs: object) -> bool:
        if template == task.BTN_HD:
            return False
        assert template == task.BTN_TOP_SHORTCUTS_EXPAND
        task._last_match_center = (1078, 40)
        return True

    task.find_image = find  # type: ignore[method-assign]
    task.click_point = lambda x, y, *, offset: clicks.append((x, y, offset))  # type: ignore[method-assign]
    task.wait_image_appear = lambda template, **_kwargs: template == task.BTN_HD  # type: ignore[method-assign]
    task._log = logs.append  # type: ignore[method-assign]

    assert task.ensure_top_shortcuts_expanded()
    assert clicks == [(1078, 40, 0)]
    assert "顶部快捷栏已展开，已确认活动入口" in logs


def test_unavailable_activity_entry_sets_special_recovery_marker() -> None:
    task = _ShortcutTask()
    task.save_debug_screenshot = lambda _prefix: "shot.png"  # type: ignore[method-assign]

    with pytest.raises(ActivityEntryUnavailableError, match="shot.png"):
        task._raise_activity_entry_unavailable("测试")

    assert task.consume_activity_entry_failure()
    assert not task.consume_activity_entry_failure()


def test_activity_entry_error_bypasses_normal_step_retry() -> None:
    task = _ShortcutTask()

    assert not task.should_retry_step_failure(ActivityEntryUnavailableError("missing"))
    assert task.should_retry_step_failure(RuntimeError("other"))


def test_enter_game_wakes_before_unknown_scene_timeout_and_recovers_shortcuts() -> None:
    task = _ShortcutTask()
    events: list[str] = []
    states = iter(
        [
            None,
            LoginState(
                name=task.LOGIN_STATE_MAIN,
                description="干净主界面",
                score=1.0,
                center=(921, 63),
            ),
        ]
    )
    task.detect_login_state = lambda **_kwargs: next(states)  # type: ignore[method-assign]
    task.wake_from_power_saving_if_needed = lambda: events.append("wake") or False  # type: ignore[method-assign]
    task.ensure_top_shortcuts_expanded = lambda **_kwargs: events.append("shortcuts") or True  # type: ignore[method-assign]
    task.close_startup_panels = lambda **_kwargs: True  # type: ignore[method-assign]
    task._log = lambda _message: None  # type: ignore[method-assign]

    task.enter_game()

    assert events == ["wake", "shortcuts"]
