from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from botCore import StepStopException, VisionEngine
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


def test_rcfb_step_sequence_merges_follow_wait_into_match() -> None:
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
    assert start_meta["timeout_ms"] == RCFBTask.MATCH_WAIT_TIMEOUT_MS == 300000
    assert flow_meta["retry"] == 0
    assert flow_meta["timeout_ms"] == RCFBTask.TASK_FLOW_TIMEOUT_MS == 1800000
    assert exit_meta["retry"] == 0
    assert exit_meta["timeout_ms"] == 420000


def test_start_daily_match_starts_follow_listener_immediately(monkeypatch) -> None:
    task = RCFBTask()
    events: list[tuple[str, int | None]] = []
    monkeypatch.setattr(task, "start_daily_auto_match", lambda: events.append(("match", None)))
    monkeypatch.setattr(
        task,
        "wait_for_team_follow_confirm",
        lambda *, timeout_ms: events.append(("follow", timeout_ms)),
    )

    task.start_daily_match()

    assert events == [("match", None), ("follow", task.MATCH_WAIT_TIMEOUT_MS)]


@pytest.mark.parametrize("template_found", [False, True])
def test_auto_match_click_has_no_post_click_wait(monkeypatch, template_found: bool) -> None:
    task = RCFBTask()
    click_kwargs: list[dict] = []
    fixed_clicks: list[tuple] = []
    waits: list[int] = []
    monkeypatch.setattr(task, "open_quick_team_panel", lambda **kwargs: None)
    monkeypatch.setattr(task, "select_daily_raid_quick_target", lambda **kwargs: None)

    def click_template(*args, **kwargs) -> bool:
        click_kwargs.append(kwargs)
        return template_found

    monkeypatch.setattr(task, "click_template_if_available", click_template)
    monkeypatch.setattr(task, "click_point", lambda *args, **kwargs: fixed_clicks.append(args))
    monkeypatch.setattr(task, "wait", waits.append)

    task.start_daily_auto_match()

    assert click_kwargs[0]["wait_after_click_ms"] == 0
    assert bool(fixed_clicks) is not template_found
    assert waits == []


def test_follow_confirmation_click_returns_before_team_state_probe(monkeypatch) -> None:
    task = RCFBTask()
    confirm_kwargs: list[dict] = []
    logs: list[str] = []
    monkeypatch.setattr(task, "is_stopped", lambda: False)

    def confirm(*args, **kwargs) -> bool:
        confirm_kwargs.append(kwargs)
        return True

    monkeypatch.setattr(task, "confirm_center_modal_ok_if_visible", confirm)
    monkeypatch.setattr(
        task,
        "open_team_panel",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("不应检查队伍面板")),
    )
    monkeypatch.setattr(task, "_log", logs.append)

    task.wait_for_team_follow_confirm(timeout_ms=task.MATCH_WAIT_TIMEOUT_MS)

    assert confirm_kwargs == [{"wait_after_click_ms": 0}]
    assert logs[-1] == "已点击入队跟随确认"
    assert hasattr(RCFBTask, "confirm_already_in_team")


def test_follow_dialog_is_polled_every_one_second(monkeypatch) -> None:
    task = RCFBTask()
    clock = [0.0]
    detection_times: list[float] = []
    waits: list[int] = []
    monkeypatch.setattr("ymjh_bot.task.RCFB_task.time.perf_counter", lambda: clock[0])
    monkeypatch.setattr(task, "is_stopped", lambda: False)

    def confirm(*args, **kwargs) -> bool:
        detection_times.append(clock[0])
        return clock[0] >= 4.0

    def advance(wait_ms: int) -> None:
        waits.append(wait_ms)
        clock[0] += wait_ms / 1000.0

    monkeypatch.setattr(task, "confirm_center_modal_ok_if_visible", confirm)
    monkeypatch.setattr(task, "wait", advance)

    task.wait_for_team_follow_confirm(timeout_ms=10000)

    assert detection_times == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert waits == [task.MATCH_WAIT_POLL_INTERVAL_MS] * 4


