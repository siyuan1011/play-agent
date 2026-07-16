from pathlib import Path

import pytest

from botCore import load_task_class
from botCore.task import StepJumpException
from ymjh_bot.task.JYPY_task import JYPYTask
from ymjh_bot.ui.task_queue_window import is_visible_task_class


class FakeJypyTask(JYPYTask):
    def __init__(
        self,
        *,
        roi_results: list[bool] | None = None,
        click_template_results: list[bool] | None = None,
        image_results: list[bool] | None = None,
        quick_panel_results: list[bool] | None = None,
        confirm_results: list[bool] | None = None,
        deadline_expired_results: list[bool] | None = None,
    ):
        super().__init__()
        self.roi_results = roi_results or []
        self.click_template_results = click_template_results or []
        self.image_results = image_results or []
        self.quick_panel_results = quick_panel_results or []
        self.confirm_results = confirm_results or []
        self.deadline_expired_results = deadline_expired_results
        self.roi_calls = []
        self.click_template_calls = []
        self.image_calls = []
        self.open_activity_calls = []
        self.close_panel_calls = []
        self.taps = []
        self.clicked_points = []
        self.click_offsets = []
        self.wait_calls = []
        self.switch_panel_calls = []
        self.swipe_calls = []
        self.quick_team_calls = []
        self.selected_targets = []
        self.auto_path_waits = []
        self.auto_battle_calls = []
        self.collapse_chat_calls = []
        self.safe_zone_calls = []
        self.leave_calls = []
        self.logs = []

    def _make_deadline(self, timeout_ms):
        if self.deadline_expired_results is None:
            return super()._make_deadline(timeout_ms)
        return object()

    def _is_deadline_expired(self, deadline):
        if self.deadline_expired_results is None:
            return super()._is_deadline_expired(deadline)
        if self.deadline_expired_results:
            return self.deadline_expired_results.pop(0)
        return False

    def wait_find_image_in_roi(
        self,
        template,
        roi,
        *,
        timeout_ms,
        description,
        threshold=0.8,
        interval_ms=500,
    ):
        self.roi_calls.append((template, roi, timeout_ms, description, threshold, interval_ms))
        return self.roi_results.pop(0) if self.roi_results else False

    def click_template_if_available(
        self,
        template,
        *,
        timeout_ms=3000,
        description,
        threshold=0.8,
        roi=None,
        wait_after_click_ms=1000,
    ):
        self.click_template_calls.append((template, timeout_ms, description, threshold, roi, wait_after_click_ms))
        return self.click_template_results.pop(0) if self.click_template_results else False

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.image_calls.append((template, timeout_ms, threshold, interval_ms))
        result = self.image_results.pop(0) if self.image_results else False
        if result and template == self.BTN_HD:
            self._last_match_center = (920, 63)
        return result

    def open_activity_panel(
        self,
        category=None,
        category_name=None,
        *,
        timeout_ms=30000,
        wait_after_open_ms=2000,
        wait_after_category_ms=0,
    ) -> None:
        self.open_activity_calls.append(
            (category, category_name, timeout_ms, wait_after_open_ms, wait_after_category_ms)
        )

    def close_all_panels(self, templates=None, *, timeout_ms=5000, wait_after_click_ms=500):
        self.close_panel_calls.append((templates, timeout_ms, wait_after_click_ms))

    def wake_from_power_saving_if_needed(self) -> bool:
        return False

    def return_to_safe_zone(self) -> None:
        self.safe_zone_calls.append(())

    def leave_team_if_present(self) -> None:
        self.leave_calls.append(())

    def collapse_chat_if_open(self, wait_after_click_ms: int = 800) -> bool:
        self.collapse_chat_calls.append(wait_after_click_ms)
        return False

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def click(self, offset: int = 3) -> None:
        self.click_offsets.append(offset)

    def tap(self, x=None, y=None):
        self.taps.append((x, y))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def is_quick_team_panel_open(self) -> bool:
        return self.quick_panel_results.pop(0) if self.quick_panel_results else False

    def quick_team(self, *args, **kwargs) -> None:
        self.quick_team_calls.append((args, kwargs))

    def select_quick_team_target(self, target: str, *, wait_after_click_ms: int = 800) -> None:
        self.selected_targets.append((target, wait_after_click_ms))

    def confirm_center_modal_ok_if_visible(self, description: str, **kwargs) -> bool:
        return self.confirm_results.pop(0) if self.confirm_results else False

    def switch_task_panel(
        self,
        panel: str,
        *,
        timeout_ms: int = 3000,
        threshold: float = 0.8,
        wait_after_click_ms: int = 500,
    ) -> None:
        self.switch_panel_calls.append((panel, timeout_ms, threshold, wait_after_click_ms))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
        self.swipe_calls.append((x1, y1, x2, y2, duration_ms))

    def wait_auto_pathfinding(self, **kwargs) -> None:
        self.auto_path_waits.append(kwargs)

    def auto_battle(self, interval_ms: int = 500) -> None:
        self.auto_battle_calls.append(interval_ms)

    def save_debug_screenshot(self, prefix: str) -> str:
        return f"screenshots/{prefix}.png"

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_jypy_task_loads_and_is_visible():
    task_cls = load_task_class(Path("src/ymjh_bot/task/JYPY_task.py"))

    assert task_cls.__name__ == "JYPYTask"
    assert is_visible_task_class(task_cls)
    assert task_cls.task_key == "JYPY"
    assert task_cls.task_name == "聚义平冤"


