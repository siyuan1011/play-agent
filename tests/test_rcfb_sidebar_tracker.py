from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import ImageMatchResult, StepStopException, VisionEngine
from ymjh_bot.task.RCFB_task import RCFBTask
from ymjh_bot.ym_game_task import TaskSidebarStateError


FIXTURES = Path(__file__).parent / "fixtures" / "ymjh"


def load_image(path: Path):
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert image is not None, path
    return image


def detect_tracker(fixture_name: str) -> RCFBTask:
    task = RCFBTask()
    task._vision = VisionEngine()
    task.screenshot = lambda: load_image(FIXTURES / fixture_name)  # type: ignore[method-assign]
    return task


@pytest.mark.parametrize(
    "fixture_name",
    [
        "rcfb_daily_tracker_dark.webp",
        "rcfb_daily_tracker_light.webp",
    ],
)
def test_daily_dungeon_title_detects_battle_and_pathfinding_cards(fixture_name: str) -> None:
    task = detect_tracker(fixture_name)

    assert task.find_dungeon_task_candidate()
    assert task._last_match_score >= 0.95
    assert task._last_match_center is not None
    x, y = task._last_match_center
    assert 95 <= x <= 108
    assert 155 <= y <= 172


@pytest.mark.parametrize(
    "fixture_name",
    [
        "bangpai_debug_task_complete.webp",
        "bprw_task_panel_scrolled_20260713_013453.webp",
        "kyrw_keye_20260707/40_keye_path_or_dialog.webp",
        "task_sidebar_v2/day_task_sidebar.webp",
    ],
)
def test_daily_dungeon_title_rejects_other_task_sidebars(fixture_name: str) -> None:
    task = detect_tracker(fixture_name)

    assert not task.find_dungeon_task_candidate()
    assert task._last_match_score < task.DUNGEON_TASK_THRESHOLD
    assert task._last_match_center is None


def test_daily_dungeon_scan_uses_task_tab(monkeypatch) -> None:
    task = RCFBTask()
    selected_panels: list[str] = []
    monkeypatch.setattr(task, "collapse_chat_if_open", lambda: False)
    monkeypatch.setattr(
        task,
        "switch_task_panel",
        lambda panel, **kwargs: selected_panels.append(panel),
    )
    monkeypatch.setattr(task, "find_dungeon_task_candidate", lambda: True)

    assert task.find_dungeon_task_in_sidebar(max_scrolls=0)
    assert selected_panels == ["任务"]


def test_daily_dungeon_tracker_templates_are_packaged() -> None:
    assert all(Path(template).is_file() for template in RCFBTask.TEXT_DAILY_DUNGEON_TRACKERS)
    assert all(
        Path(template).is_file()
        for template in RCFBTask.TAB_DUNGEON_HANGUP_ACTIVE
    )
    assert Path(RCFBTask.TEXT_DUNGEON_TRANSFER_OUT).is_file()
    assert Path(RCFBTask.ICON_DUNGEON_EXIT).is_file()
    assert Path(RCFBTask.BTN_DUNGEON_EXIT_TEAM).is_file()


@pytest.mark.parametrize(
    "fixture_name",
    [
        "rcfb_daily_tracker_dark.webp",
        "rcfb_daily_tracker_light.webp",
        "rcfb_dungeon_complete.webp",
    ],
)
def test_dungeon_hangup_active_detects_real_highlighted_tabs(
    fixture_name: str,
) -> None:
    task = detect_tracker(fixture_name)

    assert task.is_dungeon_hangup_active()
    assert task._last_match_score >= task.DUNGEON_HANGUP_ACTIVE_THRESHOLD


@pytest.mark.parametrize(
    "fixture_name",
    [
        "unstuck_real_closed_after_20260716.webp",
        "scene_loading_95.webp",
        "xsrw/jypy_victory.webp",
    ],
)
def test_dungeon_hangup_active_rejects_inactive_and_non_hud_scenes(
    fixture_name: str,
) -> None:
    task = detect_tracker(fixture_name)

    assert not task.is_dungeon_hangup_active()
    assert task._last_match_score < task.DUNGEON_HANGUP_ACTIVE_THRESHOLD


def test_dungeon_hangup_active_accepts_dim_template_with_cyan_highlight() -> None:
    task = RCFBTask()
    screenshot = np.zeros((720, 1280, 3), dtype=np.uint8)
    x, y, width, height = task.ROI_DUNGEON_HANGUP_ACTIVE
    screenshot[y : y + height, x : x + width] = (150, 150, 40)

    class DimActiveVision:
        @staticmethod
        def match_template(*args, **kwargs):
            return ImageMatchResult(True, 0.855, (198, 14), (158, 0, 238, 28))

    task._vision = DimActiveVision()  # type: ignore[assignment]
    task.screenshot = lambda: screenshot  # type: ignore[method-assign]

    assert task.is_dungeon_hangup_active()
    assert task._last_match_center == (198, 14)


