from __future__ import annotations

from collections.abc import Iterator

import pytest

from botCore import StepJumpException
from ymjh_bot.task.BPRW_task import BPRWTask
from ymjh_bot.task.MKSY_task import MKSYTask
from ymjh_bot.task.PZSY_task import PZSYTask


def stub_image_waits(
    monkeypatch,
    task,
    results: list[bool],
) -> list[tuple[object, int | None, float]]:
    calls: list[tuple[object, int | None, float]] = []
    result_iter: Iterator[bool] = iter(results)

    def wait_image_appear(
        template,
        timeout_ms: int | None = 10000,
        threshold: float = 0.8,
        **_kwargs,
    ) -> bool:
        calls.append((template, timeout_ms, threshold))
        return next(result_iter)

    monkeypatch.setattr(task, "wait_image_appear", wait_image_appear)
    return calls


def stub_debug_screenshot(monkeypatch, task) -> list[str]:
    prefixes: list[str] = []

    def save_debug_screenshot(prefix: str) -> str:
        prefixes.append(prefix)
        return f"{prefix}.png"

    monkeypatch.setattr(task, "save_debug_screenshot", save_debug_screenshot)
    return prefixes


def test_bprw_accept_button_failure_preserves_wait_and_error(monkeypatch) -> None:
    task = BPRWTask()
    calls = stub_image_waits(monkeypatch, task, [False])
    monkeypatch.setattr(task, "is_bangpai_list_visible", lambda: False)
    monkeypatch.setattr(task, "click", lambda: pytest.fail("等待失败后不应点击"))

    with pytest.raises(RuntimeError, match="^未找到NPC 帮派任务按钮$"):
        task.accept_task()

    assert calls == [(task.BTN_BANGPAI_TASK_ACCEPT, 120000, 0.8)]


def test_bprw_accept_failure_still_detects_missing_guild(monkeypatch) -> None:
    task = BPRWTask()
    visibility = iter((False, True))
    stub_image_waits(monkeypatch, task, [False])
    monkeypatch.setattr(task, "is_bangpai_list_visible", lambda: next(visibility))

    with pytest.raises(StepJumpException) as exc_info:
        task.accept_task()

    assert exc_info.value.target == StepJumpException.JUMP_TO_END


def test_bprw_confirmation_failure_preserves_sequence(monkeypatch) -> None:
    task = BPRWTask()
    calls = stub_image_waits(monkeypatch, task, [True, False])
    clicks: list[str] = []
    waits: list[int] = []
    monkeypatch.setattr(task, "is_bangpai_list_visible", lambda: False)
    monkeypatch.setattr(task, "click", lambda: clicks.append("click"))
    monkeypatch.setattr(task, "wait", waits.append)

    with pytest.raises(RuntimeError, match="^未找到帮派任务确认按钮$"):
        task.accept_task()

    assert calls == [
        (task.BTN_BANGPAI_TASK_ACCEPT, 120000, 0.8),
        (task.BTN_OK, 10000, 0.8),
    ]
    assert clicks == ["click"]
    assert waits == [1500]


def test_bprw_accept_success_preserves_sequence(monkeypatch) -> None:
    task = BPRWTask()
    calls = stub_image_waits(monkeypatch, task, [True, True])
    clicks: list[str] = []
    waits: list[int] = []
    monkeypatch.setattr(task, "is_bangpai_list_visible", lambda: False)
    monkeypatch.setattr(task, "click", lambda: clicks.append("click"))
    monkeypatch.setattr(task, "wait", waits.append)

    task.accept_task()

    assert calls == [
        (task.BTN_BANGPAI_TASK_ACCEPT, 120000, 0.8),
        (task.BTN_OK, 10000, 0.8),
    ]
    assert clicks == ["click", "click"]
    assert waits == [1500, 1500]


@pytest.mark.parametrize("task_class", [MKSYTask, PZSYTask])
def test_banquet_invite_first_wait_failure(
    monkeypatch,
    task_class,
) -> None:
    task = task_class()
    calls = stub_image_waits(monkeypatch, task, [False])
    screenshots = stub_debug_screenshot(monkeypatch, task)
    monkeypatch.setattr(task, "click", lambda: pytest.fail("等待失败后不应点击"))

    with pytest.raises(RuntimeError, match="^未找到NPC 邀请赴宴按钮$"):
        task.invite_banquet()

    assert calls == [(task.BTN_MENKE_BANQUET_INVITE, 60000, 0.8)]
    assert screenshots == [f"{task.task_key.lower()}_invite_button_missing"]


