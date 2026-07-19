from __future__ import annotations

import pytest

from ymjh_bot.task.BPRW_task import BPRWTask


NORMAL_TASK_TITLES = (
    "大宴宾客",
    "帮派建设",
    "刺探敌情",
    "紧急救援",
    "金陵护送",
)


@pytest.mark.parametrize("task_title", NORMAL_TASK_TITLES)
def test_normal_bprw_titles_wait_for_auto_pathfinding(monkeypatch, task_title: str) -> None:
    task = BPRWTask()
    waits: list[int | None] = []

    monkeypatch.setattr(
        task,
        "wait_auto_pathfinding",
        lambda *, timeout_ms=None, **kwargs: waits.append(timeout_ms) or True,
    )
    monkeypatch.setattr(
        task,
        "handle_return_task_item_after_click",
        lambda: pytest.fail("普通帮派任务不应进入回帮复命物品流程"),
    )

    assert task.handle_clicked_bangpai_task(task_title) is True
    assert waits == [task.TASK_TRANSITION_TIMEOUT_MS]


def test_return_title_waits_for_transition_before_item_flow(monkeypatch) -> None:
    task = BPRWTask()
    calls: list[str] = []

    monkeypatch.setattr(
        task,
        "wait_auto_pathfinding",
        lambda **kwargs: calls.append("wait") or True,
    )
    monkeypatch.setattr(
        task,
        "handle_return_task_item_after_click",
        lambda: calls.append("item") or True,
    )

    assert task.handle_clicked_bangpai_task("回帮复命") is True
    assert calls == ["wait", "item"]


def test_transition_timeout_saves_screenshot_and_raises(monkeypatch) -> None:
    task = BPRWTask()

    monkeypatch.setattr(task, "wait_auto_pathfinding", lambda **kwargs: False)
    monkeypatch.setattr(task, "save_debug_screenshot", lambda prefix: "timeout.png")

    with pytest.raises(RuntimeError, match="等待自动寻路或过图结束超时"):
        task.handle_clicked_bangpai_task("帮派建设")


def test_resume_existing_task_preserves_title_before_jump(monkeypatch) -> None:
    task = BPRWTask()
    calls: list[str] = []

    monkeypatch.setattr(
        task,
        "switch_task_panel",
        lambda panel: calls.append(f"switch:{panel}"),
    )
    monkeypatch.setattr(
        task,
        "click_bangpai_task_from_sidebar",
        lambda **kwargs: calls.append("click") or "回帮复命",
    )
    monkeypatch.setattr(
        task,
        "handle_clicked_bangpai_task",
        lambda title: calls.append(f"handle:{title}") or True,
    )
    monkeypatch.setattr(task, "jump_to", lambda target: calls.append(f"jump:{target}"))

    task.resume_existing_task()

    assert calls == ["switch:江湖", "click", "handle:回帮复命", "jump:run_task_flow"]


def test_start_accepted_task_preserves_title_before_return(monkeypatch) -> None:
    task = BPRWTask()
    calls: list[str] = []

    monkeypatch.setattr(
        task,
        "click_bangpai_task_from_sidebar",
        lambda **kwargs: calls.append("click") or "刺探敌情",
    )
    monkeypatch.setattr(
        task,
        "handle_clicked_bangpai_task",
        lambda title: calls.append(f"handle:{title}") or True,
    )

    task.start_accepted_task()

    assert calls == ["click", "handle:刺探敌情"]


def test_return_item_flow_prioritizes_submit(monkeypatch) -> None:
    task = BPRWTask()
    calls: list[str] = []

    monkeypatch.setattr(
        task,
        "handle_submit_panel_if_visible",
        lambda: calls.append("submit") or True,
    )
    monkeypatch.setattr(
        task,
        "handle_trade_panel_if_visible",
        lambda: calls.append("trade") or True,
    )
    monkeypatch.setattr(
        task,
        "handle_acquire_route_panel_if_visible",
        lambda: calls.append("acquire") or True,
    )

    assert task.handle_return_task_item_after_click() is True
    assert calls == ["submit"]


def test_return_item_flow_falls_back_to_acquisition(monkeypatch) -> None:
    task = BPRWTask()
    calls: list[str] = []

    monkeypatch.setattr(
        task,
        "handle_submit_panel_if_visible",
        lambda: calls.append("submit") or False,
    )
    monkeypatch.setattr(
        task,
        "handle_trade_panel_if_visible",
        lambda: calls.append("trade") or False,
    )
    monkeypatch.setattr(
        task,
        "handle_acquire_route_panel_if_visible",
        lambda: calls.append("acquire") or True,
    )

    assert task.handle_return_task_item_after_click() is True
    assert calls == ["submit", "trade", "acquire"]