def test_dungeon_hangup_active_rejects_dim_neutral_tab() -> None:
    task = RCFBTask()
    screenshot = np.full((720, 1280, 3), 100, dtype=np.uint8)

    class DimInactiveVision:
        @staticmethod
        def match_template(*args, **kwargs):
            return ImageMatchResult(True, 0.938, (198, 14), (158, 0, 238, 28))

    task._vision = DimInactiveVision()  # type: ignore[assignment]
    task.screenshot = lambda: screenshot  # type: ignore[method-assign]

    assert not task.is_dungeon_hangup_active()
    assert task._last_match_center is None


def test_dungeon_transfer_out_detects_real_completion_screen() -> None:
    task = detect_tracker("rcfb_dungeon_complete.webp")

    assert task.is_dungeon_transfer_out_visible()
    assert task._last_match_score >= 0.99
    assert task._last_match_center == (955, 194)


@pytest.mark.parametrize(
    "fixture_name",
    [
        "rcfb_daily_tracker_dark.webp",
        "rcfb_daily_tracker_light.webp",
        "bangpai_debug_task_complete.webp",
        "task_sidebar_v2/day_task_sidebar.webp",
        "rcfb_exit_modal.webp",
    ],
)
def test_dungeon_transfer_out_rejects_non_completion_screens(fixture_name: str) -> None:
    task = detect_tracker(fixture_name)

    assert not task.is_dungeon_transfer_out_visible()
    assert task._last_match_score < task.DUNGEON_TRANSFER_OUT_THRESHOLD


def test_exit_team_button_template_matches_only_left_modal_action() -> None:
    screenshot = load_image(FIXTURES / "rcfb_exit_modal.webp")
    match = VisionEngine().match_template(
        screenshot,
        RCFBTask.BTN_DUNGEON_EXIT_TEAM,
        threshold=RCFBTask.DUNGEON_EXIT_TEAM_THRESHOLD,
        roi=(300, 440, 700, 130),
    )

    assert match.found
    assert match.score >= 0.99
    assert match.center == (422, 508)


def test_rcfb_step_sequence_uses_single_player_team_flow() -> None:
    steps = RCFBTask.get_steps()
    step_names = [name for name, _, _ in steps]
    start_meta = next(meta for name, _, meta in steps if name == "start_daily_match")
    flow_meta = next(meta for name, _, meta in steps if name == "run_daily_raid_flow")
    exit_meta = next(meta for name, _, meta in steps if name == "leave_team_after_completion")

    assert step_names == [
        "start_daily_match",
        "wait_dungeon_task",
        "run_daily_raid_flow",
        "leave_team_after_completion",
    ]
    assert start_meta["retry"] == 3
    assert start_meta["timeout_ms"] == RCFBTask.DAILY_START_TIMEOUT_MS == 300000
    assert flow_meta["retry"] == 0
    assert flow_meta["timeout_ms"] == RCFBTask.TASK_FLOW_TIMEOUT_MS == 1800000
    assert exit_meta["retry"] == 0
    assert exit_meta["timeout_ms"] == 420000


def test_start_daily_match_creates_one_player_team_then_challenges(monkeypatch) -> None:
    task = RCFBTask()
    events: list[object] = []
    monkeypatch.setattr(
        task,
        "create_team",
        lambda target, **kwargs: events.append(("create", target, kwargs)),
    )
    monkeypatch.setattr(task, "close_all_panels", lambda **kwargs: events.append("close"))
    monkeypatch.setattr(task, "open_daily_dungeon_panel", lambda: events.append("panel"))
    monkeypatch.setattr(task, "enter_daily_dungeon_challenge", lambda: events.append("enter"))

    task.start_daily_match()

    assert events == [
        ("create", "日常", {"min_member_count": 1}),
        "close",
        "panel",
        "enter",
    ]