@pytest.mark.parametrize("task_class", [MKSYTask, PZSYTask])
def test_banquet_invite_confirmation_failure_preserves_sequence(monkeypatch, task_class) -> None:
    task = task_class()
    calls = stub_image_waits(monkeypatch, task, [True, False])
    screenshots = stub_debug_screenshot(monkeypatch, task)
    clicks: list[str] = []
    waits: list[int] = []
    monkeypatch.setattr(task, "click", lambda: clicks.append("click"))
    monkeypatch.setattr(task, "wait", waits.append)

    with pytest.raises(RuntimeError, match="^未找到确认邀约按钮$"):
        task.invite_banquet()

    assert calls == [
        (task.BTN_MENKE_BANQUET_INVITE, 60000, 0.8),
        (task.BTN_MENKE_CONFIRM_INVITE, 10000, 0.8),
    ]
    assert clicks == ["click"]
    assert waits == [1500]
    assert screenshots == [f"{task.task_key.lower()}_invite_confirm_missing"]


@pytest.mark.parametrize(
    ("task_class", "panel_templates"),
    [
        (
            MKSYTask,
            lambda task: [
                task.BTN_MENKE_GET_ITEM,
                task.BTN_MENKE_ONE_KEY_SUBMIT,
                task.BTN_MENKE_START_ACTIVE,
            ],
        ),
        (
            PZSYTask,
            lambda task: [
                task.BTN_POZHEN_GET_ITEM,
                task.BTN_POZHEN_ONE_KEY_SUBMIT,
                task.BTN_POZHEN_SUBMIT_5_TAB,
                task.BTN_POZHEN_SUBMIT_6_TAB,
            ],
        ),
    ],
)
def test_banquet_invite_success_preserves_sequence(monkeypatch, task_class, panel_templates) -> None:
    task = task_class()
    calls = stub_image_waits(monkeypatch, task, [True, True, True])
    clicks: list[str] = []
    waits: list[int] = []
    monkeypatch.setattr(task, "click", lambda: clicks.append("click"))
    monkeypatch.setattr(task, "wait", waits.append)

    task.invite_banquet()

    assert calls == [
        (task.BTN_MENKE_BANQUET_INVITE, 60000, 0.8),
        (task.BTN_MENKE_CONFIRM_INVITE, 10000, 0.8),
        (panel_templates(task), 30000, 0.8),
    ]
    assert clicks == ["click", "click"]
    assert waits == [1500, 1500]


@pytest.mark.parametrize(
    ("task_class", "panel_templates", "error_message"),
    [
        (
            MKSYTask,
            lambda task: [
                task.BTN_MENKE_GET_ITEM,
                task.BTN_MENKE_ONE_KEY_SUBMIT,
                task.BTN_MENKE_START_ACTIVE,
            ],
            "未进入门客设宴物品面板",
        ),
        (
            PZSYTask,
            lambda task: [
                task.BTN_POZHEN_GET_ITEM,
                task.BTN_POZHEN_ONE_KEY_SUBMIT,
                task.BTN_POZHEN_SUBMIT_5_TAB,
                task.BTN_POZHEN_SUBMIT_6_TAB,
            ],
            "未进入破阵设宴物品面板",
        ),
    ],
)
def test_banquet_invite_panel_failure_requests_complete_retry(
    monkeypatch,
    task_class,
    panel_templates,
    error_message,
) -> None:
    task = task_class()
    calls = stub_image_waits(monkeypatch, task, [True, True, False])
    screenshots = stub_debug_screenshot(monkeypatch, task)
    clicks: list[str] = []
    waits: list[int] = []
    monkeypatch.setattr(task, "click", lambda: clicks.append("click"))
    monkeypatch.setattr(task, "wait", waits.append)

    with pytest.raises(RuntimeError, match=f"^{error_message}$"):
        task.invite_banquet()

    assert calls == [
        (task.BTN_MENKE_BANQUET_INVITE, 60000, 0.8),
        (task.BTN_MENKE_CONFIRM_INVITE, 10000, 0.8),
        (panel_templates(task), 30000, 0.8),
    ]
    assert clicks == ["click", "click"]
    assert waits == [1500, 1500]
    assert screenshots == [f"{task.task_key.lower()}_item_panel_missing"]


@pytest.mark.parametrize("task_class", [MKSYTask, PZSYTask])
def test_banquet_choose_guest_includes_auto_pathfinding(monkeypatch, task_class) -> None:
    task = task_class()
    events: list[str] = []
    monkeypatch.setattr(task, "is_banquet_panel_visible", lambda: False)
    monkeypatch.setattr(
        task,
        "wait_find_image_in_roi",
        lambda *_args, **_kwargs: events.append("find_guest") or True,
    )
    monkeypatch.setattr(task, "click", lambda: events.append("click_guest"))
    monkeypatch.setattr(task, "wait", lambda timeout_ms: events.append(f"wait:{timeout_ms}"))
    monkeypatch.setattr(
        task,
        "wait_auto_pathfinding",
        lambda: events.append("wait_auto_pathfinding") or True,
    )
    monkeypatch.setattr(task, "_log", lambda _message: None)

    task.choose_guest()

    assert events == [
        "find_guest",
        "click_guest",
        "wait:1500",
        "wait_auto_pathfinding",
    ]
    assert "auto_pathfinding" not in [name for name, _, _ in task.get_steps()]
    assert task.invite_banquet._step_meta["retry"] == 0
