from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from botCore import ImageMatchResult, RunLogger
from ymjh_bot.ym_game_task import TaskSidebarStateError, YmGameTask


def make_match(
    *,
    found: bool,
    score: float,
    center: tuple[int, int] | None,
    template: str | None,
) -> ImageMatchResult:
    bbox = None
    if center is not None:
        bbox = (center[0] - 8, center[1] - 8, center[0] + 8, center[1] + 8)
    return ImageMatchResult(found, score, center, bbox, template)


class SidebarVision:
    ACTIVE_NAMES = {
        "task_active": "icon_task_rw.png",
        "jianghu_active": "icon_task_jh.png",
        "qiyu_active": "icon_task_qy.png",
    }
    ACTIVE_CENTERS = {
        "task_active": (88, 123),
        "jianghu_active": (173, 123),
        "qiyu_active": (258, 123),
    }

    def __init__(self, state_names: dict[int, str]) -> None:
        self.state_names = state_names
        self.thresholds: list[float] = []

    def match_binary_template(
        self,
        screenshot,
        template_paths,
        *,
        mode,
        threshold=0.85,
        roi=None,
    ) -> ImageMatchResult:
        self.thresholds.append(threshold)
        state = self.state_names[int(screenshot[0, 0, 0])]
        paths = [template_paths] if isinstance(template_paths, str) else template_paths
        names = {Path(path).name for path in paths}

        active_states = [state]
        if state == "multi_active":
            active_states = ["task_active", "jianghu_active"]
        for active_state in active_states:
            active_name = self.ACTIVE_NAMES.get(active_state)
            if active_name and active_name in names:
                template = next(path for path in paths if Path(path).name == active_name)
                return make_match(
                    found=True,
                    score=0.97,
                    center=self.ACTIVE_CENTERS[active_state],
                    template=str(template),
                )

        if state == "other" and "task_sidebar_entry_v2.png" in names:
            template = next(path for path in paths if Path(path).name == "task_sidebar_entry_v2.png")
            return make_match(found=True, score=0.98, center=(22, 218), template=str(template))
        if state == "collapsed" and "task_sidebar_expand_v2.png" in names:
            template = next(path for path in paths if Path(path).name == "task_sidebar_expand_v2.png")
            return make_match(found=True, score=0.98, center=(22, 358), template=str(template))
        return make_match(found=False, score=0.25, center=None, template=str(paths[0]))

    def match_template(self, screenshot, template_paths, *, threshold=0.85, roi=None):
        self.thresholds.append(threshold)
        state = self.state_names[int(screenshot[0, 0, 0])]
        paths = [template_paths] if isinstance(template_paths, str) else template_paths
        names = {Path(path).name for path in paths}
        if state == "fullscreen" and names & {
            "task_fullscreen_panel_v2.png",
            "text_task_panel_title.png",
        }:
            template = str(paths[0])
            return make_match(found=True, score=0.99, center=(60, 160), template=template)
        return make_match(found=False, score=0.25, center=None, template=str(paths[0]))