def test_open_daily_panel_uses_jianghu_activity_entry(monkeypatch) -> None:
    task = RCFBTask()
    panel_states = iter((False, True))
    events: list[object] = []
    monkeypatch.setattr(
        task,
        "is_daily_dungeon_panel_visible",
        lambda **kwargs: next(panel_states),
    )
    monkeypatch.setattr(
        task,
        "open_activity_panel",
        lambda category, **kwargs: events.append(("activity", category, kwargs)),
    )
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, *, offset: events.append(("click", x, y, offset)),
    )
    monkeypatch.setattr(task, "wait", lambda wait_ms: events.append(("wait", wait_ms)))
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task.open_daily_dungeon_panel()

    assert events == [
        (
            "activity",
            "江湖",
            {"wait_after_open_ms": task.DAILY_ACTIVITY_SETTLE_MS},
        ),
        ("click", *task.POINT_ACTIVITY_DAILY_ENTRY, 0),
        ("wait", task.DAILY_ACTIVITY_SETTLE_MS),
    ]


def test_daily_challenge_clicks_challenge_then_countdown_confirm(monkeypatch) -> None:
    task = RCFBTask()
    matches = iter(
        (
            ImageMatchResult(False, 0.1, None, None),
            ImageMatchResult(True, 0.99, (1165, 660), None),
            ImageMatchResult(True, 0.78, (1067, 597), None),
        )
    )
    taps: list[tuple[int, int]] = []
    monkeypatch.setattr(task, "_wait_daily_binary_match", lambda *args, **kwargs: next(matches))
    monkeypatch.setattr(task, "is_daily_dungeon_panel_visible", lambda **kwargs: True)
    monkeypatch.setattr(task, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(task, "wait", lambda wait_ms: None)
    monkeypatch.setattr(task, "wait_for_daily_dungeon_panel_close", lambda: True)
    monkeypatch.setattr(task, "_log", lambda *args: None)

    task.enter_daily_dungeon_challenge()

    assert taps == [(1165, 660), (1067, 597)]


def configure_dungeon_wait_clock(monkeypatch, task: RCFBTask, scans: int) -> None:
    expiration_checks = iter([False] * scans + [True])
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: next(expiration_checks))
    monkeypatch.setattr(task, "_remaining_ms", lambda deadline: task.DUNGEON_TASK_POLL_INTERVAL_MS)
    monkeypatch.setattr(task, "wait", lambda wait_ms: None)


def test_dungeon_wait_retries_sidebar_transition_then_recovers(monkeypatch) -> None:
    task = RCFBTask()
    scans = iter([TaskSidebarStateError("侧栏切换中"), True])
    configure_dungeon_wait_clock(monkeypatch, task, scans=2)

    def find_tracker(**kwargs) -> bool:
        result = next(scans)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(task, "find_dungeon_task_in_sidebar", find_tracker)

    assert task.wait_for_dungeon_task(timeout_ms=1000)


def test_dungeon_wait_reraises_last_error_when_no_valid_scan_completes(monkeypatch) -> None:
    task = RCFBTask()
    errors = iter([TaskSidebarStateError("首次异常"), TaskSidebarStateError("最终异常")])
    configure_dungeon_wait_clock(monkeypatch, task, scans=2)
    monkeypatch.setattr(
        task,
        "find_dungeon_task_in_sidebar",
        lambda **kwargs: (_ for _ in ()).throw(next(errors)),
    )

    with pytest.raises(TaskSidebarStateError, match="最终异常"):
        task.wait_for_dungeon_task(timeout_ms=1000)


def test_dungeon_wait_returns_false_only_after_valid_missing_scans(monkeypatch) -> None:
    task = RCFBTask()
    configure_dungeon_wait_clock(monkeypatch, task, scans=2)
    monkeypatch.setattr(task, "find_dungeon_task_in_sidebar", lambda **kwargs: False)

    assert not task.wait_for_dungeon_task(timeout_ms=1000)


def test_dungeon_wait_keeps_valid_missing_result_after_later_sidebar_error(monkeypatch) -> None:
    task = RCFBTask()
    scans = iter([False, TaskSidebarStateError("后续过渡异常")])
    configure_dungeon_wait_clock(monkeypatch, task, scans=2)

    def find_tracker(**kwargs) -> bool:
        result = next(scans)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(task, "find_dungeon_task_in_sidebar", find_tracker)

    assert not task.wait_for_dungeon_task(timeout_ms=1000)


def test_missing_tracker_in_self_created_team_fails_without_rematching(monkeypatch) -> None:
    task = RCFBTask()
    jumps: list[str] = []
    monkeypatch.setattr(task, "wait_for_dungeon_task", lambda **kwargs: False)
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: "missing-tracker.png")
    monkeypatch.setattr(task, "jump_to", jumps.append)

    with pytest.raises(RuntimeError, match="自建单人队伍挑战后") as exc_info:
        task.wait_dungeon_task()

    assert "missing-tracker.png" in str(exc_info.value)
    assert jumps == []


