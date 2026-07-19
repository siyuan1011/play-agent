from __future__ import annotations

import pytest

from ymjh_bot.task.BPRW_task import BPRWTask
from ymjh_bot.task.JYPY_task import JYPYTask
from ymjh_bot.task.KYRW_task import KyrwTask
from ymjh_bot.task.RCFB_task import RichangFubenTask
from ymjh_bot.ym_game_task import TaskSidebarStateError


def raise_sidebar_error(*args, **kwargs) -> None:
    raise TaskSidebarStateError("侧栏状态未知")


def test_bprw_initial_sidebar_error_is_not_treated_as_missing_task(monkeypatch) -> None:
    task = BPRWTask()
    monkeypatch.setattr(task, "switch_task_panel", raise_sidebar_error)

    with pytest.raises(TaskSidebarStateError, match="侧栏状态未知"):
        task.resume_existing_task()


def test_rcfb_does_not_treat_sidebar_error_as_missing_task(monkeypatch) -> None:
    task = RichangFubenTask()
    monkeypatch.setattr(task, "collapse_chat_if_open", lambda *args, **kwargs: False)
    monkeypatch.setattr(task, "switch_task_panel", raise_sidebar_error)

    with pytest.raises(TaskSidebarStateError, match="侧栏状态未知"):
        task.find_dungeon_task_in_sidebar(max_scrolls=0)


@pytest.mark.parametrize(
    ("task", "find_method", "setup_method"),
    [
        (JYPYTask(), "find_jypy_task_in_sidebar", None),
        (KyrwTask(), "find_course_task_in_sidebar", "ensure_left_task_sidebar_visible"),
    ],
)
def test_two_tab_scans_require_every_panel_to_be_confirmed(
    monkeypatch,
    task,
    find_method: str,
    setup_method: str | None,
) -> None:
    if setup_method is not None:
        monkeypatch.setattr(task, setup_method, lambda: None)
    else:
        monkeypatch.setattr(task, "collapse_chat_if_open", lambda *args, **kwargs: False)

    def switch(panel: str, **kwargs) -> None:
        if panel == "任务":
            raise TaskSidebarStateError("任务页签状态未知")

    monkeypatch.setattr(task, "switch_task_panel", switch)
    monkeypatch.setattr(task, "wait_find_image_in_roi", lambda *args, **kwargs: False)

    method = getattr(task, find_method)
    call_kwargs = {"max_scrolls": 0}
    if isinstance(task, KyrwTask):
        call_kwargs["panels"] = ("任务", "江湖")

    with pytest.raises(TaskSidebarStateError, match="前置检查不完整"):
        method(**call_kwargs)


def test_two_confirmed_empty_panels_may_return_false(monkeypatch) -> None:
    task = JYPYTask()
    monkeypatch.setattr(task, "collapse_chat_if_open", lambda *args, **kwargs: False)
    monkeypatch.setattr(task, "switch_task_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(task, "wait_find_image_in_roi", lambda *args, **kwargs: False)

    assert task.find_jypy_task_in_sidebar(max_scrolls=0) is False
