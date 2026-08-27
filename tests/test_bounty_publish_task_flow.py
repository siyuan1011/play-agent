from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from botCore import ImageMatchResult, VisionEngine, load_task_class
from ymjh_bot.run_queue import _load_available_tasks
from ymjh_bot.task.JHXS_task import JHXSTask
from ymjh_bot.task.JYPY_task import JYPYTask
from ymjh_bot.ym_game_task import YmGameTask

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ymjh" / "bounty_publish"


def load_fixture(name: str):
    image = cv2.imread(str(FIXTURE_DIR / name), cv2.IMREAD_COLOR)
    assert image is not None
    return image


@pytest.mark.parametrize("task_class", [JHXSTask, JYPYTask])
def test_bounty_publish_tasks_use_the_six_requested_steps(task_class) -> None:
    assert [name for name, _, _ in task_class.get_steps()] == [
        "open_any_activity_panel",
        "open_bounty_panel",
        "open_bounty_publish_panel",
        "open_bounty_target_dropdown",
        "select_bounty_target",
        "publish_bounty",
    ]


def test_bounty_publish_tasks_are_discoverable() -> None:
    task_dir = Path(__file__).parents[1] / "src" / "ymjh_bot" / "task"

    assert JHXSTask.__bases__ == (YmGameTask,)
    assert JYPYTask.__bases__ == (YmGameTask,)
    assert not (task_dir / "bounty_publish.py").exists()
    assert not hasattr(JHXSTask, "TEXT_TARGET_OPTION_JUYI_PINGYUAN")
    assert not hasattr(JYPYTask, "TEXT_TARGET_OPTION_JIANGHU_XINGSHANG")
    for task_class in (JHXSTask, JYPYTask):
        assert all(step_name in task_class.__dict__ for step_name in task_class.STEP_ORDER)
        assert "confirm_publish_modal_if_visible" in task_class.__dict__
        assert "ensure_bounty_panel_open" in task_class.__dict__
        assert "_wait_bounty_match" in task_class.__dict__

    assert load_task_class(task_dir / "JHXS_task.py").task_key == "JHXS"
    assert load_task_class(task_dir / "JYPY_task.py").task_key == "JYPY"

    available = {
        task_info["key"]: task_info["name"]
        for task_info in _load_available_tasks()
    }
    assert available["JHXS"] == "江湖行商"
    assert available["JYPY"] == "聚义平冤"


def test_live_frames_verify_panel_dropdown_and_target_anchors() -> None:
    jhxs = JHXSTask()
    jypy = JYPYTask()
    vision = VisionEngine()
    for task in (jhxs, jypy):
        task._vision = vision
        task._screen_resolution = task.design_resolution

    panel = load_fixture("panel.png")
    dropdown = load_fixture("dropdown.png")
    jhxs_selected = load_fixture("jianghu_xingshang_selected.png")
    jypy_selected = load_fixture("juyi_pingyuan_selected.png")
    confirmation_modal = load_fixture("confirmation_modal.png")
    published = load_fixture("published.png")

    assert jhxs.is_bounty_panel_visible(panel)
    assert jhxs.is_bounty_target_dropdown_open(dropdown)
    assert jhxs.is_bounty_publish_panel_visible(jhxs_selected)
    assert jypy.is_bounty_publish_panel_visible(jypy_selected)
    assert jhxs.is_bounty_target_selected(jhxs_selected)
    assert not jhxs.is_bounty_target_selected(jypy_selected)
    assert jypy.is_bounty_target_selected(jypy_selected)
    assert not jypy.is_bounty_target_selected(jhxs_selected)
    assert jhxs.is_bounty_panel_visible(published)
    assert not jhxs.is_bounty_publish_panel_visible(published)
    modal_confirm = jhxs._match_bounty_template(
        confirmation_modal,
        jhxs.BTN_PUBLISH_MODAL_CONFIRM,
        mode="otsu_dark",
        threshold=jhxs.PUBLISH_MODAL_CONFIRM_THRESHOLD,
        roi=jhxs.ROI_PUBLISH_MODAL_CONFIRM,
    )
    assert modal_confirm.found
    assert modal_confirm.center == (854, 508)