def test_current_tracker_click_does_not_switch_or_scroll_sidebar(monkeypatch) -> None:
    task = RCFBTask()
    events: list[object] = []
    monkeypatch.setattr(task, "find_dungeon_task_candidate", lambda: True)
    monkeypatch.setattr(task, "click", lambda **kwargs: events.append("click"))
    monkeypatch.setattr(task, "wait", lambda wait_ms: events.append(wait_ms))
    monkeypatch.setattr(
        task,
        "switch_task_panel",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应切换任务页签")),
    )
    monkeypatch.setattr(
        task,
        "scroll_task_list_down",
        lambda: (_ for _ in ()).throw(AssertionError("不应滚动任务栏")),
    )

    assert task.click_current_dungeon_task_if_visible()
    assert events == ["click", task.DUNGEON_TRACKER_CLICK_INTERVAL_MS]
    assert task.DUNGEON_TRACKER_CLICK_INTERVAL_MS == 5000


def test_current_tracker_click_can_skip_internal_wait(monkeypatch) -> None:
    task = RCFBTask()
    events: list[object] = []
    monkeypatch.setattr(task, "find_dungeon_task_candidate", lambda: True)
    monkeypatch.setattr(task, "click", lambda **kwargs: events.append("click"))
    monkeypatch.setattr(task, "wait", lambda wait_ms: events.append(wait_ms))

    assert task.click_current_dungeon_task_if_visible(wait_after_click_ms=0)
    assert events == ["click"]


def test_raid_flow_prioritizes_completion_marker_over_visible_tracker(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_entered()
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: False)
    monkeypatch.setattr(task, "is_dungeon_transfer_out_visible", lambda: True)
    monkeypatch.setattr(
        task,
        "wake_from_power_saving_if_needed",
        lambda: (_ for _ in ()).throw(
            AssertionError("结束标识出现后不应执行省电唤醒")
        ),
    )
    monkeypatch.setattr(
        task,
        "is_dungeon_hangup_active",
        lambda: (_ for _ in ()).throw(
            AssertionError("结束标识出现后不应检测挂机状态")
        ),
    )
    monkeypatch.setattr(
        task,
        "click_current_dungeon_task_if_visible",
        lambda: (_ for _ in ()).throw(AssertionError("结束标识出现后不应点击任务追踪")),
    )
    monkeypatch.setattr(
        task,
        "wait_auto_pathfinding",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("不应等待自动寻路")),
    )
    monkeypatch.setattr(
        task,
        "auto_battle",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("不应主动执行自动战斗")),
    )

    task.run_daily_raid_flow()

    assert task._dungeon_completion_confirmed


def test_raid_flow_rejects_unconfirmed_dungeon_without_polling(monkeypatch) -> None:
    task = RCFBTask()
    monkeypatch.setattr(
        task,
        "is_dungeon_transfer_out_visible",
        lambda: (_ for _ in ()).throw(
            AssertionError("未确认入本时不应开始副本画面轮询")
        ),
    )

    with pytest.raises(RuntimeError, match="未确认进入日常副本"):
        task.run_daily_raid_flow()


def test_raid_flow_never_clicks_while_hangup_highlight_is_active(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_entered()
    completion_results = iter((False, False, True))
    hangup_results = iter((True, True))
    waits: list[int] = []
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: False)
    monkeypatch.setattr(
        task,
        "_remaining_ms",
        lambda deadline: task.DUNGEON_HANGUP_VERIFY_INTERVAL_MS,
    )
    monkeypatch.setattr(task, "is_stopped", lambda: False)
    monkeypatch.setattr(
        task,
        "is_dungeon_transfer_out_visible",
        lambda: next(completion_results),
    )
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_outside_main_frame", lambda: False)
    monkeypatch.setattr(
        task,
        "is_dungeon_hangup_active",
        lambda: next(hangup_results),
    )
    monkeypatch.setattr(
        task,
        "click_current_dungeon_task_if_visible",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("挂机高亮时不应点击任务栏")
        ),
    )
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "_log", lambda message: None)

    task.run_daily_raid_flow()

    assert waits == [task.DUNGEON_HANGUP_VERIFY_INTERVAL_MS] * 2


