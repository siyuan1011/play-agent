from __future__ import annotations

from typing import TypeAlias

import pytest

from ymjh_bot.task.JHXS_task import JHXSTask
from ymjh_bot.task.JYPY_task import JYPYTask

PublishTask: TypeAlias = type[JHXSTask] | type[JYPYTask]


@pytest.mark.parametrize("task_class", [JHXSTask, JYPYTask])
def test_open_publish_panel_does_not_read_previous_target_quota(
    task_class: PublishTask,
) -> None:
    task = task_class()
    quota_checks: list[str] = []

    task.ensure_bounty_publish_panel_open = lambda: None  # type: ignore[method-assign]
    task._is_bounty_publish_quota_exhausted = (  # type: ignore[method-assign]
        lambda: quota_checks.append("quota") or True
    )

    task.open_bounty_publish_panel()

    assert quota_checks == []


@pytest.mark.parametrize("task_class", [JHXSTask, JYPYTask])
def test_publish_selects_own_target_before_reading_quota(
    task_class: PublishTask,
) -> None:
    task = task_class()
    state = {"target_selected": False}
    events: list[str] = []
    logs: list[str] = []

    task.confirm_publish_modal_if_visible = lambda **_kwargs: False  # type: ignore[method-assign]
    task.is_bounty_publish_panel_visible = lambda: True  # type: ignore[method-assign]
    task.is_bounty_target_selected = (  # type: ignore[method-assign]
        lambda: state["target_selected"]
    )

    def select_own_target() -> None:
        events.append("select_target")
        state["target_selected"] = True

    def read_selected_target_quota() -> bool:
        events.append("read_quota")
        assert state["target_selected"] is True
        return True

    task.select_bounty_target = select_own_target  # type: ignore[method-assign]
    task._is_bounty_publish_quota_exhausted = (  # type: ignore[method-assign]
        read_selected_target_quota
    )
    task._log = logs.append  # type: ignore[method-assign]

    task.publish_bounty()

    assert events == ["select_target", "read_quota"]
    assert logs == ["悬赏发布次数已用完，按今日已完成处理"]
