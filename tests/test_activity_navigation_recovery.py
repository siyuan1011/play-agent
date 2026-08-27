from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import GameTask, VisionEngine, step
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner
from ymjh_bot.task.HSLJ_task import HSLJTask
from ymjh_bot.task.JHYXB_task import JianghuYingxiongbangTask
from ymjh_bot.ym_game_task import YmGameTask


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ymjh"


def load_fixture(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return image


class StaticADB:
    serial = "test-device"

    def __init__(self, screenshot: np.ndarray | None = None) -> None:
        self._screenshot = (
            np.zeros((720, 1280, 3), dtype=np.uint8)
            if screenshot is None
            else screenshot
        )

    def ensure_device(self) -> None:
        pass

    def get_screen_size(self) -> tuple[int, int]:
        return (1280, 720)

    def screenshot(self) -> np.ndarray:
        return self._screenshot.copy()


class LifecycleRetryTask(GameTask):
    task_name = "生命周期重试任务"

    def __init__(self) -> None:
        super().__init__()
        self.before_start_calls = 0
        self.on_start_calls = 0
        self.navigation_calls = 0

    def before_start(self) -> None:
        self.before_start_calls += 1

    def on_start(self) -> None:
        self.on_start_calls += 1

    @step(retry=0, timeout_ms=1000)
    def navigate(self) -> None:
        self.navigation_calls += 1
        if self.navigation_calls < 3:
            raise RuntimeError("temporary navigation failure")


def test_activity_tasks_expose_one_atomic_navigation_step() -> None:
    hslj_steps = HSLJTask.get_steps()
    jhyxb_steps = JianghuYingxiongbangTask.get_steps()

    assert hslj_steps[0][0] == "open_hslj_panel"
    assert hslj_steps[0][2]["retry"] == 0
    assert hslj_steps[0][2]["timeout_ms"] == 60_000
    assert "open_fenzheng_activity" not in [name for name, _, _ in hslj_steps]

    assert jhyxb_steps[0][0] == "open_jhyxb_panel"
    assert jhyxb_steps[0][2]["retry"] == 0
    assert jhyxb_steps[0][2]["timeout_ms"] == 60_000
    assert "open_fenzheng_activity" not in [name for name, _, _ in jhyxb_steps]


def test_hslj_initial_navigation_does_not_repeat_panel_cleanup(monkeypatch) -> None:
    task = HSLJTask()
    calls: list[tuple[object, ...]] = []
    finds = iter([True, True])

    monkeypatch.setattr(
        task,
        "close_all_panels",
        lambda *args, **kwargs: pytest.fail("initial navigation must not clean panels again"),
    )
    monkeypatch.setattr(
        task,
        "open_activity_panel",
        lambda category, **kwargs: calls.append(("activity", category, kwargs)),
    )
    monkeypatch.setattr(
        task,
        "wait_find_image_in_roi",
        lambda *args, **kwargs: next(finds),
    )
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, offset=3: calls.append(("point", x, y, offset)),
    )
    monkeypatch.setattr(task, "click", lambda offset=3: calls.append(("click", offset)))
    monkeypatch.setattr(task, "wait", lambda ms: calls.append(("wait", ms)))
    monkeypatch.setattr(task, "ensure_hslj_panel_visible", lambda **kwargs: True)

    task.open_hslj_panel()

    assert calls[0] == (
        "activity",
        "纷争",
        {"wait_after_open_ms": 2500, "wait_after_category_ms": 1500},
    )
    assert ("point", 220, 222, 0) in calls
    assert ("click", 0) in calls


def test_hslj_missing_card_never_clicks_fixed_coordinate(monkeypatch) -> None:
    task = HSLJTask()
    points: list[tuple[int, int]] = []

    monkeypatch.setattr(task, "open_activity_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "wait_find_image_in_roi", lambda *args, **kwargs: False)
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: f"{prefix}.png")
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, offset=3: points.append((x, y)),
    )

    with pytest.raises(RuntimeError, match="未找到华山论剑卡片"):
        task.open_hslj_panel()

    assert points == []


def test_hslj_missing_open_button_does_not_use_old_fallback(monkeypatch) -> None:
    task = HSLJTask()
    finds = iter([True, False])
    points: list[tuple[int, int]] = []
    template_clicks: list[int] = []

    monkeypatch.setattr(task, "open_activity_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        task,
        "wait_find_image_in_roi",
        lambda *args, **kwargs: next(finds),
    )
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: f"{prefix}.png")
    monkeypatch.setattr(task, "wait", lambda ms: None)
    monkeypatch.setattr(
        task,
        "click_point",
        lambda x, y, offset=3: points.append((x, y)),
    )
    monkeypatch.setattr(task, "click", lambda offset=3: template_clicks.append(offset))

    with pytest.raises(RuntimeError, match="未找到华山论剑打开按钮"):
        task.open_hslj_panel()

    assert points == [(220, 222)]
    assert template_clicks == []


