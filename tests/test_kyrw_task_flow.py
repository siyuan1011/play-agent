from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import ImageMatchResult, StepJumpException, StepStopException, VisionEngine
from ymjh_bot.task.KYRW_task import KYRWTask, _YinshiState
from ymjh_bot.ym_game_task import TaskSidebarStateError


REPO_ROOT = Path(__file__).parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ymjh" / "kyrw_keye_20260707"


def load_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path))
    assert image is not None, f"无法读取测试图片：{path}"
    return image


def make_yinshi_match(card_id: int, center_x: int, center_y: int = 112) -> ImageMatchResult:
    return ImageMatchResult(
        found=True,
        score=0.99,
        center=(center_x, center_y),
        bbox=(center_x - 44, center_y - 38, center_x + 44, center_y + 38),
        template_path=str(card_id),
    )


def make_yinshi_state(
    order: list[int],
    target_order: list[int],
    positions: list[int],
) -> _YinshiState:
    cards = tuple(
        make_yinshi_match(card_id, positions[index])
        for index, card_id in enumerate(order)
    )
    correct_slots = frozenset(
        index
        for index, card_id in enumerate(order)
        if card_id == target_order[index]
    )
    return _YinshiState(
        visible=True,
        screenshot=np.zeros((720, 1280, 3), dtype=np.uint8),
        cards=cards,
        correct_slots=correct_slots,
    )


@pytest.mark.parametrize(
    ("fixture_name", "expected_centers", "expected_correct_slots"),
    [
        ("54_yinshi_4_cards.png", [511, 646, 781, 916], set()),
        ("55_yinshi_3_cards.png", [579, 714, 849], set()),
        ("56_yinshi_5_cards.png", [444, 579, 714, 849, 984], set()),
        ("57_yinshi_partial_correct.png", [444, 579, 714, 849, 984], {2}),
    ],
)
def test_yinshi_state_uses_dynamic_real_device_card_positions(
    fixture_name: str,
    expected_centers: list[int],
    expected_correct_slots: set[int],
) -> None:
    task = KYRWTask()
    task._vision = VisionEngine()
    state = task._read_yinshi_state(load_image(FIXTURE_DIR / fixture_name))

    assert state.visible
    assert [card.center[0] for card in state.cards] == expected_centers
    assert state.correct_slots == expected_correct_slots


def test_yinshi_templates_reject_non_poetry_frame() -> None:
    task = KYRWTask()
    task._vision = VisionEngine()

    state = task._read_yinshi_state(load_image(FIXTURE_DIR / "52_dialog_requires_confirm.png"))

    assert not state.visible
    assert state.cards == ()
    assert state.correct_slots == frozenset()


def test_yinshi_card_matches_merge_duplicate_peaks_and_keep_dynamic_spacing() -> None:
    task = KYRWTask()
    matches = [
        make_yinshi_match(0, 710),
        ImageMatchResult(
            found=True,
            score=0.91,
            center=(718, 113),
            bbox=(674, 75, 762, 151),
            template_path="duplicate",
        ),
        make_yinshi_match(1, 292),
        make_yinshi_match(2, 487),
        make_yinshi_match(3, 1035),
    ]

    merged = task._merge_yinshi_card_matches(matches)

    assert [match.center[0] for match in merged] == [292, 487, 710, 1035]


def test_yinshi_fingerprint_tracks_same_card_without_reading_text() -> None:
    task = KYRWTask()
    task._vision = VisionEngine()
    before = task._read_yinshi_state(load_image(FIXTURE_DIR / "56_yinshi_5_cards.png"))
    after = task._read_yinshi_state(load_image(FIXTURE_DIR / "57_yinshi_partial_correct.png"))

    source = task._yinshi_card_fingerprint(before.screenshot, before.cards[2])
    moved_target = task._yinshi_card_fingerprint(after.screenshot, after.cards[1])
    different_card = task._yinshi_card_fingerprint(after.screenshot, after.cards[2])

    assert task._yinshi_fingerprint_similarity(source, moved_target) >= 0.99
    assert task._yinshi_fingerprint_similarity(source, different_card) < 0.6


def test_yinshi_drag_uses_current_detected_card_coordinates(monkeypatch) -> None:
    task = KYRWTask()
    source = make_yinshi_match(1, 887, center_y=126)
    target = make_yinshi_match(0, 361, center_y=104)
    swipes: list[tuple[int, int, int, int, int]] = []
    waits: list[int] = []
    monkeypatch.setattr(
        task,
        "swipe",
        lambda x1, y1, x2, y2, *, duration_ms: swipes.append(
            (x1, y1, x2, y2, duration_ms)
        ),
    )
    monkeypatch.setattr(task, "wait", waits.append)

    task._drag_yinshi_card(source, target)

    assert swipes == [
        (
            source.center[0],
            source.bbox[3] + task.YINSHI_DRAG_Y_OFFSET_FROM_TOP_BOTTOM,
            target.center[0],
            target.bbox[3] + task.YINSHI_DRAG_Y_OFFSET_FROM_TOP_BOTTOM,
            task.YINSHI_DRAG_DURATION_MS,
        )
    ]
    assert waits == [task.YINSHI_DRAG_SETTLE_MS]


