from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import StepJumpException, StepStopException, VisionEngine
from ymjh_bot.task.KYRW_task import KYRWTask
from ymjh_bot.ym_game_task import TaskSidebarStateError


REPO_ROOT = Path(__file__).parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "ymjh" / "kyrw_keye_20260707"


def load_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path))
    assert image is not None, f"无法读取测试图片：{path}"
    return image


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
    monkeypatch.setattr(task, "wait", waits.append)

    def capture(*args, **kwargs):
        captures.append(1)
        return np.zeros((8, 8, 3), dtype=np.uint8), []

    monkeypatch.setattr(task, "_capture_close_candidates", capture)

    task.close_all_panels(timeout_ms=0)

    assert len(captures) == 2
    assert waits == [0]


def test_keye_sidebar_scroll_uses_expected_coordinates(monkeypatch) -> None:
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

    assert swipes == [(190, 360, 190, 170, 350)]
    assert waits == [800]


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
    assert entry_checks[0][1]["roi"] == task.ROI_KEYE_ENTRY
    assert clicks == [1]
    assert waits == [1500]
    assert task.AUTO_PATHFIND_TO_NPC_TIMEOUT_MS == 120000
    assert timeouts == [task.AUTO_PATHFIND_TO_NPC_TIMEOUT_MS]
    assert logs == ["等待接取前自动寻路结束", "接取前自动寻路已结束"]
    assert task.enter_keye_from_activity_panel._step_meta["retry"] == 0
    assert (
        task.enter_keye_from_activity_panel._step_meta["timeout_ms"]
        == task.ENTER_KEYE_STEP_TIMEOUT_MS
    )


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
    assert timeouts == [
        task.AUTO_PATHFIND_TO_NPC_TIMEOUT_MS,
        task.AUTO_PATHFIND_TO_NPC_TIMEOUT_MS,
    ]
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
    assert timeouts == [
        task.AUTO_PATHFIND_TO_NPC_TIMEOUT_MS,
        task.AUTO_PATHFIND_TO_NPC_TIMEOUT_MS,
    ]
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
                "roi": task.ROI_DIALOG_CONFIRM,
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
    ]
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
        roi=KYRWTask.ROI_DIALOG_CONFIRM,
    )
    next_match = VisionEngine().match_template(
        frame,
        KYRWTask.BTN_DIALOG_NEXT,
        threshold=0.85,
        roi=KYRWTask.ROI_DIALOG_NEXT,
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
        roi=KYRWTask.ROI_ONE_KEY_SUBMIT,
    )

    assert KYRWTask.ROI_ONE_KEY_SUBMIT == (900, 330, 340, 240)
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
        roi=KYRWTask.ROI_TASK_LIST,
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
        roi=KYRWTask.ROI_TASK_LIST,
    )

    assert not match.found
    assert match.score < 0.5
