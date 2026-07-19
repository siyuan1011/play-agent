from __future__ import annotations

import pytest

from ymjh_bot.task.BPRW_task import BPRWTask


def test_bprw_sidebar_scroll_uses_short_slow_drag(monkeypatch) -> None:
    task = BPRWTask()
    swipes: list[tuple[int, int, int, int, int]] = []
    waits: list[int] = []

    def record_swipe(
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 400,
    ) -> None:
        swipes.append((x1, y1, x2, y2, duration_ms))

    monkeypatch.setattr(task, "swipe", record_swipe)
    monkeypatch.setattr(task, "wait", waits.append)

    task.scroll_task_list_down()

    assert swipes == [(190, 360, 190, 260, 1000)]
    assert waits == [500]


def test_bprw_sidebar_search_scrolls_once_between_each_failed_scan(monkeypatch) -> None:
    task = BPRWTask()
    scan_results = iter((None, None, "刺探敌情"))
    scrolls: list[None] = []

    monkeypatch.setattr(
        task,
        "switch_task_panel",
        lambda *args, **kwargs: pytest.fail("后续侧栏搜索不应重复切换江湖页签"),
    )
    monkeypatch.setattr(
        task,
        "wait_bangpai_task_title_in_sidebar",
        lambda *args, **kwargs: next(scan_results),
    )
    monkeypatch.setattr(task, "scroll_task_list_down", lambda: scrolls.append(None))

    assert task.find_bangpai_task_in_sidebar(max_scrolls=2) == "刺探敌情"
    assert len(scrolls) == 2


def test_bprw_sidebar_search_honors_max_scrolls(monkeypatch) -> None:
    task = BPRWTask()
    scans: list[None] = []
    scrolls: list[None] = []

    monkeypatch.setattr(
        task,
        "switch_task_panel",
        lambda *args, **kwargs: pytest.fail("后续侧栏搜索不应重复切换江湖页签"),
    )

    def miss_task(*args, **kwargs) -> None:
        scans.append(None)
        return None

    monkeypatch.setattr(task, "wait_bangpai_task_title_in_sidebar", miss_task)
    monkeypatch.setattr(task, "scroll_task_list_down", lambda: scrolls.append(None))

    assert task.find_bangpai_task_in_sidebar(max_scrolls=2) is None
    assert len(scans) == 3
    assert len(scrolls) == 2