def test_reopen_acquire_panel_waits_for_return_task_transition(monkeypatch) -> None:
    task = BPRWTask()
    calls: list[str] = []

    monkeypatch.setattr(task, "is_acquire_route_panel_visible", lambda: False)
    monkeypatch.setattr(
        task,
        "click_bangpai_task_from_sidebar",
        lambda **kwargs: calls.append("click") or "回帮复命",
    )
    monkeypatch.setattr(
        task,
        "wait_bangpai_task_transition",
        lambda description: calls.append("wait"),
    )
    monkeypatch.setattr(
        task,
        "wait_acquire_route_panel_visible",
        lambda **kwargs: calls.append("panel") or True,
    )

    assert task.ensure_acquire_route_panel_open() is True
    assert calls == ["click", "wait", "panel"]


@pytest.mark.parametrize(
    ("handled_panel", "expected_calls"),
    [
        ("submit", ["submit"]),
        ("trade", ["submit", "trade"]),
        ("acquire", ["submit", "trade", "acquire"]),
    ],
)
def test_task_flow_panel_handlers_short_circuit_and_retry(
    monkeypatch,
    handled_panel: str,
    expected_calls: list[str],
) -> None:
    task = BPRWTask()
    calls: list[str] = []
    completion_results = iter((False, True))

    monkeypatch.setattr(task, "close_completion_dialog_if_visible", lambda: next(completion_results))
    for panel_name, method_name in (
        ("submit", "handle_submit_panel_if_visible"),
        ("trade", "handle_trade_panel_if_visible"),
        ("acquire", "handle_acquire_route_panel_if_visible"),
    ):
        monkeypatch.setattr(
            task,
            method_name,
            lambda name=panel_name: calls.append(name) or name == handled_panel,
        )
    monkeypatch.setattr(
        task,
        "click_bangpai_task_from_sidebar",
        lambda **kwargs: pytest.fail("面板处理成功后不应搜索侧栏"),
    )
    monkeypatch.setattr(task, "wait", lambda ms: calls.append(f"wait:{ms}"))

    task.run_task_flow()

    assert calls == [*expected_calls, f"wait:{task.TASK_FLOW_RETRY_WAIT_MS}"]


@pytest.mark.parametrize("task_title", ["帮派建设", "回帮复命"])
def test_task_flow_uses_same_sidebar_entry_for_all_titles(monkeypatch, task_title: str) -> None:
    task = BPRWTask()
    calls: list[str] = []
    completion_results = iter((False, True))

    monkeypatch.setattr(task, "close_completion_dialog_if_visible", lambda: next(completion_results))
    monkeypatch.setattr(task, "handle_submit_panel_if_visible", lambda: False)
    monkeypatch.setattr(task, "handle_trade_panel_if_visible", lambda: False)
    monkeypatch.setattr(task, "handle_acquire_route_panel_if_visible", lambda: False)
    monkeypatch.setattr(
        task,
        "close_transient_panels",
        lambda **kwargs: pytest.fail("无面板时不应执行额外关闭操作"),
    )
    monkeypatch.setattr(
        task,
        "click_bangpai_task_from_sidebar",
        lambda **kwargs: calls.append("search") or task_title,
    )
    monkeypatch.setattr(
        task,
        "handle_clicked_bangpai_task",
        lambda title: calls.append(f"handle:{title}") or True,
    )
    monkeypatch.setattr(task, "wait", lambda ms: calls.append(f"wait:{ms}"))

    task.run_task_flow()

    assert calls == ["search", f"handle:{task_title}", f"wait:{task.TASK_FLOW_RETRY_WAIT_MS}"]


def test_task_flow_waits_and_retries_when_sidebar_title_is_missing(monkeypatch) -> None:
    task = BPRWTask()
    waits: list[int] = []
    completion_results = iter((False, True))

    monkeypatch.setattr(task, "close_completion_dialog_if_visible", lambda: next(completion_results))
    monkeypatch.setattr(task, "handle_submit_panel_if_visible", lambda: False)
    monkeypatch.setattr(task, "handle_trade_panel_if_visible", lambda: False)
    monkeypatch.setattr(task, "handle_acquire_route_panel_if_visible", lambda: False)
    monkeypatch.setattr(
        task,
        "close_transient_panels",
        lambda **kwargs: pytest.fail("无面板时不应执行额外关闭操作"),
    )
    monkeypatch.setattr(task, "click_bangpai_task_from_sidebar", lambda **kwargs: None)
    monkeypatch.setattr(
        task,
        "handle_clicked_bangpai_task",
        lambda title: pytest.fail("未找到标题时不应执行点击后处理"),
    )
    monkeypatch.setattr(task, "wait", waits.append)

    task.run_task_flow()

    assert waits == [task.TASK_FLOW_RETRY_WAIT_MS]


def test_bprw_keeps_merged_six_step_order() -> None:
    step_names = [name for name, _, _ in BPRWTask.get_steps()]

    assert step_names == [
        "resume_existing_task",
        "open_bangpai_activity",
        "auto_pathfinding",
        "accept_task",
        "start_accepted_task",
        "run_task_flow",
    ]
    assert not hasattr(BPRWTask, "TASK_FLOW_POLL_INTERVAL_MS")
    assert not hasattr(BPRWTask, "TASK_IDLE_CLICK_LIMIT")