def test_yinshi_solver_rechecks_correct_slots_and_dynamic_positions(monkeypatch) -> None:
    task = KYRWTask()
    target_order = [0, 1, 2, 3]
    order = [2, 0, 1, 3]
    position_sets = [
        [274, 449, 708, 1038],
        [288, 463, 721, 1050],
    ]
    last_positions: list[int] = []
    read_count = 0
    drags: list[tuple[int, int, int, int]] = []

    def read_state(*args, **kwargs) -> _YinshiState:
        nonlocal read_count, last_positions
        last_positions = position_sets[read_count % len(position_sets)]
        read_count += 1
        return make_yinshi_state(order, target_order, last_positions)

    def drag(source: ImageMatchResult, target: ImageMatchResult) -> None:
        source_index = last_positions.index(source.center[0])
        target_index = last_positions.index(target.center[0])
        drags.append((source_index, target_index, source.center[0], target.center[0]))
        card_id = order.pop(source_index)
        order.insert(target_index, card_id)

    monkeypatch.setattr(task, "_read_yinshi_state", read_state)
    monkeypatch.setattr(task, "_drag_yinshi_card", drag)
    monkeypatch.setattr(
        task,
        "_yinshi_card_fingerprint",
        lambda screenshot, card: np.array([[int(card.template_path)]], dtype=np.uint8),
    )
    monkeypatch.setattr(
        task,
        "_yinshi_fingerprint_similarity",
        lambda expected, actual: 1.0 if np.array_equal(expected, actual) else 0.0,
    )
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "_log", lambda *args, **kwargs: None)

    assert task.handle_yinshi_task_if_visible()
    assert order == target_order
    assert read_count > len(drags)
    assert all(source_index > target_index for source_index, target_index, _, _ in drags)
    assert len({source_x for _, _, source_x, _ in drags}) > 1
    assert {target_index for _, target_index, _, _ in drags} == {0, 1}


def test_yinshi_solver_skips_an_already_correct_panel(monkeypatch) -> None:
    task = KYRWTask()
    order = [0, 1, 2, 3, 4, 5]
    state = make_yinshi_state(order, order, [258, 374, 531, 689, 884, 1055])
    monkeypatch.setattr(task, "_read_yinshi_state", lambda *args, **kwargs: state)
    monkeypatch.setattr(
        task,
        "_drag_yinshi_card",
        lambda *args, **kwargs: pytest.fail("已有红勾的槽位不应拖动"),
    )
    waits: list[int] = []
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "_log", lambda *args, **kwargs: None)

    assert task.handle_yinshi_task_if_visible()
    assert waits == [task.YINSHI_COMPLETE_WAIT_MS]


def test_yinshi_solver_treats_panel_disappearance_as_handled(monkeypatch) -> None:
    task = KYRWTask()
    visible = make_yinshi_state([1, 0], [0, 1], [402, 811])
    hidden = _YinshiState(
        visible=False,
        screenshot=np.zeros((720, 1280, 3), dtype=np.uint8),
    )
    states = iter([visible, visible, visible, hidden])
    drag_calls: list[int] = []
    monkeypatch.setattr(task, "_read_yinshi_state", lambda *args, **kwargs: next(states))
    monkeypatch.setattr(
        task,
        "_drag_yinshi_card",
        lambda *args, **kwargs: drag_calls.append(1),
    )
    monkeypatch.setattr(task, "_log", lambda *args, **kwargs: None)

    assert task.handle_yinshi_task_if_visible()
    assert drag_calls == [1]


def test_yinshi_solver_retries_failed_drag_then_saves_screenshot(monkeypatch) -> None:
    task = KYRWTask()
    state = make_yinshi_state([1, 0], [0, 1], [355, 919])
    drag_calls: list[int] = []
    screenshots: list[str] = []
    monkeypatch.setattr(task, "_read_yinshi_state", lambda *args, **kwargs: state)
    monkeypatch.setattr(
        task,
        "_drag_yinshi_card",
        lambda *args, **kwargs: drag_calls.append(1),
    )
    monkeypatch.setattr(
        task,
        "_yinshi_card_fingerprint",
        lambda screenshot, card: np.array([[int(card.template_path)]], dtype=np.uint8),
    )
    monkeypatch.setattr(
        task,
        "_yinshi_fingerprint_similarity",
        lambda expected, actual: 0.0,
    )
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or f"{prefix}.png",
    )
    monkeypatch.setattr(task, "_log", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="拖动到 1 后未生效"):
        task.handle_yinshi_task_if_visible()

    assert drag_calls == [1, 1]
    assert screenshots == ["kyrw_yinshi_drag_failed"]


def test_yinshi_solver_rejects_card_count_change(monkeypatch) -> None:
    task = KYRWTask()
    initial = make_yinshi_state([1, 0], [0, 1], [356, 914])
    changed = make_yinshi_state([2, 1, 0], [0, 1, 2], [289, 631, 1007])
    states = iter([initial, changed])
    screenshots: list[str] = []
    monkeypatch.setattr(task, "_read_yinshi_state", lambda *args, **kwargs: next(states))
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or f"{prefix}.png",
    )

    with pytest.raises(RuntimeError, match="卡片数量异常：预期 2，实际 3"):
        task.handle_yinshi_task_if_visible()

    assert screenshots == ["kyrw_yinshi_card_count_changed"]


def test_yinshi_correct_mark_must_map_to_a_detected_card(monkeypatch) -> None:
    task = KYRWTask()
    cards = (make_yinshi_match(0, 310), make_yinshi_match(1, 518))
    far_mark = ImageMatchResult(
        found=True,
        score=0.99,
        center=(1010, 488),
        bbox=(975, 463, 1045, 514),
        template_path=task.ICON_YINSHI_CORRECT,
    )
    screenshots: list[str] = []
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or f"{prefix}.png",
    )

    with pytest.raises(RuntimeError, match="红勾无法映射"):
        task._map_yinshi_correct_slots(cards, [far_mark])

    assert screenshots == ["kyrw_yinshi_correct_unmapped"]


def test_resume_existing_keye_uses_one_fast_cleanup_when_task_is_missing(monkeypatch) -> None:
    task = KYRWTask()
    cleanup_calls: list[dict[str, int]] = []
    monkeypatch.setattr(task, "close_all_panels", lambda **kwargs: cleanup_calls.append(kwargs))
    monkeypatch.setattr(task, "click_keye_task_from_sidebar", lambda **kwargs: False)

    task.resume_existing_keye()

    assert cleanup_calls == [{"timeout_ms": 0}]


