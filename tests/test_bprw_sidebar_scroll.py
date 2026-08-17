from __future__ import annotations

import pytest

from ymjh_bot.task.BPRW_task import BPRWTask
from ymjh_bot.ym_game_task import TaskSidebarStateError


def test_bprw_sidebar_scroll_uses_unified_drags(monkeypatch) -> None:
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
    task.scroll_task_list_up()

    assert swipes == [
        (190, 330, 190, 190, 1000),
        (190, 190, 190, 330, 400),
    ]
    assert waits == [500, 500]


def test_bprw_sidebar_search_scrolls_once_between_each_failed_scan(monkeypatch) -> None:
    task = BPRWTask()
    scan_results = iter((None, None, "刺探敌情"))
    events: list[str] = []
    wait_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        task,
        "switch_task_panel",
        lambda panel, **kwargs: events.append(f"switch:{panel}"),
    )

    def scan(*args, **kwargs) -> str | None:
        events.append("scan")
        wait_calls.append(kwargs)
        return next(scan_results)

    monkeypatch.setattr(
        task,
        "wait_bangpai_task_title_in_sidebar",
        scan,
    )
    monkeypatch.setattr(task, "scroll_task_list_up", lambda: events.append("scroll_up"))
    monkeypatch.setattr(task, "scroll_task_list_down", lambda: events.append("scroll"))

    assert task.find_bangpai_task_in_sidebar(max_scrolls=2) == "刺探敌情"
    assert events == [
        "switch:江湖",
        "scroll_up",
        "switch:江湖",
        "scroll_up",
        "switch:江湖",
        "scan",
        "switch:江湖",
        "scroll",
        "switch:江湖",
        "scan",
        "switch:江湖",
        "scroll",
        "switch:江湖",
        "scan",
    ]
    assert wait_calls == [
        {
            "timeout_ms": 1500,
            "threshold": 0.8,
            "interval_ms": 500,
        }
    ] * 3


def test_bprw_sidebar_search_honors_max_scrolls(monkeypatch) -> None:
    task = BPRWTask()
    scans: list[None] = []
    scrolls: list[None] = []
    scroll_ups: list[None] = []
    switched_panels: list[str] = []

    monkeypatch.setattr(
        task,
        "switch_task_panel",
        lambda panel, **kwargs: switched_panels.append(panel),
    )

    def miss_task(*args, **kwargs) -> None:
        scans.append(None)
        return None

    monkeypatch.setattr(task, "wait_bangpai_task_title_in_sidebar", miss_task)
    monkeypatch.setattr(task, "scroll_task_list_up", lambda: scroll_ups.append(None))
    monkeypatch.setattr(task, "scroll_task_list_down", lambda: scrolls.append(None))

    assert task.find_bangpai_task_in_sidebar(max_scrolls=2) is None
    assert switched_panels == ["江湖"] * 7
    assert len(scroll_ups) == 2
    assert len(scans) == 3
    assert len(scrolls) == 2


def test_bprw_sidebar_overlay_error_stops_before_scan_click_or_scroll(monkeypatch) -> None:
    task = BPRWTask()
    logs: list[str] = []

    def raise_overlay_error(*args, **kwargs) -> None:
        raise TaskSidebarStateError("活动日历覆盖任务侧栏")

    monkeypatch.setattr(task, "switch_task_panel", raise_overlay_error)
    monkeypatch.setattr(
        task,
        "wait_bangpai_task_title_in_sidebar",
        lambda *args, **kwargs: pytest.fail("侧栏状态异常时不应扫描任务标题"),
    )
    monkeypatch.setattr(
        task,
        "scroll_task_list_down",
        lambda: pytest.fail("侧栏状态异常时不应滑动"),
    )
    monkeypatch.setattr(
        task,
        "scroll_task_list_up",
        lambda: pytest.fail("侧栏状态异常时不应归顶"),
    )
    monkeypatch.setattr(task, "click", lambda *args, **kwargs: pytest.fail("侧栏状态异常时不应点击"))
    monkeypatch.setattr(task, "_log", logs.append)

    with pytest.raises(TaskSidebarStateError, match="活动日历覆盖任务侧栏"):
        task.click_bangpai_task_from_sidebar(max_scrolls=2, required=False)

    assert logs == ["帮派任务侧栏状态不可用，停止本轮扫描：活动日历覆盖任务侧栏"]


def test_bprw_sidebar_overlay_after_scan_stops_before_scroll(monkeypatch) -> None:
    task = BPRWTask()
    switch_calls: list[str] = []
    scans: list[int] = []
    logs: list[str] = []

    def switch(panel: str, **kwargs) -> None:
        switch_calls.append(panel)
        if len(switch_calls) == 4:
            raise TaskSidebarStateError("扫描期间活动日历覆盖任务侧栏")

    monkeypatch.setattr(task, "switch_task_panel", switch)
    monkeypatch.setattr(
        task,
        "wait_bangpai_task_title_in_sidebar",
        lambda *args, **kwargs: scans.append(1) or None,
    )
    scroll_ups: list[int] = []
    monkeypatch.setattr(task, "scroll_task_list_up", lambda: scroll_ups.append(1))
    monkeypatch.setattr(
        task,
        "scroll_task_list_down",
        lambda: pytest.fail("扫描期间出现覆盖层后不应滑动"),
    )
    monkeypatch.setattr(task, "_log", logs.append)

    with pytest.raises(TaskSidebarStateError, match="扫描期间活动日历覆盖任务侧栏"):
        task.find_bangpai_task_in_sidebar(max_scrolls=2)

    assert switch_calls == ["江湖", "江湖", "江湖", "江湖"]
    assert scroll_ups == [1, 1]
    assert scans == [1]
    assert logs[-1] == "帮派任务侧栏状态不可用，停止本轮扫描：扫描期间活动日历覆盖任务侧栏"
