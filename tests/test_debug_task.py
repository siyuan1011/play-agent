from __future__ import annotations

from ymjh_bot.run_queue import _load_available_tasks
from ymjh_bot.task.DEBUG_task import DebugTask


def test_debug_task_waits_ten_seconds_then_completes(monkeypatch) -> None:
    task = DebugTask()
    waits: list[int] = []
    logs: list[str] = []
    monkeypatch.setattr(task, "wait", waits.append)
    monkeypatch.setattr(task, "_log", logs.append)

    assert task.wait_ten_seconds() is None
    assert waits == [10_000]
    assert logs == ["调试任务开始，等待 10 秒", "调试任务完成"]


def test_debug_task_is_visible_in_the_queue() -> None:
    available = {task["key"]: task for task in _load_available_tasks()}

    assert available["DEBUG"]["name"] == "调试任务（等待 10 秒）"
    assert available["DEBUG"]["class"].get_steps()[0][0] == "wait_ten_seconds"