def test_raid_flow_retries_after_highlight_disappears_and_resets_failures(
    monkeypatch,
) -> None:
    task = RCFBTask()
    task.mark_dungeon_entered()
    completion_results = iter((False, False, False, False, True))
    hangup_results = iter((False, True, False, True))
    click_kwargs: list[dict] = []
    waits: list[int] = []
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: False)
    monkeypatch.setattr(
        task,
        "_remaining_ms",
        lambda deadline: task.DUNGEON_HANGUP_VERIFY_INTERVAL_MS,
    )
    monkeypatch.setattr(task, "is_stopped", lambda: False)
    monkeypatch.setattr(
        task,
        "is_dungeon_transfer_out_visible",
        lambda: next(completion_results),
    )
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_outside_main_frame", lambda: False)
    monkeypatch.setattr(
        task,
        "is_dungeon_hangup_active",
        lambda: next(hangup_results),
    )
    monkeypatch.setattr(
        task,
        "click_current_dungeon_task_if_visible",
        lambda **kwargs: click_kwargs.append(kwargs) or True,
    )
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "_log", lambda message: None)

    task.run_daily_raid_flow()

    assert click_kwargs == [
        {"wait_after_click_ms": 0},
        {"wait_after_click_ms": 0},
    ]
    assert waits == [task.DUNGEON_HANGUP_VERIFY_INTERVAL_MS] * 4


def test_raid_flow_fails_after_three_full_hangup_verification_windows(
    monkeypatch,
) -> None:
    task = RCFBTask()
    task.mark_dungeon_entered()
    click_kwargs: list[dict] = []
    waits: list[int] = []
    screenshots: list[str] = []
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: False)
    monkeypatch.setattr(
        task,
        "_remaining_ms",
        lambda deadline: task.DUNGEON_HANGUP_VERIFY_INTERVAL_MS,
    )
    monkeypatch.setattr(task, "is_stopped", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_transfer_out_visible", lambda: False)
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_outside_main_frame", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_hangup_active", lambda: False)
    monkeypatch.setattr(
        task,
        "click_current_dungeon_task_if_visible",
        lambda **kwargs: click_kwargs.append(kwargs) or True,
    )
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "_log", lambda message: None)
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or "hangup-missing.png",
    )

    with pytest.raises(RuntimeError, match="连续 3 次") as exc_info:
        task.run_daily_raid_flow()

    assert "hangup-missing.png" in str(exc_info.value)
    assert click_kwargs == [{"wait_after_click_ms": 0}] * 3
    assert waits == [task.DUNGEON_HANGUP_VERIFY_INTERVAL_MS] * 3
    assert screenshots == ["rcfb_hangup_state_failed"]


def test_raid_flow_does_not_blind_tap_when_tracker_is_hidden(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_entered()
    tracker_checks: list[dict] = []
    screenshots: list[str] = []
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: False)
    monkeypatch.setattr(
        task,
        "_remaining_ms",
        lambda deadline: task.DUNGEON_HANGUP_VERIFY_INTERVAL_MS,
    )
    monkeypatch.setattr(task, "is_stopped", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_transfer_out_visible", lambda: False)
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_outside_main_frame", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_hangup_active", lambda: False)
    monkeypatch.setattr(
        task,
        "click_current_dungeon_task_if_visible",
        lambda **kwargs: tracker_checks.append(kwargs) or False,
    )
    monkeypatch.setattr(task, "wait", lambda wait_ms: None)
    monkeypatch.setattr(task, "_log", lambda message: None)
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or "hangup-missing.png",
    )

    with pytest.raises(RuntimeError, match="连续 3 次"):
        task.run_daily_raid_flow()

    assert tracker_checks == [{"wait_after_click_ms": 0}] * 3
    assert screenshots == ["rcfb_hangup_state_failed"]


def test_raid_flow_wakes_power_saving_before_hangup_detection(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_entered()
    completion_results = iter((False, False, False, True))
    wake_results = iter((True, False))
    hangup_results = iter((True, True))
    events: list[str] = []
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: False)
    monkeypatch.setattr(
        task,
        "_remaining_ms",
        lambda deadline: task.DUNGEON_HANGUP_VERIFY_INTERVAL_MS,
    )
    monkeypatch.setattr(task, "is_stopped", lambda: False)
    monkeypatch.setattr(
        task,
        "is_dungeon_transfer_out_visible",
        lambda: next(completion_results),
    )
    monkeypatch.setattr(
        task,
        "wake_from_power_saving_if_needed",
        lambda: events.append("wake") or next(wake_results),
    )
    monkeypatch.setattr(task, "is_dungeon_outside_main_frame", lambda: False)
    monkeypatch.setattr(
        task,
        "is_dungeon_hangup_active",
        lambda: events.append("hangup") or next(hangup_results),
    )
    monkeypatch.setattr(
        task,
        "click_current_dungeon_task_if_visible",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("省电唤醒后已恢复挂机，不应点击任务栏")
        ),
    )
    monkeypatch.setattr(task, "wait", lambda wait_ms: None)
    monkeypatch.setattr(task, "_log", lambda message: None)

    task.run_daily_raid_flow()

    assert events == ["wake", "hangup", "wake", "hangup"]