def test_resume_existing_keye_keeps_cleanup_before_refresh_or_pause_reentry(monkeypatch) -> None:
    task = KYRWTask()
    cleanup_calls: list[dict[str, int]] = []
    monkeypatch.setattr(task, "close_all_panels", lambda **kwargs: cleanup_calls.append(kwargs))
    monkeypatch.setattr(task, "click_keye_task_from_sidebar", lambda **kwargs: True)

    with pytest.raises(StepJumpException) as exc_info:
        task.resume_existing_keye()

    assert exc_info.value.target == "run_keye_flow"
    assert cleanup_calls == [{"timeout_ms": 0}]


def test_zero_timeout_panel_cleanup_checks_two_frames_without_waiting(monkeypatch) -> None:
    task = KYRWTask()
    captures: list[int] = []
    waits: list[int] = []
    monkeypatch.setattr(task, "collapse_chat_if_open", lambda *args, **kwargs: False)
    monkeypatch.setattr(task, "collapse_emotion_panel_if_open", lambda **kwargs: False)
    monkeypatch.setattr(task, "_prepare_jianghu_calendar_close", lambda: False)
    monkeypatch.setattr(task, "wait", waits.append)

    def capture(*args, **kwargs):
        captures.append(1)
        return np.zeros((8, 8, 3), dtype=np.uint8), []

    monkeypatch.setattr(task, "_capture_close_candidates", capture)

    task.close_all_panels(timeout_ms=0)

    assert len(captures) == 2
    assert waits == [0]


def test_keye_sidebar_scroll_uses_unified_coordinates(monkeypatch) -> None:
    task = KYRWTask()
    swipes: list[tuple[int, int, int, int, int]] = []
    waits: list[int] = []

    def record_swipe(
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        *,
        duration_ms: int,
    ) -> None:
        swipes.append((start_x, start_y, end_x, end_y, duration_ms))

    monkeypatch.setattr(task, "swipe", record_swipe)
    monkeypatch.setattr(task, "wait", waits.append)

    task.scroll_task_list_down()
    task.scroll_task_list_up()

    assert swipes == [
        (190, 330, 190, 190, 1000),
        (190, 190, 190, 330, 400),
    ]
    assert waits == [500, 500]


def test_refresh_cancel_still_jumps_to_resume_cleanup(monkeypatch) -> None:
    task = KYRWTask()
    monkeypatch.setattr(task, "cancel_refresh_confirm_if_visible", lambda: True)

    with pytest.raises(StepJumpException) as exc_info:
        task.try_continue_after_keye_panel_opened()

    assert exc_info.value.target == "resume_existing_keye"


def test_default_keye_card_dialog_enters_flow_without_sidebar_scan(monkeypatch) -> None:
    task = KYRWTask()
    dialog_checks: list[bool] = []
    monkeypatch.setattr(task, "cancel_refresh_confirm_if_visible", lambda: False)
    monkeypatch.setattr(task, "find_image_once", lambda *args, **kwargs: True)
    monkeypatch.setattr(task, "click_point", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        task,
        "click_dialog_next_if_visible",
        lambda: dialog_checks.append(True) or True,
    )
    monkeypatch.setattr(
        task,
        "click_keye_task_from_sidebar",
        lambda **kwargs: pytest.fail("剧情界面不应打开任务侧栏"),
    )
    monkeypatch.setattr(
        task,
        "close_all_panels",
        lambda **kwargs: pytest.fail("剧情界面不应执行面板清理"),
    )

    with pytest.raises(StepJumpException) as exc_info:
        task.try_continue_after_keye_panel_opened()

    assert exc_info.value.target == "run_keye_flow"
    assert dialog_checks == [True]


def test_exhausted_keye_accept_recovery_is_a_failure(monkeypatch) -> None:
    task = KYRWTask()
    task._npc_accept_recoveries = task.MAX_NPC_ACCEPT_RECOVERY
    monkeypatch.setattr(task, "click_npc_keye_action_if_visible", lambda **kwargs: False)
    monkeypatch.setattr(task, "click_point", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "try_continue_after_keye_panel_opened", lambda: False)
    monkeypatch.setattr(task, "close_all_panels", lambda **kwargs: None)
    monkeypatch.setattr(task, "click_keye_task_from_sidebar", lambda **kwargs: False)

    with pytest.raises(RuntimeError, match="接取恢复次数已耗尽"):
        task.accept_or_open_keye_panel()


def test_enter_keye_clicks_entry_and_waits_for_pathfinding(monkeypatch) -> None:
    task = KYRWTask()
    entry_checks: list[tuple[str, dict[str, object]]] = []
    clicks: list[int] = []
    waits: list[int] = []
    timeouts: list[int | None] = []
    logs: list[str] = []
    monkeypatch.setattr(
        task,
        "wait_image_appear",
        lambda template, **kwargs: entry_checks.append((template, kwargs)) or True,
    )
    monkeypatch.setattr(task, "click", lambda **kwargs: clicks.append(1))
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(
        task,
        "wait_auto_pathfinding",
        lambda *, timeout_ms: timeouts.append(timeout_ms) or True,
    )
    monkeypatch.setattr(task, "_log", logs.append)

    task.enter_keye_from_activity_panel()

    assert [call[0] for call in entry_checks] == [task.BTN_KEYE_ENTRY_FORWARD]
    assert entry_checks[0][1]["roi"] == (175, 440, 205, 110)
    assert clicks == [1]
    assert waits == [1500]
    assert timeouts == [120000]
    assert logs == ["等待接取前自动寻路结束", "接取前自动寻路已结束"]
    assert task.enter_keye_from_activity_panel._step_meta["retry"] == 0
    assert task.enter_keye_from_activity_panel._step_meta["timeout_ms"] == 390000