class SidebarTask(YmGameTask):
    STATE_IDS = {
        "unknown": 1,
        "dormant": 2,
        "collapsed": 3,
        "other": 4,
        "task_active": 5,
        "jianghu_active": 6,
        "qiyu_active": 7,
        "fullscreen": 8,
        "multi_active": 9,
        "activity": 10,
        "power": 11,
        "battle": 12,
    }

    def __init__(
        self,
        state: str,
        transitions: dict[tuple[str, tuple[int, int]], str] | None = None,
        *,
        main_ready: bool = True,
        fullscreen_close_state: str = "task_active",
        logger: RunLogger | None = None,
    ) -> None:
        super().__init__()
        self.state = state
        self.transitions = transitions or {}
        self.main_ready = main_ready
        self.fullscreen_close_state = fullscreen_close_state
        self.taps: list[tuple[int, int]] = []
        self.close_calls = 0
        self._logger = logger
        self._vision = SidebarVision(
            {state_id: name for name, state_id in self.STATE_IDS.items()}
        )

    def screenshot(self) -> np.ndarray:
        return np.full((720, 1280, 3), self.STATE_IDS[self.state], dtype=np.uint8)

    def tap(self, x: int | None = None, y: int | None = None) -> None:
        assert x is not None and y is not None
        point = (x, y)
        self.taps.append(point)
        self.state = self.transitions.get((self.state, point), self.state)

    def wait(self, ms: int | float) -> None:
        return None

    def is_chat_open(self) -> bool:
        return False

    def is_power_saving_mode(self) -> bool:
        return self.state == "power"

    def _is_activity_panel_open(self) -> bool:
        return self.state == "activity"

    def is_game_main_ready(self, *, timeout_ms: int = 2000, threshold: float = 0.8) -> bool:
        return self.main_ready and self.state not in {"activity", "power", "battle"}

    def _close_task_fullscreen_with_deadline(self, *args, **kwargs):
        self.close_calls += 1
        if self.state == "fullscreen":
            self.state = self.fullscreen_close_state
        return self._capture_task_sidebar_snapshot(self.TASK_SIDEBAR_THRESHOLD)


def test_target_panel_already_active_returns_without_clicking() -> None:
    task = SidebarTask("jianghu_active")

    task.switch_task_panel("江湖")

    assert task.taps == []


@pytest.mark.parametrize(
    ("source_state", "source_panel", "source_center", "target_panel"),
    [
        ("task_active", "任务", (88, 123), "江湖"),
        ("task_active", "任务", (88, 123), "奇遇"),
        ("jianghu_active", "江湖", (173, 123), "任务"),
        ("jianghu_active", "江湖", (173, 123), "奇遇"),
        ("qiyu_active", "奇遇", (258, 123), "任务"),
        ("qiyu_active", "奇遇", (258, 123), "江湖"),
    ],
)
def test_all_tab_directions_use_active_anchor_relative_pitch(
    source_state: str,
    source_panel: str,
    source_center: tuple[int, int],
    target_panel: str,
) -> None:
    delta = SidebarTask.TASK_TAB_ORDER.index(target_panel) - SidebarTask.TASK_TAB_ORDER.index(
        source_panel
    )
    target_center = (source_center[0] + delta * 84, source_center[1])
    target_state = {
        "任务": "task_active",
        "江湖": "jianghu_active",
        "奇遇": "qiyu_active",
    }[target_panel]
    task = SidebarTask(
        source_state,
        {(source_state, target_center): target_state},
    )

    task.switch_task_panel(target_panel)

    assert task.taps == [target_center]


def test_dormant_sidebar_uses_default_activation_once() -> None:
    task = SidebarTask(
        "dormant",
        {("dormant", (22, 218)): "task_active"},
    )

    task.ensure_task_sidebar_open()

    assert task.taps == [(22, 218)]


def test_default_activation_may_open_fullscreen_and_recovers_once() -> None:
    task = SidebarTask(
        "dormant",
        {("dormant", (22, 218)): "fullscreen"},
        fullscreen_close_state="task_active",
    )

    task.ensure_task_sidebar_open()

    assert task.taps == [(22, 218)]
    assert task.close_calls == 1


def test_default_activation_without_effect_fails_after_one_click(tmp_path: Path) -> None:
    task = SidebarTask("dormant", logger=RunLogger(tmp_path, retention_days=None))

    with pytest.raises(TaskSidebarStateError, match="单次任务图标激活后"):
        task.ensure_task_sidebar_open()

    assert task.taps == [(22, 218)]
    assert len(list(task._logger.shots_dir.glob("task_sidebar_state_failed_*.png"))) == 1


def test_collapsed_sidebar_expands_once_then_activates_entry_once() -> None:
    task = SidebarTask(
        "collapsed",
        {
            ("collapsed", (22, 358)): "other",
            ("other", (22, 218)): "task_active",
        },
    )

    task.ensure_task_sidebar_open()

    assert task.taps == [(22, 358), (22, 218)]