def test_raid_flow_accepts_stable_main_scene_when_transfer_countdown_was_missed(
    monkeypatch,
) -> None:
    task = RCFBTask()
    task.mark_dungeon_entered()
    waits: list[int] = []
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: False)
    monkeypatch.setattr(
        task,
        "_remaining_ms",
        lambda deadline: task.DUNGEON_HANGUP_VERIFY_INTERVAL_MS,
    )
    monkeypatch.setattr(task, "is_stopped", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_transfer_out_visible", lambda: False)
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_outside_main_frame", lambda: True)
    monkeypatch.setattr(
        task,
        "is_dungeon_hangup_active",
        lambda: True,
    )
    monkeypatch.setattr(
        task,
        "click_current_dungeon_task_if_visible",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("已稳定回到主界面时不应点击任务追踪")
        ),
    )
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "_log", lambda message: None)
    monkeypatch.setattr(task, "_debug", lambda message: None)

    task.run_daily_raid_flow()

    assert task._dungeon_completion_confirmed
    assert waits == [task.DUNGEON_HANGUP_VERIFY_INTERVAL_MS] * 2


def test_leave_after_completion_clicks_exit_then_exit_team(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_completed()
    clicks: list[tuple[str, dict]] = []
    transfers: list[int] = []

    def click_template(template: str, **kwargs) -> bool:
        clicks.append((template, kwargs))
        return True

    monkeypatch.setattr(task, "click_template_if_available", click_template)
    monkeypatch.setattr(task, "click_visible_dungeon_exit_team_button", lambda: False)
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(
        task,
        "wait_for_dungeon_transfer_complete",
        lambda *, timeout_ms: transfers.append(timeout_ms),
    )
    monkeypatch.setattr(
        task,
        "leave_team_if_present",
        lambda: (_ for _ in ()).throw(AssertionError("完成退本不应调用吞异常的通用退队")),
    )

    task.leave_team_after_completion()

    assert [template for template, _ in clicks] == [
        task.ICON_DUNGEON_EXIT,
        task.BTN_DUNGEON_EXIT_TEAM,
    ]
    assert clicks[0][1]["roi"] == task.ROI_DUNGEON_EXIT
    assert clicks[1][1]["roi"] == (300, 440, 700, 130)
    assert clicks[1][1]["wait_after_click_ms"] == 0
    assert transfers == [60000]


def test_leave_after_completion_clicks_already_open_exit_team_dialog(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_completed()
    transfers: list[int] = []
    monkeypatch.setattr(task, "click_visible_dungeon_exit_team_button", lambda: True)
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(
        task,
        "click_template_if_available",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("弹框已打开时不应再次点击退出图标")
        ),
    )
    monkeypatch.setattr(
        task,
        "wait_for_dungeon_transfer_complete",
        lambda *, timeout_ms: transfers.append(timeout_ms),
    )

    task.leave_team_after_completion()

    assert transfers == [60000]


def test_leave_after_completion_retries_exit_locally_before_success(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_completed()
    clicked_templates: list[str] = []
    button_results = iter([False, True])
    transfers: list[int] = []
    monkeypatch.setattr(task, "click_visible_dungeon_exit_team_button", lambda: False)
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)

    def click_template(template: str, **kwargs) -> bool:
        clicked_templates.append(template)
        if template == task.ICON_DUNGEON_EXIT:
            return True
        return next(button_results)

    monkeypatch.setattr(task, "click_template_if_available", click_template)
    monkeypatch.setattr(
        task,
        "wait_for_dungeon_transfer_complete",
        lambda *, timeout_ms: transfers.append(timeout_ms),
    )
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: (_ for _ in ()).throw(
            AssertionError("局部重试成功后不应保存失败截图")
        ),
    )

    task.leave_team_after_completion()

    assert clicked_templates == [
        task.ICON_DUNGEON_EXIT,
        task.BTN_DUNGEON_EXIT_TEAM,
        task.ICON_DUNGEON_EXIT,
        task.BTN_DUNGEON_EXIT_TEAM,
    ]
    assert transfers == [60000]