def test_follow_wait_times_out_after_heartbeat_and_final_team_checks(monkeypatch) -> None:
    task = RCFBTask()
    clock = [0.0]
    detection_times: list[float] = []
    waits: list[int] = []
    cancelled: list[bool] = []
    team_checks: list[float] = []
    monkeypatch.setattr("ymjh_bot.task.RCFB_task.time.perf_counter", lambda: clock[0])
    monkeypatch.setattr(task, "is_stopped", lambda: False)

    def confirm(*args, **kwargs) -> bool:
        detection_times.append(clock[0])
        return False

    def advance(wait_ms: int) -> None:
        waits.append(wait_ms)
        clock[0] += wait_ms / 1000.0

    monkeypatch.setattr(task, "confirm_center_modal_ok_if_visible", confirm)
    monkeypatch.setattr(task, "wait", advance)
    monkeypatch.setattr(
        task,
        "confirm_already_in_team",
        lambda: team_checks.append(clock[0]) or False,
    )
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: "follow-timeout.png")
    monkeypatch.setattr(
        task,
        "cancel_daily_match_after_timeout",
        lambda: cancelled.append(True) or True,
    )

    with pytest.raises(RuntimeError, match="5 分钟") as exc_info:
        task.wait_for_team_follow_confirm(timeout_ms=task.MATCH_WAIT_TIMEOUT_MS)

    assert "follow-timeout.png" in str(exc_info.value)
    assert detection_times == [float(second) for second in range(300)]
    assert waits == [task.MATCH_WAIT_POLL_INTERVAL_MS] * 300
    assert team_checks == [float(second) for second in range(30, 301, 30)]
    assert cancelled == [True]


def test_follow_wait_returns_when_heartbeat_confirms_existing_team(monkeypatch) -> None:
    task = RCFBTask()
    clock = [0.0]
    team_checks: list[float] = []
    cancelled: list[bool] = []
    monkeypatch.setattr("ymjh_bot.task.RCFB_task.time.perf_counter", lambda: clock[0])
    monkeypatch.setattr(task, "is_stopped", lambda: False)
    monkeypatch.setattr(task, "confirm_center_modal_ok_if_visible", lambda *args, **kwargs: False)
    monkeypatch.setattr(task, "wait", lambda wait_ms: clock.__setitem__(0, clock[0] + wait_ms / 1000.0))
    monkeypatch.setattr(
        task,
        "confirm_already_in_team",
        lambda: team_checks.append(clock[0]) or True,
    )
    monkeypatch.setattr(
        task,
        "cancel_daily_match_after_timeout",
        lambda: cancelled.append(True) or True,
    )

    task.wait_for_team_follow_confirm(timeout_ms=task.MATCH_WAIT_TIMEOUT_MS)

    assert team_checks == [30.0]
    assert cancelled == []


def test_follow_timeout_final_team_check_does_not_cancel_joined_team(monkeypatch) -> None:
    task = RCFBTask()
    clock = [0.0]
    cancelled: list[bool] = []
    monkeypatch.setattr("ymjh_bot.task.RCFB_task.time.perf_counter", lambda: clock[0])
    monkeypatch.setattr(task, "is_stopped", lambda: False)
    monkeypatch.setattr(task, "confirm_center_modal_ok_if_visible", lambda *args, **kwargs: False)
    monkeypatch.setattr(task, "wait", lambda wait_ms: clock.__setitem__(0, clock[0] + wait_ms / 1000.0))
    monkeypatch.setattr(task, "confirm_already_in_team", lambda: True)
    monkeypatch.setattr(
        task,
        "cancel_daily_match_after_timeout",
        lambda: cancelled.append(True) or True,
    )

    task.wait_for_team_follow_confirm(timeout_ms=10000)

    assert cancelled == []


def test_confirm_already_in_team_closes_panel_after_explicit_leave_marker(monkeypatch) -> None:
    task = RCFBTask()
    events: list[str] = []
    monkeypatch.setattr(task, "open_team_panel", lambda **kwargs: events.append("open"))
    monkeypatch.setattr(task, "is_in_team", lambda: events.append("state") or True)
    monkeypatch.setattr(task, "close_all_panels", lambda **kwargs: events.append("close"))
    monkeypatch.setattr(task, "_log", lambda message: events.append(message))

    assert task.confirm_already_in_team()
    assert events == [
        "open",
        "state",
        "检测到已处于队伍中，继续进入副本任务检测",
        "close",
    ]


def test_match_timeout_cancellation_uses_template_and_cleans_panels(monkeypatch) -> None:
    task = RCFBTask()
    events: list[str] = []
    clicked_templates: list[str] = []
    monkeypatch.setattr(task, "open_quick_team_panel", lambda **kwargs: events.append("open"))
    monkeypatch.setattr(
        task,
        "select_daily_raid_quick_target",
        lambda **kwargs: events.append("select"),
    )

    def click_template(template, **kwargs) -> bool:
        clicked_templates.append(template)
        events.append("cancel")
        return True

    monkeypatch.setattr(task, "click_template_if_available", click_template)
    monkeypatch.setattr(task, "close_all_panels", lambda **kwargs: events.append("close"))

    assert task.cancel_daily_match_after_timeout()
    assert clicked_templates == [task.BTN_TEAM_CANCEL_MATCH]
    assert events == ["open", "select", "cancel", "close"]


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


