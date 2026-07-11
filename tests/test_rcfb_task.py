from pathlib import Path

import numpy as np
import pytest

from botCore import load_task_class
from botCore.task import StepJumpException
from ymjh_bot.task.RCFB_task import RichangFubenTask
from ymjh_bot.ui.task_queue_window import is_visible_task_class


class FakeRcfbTask(RichangFubenTask):
    def __init__(
        self,
        *,
        dungeon_results: list[bool] | None = None,
        click_template_results: list[bool] | None = None,
        confirm_results: list[bool] | None = None,
        already_in_team_results: list[bool] | None = None,
        deadline_expired_results: list[bool] | None = None,
    ):
        super().__init__()
        self.dungeon_results = dungeon_results or []
        self.click_template_results = click_template_results or []
        self.confirm_results = confirm_results or []
        self.already_in_team_results = already_in_team_results or []
        self.deadline_expired_results = deadline_expired_results
        self.quick_team_calls = []
        self.open_quick_team_calls = []
        self.leave_calls = []
        self.close_panel_calls = []
        self.clicked_points = []
        self.wait_calls = []
        self.click_template_calls = []
        self.auto_path_waits = []
        self.auto_battle_calls = []
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

    def close_all_panels(self, templates=None, *, timeout_ms=5000, wait_after_click_ms=500):
        self.close_panel_calls.append((templates, timeout_ms, wait_after_click_ms))

    def wake_from_power_saving_if_needed(self) -> bool:
        return False

    def leave_team_if_present(self) -> None:
        self.leave_calls.append("leave")

    def quick_team(self, *args, **kwargs) -> None:
        self.quick_team_calls.append((args, kwargs))

    def open_quick_team_panel(self, *, timeout_ms=3000, wait_after_click_ms=1000) -> None:
        self.open_quick_team_calls.append((timeout_ms, wait_after_click_ms))

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def confirm_center_modal_ok_if_visible(self, description: str, **kwargs) -> bool:
        return self.confirm_results.pop(0) if self.confirm_results else False

    def confirm_already_in_team(self) -> bool:
        return self.already_in_team_results.pop(0) if self.already_in_team_results else False

    def find_dungeon_task_in_sidebar(self, max_scrolls: int = 2) -> bool:
        return self.dungeon_results.pop(0) if self.dungeon_results else False

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

    def wait_auto_pathfinding(self, **kwargs) -> None:
        self.auto_path_waits.append(kwargs)

    def auto_battle(self, interval_ms: int = 500) -> None:
        self.auto_battle_calls.append(interval_ms)

    def wait(self, ms):
        self.wait_calls.append(ms)

    def save_debug_screenshot(self, prefix: str) -> str:
        return f"screenshots/{prefix}.png"

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_rcfb_task_loads_and_is_visible():
    task_cls = load_task_class(Path("src/ymjh_bot/task/RCFB_task.py"))

    assert task_cls.__name__ == "RichangFubenTask"
    assert is_visible_task_class(task_cls)
    assert task_cls.task_key == "RCFB"
    assert task_cls.task_name == "日常副本"


def test_rcfb_step_order():
    assert [name for name, _, _ in RichangFubenTask.get_steps()] == [
        "close_all_and_leave_team",
        "start_daily_match",
        "wait_team_follow",
        "wait_dungeon_task",
        "run_daily_raid_flow",
        "leave_team_after_completion",
    ]


def test_start_daily_auto_match_uses_daily_target():
    task = FakeRcfbTask(click_template_results=[True, True], confirm_results=[False])

    task.start_daily_auto_match()

    assert task.open_quick_team_calls == [(5000, 1000)]
    assert task.click_template_calls == [
        (
            [
                task.TEXT_TEAM_QUICK_CATEGORY_JIANGHU,
                task.TEXT_TEAM_QUICK_CATEGORY_JIANGHU_ACTIVE,
            ],
            3000,
            "便捷组队分类 江湖纪事",
            0.82,
            task.ROI_TEAM_QUICK_LEFT_PANEL,
            800,
        ),
        (
            task.BTN_TEAM_AUTO_MATCH,
            5000,
            "日常副本自动匹配按钮",
            0.9,
            task.ROI_TEAM_QUICK_ACTIONS,
            1000,
        ),
    ]
    assert "已开始江湖纪事日常副本自动匹配" in task.logs


def test_wait_team_follow_confirms_popup():
    task = FakeRcfbTask(confirm_results=[False, True])

    task.wait_for_team_follow_confirm()

    assert task.wait_calls == [task.MATCH_WAIT_POLL_INTERVAL_MS]
    assert "已确认入队跟随" in task.logs


def test_wait_team_follow_accepts_existing_team_state():
    task = FakeRcfbTask(confirm_results=[False], already_in_team_results=[True])

    task.wait_for_team_follow_confirm()

    assert task.wait_calls == []


def test_wait_dungeon_task_accepts_found_tracker():
    task = FakeRcfbTask(dungeon_results=[True])

    task.wait_dungeon_task()

    assert task.leave_calls == []
    assert "检测到江湖副本任务，确认已进入副本流程" in task.logs


def test_wait_dungeon_task_reteams_when_missing_for_five_minutes():
    task = FakeRcfbTask(
        dungeon_results=[False],
        deadline_expired_results=[False, True],
    )

    with pytest.raises(StepJumpException) as exc_info:
        task.wait_dungeon_task()

    assert exc_info.value.target == "wait_team_follow"
    assert task.leave_calls == ["leave"]
    assert task.open_quick_team_calls == [(5000, 1000)]


def test_run_daily_raid_flow_finishes_after_stable_missing_tracker():
    task = FakeRcfbTask(
        dungeon_results=[False, False, False],
        deadline_expired_results=[False, False, False],
    )

    task.run_daily_raid_flow()

    assert len(task.auto_path_waits) == 3
    assert "副本任务追踪已稳定消失，判断副本完成" in task.logs


def test_sidebar_text_block_candidate_detects_bright_text_region():
    class ScreenshotTask(RichangFubenTask):
        def __init__(self):
            super().__init__()
            self.logs = []

        def screenshot(self):
            image = np.zeros((720, 1280, 3), dtype=np.uint8)
            image[170:190, 80:150] = (40, 220, 40)
            image[205:225, 90:180] = (30, 210, 210)
            image[240:260, 100:220] = (40, 220, 40)
            return image

        def _log(self, message: str) -> None:
            self.logs.append(message)

    task = ScreenshotTask()

    assert task.find_sidebar_text_block_candidate()
    assert task._last_match_center is not None