def test_enter_keye_retries_only_pathfinding_without_clicking_entry_again(monkeypatch) -> None:
    task = KYRWTask()
    pathfinding_results = iter([False, True])
    clicks: list[int] = []
    timeouts: list[int | None] = []
    logs: list[str] = []
    monkeypatch.setattr(task, "wait_image_appear", lambda *args, **kwargs: True)
    monkeypatch.setattr(task, "click", lambda **kwargs: clicks.append(1))
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        task,
        "wait_auto_pathfinding",
        lambda *, timeout_ms: timeouts.append(timeout_ms) or next(pathfinding_results),
    )
    monkeypatch.setattr(task, "_log", logs.append)

    task.enter_keye_from_activity_panel()

    assert clicks == [1]
    assert timeouts == [120000, 120000]
    assert logs == [
        "等待接取前自动寻路结束",
        "接取前自动寻路尚未结束，重试等待 2/2",
        "接取前自动寻路已结束",
    ]


def test_enter_keye_pathfinding_timeout_is_a_failure(monkeypatch) -> None:
    task = KYRWTask()
    clicks: list[int] = []
    timeouts: list[int | None] = []
    logs: list[str] = []
    monkeypatch.setattr(task, "wait_image_appear", lambda *args, **kwargs: True)
    monkeypatch.setattr(task, "click", lambda **kwargs: clicks.append(1))
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        task,
        "wait_auto_pathfinding",
        lambda *, timeout_ms: timeouts.append(timeout_ms) or False,
    )
    monkeypatch.setattr(task, "_log", logs.append)

    with pytest.raises(RuntimeError, match="自动寻路等待超时"):
        task.enter_keye_from_activity_panel()

    assert clicks == [1]
    assert timeouts == [120000, 120000]
    assert logs == [
        "等待接取前自动寻路结束",
        "接取前自动寻路尚未结束，重试等待 2/2",
        "接取前自动寻路等待超时",
    ]


def test_enter_keye_pathfinding_preserves_stop_signal(monkeypatch) -> None:
    task = KYRWTask()

    def stop(**kwargs):
        raise StepStopException("Stop requested")

    monkeypatch.setattr(task, "wait_image_appear", lambda *args, **kwargs: True)
    monkeypatch.setattr(task, "click", lambda **kwargs: None)
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "wait_auto_pathfinding", stop)

    with pytest.raises(StepStopException):
        task.enter_keye_from_activity_panel()


def test_keye_use_button_is_checked_full_screen_and_clicked(monkeypatch) -> None:
    task = KYRWTask()
    calls: list[tuple[str, dict[str, object]]] = []

    def click_template(template: str, **kwargs) -> bool:
        calls.append((template, kwargs))
        return True

    monkeypatch.setattr(task, "click_template_if_available", click_template)

    assert task.click_keye_use_if_visible() is True
    assert calls == [
        (
            task.BTN_KEYE_USE,
            {
                "timeout_ms": 600,
                "description": "课业使用按钮",
                "threshold": 0.85,
                "wait_after_click_ms": 1500,
            },
        )
    ]
    assert Path(task.BTN_KEYE_USE).is_file()


def test_keye_flow_handles_state_then_confirms_tracker_missing(monkeypatch) -> None:
    task = KYRWTask()
    states = iter(
        [
            task.KEYE_FLOW_STATE_HANDLED,
            task.KEYE_FLOW_STATE_IDLE,
            task.KEYE_FLOW_STATE_IDLE,
            task.KEYE_FLOW_STATE_IDLE,
        ]
    )
    pathfinding_calls: list[int] = []
    tracker_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        task,
        "wait_auto_pathfinding",
        lambda *, timeout_ms: pathfinding_calls.append(timeout_ms) or True,
    )
    monkeypatch.setattr(task, "_handle_keye_flow_state_once", lambda: next(states))
    monkeypatch.setattr(
        task,
        "click_keye_task_from_sidebar",
        lambda **kwargs: tracker_calls.append(kwargs) or False,
    )
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)

    task.run_keye_flow()

    assert pathfinding_calls == [30000, 30000, 30000, 30000]
    assert tracker_calls == [
        {"max_scrolls": 2, "required": False},
        {"max_scrolls": 2, "required": False},
        {"max_scrolls": 2, "required": False},
    ]


def test_keye_flow_skips_state_checks_while_transition_is_unstable(monkeypatch) -> None:
    task = KYRWTask()
    task.KEYE_TASK_MISSING_CONFIRMATIONS = 1
    transitions = iter([False, True])
    events: list[str] = []
    monkeypatch.setattr(
        task,
        "wait_auto_pathfinding",
        lambda *, timeout_ms: events.append("wait") or next(transitions),
    )
    monkeypatch.setattr(
        task,
        "_handle_keye_flow_state_once",
        lambda: events.append("handle") or task.KEYE_FLOW_STATE_IDLE,
    )
    monkeypatch.setattr(
        task,
        "open_activity_panel",
        lambda *args, **kwargs: pytest.fail("执行循环不应打开活动入口"),
    )
    monkeypatch.setattr(
        task,
        "click_keye_task_from_sidebar",
        lambda **kwargs: events.append("tracker") or False,
    )

    task.run_keye_flow()

    assert events == ["wait", "wait", "handle", "tracker"]


@pytest.mark.parametrize(
    "target_handler",
    [
        "close_keye_completion_dialog_if_visible",
        "cancel_refresh_confirm_if_visible",
        "handle_yinshi_task_if_visible",
        "click_keye_use_if_visible",
        "handle_submit_panel_if_visible",
        "handle_acquire_route_panel_if_visible",
        "handle_trade_panel_if_visible",
        "click_dialog_confirm_if_visible",
        "click_npc_keye_action_if_visible",
        "click_dialog_next_if_visible",
    ],
)
def test_keye_flow_state_handler_preserves_priority_and_short_circuits(
    monkeypatch,
    target_handler: str,
) -> None:
    task = KYRWTask()
    handlers = [
        "close_keye_completion_dialog_if_visible",
        "cancel_refresh_confirm_if_visible",
        "handle_yinshi_task_if_visible",
        "click_keye_use_if_visible",
        "handle_submit_panel_if_visible",
        "handle_acquire_route_panel_if_visible",
        "handle_trade_panel_if_visible",
        "click_dialog_confirm_if_visible",
        "click_npc_keye_action_if_visible",
        "click_dialog_next_if_visible",
    ]
    events: list[str] = []

    for name in handlers:
        monkeypatch.setattr(
            task,
            name,
            lambda *args, _name=name, **kwargs: events.append(_name) or _name == target_handler,
        )

    state = task._handle_keye_flow_state_once()

    target_index = handlers.index(target_handler)
    assert events == handlers[: target_index + 1]
    assert state == task.KEYE_FLOW_STATE_HANDLED