def test_missing_tracker_rematches_three_times_then_fails(monkeypatch) -> None:
    task = RCFBTask()
    leaves: list[bool] = []
    jumps: list[str] = []
    monkeypatch.setattr(task, "wait_for_dungeon_task", lambda **kwargs: False)
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: "missing-tracker.png")
    monkeypatch.setattr(task, "leave_team_if_present", lambda: leaves.append(True))
    monkeypatch.setattr(task, "jump_to", jumps.append)

    for expected_count in range(1, task.MAX_LEADER_REMATCHES + 1):
        task.wait_dungeon_task()
        assert task._leader_rematch_count == expected_count

    with pytest.raises(RuntimeError, match="连续 4 支队伍"):
        task.wait_dungeon_task()

    assert jumps == ["start_daily_match"] * task.MAX_LEADER_REMATCHES
    assert len(leaves) == task.MAX_LEADER_REMATCHES + 1


def test_sidebar_error_does_not_consume_leader_rematch(monkeypatch) -> None:
    task = RCFBTask()
    monkeypatch.setattr(
        task,
        "wait_for_dungeon_task",
        lambda **kwargs: (_ for _ in ()).throw(TaskSidebarStateError("过渡异常")),
    )

    with pytest.raises(TaskSidebarStateError, match="过渡异常"):
        task.wait_dungeon_task()

    assert task._leader_rematch_count == 0


def test_startup_reset_clears_leader_rematch_count() -> None:
    task = RCFBTask()
    task._leader_rematch_count = task.MAX_LEADER_REMATCHES

    task.reset_startup_state()

    assert task._leader_rematch_count == 0


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


def test_raid_flow_never_clicks_while_hangup_highlight_is_active(monkeypatch) -> None:
    task = RCFBTask()
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


def test_leave_after_completion_clicks_exit_then_exit_team(monkeypatch) -> None:
    task = RCFBTask()
    clicks: list[tuple[str, dict]] = []
    transfers: list[int] = []

    def click_template(template: str, **kwargs) -> bool:
        clicks.append((template, kwargs))
        return True

    monkeypatch.setattr(task, "click_template_if_available", click_template)
    monkeypatch.setattr(task, "click_visible_dungeon_exit_team_button", lambda: False)
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
    transfers: list[int] = []
    monkeypatch.setattr(task, "click_visible_dungeon_exit_team_button", lambda: True)
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
    clicked_templates: list[str] = []
    button_results = iter([False, True])
    transfers: list[int] = []
    monkeypatch.setattr(task, "click_visible_dungeon_exit_team_button", lambda: False)

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
    transfers: list[int] = []
    leaves: list[bool] = []
    screenshots: list[str] = []
    monkeypatch.setattr(task, "click_visible_dungeon_exit_team_button", lambda: False)
    monkeypatch.setattr(task, "click_template_if_available", lambda *args, **kwargs: False)
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
    monkeypatch.setattr(task, "leave_team_if_present", lambda: leaves.append(True))

    task.leave_team_after_completion()

    assert screenshots == ["rcfb_exit_team_button_missing"]
    assert transfers == [task.DUNGEON_AUTO_TRANSFER_TIMEOUT_MS]
    assert task.DUNGEON_AUTO_TRANSFER_TIMEOUT_MS == 330000
    assert leaves == [True]


@pytest.mark.parametrize("exit_team_clicked", [False, True])
def test_leave_after_completion_transfer_timeout_does_not_rerun(
    monkeypatch,
    exit_team_clicked: bool,
) -> None:
    task = RCFBTask()
    leaves: list[bool] = []
    monkeypatch.setattr(
        task,
        "click_dungeon_exit_team_with_retries",
        lambda: exit_team_clicked,
    )
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: "exit-missing.png")
    monkeypatch.setattr(
        task,
        "wait_for_dungeon_transfer_complete",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("传送超时")),
    )
    monkeypatch.setattr(task, "leave_team_if_present", lambda: leaves.append(True))

    task.leave_team_after_completion()

    assert leaves == [True]


def test_leave_after_completion_stop_interrupts_auto_transfer(monkeypatch) -> None:
    task = RCFBTask()
    monkeypatch.setattr(task, "click_dungeon_exit_team_with_retries", lambda: False)
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