def test_hslj_runtime_recovery_cleans_once_then_reopens(monkeypatch) -> None:
    task = HSLJTask()
    calls: list[str] = []

    monkeypatch.setattr(task, "ensure_hslj_panel_visible", lambda **kwargs: False)
    monkeypatch.setattr(task, "resolve_hslj_transient_state", lambda mode: False)
    monkeypatch.setattr(
        task,
        "close_all_panels",
        lambda **kwargs: calls.append("cleanup"),
    )
    monkeypatch.setattr(
        task,
        "_open_hslj_panel_via_activity",
        lambda: calls.append("open"),
    )

    task.ensure_hslj_panel_ready(mode=task.MODE_1V1, timeout_ms=1000)

    assert calls == ["cleanup", "open"]


def test_jhyxb_initial_and_runtime_navigation_have_separate_cleanup(monkeypatch) -> None:
    task = JianghuYingxiongbangTask()
    calls: list[str] = []

    monkeypatch.setattr(
        task,
        "_open_jhyxb_panel_via_activity",
        lambda: calls.append("open"),
    )
    monkeypatch.setattr(
        task,
        "close_all_panels",
        lambda **kwargs: calls.append("cleanup"),
    )

    task.open_jhyxb_panel()
    assert calls == ["open"]

    calls.clear()
    monkeypatch.setattr(task, "ensure_jhyxb_panel_visible", lambda **kwargs: False)
    task.ensure_jhyxb_panel_ready(timeout_ms=1000)
    assert calls == ["cleanup", "open"]


def test_jhyxb_missing_entry_saves_debug_screenshot_without_click(monkeypatch) -> None:
    task = JianghuYingxiongbangTask()
    screenshots: list[str] = []
    clicks: list[int] = []

    monkeypatch.setattr(task, "open_activity_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "wait_find_image_in_roi", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: screenshots.append(prefix) or f"{prefix}.png",
    )
    monkeypatch.setattr(task, "click", lambda offset=3: clicks.append(offset))

    with pytest.raises(RuntimeError, match="未找到江湖英雄榜打开按钮"):
        task.open_jhyxb_panel()

    assert screenshots == ["jhyxb_activity_open_missing"]
    assert clicks == []


def test_existing_activity_fixture_still_matches_both_entries() -> None:
    screenshot = load_fixture(FIXTURE_DIR / "活动-纷争.webp")
    vision = VisionEngine()

    hslj = vision.match_template(
        screenshot,
        HSLJTask.BTN_HSLJ_ACTIVITY_1V1,
        threshold=0.85,
        roi=(105, 170, 250, 190),
    )
    jhyxb = vision.match_template(
        screenshot,
        JianghuYingxiongbangTask.BTN_JHYXB_ACTIVITY_OPEN,
        threshold=0.85,
        roi=(720, 500, 240, 120),
    )

    assert hslj.found
    assert jhyxb.found


def test_jianghu_huashi_close_is_a_startup_popup_without_main_scene_false_positive() -> None:
    huashi = load_fixture(FIXTURE_DIR / "jianghu_huashi_panel.webp")
    main = load_fixture(FIXTURE_DIR / "role_switch_navigation" / "main_menu_collapsed.webp")
    vision = VisionEngine()

    positive = vision.match_template(
        huashi,
        YmGameTask.BTN_JIANGHU_HUASHI_CLOSE,
        threshold=YmGameTask.CLOSE_MATCH_THRESHOLD,
    )
    negative = vision.match_template(
        main,
        YmGameTask.BTN_JIANGHU_HUASHI_CLOSE,
        threshold=YmGameTask.CLOSE_MATCH_THRESHOLD,
    )

    assert positive.found
    assert positive.center == (1253, 30)
    assert not negative.found

    task = YmGameTask()
    task._vision = vision
    task._adb = StaticADB(huashi)  # type: ignore[assignment]
    state = task.detect_login_state(include_modal_controls=True)

    assert state is not None
    assert state.name == task.LOGIN_STATE_POPUP
    assert state.center == (1253, 30)
    assert state.template_path == task.BTN_JIANGHU_HUASHI_CLOSE


def test_task_level_navigation_retry_repeats_lifecycle() -> None:
    task = LifecycleRetryTask()
    runner = TaskQueueRunner(
        [task],
        StaticADB(),  # type: ignore[arg-type]
        VisionEngine(),
    )

    results = runner.run()

    assert task.before_start_calls == 3
    assert task.on_start_calls == 3
    assert task.navigation_calls == 3
    assert results[-1].success