@pytest.mark.parametrize("state", ["activity", "power", "battle"])
def test_unsafe_negative_states_never_use_default_activation(
    state: str,
    tmp_path: Path,
) -> None:
    task = SidebarTask(state, logger=RunLogger(tmp_path, retention_days=None))

    with pytest.raises(TaskSidebarStateError):
        task.ensure_task_sidebar_open()

    assert task.taps == []


def test_fullscreen_after_activation_closes_once_but_never_activates_again(
    tmp_path: Path,
) -> None:
    task = SidebarTask(
        "dormant",
        {("dormant", (22, 218)): "fullscreen"},
        fullscreen_close_state="unknown",
        logger=RunLogger(tmp_path, retention_days=None),
    )

    with pytest.raises(TaskSidebarStateError, match="关闭后仍未确认 active"):
        task.ensure_task_sidebar_open()

    assert task.taps == [(22, 218)]
    assert task.close_calls == 1


def test_multiple_active_tabs_fail_without_clicking(tmp_path: Path) -> None:
    task = SidebarTask("multi_active", logger=RunLogger(tmp_path, retention_days=None))

    with pytest.raises(TaskSidebarStateError, match="同时识别到多个"):
        task.switch_task_panel("任务")

    assert task.taps == []


def test_sidebar_disappearing_after_tab_click_raises_without_second_click(
    tmp_path: Path,
) -> None:
    task = SidebarTask(
        "task_active",
        {("task_active", (172, 123)): "unknown"},
        main_ready=False,
        logger=RunLogger(tmp_path, retention_days=None),
    )

    with pytest.raises(TaskSidebarStateError, match="切换后侧栏状态无法确认"):
        task.switch_task_panel("江湖")

    assert task.taps == [(172, 123)]


def test_missing_required_template_fails_before_any_click(tmp_path: Path) -> None:
    task = SidebarTask("collapsed", logger=RunLogger(tmp_path, retention_days=None))
    task.TASK_SIDEBAR_ENTRY_V2 = str(tmp_path / "missing_entry.png")

    with pytest.raises(TaskSidebarStateError, match="视觉模板缺失"):
        task.switch_task_panel("任务")

    assert task.taps == []


def test_chat_must_be_confirmed_closed_before_task_clicks(tmp_path: Path) -> None:
    task = SidebarTask("task_active", logger=RunLogger(tmp_path, retention_days=None))
    chat_states = iter((True, True))
    task.is_chat_open = lambda: next(chat_states)

    with pytest.raises(TaskSidebarStateError, match="聊天框收起后仍可识别"):
        task.switch_task_panel("江湖")

    assert task.taps == [task.POINT_CHAT_COLLAPSE_ARROW]


def test_total_timeout_expiring_during_capture_prevents_entry_click(tmp_path: Path) -> None:
    task = SidebarTask("collapsed", logger=RunLogger(tmp_path, retention_days=None))
    deadline_checks = iter((False, True))
    task._make_deadline = lambda timeout_ms: 1.0
    task._is_deadline_expired = lambda deadline: next(deadline_checks, True)

    with pytest.raises(TaskSidebarStateError, match="打开任务侧栏超时"):
        task.switch_task_panel("任务", timeout_ms=1)

    assert task.taps == []


def test_confirmed_chat_close_precedes_task_state_detection() -> None:
    task = SidebarTask("task_active")
    chat_states = iter((True, False))
    task.is_chat_open = lambda: next(chat_states)

    task.switch_task_panel("任务")

    assert task.taps == [task.POINT_CHAT_COLLAPSE_ARROW]


def test_caller_cannot_lower_task_sidebar_threshold() -> None:
    task = SidebarTask("task_active")

    task.switch_task_panel("任务", threshold=0.2)

    assert task._vision.thresholds
    assert min(task._vision.thresholds) >= 0.85
    active_thresholds = task._vision.thresholds[:3]
    assert min(active_thresholds) >= 0.90