def test_keye_flow_state_handler_returns_idle_after_one_complete_scan(monkeypatch) -> None:
    task = KYRWTask()
    events: list[str] = []
    handlers = [
        "close_keye_completion_dialog_if_visible",
        "cancel_refresh_confirm_if_visible",
        "handle_yinshi_task_if_visible",
        "click_keye_use_if_visible",
        "handle_submit_panel_if_visible",
        "handle_acquire_route_panel_if_visible",
        "handle_trade_panel_if_visible",
        "click_dialog_confirm_if_visible",
        "click_npc_keye_action_if_visible",
        "click_dialog_next_if_visible",
    ]
    for name in handlers:
        monkeypatch.setattr(
            task,
            name,
            lambda *args, _name=name, **kwargs: events.append(_name) or False,
        )

    assert task._handle_keye_flow_state_once() == task.KEYE_FLOW_STATE_IDLE
    assert events == handlers


def test_keye_dialog_confirm_uses_scoped_ok_template(monkeypatch) -> None:
    task = KYRWTask()
    calls: list[tuple[str, dict[str, object]]] = []

    def click_template(template: str, **kwargs) -> bool:
        calls.append((template, kwargs))
        return True

    monkeypatch.setattr(task, "click_template_if_available", click_template)

    assert task.click_dialog_confirm_if_visible() is True
    assert calls == [
        (
            task.BTN_OK,
            {
                "timeout_ms": 600,
                "description": "课业剧情确定按钮",
                "roi": (900, 400, 360, 120),
                "threshold": 0.85,
                "wait_after_click_ms": 1500,
            },
        )
    ]


def test_keye_dialog_confirm_short_circuits_dialog_next(monkeypatch) -> None:
    task = KYRWTask()
    events: list[str] = []
    earlier_handlers = [
        "close_keye_completion_dialog_if_visible",
        "cancel_refresh_confirm_if_visible",
        "handle_yinshi_task_if_visible",
        "click_keye_use_if_visible",
        "handle_submit_panel_if_visible",
        "handle_acquire_route_panel_if_visible",
        "handle_trade_panel_if_visible",
    ]
    for name in earlier_handlers:
        monkeypatch.setattr(
            task,
            name,
            lambda *args, _name=name, **kwargs: events.append(_name) or False,
        )
    monkeypatch.setattr(
        task,
        "click_dialog_confirm_if_visible",
        lambda: events.append("confirm") or True,
    )
    monkeypatch.setattr(
        task,
        "click_npc_keye_action_if_visible",
        lambda **kwargs: pytest.fail("剧情确定命中后不应继续检测NPC动作"),
    )
    monkeypatch.setattr(
        task,
        "click_dialog_next_if_visible",
        lambda: pytest.fail("剧情确定命中后不应点击剧情箭头"),
    )

    assert task._handle_keye_flow_state_once() == task.KEYE_FLOW_STATE_HANDLED
    assert events == [*earlier_handlers, "confirm"]


@pytest.mark.parametrize(
    ("mall_succeeds", "submit_succeeds", "expected_events"),
    [
        (True, True, ["mall", "submit:1500"]),
        (True, False, ["mall", "submit:1500"]),
        (False, True, ["mall", "stall", "submit:1500"]),
        (False, False, ["mall", "stall", "submit:1500"]),
    ],
)
def test_keye_acquisition_immediately_checks_one_key_submit(
    monkeypatch,
    mall_succeeds: bool,
    submit_succeeds: bool,
    expected_events: list[str],
) -> None:
    task = KYRWTask()
    events: list[str] = []
    monkeypatch.setattr(task, "is_acquire_route_panel_visible", lambda: True)
    monkeypatch.setattr(
        task,
        "try_mall_route",
        lambda: events.append("mall") or mall_succeeds,
    )
    monkeypatch.setattr(
        task,
        "try_stall_route",
        lambda: events.append("stall") or True,
    )
    monkeypatch.setattr(
        task,
        "handle_submit_panel_if_visible",
        lambda *, timeout_ms=600: events.append(f"submit:{timeout_ms}") or submit_succeeds,
    )

    assert task.handle_acquire_route_panel_if_visible() is True
    assert events == expected_events


@pytest.mark.parametrize("direct_trade_succeeds", [True, False])
def test_keye_open_trade_purchase_immediately_checks_one_key_submit(
    monkeypatch,
    direct_trade_succeeds: bool,
) -> None:
    task = KYRWTask()
    events: list[str] = []
    purchase_results = iter([direct_trade_succeeds, True])
    monkeypatch.setattr(
        task,
        "buy_from_current_trade_panel",
        lambda description, **kwargs: events.append(description) or next(purchase_results),
    )
    monkeypatch.setattr(
        task,
        "click_template_if_available",
        lambda template, **kwargs: events.append("all-server") or True,
    )
    monkeypatch.setattr(
        task,
        "handle_submit_panel_if_visible",
        lambda *, timeout_ms=600: events.append(f"submit:{timeout_ms}") or False,
    )

    assert task.handle_trade_panel_if_visible() is True
    if direct_trade_succeeds:
        assert events == ["自动打开的交易购买按钮", "submit:1500"]
    else:
        assert events == [
            "自动打开的交易购买按钮",
            "all-server",
            "自动打开的全服摆摊购买按钮",
            "submit:1500",
        ]


