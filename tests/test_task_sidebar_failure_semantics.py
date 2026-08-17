from __future__ import annotations

from pathlib import Path

import pytest

from botCore import load_task_class
from ymjh_bot.task.BPRW_task import BPRWTask
from ymjh_bot.task.JYPY_task import JYPYTask
from ymjh_bot.task.KYRW_task import KYRWTask
from ymjh_bot.task.RCFB_task import RCFBTask
from ymjh_bot.ym_game_task import TaskSidebarStateError


def raise_sidebar_error(*args, **kwargs) -> None:
    raise TaskSidebarStateError("侧栏状态未知")


def test_bprw_initial_sidebar_error_is_not_treated_as_missing_task(monkeypatch) -> None:
    task = BPRWTask()
    monkeypatch.setattr(task, "switch_task_panel", raise_sidebar_error)

    with pytest.raises(TaskSidebarStateError, match="侧栏状态未知"):
        task.resume_existing_task()


def test_rcfb_does_not_treat_sidebar_error_as_missing_task(monkeypatch) -> None:
    task = RCFBTask()
    monkeypatch.setattr(task, "collapse_chat_if_open", lambda *args, **kwargs: False)
    monkeypatch.setattr(task, "switch_task_panel", raise_sidebar_error)

    with pytest.raises(TaskSidebarStateError, match="侧栏状态未知"):
        task.find_dungeon_task_in_sidebar(max_scrolls=0)


def test_jypy_two_tab_scan_requires_every_panel_to_be_confirmed(monkeypatch) -> None:
    task = JYPYTask()
    monkeypatch.setattr(task, "collapse_chat_if_open", lambda *args, **kwargs: False)

    def switch(panel: str, **kwargs) -> None:
        if panel == "任务":
            raise TaskSidebarStateError("任务页签状态未知")

    monkeypatch.setattr(task, "switch_task_panel", switch)
    monkeypatch.setattr(task, "wait_find_image_in_roi", lambda *args, **kwargs: False)

    with pytest.raises(TaskSidebarStateError, match="前置检查不完整"):
        task.find_jypy_task_in_sidebar(max_scrolls=0)


def test_two_confirmed_empty_panels_may_return_false(monkeypatch) -> None:
    task = JYPYTask()
    monkeypatch.setattr(task, "collapse_chat_if_open", lambda *args, **kwargs: False)
    monkeypatch.setattr(task, "switch_task_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "wait_find_image_in_roi", lambda *args, **kwargs: False)

    assert task.find_jypy_task_in_sidebar(max_scrolls=0) is False


def test_kyrw_keye_scan_only_uses_jianghu_panel(monkeypatch) -> None:
    task = KYRWTask()
    switched_panels: list[str] = []
    scroll_ups: list[int] = []
    monkeypatch.setattr(task, "ensure_left_task_sidebar_visible", lambda: None)
    monkeypatch.setattr(
        task,
        "switch_task_panel",
        lambda panel, **kwargs: switched_panels.append(panel),
    )
    monkeypatch.setattr(task, "scroll_task_list_up", lambda: scroll_ups.append(1))
    monkeypatch.setattr(task, "wait_image_appear", lambda *args, **kwargs: False)

    assert task.find_keye_task_in_sidebar(max_scrolls=0) is False
    assert scroll_ups == [1, 1]
    assert switched_panels == ["江湖", "江湖", "江湖"]


def test_kyrw_keye_scan_reconfirms_jianghu_after_each_scroll(monkeypatch) -> None:
    task = KYRWTask()
    events: list[str] = []
    wait_calls: list[dict[str, object]] = []
    monkeypatch.setattr(task, "ensure_left_task_sidebar_visible", lambda: None)
    monkeypatch.setattr(
        task,
        "switch_task_panel",
        lambda panel, **kwargs: events.append(f"switch:{panel}"),
    )
    monkeypatch.setattr(task, "scroll_task_list_up", lambda: events.append("scroll_up"))

    def miss_task(*args, **kwargs) -> bool:
        events.append("scan")
        wait_calls.append(kwargs)
        return False

    monkeypatch.setattr(task, "wait_image_appear", miss_task)
    monkeypatch.setattr(task, "scroll_task_list_down", lambda: events.append("scroll"))

    assert task.find_keye_task_in_sidebar(max_scrolls=2) is False
    assert events == [
        "switch:江湖",
        "scroll_up",
        "switch:江湖",
        "scroll_up",
        "switch:江湖",
        "scan",
        "scroll",
        "switch:江湖",
        "scan",
        "scroll",
        "switch:江湖",
        "scan",
    ]
    assert wait_calls == [
        {
            "timeout_ms": 1500,
            "threshold": 0.85,
            "roi": task.scale_roi((40, 135, 330, 430)),
        }
    ] * 3


def test_kyrw_jianghu_sidebar_error_is_not_treated_as_missing_task(monkeypatch) -> None:
    task = KYRWTask()
    monkeypatch.setattr(task, "ensure_left_task_sidebar_visible", lambda: None)
    monkeypatch.setattr(task, "switch_task_panel", raise_sidebar_error)

    with pytest.raises(TaskSidebarStateError, match="前置检查不完整"):
        task.find_keye_task_in_sidebar(max_scrolls=0)


def test_kyrw_post_scroll_sidebar_error_stops_scanning(monkeypatch) -> None:
    task = KYRWTask()
    switch_calls: list[str] = []
    scans: list[int] = []
    scrolls: list[int] = []
    scroll_ups: list[int] = []
    monkeypatch.setattr(task, "ensure_left_task_sidebar_visible", lambda: None)

    def switch(panel: str, **kwargs) -> None:
        switch_calls.append(panel)
        if len(switch_calls) == 4:
            raise TaskSidebarStateError("上拉后侧栏状态未知")

    monkeypatch.setattr(task, "switch_task_panel", switch)
    monkeypatch.setattr(task, "scroll_task_list_up", lambda: scroll_ups.append(1))
    monkeypatch.setattr(
        task,
        "wait_image_appear",
        lambda *args, **kwargs: scans.append(1) or False,
    )
    monkeypatch.setattr(task, "scroll_task_list_down", lambda: scrolls.append(1))

    with pytest.raises(TaskSidebarStateError, match="前置检查不完整"):
        task.find_keye_task_in_sidebar(max_scrolls=2)

    assert switch_calls == ["江湖", "江湖", "江湖", "江湖"]
    assert scroll_ups == [1, 1]
    assert scans == [1]
    assert scrolls == [1]


def test_kyrw_task_class_uses_acronym_naming_and_remains_loadable() -> None:
    task_file = Path(__file__).parents[1] / "src" / "ymjh_bot" / "task" / "KYRW_task.py"

    assert KYRWTask.__name__ == "KYRWTask"
    assert load_task_class(task_file).__name__ == "KYRWTask"


def test_rcfb_task_class_uses_acronym_naming_and_remains_loadable() -> None:
    task_file = Path(__file__).parents[1] / "src" / "ymjh_bot" / "task" / "RCFB_task.py"

    assert RCFBTask.__name__ == "RCFBTask"
    assert load_task_class(task_file).__name__ == "RCFBTask"