def test_jypy_step_order():
    assert [name for name, _, _ in JYPYTask.get_steps()] == [
        "open_hangdang_activity",
        "start_auto_pathfinding",
        "wait_arrive_npc",
        "enter_quick_team",
        "wait_team_follow",
        "run_jypy_flow",
        "verify_completion",
    ]


def test_on_start_returns_to_safe_zone_and_leaves_team():
    task = FakeJypyTask()

    task.on_start()

    assert task.close_panel_calls == [
        (None, 5000, 500),
        (None, 3000, 500),
    ]
    assert task.wait_calls == [1000]
    assert task.safe_zone_calls == [()]
    assert task.leave_calls == [()]


def test_open_hangdang_activity_uses_hangdang_tab():
    task = FakeJypyTask()

    task.open_hangdang_activity()

    assert task.open_activity_calls == [("行当", None, 30000, 2500, 1500)]
    assert task.image_calls == []
    assert task.taps == []
    assert task.clicked_points == []
    assert task.wait_calls == []


def test_start_auto_pathfinding_clicks_activity_forward():
    task = FakeJypyTask(roi_results=[True])

    task.start_auto_pathfinding()

    assert task.roi_calls == [
        (
            task.BTN_ACTIVITY_FORWARD,
            task.ROI_ACTIVITY_JYPY_FORWARD,
            5000,
            "活动页聚义平冤前往按钮",
            task.ACTIVITY_FORWARD_THRESHOLD,
            500,
        )
    ]
    assert task.click_offsets == [0]
    assert task.wait_calls == [1500]


def test_start_auto_pathfinding_jumps_to_verify_when_entry_missing():
    task = FakeJypyTask(roi_results=[False])

    with pytest.raises(StepJumpException) as exc_info:
        task.start_auto_pathfinding()

    assert exc_info.value.target == "verify_completion"
    assert task.click_offsets == []


def test_open_quick_team_from_npc_menu_clicks_dialog_sequence():
    task = FakeJypyTask(click_template_results=[True])

    task.open_quick_team_from_npc_menu()

    assert task.clicked_points == [
        (task.POINT_NPC_ACTION[0], task.POINT_NPC_ACTION[1], 0),
        (task.POINT_NPC_ACTION[0], task.POINT_NPC_ACTION[1], 0),
        (task.POINT_NPC_QUICK_TEAM[0], task.POINT_NPC_QUICK_TEAM[1], 0),
    ]
    assert task.click_template_calls == [
        (task.BTN_OK, 2500, "NPC 确认按钮", 0.85, task.ROI_NPC_CONFIRM, 1500)
    ]


def test_start_quick_match_falls_back_to_generic_quick_team():
    task = FakeJypyTask(quick_panel_results=[False])

    task.start_quick_match()

    assert task.quick_team_calls == [
        ((task.TEAM_TARGET_JUYI_PINGYUAN,), {"wait_after_click_ms": 1000})
    ]


def test_start_quick_match_selects_target_and_auto_match_when_panel_open():
    task = FakeJypyTask(quick_panel_results=[True], click_template_results=[True], confirm_results=[False])

    task.start_quick_match()

    assert task.selected_targets == [(task.TEAM_TARGET_JUYI_PINGYUAN, 800)]
    assert task.click_template_calls == [
        (
            task.BTN_TEAM_AUTO_MATCH,
            5000,
            "聚义平冤自动匹配按钮",
            0.9,
            task.ROI_TEAM_QUICK_ACTIONS,
            1000,
        )
    ]
    assert "已开始聚义平冤便捷组队自动匹配" in task.logs


def test_wait_team_follow_confirms_popup():
    task = FakeJypyTask(confirm_results=[False, True])

    task.wait_for_team_follow_confirm()

    assert task.wait_calls == [task.MATCH_WAIT_POLL_INTERVAL_MS]
    assert "已确认入队跟随" in task.logs


def test_find_jypy_task_in_sidebar_scrolls_and_matches():
    task = FakeJypyTask(roi_results=[False, True])

    assert task.find_jypy_task_in_sidebar(max_scrolls=1)

    assert task.switch_panel_calls == [("任务", 2500, 0.8, 500)]
    assert task.swipe_calls == [
        (
            task.POINT_TASK_LIST_SCROLL_START[0],
            task.POINT_TASK_LIST_SCROLL_START[1],
            task.POINT_TASK_LIST_SCROLL_END[0],
            task.POINT_TASK_LIST_SCROLL_END[1],
            350,
        )
    ]


def test_run_jypy_flow_finishes_after_stable_missing_tracker():
    task = FakeJypyTask(
        roi_results=[False, False, False],
        deadline_expired_results=[False, False, False],
    )

    task.run_jypy_flow()

    assert len(task.auto_path_waits) == 3
    assert "聚义平冤任务追踪已稳定消失" in task.logs


def test_verify_completion_accepts_missing_activity_entry():
    task = FakeJypyTask(image_results=[True], roi_results=[False])

    task.verify_completion()

    assert "完成验证：活动-行当页聚义平冤入口已消失" in task.logs


def test_verify_completion_raises_when_activity_entry_remains():
    task = FakeJypyTask(image_results=[True], roi_results=[True])

    with pytest.raises(RuntimeError, match="聚义平冤完成验证失败"):
        task.verify_completion()