def test_keye_submit_handler_keeps_default_and_post_acquire_timeouts(monkeypatch) -> None:
    task = KYRWTask()
    timeouts: list[int] = []
    confirmations: list[int] = []
    waits: list[int] = []

    def click_template(template: str, **kwargs) -> bool:
        assert template == task.BTN_ONE_KEY_SUBMIT
        timeouts.append(kwargs["timeout_ms"])
        return True

    monkeypatch.setattr(task, "click_template_if_available", click_template)
    monkeypatch.setattr(
        task,
        "confirm_submit_if_needed",
        lambda: confirmations.append(1) or True,
    )
    monkeypatch.setattr(task, "wait", waits.append)

    assert task.handle_submit_panel_if_visible() is True
    assert task.handle_submit_panel_if_visible(timeout_ms=1500) is True
    assert timeouts == [600, 1500]
    assert confirmations == [1, 1]
    assert waits == [1500, 1500]


def test_keye_sidebar_templates_only_keep_dynamic_prefixes() -> None:
    assert KYRWTask.KEYE_SIDEBAR_TEMPLATES == [
        KYRWTask.TEXT_KEYE_PREFIX,
        KYRWTask.TEXT_ZHISHA_PREFIX,
        KYRWTask.TEXT_ZHUOJIAN_PREFIX,
        KYRWTask.TEXT_LIEXUE_PREFIX,
        KYRWTask.TEXT_XUNDAO_PREFIX,
        KYRWTask.TEXT_DUANXIN_PREFIX,
    ]
    for template in [
        KYRWTask.TEXT_LIEXUE_PREFIX,
        KYRWTask.TEXT_XUNDAO_PREFIX,
        KYRWTask.TEXT_DUANXIN_PREFIX,
    ]:
        assert Path(template).is_file()
        image = cv2.imread(template, cv2.IMREAD_UNCHANGED)
        assert image is not None
        assert image.shape == (18, 47, 4)
    assert not hasattr(KYRWTask, "TEXT_KEYE_SIDEBAR")
    assert not hasattr(KYRWTask, "TEXT_KEYE_SHIMEN_SIDEBAR")


def test_keye_dsl_step_names_are_semantic_and_loadable() -> None:
    assert [name for name, _, _ in KYRWTask.get_steps()] == [
        "resume_existing_keye",
        "open_keye_activity",
        "enter_keye_from_activity_panel",
        "accept_or_open_keye_panel",
        "run_keye_flow",
        "verify_completion",
    ]
    assert not hasattr(KYRWTask, "auto_pathfinding_to_npc")


def test_keye_template_helper_uses_wait_image_appear_for_roi(monkeypatch) -> None:
    task = KYRWTask()
    calls: list[tuple[str, dict[str, object]]] = []

    def wait_image(template: str, **kwargs) -> bool:
        calls.append((template, kwargs))
        return False

    monkeypatch.setattr(task, "wait_image_appear", wait_image)
    monkeypatch.setattr(
        task,
        "wait_find_image_in_roi",
        lambda *args, **kwargs: pytest.fail("课业 ROI 等待应统一使用 wait_image_appear"),
    )

    assert not task.click_template_if_available(
        "template.png",
        timeout_ms=700,
        description="测试模板",
        threshold=0.86,
        roi=(1, 2, 3, 4),
    )
    assert calls == [
        (
            "template.png",
            {
                "timeout_ms": 700,
                "threshold": 0.86,
                "roi": (1, 2, 3, 4),
            },
        )
    ]


def test_verify_completion_succeeds_when_outer_keye_entry_is_missing(monkeypatch) -> None:
    task = KYRWTask()
    cleanup_calls: list[dict[str, int]] = []
    activity_calls: list[tuple[str, dict[str, int]]] = []
    clicks: list[int] = []
    logs: list[str] = []
    wait_calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(task, "close_all_panels", lambda **kwargs: cleanup_calls.append(kwargs))
    monkeypatch.setattr(
        task,
        "find_keye_task_in_sidebar",
        lambda **kwargs: pytest.fail("完成验证不应查找任务侧栏"),
    )
    monkeypatch.setattr(
        task,
        "ensure_task_sidebar_open",
        lambda **kwargs: pytest.fail("完成验证不应打开任务侧栏"),
    )
    monkeypatch.setattr(
        task,
        "switch_task_panel",
        lambda *args, **kwargs: pytest.fail("完成验证不应切换任务页签"),
    )
    monkeypatch.setattr(
        task,
        "scroll_task_list_down",
        lambda: pytest.fail("完成验证不应滚动任务侧栏"),
    )
    monkeypatch.setattr(
        task,
        "open_activity_panel",
        lambda category, **kwargs: activity_calls.append((category, kwargs)),
    )

    def find(template: str, **kwargs) -> bool:
        wait_calls.append((template, kwargs))
        return False

    monkeypatch.setattr(task, "wait_image_appear", find)
    monkeypatch.setattr(task, "click", lambda **kwargs: clicks.append(1))
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "_log", logs.append)
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda *args, **kwargs: pytest.fail("完成状态不应保存失败截图"),
    )

    task.verify_completion()

    assert cleanup_calls == [{}]
    assert activity_calls == [("江湖", {"wait_after_category_ms": 2000})]
    assert clicks == []
    assert [call[0] for call in wait_calls] == [task.BTN_KEYE_ACTIVITY_FORWARD]
    assert wait_calls[0][1]["roi"] == task.ROI_KEYE_ACTIVITY_ENTRY
    assert logs == ["完成验证：活动页课业入口已消失"]
    assert task.verify_completion._step_meta["timeout_ms"] == 60000