def test_leave_after_completion_waits_for_auto_transfer_then_leaves_team(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_completed()
    transfers: list[int] = []
    leaves: list[bool] = []
    screenshots: list[str] = []
    monkeypatch.setattr(task, "click_visible_dungeon_exit_team_button", lambda: False)
    monkeypatch.setattr(task, "click_template_if_available", lambda *args, **kwargs: False)
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    outside_states = iter((False, True))
    monkeypatch.setattr(
        task,
        "wait_for_verified_outside_dungeon",
        lambda **kwargs: next(outside_states),
    )
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or "exit-missing.png",
    )
    monkeypatch.setattr(
        task,
        "wait_for_dungeon_transfer_complete",
        lambda *, timeout_ms: transfers.append(timeout_ms),
    )
    monkeypatch.setattr(task, "leave_team", lambda **kwargs: leaves.append(True))
    monkeypatch.setattr(task, "close_all_panels", lambda **kwargs: None)
    monkeypatch.setattr(task, "is_game_main_ready", lambda **kwargs: True)

    task.leave_team_after_completion()

    assert screenshots == ["rcfb_exit_team_button_missing"]
    assert transfers == [task.DUNGEON_AUTO_TRANSFER_TIMEOUT_MS]
    assert task.DUNGEON_AUTO_TRANSFER_TIMEOUT_MS == 330000
    assert leaves == [True]


def test_failed_uncompleted_dungeon_never_waits_for_auto_transfer(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_entered()
    screenshots: list[str] = []
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(task, "click_dungeon_exit_team_with_retries", lambda: False)
    monkeypatch.setattr(task, "wait_for_verified_outside_dungeon", lambda **kwargs: False)
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or "failure-exit.png",
    )
    monkeypatch.setattr(
        task,
        "wait_for_dungeon_transfer_complete",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("未完成副本不得等待自动传出")
        ),
    )

    with pytest.raises(RuntimeError, match="禁止依赖自动传出"):
        task.exit_team_dungeon_strict(
            allow_auto_transfer=False,
            screenshot_prefix="rcfb_failure_exit_missing",
        )

    assert screenshots == ["rcfb_failure_exit_missing"]


def test_failed_dungeon_cleanup_accepts_verified_outside_scene(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_entered()
    events: list[str] = []
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(task, "click_dungeon_exit_team_with_retries", lambda: False)
    monkeypatch.setattr(
        task,
        "wait_for_verified_outside_dungeon",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        task,
        "finish_verified_outside_dungeon_cleanup",
        lambda: events.append("outside-cleaned"),
    )

    task.exit_team_dungeon_strict(
        allow_auto_transfer=False,
        screenshot_prefix="must-not-save",
    )

    assert events == ["outside-cleaned"]


def test_outside_verification_wakes_power_saving_and_requires_three_frames(
    monkeypatch,
) -> None:
    task = RCFBTask()
    wake_states = iter((True, False, False))
    outside_frame_calls: list[bool] = []
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: False)
    monkeypatch.setattr(task, "_remaining_ms", lambda deadline: 1000)
    monkeypatch.setattr(task, "wait", lambda ms: None)
    monkeypatch.setattr(
        task,
        "wake_from_power_saving_if_needed",
        lambda: next(wake_states),
    )
    monkeypatch.setattr(
        task,
        "is_dungeon_outside_main_frame",
        lambda: outside_frame_calls.append(True) or True,
    )

    assert task.wait_for_verified_outside_dungeon()
    assert len(outside_frame_calls) == task.DUNGEON_OUTSIDE_STABLE_CONFIRMATIONS


def test_outside_main_frame_uses_one_atomic_screenshot() -> None:
    task = RCFBTask()
    screenshot = np.zeros((720, 1280, 3), dtype=np.uint8)
    screenshot_calls: list[bool] = []

    class MainFrameVision:
        @staticmethod
        def match_template(image, templates, **kwargs):
            assert image is screenshot
            candidates = [templates] if isinstance(templates, str) else templates
            found = task.BTN_HD in candidates
            return ImageMatchResult(
                found,
                0.99 if found else 0.0,
                (921, 63) if found else None,
                None,
            )

    task._vision = MainFrameVision()  # type: ignore[assignment]
    task.screenshot = lambda: screenshot_calls.append(True) or screenshot  # type: ignore[method-assign]

    assert task.is_dungeon_outside_main_frame()
    assert screenshot_calls == [True]