@pytest.mark.parametrize(
    ("task_class", "expected_target"),
    [
        (JHXSTask, "jianghu_xingshang"),
        (JYPYTask, "juyi_pingyuan"),
    ],
)
def test_select_bounty_target_clicks_the_configured_dropdown_item(
    monkeypatch,
    task_class,
    expected_target: str,
) -> None:
    task = task_class()
    calls: list[tuple[object, str, tuple[int, int, int, int]]] = []
    taps: list[tuple[int, int]] = []
    monkeypatch.setattr(task, "is_bounty_target_dropdown_open", lambda *args, **kwargs: True)
    monkeypatch.setattr(task, "is_bounty_target_selected", lambda *args, **kwargs: True)

    def wait_match(template, *, mode, roi, **kwargs):
        calls.append((template, mode, roi))
        return ImageMatchResult(True, 1.0, (577, 293), (528, 276, 627, 310))

    monkeypatch.setattr(task, "_wait_bounty_match", wait_match)
    monkeypatch.setattr(task, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(task, "wait", lambda _timeout_ms: None)
    monkeypatch.setattr(task, "_log", lambda _message: None)

    task.select_bounty_target()

    assert expected_target in str(calls[0][0])
    assert calls[0][1:] == ("light_foreground", task.ROI_TARGET_OPTIONS)
    assert taps == [(577, 293)]


def test_open_activity_step_keeps_the_current_activity_category(monkeypatch) -> None:
    task = JHXSTask()
    calls: list[dict[str, int]] = []
    monkeypatch.setattr(
        task,
        "open_activity_panel",
        lambda **kwargs: calls.append(kwargs),
    )

    task.open_any_activity_panel()

    assert calls == [{"wait_after_open_ms": task.ACTIVITY_SETTLE_MS}]


@pytest.mark.parametrize("task_class", [JHXSTask, JYPYTask])
def test_retry_confirms_each_tasks_own_pending_publish_modal(
    monkeypatch,
    task_class,
) -> None:
    task = task_class()
    timeouts: list[int] = []
    monkeypatch.setattr(
        task,
        "confirm_publish_modal_if_visible",
        lambda *, timeout_ms: timeouts.append(timeout_ms) or True,
    )
    monkeypatch.setattr(task, "_log", lambda _message: None)

    task.before_retry("step", RuntimeError("retry"))

    assert timeouts == [1000]


def test_publish_step_confirms_the_second_modal(monkeypatch) -> None:
    task = JHXSTask()
    matches = iter(
        (
            ImageMatchResult(False, 0.0, None, None),
            ImageMatchResult(True, 1.0, (877, 549), (812, 527, 942, 571)),
            ImageMatchResult(True, 1.0, (854, 508), (777, 477, 931, 539)),
        )
    )
    templates: list[object] = []
    taps: list[tuple[int, int]] = []
    monkeypatch.setattr(task, "is_bounty_publish_panel_visible", lambda *args, **kwargs: True)
    monkeypatch.setattr(task, "is_bounty_target_selected", lambda *args, **kwargs: True)

    def wait_match(template, **_kwargs):
        templates.append(template)
        return next(matches)

    monkeypatch.setattr(task, "_wait_bounty_match", wait_match)
    monkeypatch.setattr(task, "_wait_publish_success", lambda **kwargs: True)
    monkeypatch.setattr(task, "tap", lambda x, y: taps.append((x, y)))
    monkeypatch.setattr(task, "wait", lambda _timeout_ms: None)
    monkeypatch.setattr(task, "_log", lambda _message: None)

    task.publish_bounty()

    assert templates == [
        task.BTN_PUBLISH_MODAL_CONFIRM,
        task.BTN_PUBLISH_CONFIRM,
        task.BTN_PUBLISH_MODAL_CONFIRM,
    ]
    assert taps == [(877, 549), (854, 508)]
    assert task._publish_submitted is True


@pytest.mark.parametrize(
    ("task_class", "target_center", "selected_fixture"),
    [
        (JHXSTask, (577, 293), "jianghu_xingshang_selected.png"),
        (JYPYTask, (577, 360), "juyi_pingyuan_selected.png"),
    ],
)
def test_real_frame_state_machine_replays_the_complete_six_step_flow(
    monkeypatch,
    task_class,
    target_center: tuple[int, int],
    selected_fixture: str,
) -> None:
    task = task_class()
    task._vision = VisionEngine()
    task._screen_resolution = task.design_resolution
    task.PANEL_TIMEOUT_MS = 100
    frames = {
        "activity": load_fixture("activity.png"),
        "panel": load_fixture("panel.png"),
        "default_selected": load_fixture("jianghu_xingshang_selected.png"),
        "dropdown": load_fixture("dropdown.png"),
        "target_selected": load_fixture(selected_fixture),
        "confirmation": load_fixture("confirmation_modal.png"),
        "published": load_fixture("published.png"),
    }
    state = {"name": "activity"}
    taps: list[tuple[int, int]] = []

    def open_activity_panel(**_kwargs) -> None:
        state["name"] = "activity"

    def tap(x: int, y: int) -> None:
        point = (x, y)
        taps.append(point)
        transitions = {
            ("activity", (1113, 51)): "panel",
            ("panel", (1068, 586)): "default_selected",
            ("default_selected", (700, 228)): "dropdown",
            ("dropdown", target_center): "target_selected",
            ("target_selected", (877, 549)): "confirmation",
            ("confirmation", (854, 508)): "published",
        }
        next_state = transitions.get((state["name"], point))
        assert next_state is not None, f"unexpected tap {point} in {state['name']}"
        state["name"] = next_state

    monkeypatch.setattr(task, "open_activity_panel", open_activity_panel)
    monkeypatch.setattr(task, "screenshot", lambda: frames[state["name"]])
    monkeypatch.setattr(task, "tap", tap)
    monkeypatch.setattr(task, "wait", lambda _timeout_ms: None)
    monkeypatch.setattr(task, "_log", lambda _message: None)
    monkeypatch.setattr(
        task,
        "save_debug_screenshot",
        lambda prefix: pytest.fail(f"unexpected debug screenshot: {prefix}"),
    )

    for _, func, _ in task.get_steps():
        func(task)

    assert state["name"] == "published"
    assert taps == [
        (1113, 51),
        (1068, 586),
        (700, 228),
        target_center,
        (877, 549),
        (854, 508),
    ]