def test_verify_completion_jumps_to_open_keye_activity_when_outer_entry_exists(
    monkeypatch,
) -> None:
    task = KYRWTask()
    cleanup_calls: list[dict[str, int]] = []
    activity_calls: list[tuple[str, dict[str, int]]] = []
    wait_calls: list[tuple[str, dict[str, object]]] = []
    logs: list[str] = []
    monkeypatch.setattr(task, "close_all_panels", lambda **kwargs: cleanup_calls.append(kwargs))
    monkeypatch.setattr(
        task,
        "find_keye_task_in_sidebar",
        lambda **kwargs: pytest.fail("未完成续接不应查找任务侧栏"),
    )
    monkeypatch.setattr(
        task,
        "open_activity_panel",
        lambda category, **kwargs: activity_calls.append((category, kwargs)),
    )

    def find(template: str, **kwargs) -> bool:
        wait_calls.append((template, kwargs))
        assert template == task.BTN_KEYE_ACTIVITY_FORWARD
        return True

    monkeypatch.setattr(task, "wait_image_appear", find)
    monkeypatch.setattr(
        task,
        "click",
        lambda **kwargs: pytest.fail("完成验证不应点击外层课业入口"),
    )
    monkeypatch.setattr(task, "_log", logs.append)
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda *args, **kwargs: pytest.fail("入口仍存在属于续接状态，不应保存失败截图"),
    )

    with pytest.raises(StepJumpException) as exc_info:
        task.verify_completion()

    assert exc_info.value.target == "open_keye_activity"
    assert cleanup_calls == [{}]
    assert activity_calls == [("江湖", {"wait_after_category_ms": 2000})]
    assert [call[0] for call in wait_calls] == [task.BTN_KEYE_ACTIVITY_FORWARD]
    assert wait_calls[0][1]["roi"] == task.ROI_KEYE_ACTIVITY_ENTRY
    assert logs == ["完成验证：活动页仍存在课业入口，继续接取课业"]


def test_open_keye_activity_uses_confirmed_activity_panel_to_enter_keye(monkeypatch) -> None:
    task = KYRWTask()
    activity_calls: list[tuple[str, dict[str, int]]] = []
    wait_calls: list[tuple[str, dict[str, object]]] = []
    clicks: list[int] = []
    waits: list[int] = []
    monkeypatch.setattr(
        task,
        "open_activity_panel",
        lambda category, **kwargs: activity_calls.append((category, kwargs)),
    )

    def find(template: str, **kwargs) -> bool:
        wait_calls.append((template, kwargs))
        return True

    monkeypatch.setattr(task, "wait_image_appear", find)
    monkeypatch.setattr(task, "click", lambda **kwargs: clicks.append(1))
    monkeypatch.setattr(
        task,
        "click_point",
        lambda *args, **kwargs: pytest.fail("模板已确认时不应使用固定坐标"),
    )
    monkeypatch.setattr(task, "wait", waits.append)

    task.open_keye_activity()

    assert activity_calls == [("江湖", {"wait_after_category_ms": 2000})]
    assert [call[0] for call in wait_calls] == [task.BTN_KEYE_ACTIVITY_FORWARD]
    assert clicks == [1]
    assert waits == [1500]


def test_keye_completion_dialog_is_handled_before_three_missing_trackers(monkeypatch) -> None:
    task = KYRWTask()
    completion_results = iter([True, False, False, False])
    completion_checks: list[int] = []
    tracker_calls: list[int] = []
    monkeypatch.setattr(
        task,
        "wait_auto_pathfinding",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        task,
        "close_keye_completion_dialog_if_visible",
        lambda: completion_checks.append(1) or next(completion_results),
    )
    monkeypatch.setattr(task, "cancel_refresh_confirm_if_visible", lambda: False)
    monkeypatch.setattr(task, "handle_yinshi_task_if_visible", lambda: False)
    monkeypatch.setattr(task, "click_keye_use_if_visible", lambda: False)
    monkeypatch.setattr(task, "handle_submit_panel_if_visible", lambda: False)
    monkeypatch.setattr(task, "handle_acquire_route_panel_if_visible", lambda: False)
    monkeypatch.setattr(task, "handle_trade_panel_if_visible", lambda: False)
    monkeypatch.setattr(task, "click_dialog_confirm_if_visible", lambda: False)
    monkeypatch.setattr(task, "click_npc_keye_action_if_visible", lambda **kwargs: False)
    monkeypatch.setattr(task, "click_dialog_next_if_visible", lambda: False)
    monkeypatch.setattr(
        task,
        "open_activity_panel",
        lambda *args, **kwargs: pytest.fail("执行循环不应打开活动入口"),
    )
    monkeypatch.setattr(
        task,
        "click_keye_task_from_sidebar",
        lambda **kwargs: tracker_calls.append(1) or False,
    )
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)

    task.run_keye_flow()

    assert completion_checks == [1, 1, 1, 1]
    assert tracker_calls == [1, 1, 1]


def test_keye_tracker_found_resets_missing_confirmation_count(monkeypatch) -> None:
    task = KYRWTask()
    tracker_results = iter([False, False, True, False, False, False])
    tracker_calls: list[int] = []
    waits: list[int] = []
    monkeypatch.setattr(task, "wait_auto_pathfinding", lambda **kwargs: True)
    monkeypatch.setattr(task, "_handle_keye_flow_state_once", lambda: task.KEYE_FLOW_STATE_IDLE)
    monkeypatch.setattr(
        task,
        "open_activity_panel",
        lambda *args, **kwargs: pytest.fail("执行循环不应打开活动入口"),
    )
    monkeypatch.setattr(
        task,
        "click_keye_task_from_sidebar",
        lambda **kwargs: tracker_calls.append(1) or next(tracker_results),
    )
    monkeypatch.setattr(task, "wait", waits.append)

    task.run_keye_flow()

    assert tracker_calls == [1, 1, 1, 1, 1, 1]
    assert waits == [
        task.KEYE_FLOW_IDLE_WAIT_MS,
        task.KEYE_FLOW_IDLE_WAIT_MS,
        task.KEYE_FLOW_IDLE_WAIT_MS,
        task.KEYE_FLOW_IDLE_WAIT_MS,
    ]