def test_failure_cleanup_wakes_and_exits_confirmed_dungeon(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_entered()
    events: list[object] = []
    monkeypatch.setattr(
        task,
        "wake_from_power_saving_if_needed",
        lambda: events.append("wake") or True,
    )
    monkeypatch.setattr(
        task,
        "close_all_panels",
        lambda **kwargs: events.append(("close", kwargs)),
    )
    monkeypatch.setattr(
        task,
        "exit_team_dungeon_strict",
        lambda **kwargs: events.append(("exit", kwargs)),
    )

    task.cleanup_after_failure("hangup failed")

    assert events == [
        "wake",
        (
            "close",
            {"timeout_ms": task.DUNGEON_FAILURE_PANEL_CLEANUP_TIMEOUT_MS},
        ),
        (
            "exit",
            {
                "allow_auto_transfer": False,
                "screenshot_prefix": "rcfb_failure_exit_missing",
            },
        ),
    ]


@pytest.mark.parametrize("exit_team_clicked", [False, True])
def test_leave_after_completion_transfer_timeout_is_not_swallowed(
    monkeypatch,
    exit_team_clicked: bool,
) -> None:
    task = RCFBTask()
    task.mark_dungeon_completed()
    leaves: list[bool] = []
    monkeypatch.setattr(
        task,
        "click_dungeon_exit_team_with_retries",
        lambda: exit_team_clicked,
    )
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    if not exit_team_clicked:
        monkeypatch.setattr(task, "wait_for_verified_outside_dungeon", lambda **kwargs: False)
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: "exit-missing.png")
    monkeypatch.setattr(
        task,
        "wait_for_dungeon_transfer_complete",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("传送超时")),
    )
    monkeypatch.setattr(task, "leave_team", lambda **kwargs: leaves.append(True))

    with pytest.raises(RuntimeError, match="传送超时"):
        task.leave_team_after_completion()

    assert leaves == []


def test_leave_after_completion_stop_interrupts_auto_transfer(monkeypatch) -> None:
    task = RCFBTask()
    task.mark_dungeon_completed()
    monkeypatch.setattr(task, "click_dungeon_exit_team_with_retries", lambda: False)
    monkeypatch.setattr(task, "wake_from_power_saving_if_needed", lambda: False)
    monkeypatch.setattr(task, "wait_for_verified_outside_dungeon", lambda **kwargs: False)
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: "exit-missing.png")
    monkeypatch.setattr(
        task,
        "wait_for_dungeon_transfer_complete",
        lambda **kwargs: (_ for _ in ()).throw(StepStopException("Stop requested")),
    )
    monkeypatch.setattr(
        task,
        "leave_team_if_present",
        lambda: (_ for _ in ()).throw(AssertionError("停止后不应继续退队")),
    )

    with pytest.raises(StepStopException):
        task.leave_team_after_completion()


def test_transfer_wait_requires_three_stable_main_scene_frames(monkeypatch) -> None:
    task = RCFBTask()
    exit_states = iter([True, False, False, False])
    transfer_out_states = iter([True, False, False, False])
    main_ready_calls: list[dict] = []
    waits: list[int] = []
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: False)
    monkeypatch.setattr(task, "_remaining_ms", lambda deadline: task.DUNGEON_TRANSFER_POLL_INTERVAL_MS)
    monkeypatch.setattr(task, "is_stopped", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_exit_visible", lambda: next(exit_states))
    monkeypatch.setattr(task, "is_dungeon_transfer_out_visible", lambda: next(transfer_out_states))

    def main_ready(**kwargs) -> bool:
        main_ready_calls.append(kwargs)
        return True

    monkeypatch.setattr(task, "is_game_main_ready", main_ready)
    monkeypatch.setattr(task, "wait", waits.append)

    task.wait_for_dungeon_transfer_complete(timeout_ms=60000)

    assert main_ready_calls == [{"timeout_ms": 0, "threshold": 0.8}] * 3
    assert waits == [task.DUNGEON_TRANSFER_POLL_INTERVAL_MS] * 3


def test_transfer_wait_times_out_when_main_scene_never_stabilizes(monkeypatch) -> None:
    task = RCFBTask()
    expiration_checks = iter([False, False, True])
    waits: list[int] = []
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: next(expiration_checks))
    monkeypatch.setattr(task, "_remaining_ms", lambda deadline: task.DUNGEON_TRANSFER_POLL_INTERVAL_MS)
    monkeypatch.setattr(task, "is_stopped", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_exit_visible", lambda: False)
    monkeypatch.setattr(task, "is_dungeon_transfer_out_visible", lambda: False)
    monkeypatch.setattr(task, "is_game_main_ready", lambda **kwargs: False)
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: "transfer-timeout.png")

    with pytest.raises(RuntimeError, match="等待传送结束超时") as exc_info:
        task.wait_for_dungeon_transfer_complete(timeout_ms=1000)

    assert "transfer-timeout.png" in str(exc_info.value)
    assert waits == [task.DUNGEON_TRANSFER_POLL_INTERVAL_MS] * 2