def test_keye_handled_state_resets_missing_confirmation_count(monkeypatch) -> None:
    task = KYRWTask()
    states = iter(
        [
            task.KEYE_FLOW_STATE_IDLE,
            task.KEYE_FLOW_STATE_HANDLED,
            task.KEYE_FLOW_STATE_IDLE,
            task.KEYE_FLOW_STATE_IDLE,
            task.KEYE_FLOW_STATE_IDLE,
        ]
    )
    tracker_calls: list[int] = []
    monkeypatch.setattr(task, "wait_auto_pathfinding", lambda **kwargs: True)
    monkeypatch.setattr(task, "_handle_keye_flow_state_once", lambda: next(states))
    monkeypatch.setattr(
        task,
        "click_keye_task_from_sidebar",
        lambda **kwargs: tracker_calls.append(1) or False,
    )
    monkeypatch.setattr(task, "wait", lambda *args, **kwargs: None)

    task.run_keye_flow()

    assert tracker_calls == [1, 1, 1, 1]


def test_keye_sidebar_state_error_is_not_counted_as_missing(monkeypatch) -> None:
    task = KYRWTask()
    monkeypatch.setattr(task, "wait_auto_pathfinding", lambda **kwargs: True)
    monkeypatch.setattr(task, "_handle_keye_flow_state_once", lambda: task.KEYE_FLOW_STATE_IDLE)
    monkeypatch.setattr(
        task,
        "click_keye_task_from_sidebar",
        lambda **kwargs: (_ for _ in ()).throw(TaskSidebarStateError("侧栏状态未知")),
    )

    with pytest.raises(TaskSidebarStateError, match="侧栏状态未知"):
        task.run_keye_flow()


def test_keye_flow_timeout_saves_screenshot(monkeypatch) -> None:
    task = KYRWTask()
    deadline_checks = iter([False, True])
    screenshots: list[str] = []
    monkeypatch.setattr(task, "_make_deadline", lambda timeout_ms: 1.0)
    monkeypatch.setattr(task, "_is_deadline_expired", lambda deadline: next(deadline_checks))
    monkeypatch.setattr(task, "wait_auto_pathfinding", lambda **kwargs: True)
    monkeypatch.setattr(
        task,
        "_handle_keye_flow_state_once",
        lambda: task.KEYE_FLOW_STATE_HANDLED,
    )
    monkeypatch.setattr(
        task,
        "click_keye_task_from_sidebar",
        lambda **kwargs: pytest.fail("已处理状态不应扫描任务侧栏"),
    )
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or f"{prefix}.png",
    )

    with pytest.raises(RuntimeError, match="课业任务执行流程超时.*kyrw_keye_flow_timeout.png"):
        task.run_keye_flow()

    assert screenshots == ["kyrw_keye_flow_timeout"]


def test_keye_dialog_confirm_template_matches_timeout_frame_with_next_arrow() -> None:
    frame = load_image(FIXTURE_DIR / "52_dialog_requires_confirm.png")
    confirm_match = VisionEngine().match_template(
        frame,
        KYRWTask.BTN_OK,
        threshold=0.85,
        roi=(900, 400, 360, 120),
    )
    next_match = VisionEngine().match_template(
        frame,
        KYRWTask.BTN_DIALOG_NEXT,
        threshold=0.85,
        roi=(1180, 640, 100, 80),
    )

    assert confirm_match.found
    assert confirm_match.score >= 0.99
    assert next_match.found
    assert next_match.score >= 0.99


@pytest.mark.parametrize(
    "fixture",
    [
        FIXTURE_DIR / "49_after_buy_18_humabing.webp",
        FIXTURE_DIR / "53_tracker_submit_panel_lower.png",
    ],
)
def test_keye_one_key_submit_template_matches_old_and_lower_panels(fixture: Path) -> None:
    match = VisionEngine().match_template(
        load_image(fixture),
        KYRWTask.BTN_ONE_KEY_SUBMIT,
        threshold=0.85,
        roi=(900, 330, 340, 240),
    )

    assert match.found
    assert match.score >= 0.99


def test_keye_activity_entry_template_matches_real_device_frame() -> None:
    template = Path(KYRWTask.BTN_KEYE_ACTIVITY_FORWARD)
    assert template.is_file()

    match = VisionEngine().match_template(
        load_image(FIXTURE_DIR / "01_activity_jianghu_wuchan_entry.webp"),
        str(template),
        threshold=0.9,
        roi=KYRWTask.ROI_KEYE_ACTIVITY_ENTRY,
    )

    assert match.found
    assert match.score >= 0.95


@pytest.mark.parametrize(
    ("template", "fixture"),
    [
        (KYRWTask.TEXT_KEYE_PREFIX, FIXTURE_DIR / "36_manual_accept_current_state.webp"),
        (
            KYRWTask.TEXT_ZHISHA_PREFIX,
            REPO_ROOT / "docs" / "assets" / "real_device" / "queue" / "kyrw_keye_flow.webp",
        ),
    ],
)
def test_keye_prefix_templates_match_real_device_trackers(template: str, fixture: Path) -> None:
    match = VisionEngine().match_template(
        load_image(fixture),
        template,
        threshold=0.85,
        roi=(40, 135, 330, 430),
    )

    assert match.found
    assert match.score >= 0.95
    assert template in KYRWTask.KEYE_SIDEBAR_TEMPLATES


@pytest.mark.parametrize(
    "template",
    [KYRWTask.TEXT_KEYE_PREFIX, KYRWTask.TEXT_ZHISHA_PREFIX],
)
def test_keye_prefix_templates_reject_non_tracker_frame(template: str) -> None:
    match = VisionEngine().match_template(
        load_image(FIXTURE_DIR / "01_activity_jianghu_wuchan_entry.webp"),
        template,
        threshold=0.85,
        roi=(40, 135, 330, 430),
    )

    assert not match.found
    assert match.score < 0.5
