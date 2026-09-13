from __future__ import annotations

import pytest

from botCore import StepStopException
from ymjh_bot.ym_game_task import YmGameTask


class _RuntimeStatusTask(YmGameTask):
    task_name = "运行状态检测测试"


def test_check_runtime_status_defaults_to_safe_canonical_order() -> None:
    task = _RuntimeStatusTask()
    events: list[object] = []
    task._log = lambda _message: None  # type: ignore[method-assign]
    task.wake_from_power_saving_if_needed = (  # type: ignore[method-assign]
        lambda: events.append("power") or False
    )

    def wait_image_missing(templates, **kwargs) -> bool:
        events.append(("transition", templates, kwargs))
        return True

    task.wait_image_missing = wait_image_missing  # type: ignore[method-assign]
    task.recover_health_if_needed = (  # type: ignore[method-assign]
        lambda *, context="": events.append(("health", context))
    )

    assert task.check_runtime_status()
    transition_templates = [
        task.TEXT_AUTO_PATH,
        *task.SCENE_LOADING_LOGO_TEMPLATES,
    ]
    assert events == [
        "power",
        (
            "transition",
            transition_templates,
            {
                "timeout_ms": 120_000,
                "threshold": 0.8,
                "missing_threshold": 3,
                "interval_ms": task.AUTO_PATH_POLL_INTERVAL_MS,
            },
        ),
        ("health", "状态检测"),
    ]


def test_check_runtime_status_only_runs_requested_items_and_deduplicates() -> None:
    task = _RuntimeStatusTask()
    events: list[str] = []
    task._log = lambda _message: None  # type: ignore[method-assign]
    task.wake_from_power_saving_if_needed = (  # type: ignore[method-assign]
        lambda: events.append("power") or False
    )
    task.wait_image_missing = (  # type: ignore[method-assign]
        lambda *_args, **_kwargs: pytest.fail("不应检测过渡状态")
    )
    task.recover_health_if_needed = (  # type: ignore[method-assign]
        lambda *, context="": events.append(f"health:{context}")
    )

    assert task.check_runtime_status("health", "power", "power")
    assert events == ["power", "health:状态检测"]


@pytest.mark.parametrize(
    ("items", "expected_templates"),
    [
        (("finding",), lambda task: [task.TEXT_AUTO_PATH]),
        (("loading",), lambda task: list(task.SCENE_LOADING_LOGO_TEMPLATES)),
        (
            ("finding", "loading"),
            lambda task: [task.TEXT_AUTO_PATH, *task.SCENE_LOADING_LOGO_TEMPLATES],
        ),
    ],
)
def test_check_runtime_status_waits_for_selected_transition_templates_once(
    items,
    expected_templates,
) -> None:
    task = _RuntimeStatusTask()
    calls: list[tuple[list[str], dict[str, object]]] = []
    task._log = lambda _message: None  # type: ignore[method-assign]

    def wait_image_missing(templates, **kwargs) -> bool:
        calls.append((templates, kwargs))
        return True

    task.wait_image_missing = wait_image_missing  # type: ignore[method-assign]

    assert task.check_runtime_status(*items)
    assert calls == [
        (
            expected_templates(task),
            {
                "timeout_ms": 120_000,
                "threshold": 0.8,
                "missing_threshold": 3,
                "interval_ms": task.AUTO_PATH_POLL_INTERVAL_MS,
            },
        )
    ]
    assert "roi" not in calls[0][1]


def test_check_runtime_status_transition_failure_stops_before_health() -> None:
    task = _RuntimeStatusTask()
    task._log = lambda _message: None  # type: ignore[method-assign]

    def fail_transition_wait(*_args, **_kwargs) -> bool:
        task._last_match_center = (100, 100)
        return False

    task.wait_image_missing = fail_transition_wait  # type: ignore[method-assign]
    task.recover_health_if_needed = (  # type: ignore[method-assign]
        lambda **_kwargs: pytest.fail("过渡状态失败后不应检查血量")
    )

    assert not task.check_runtime_status("finding", "loading", "health")
    assert task._last_match_center is None


@pytest.mark.parametrize(
    ("items", "timeout_ms"),
    [
        (("power", "invalid"), 120_000),
        (("power",), 0),
        (("power",), -1),
    ],
)
def test_check_runtime_status_rejects_invalid_input_before_device_actions(
    items: tuple[str, ...],
    timeout_ms: int,
) -> None:
    task = _RuntimeStatusTask()
    task.wake_from_power_saving_if_needed = (  # type: ignore[method-assign]
        lambda: pytest.fail("参数无效时不应检查或操作设备")
    )

    with pytest.raises(ValueError):
        task.check_runtime_status(*items, timeout_ms=timeout_ms)  # type: ignore[arg-type]


def test_check_runtime_status_power_rechecks_only_after_wake() -> None:
    task = _RuntimeStatusTask()
    logs: list[str] = []
    task._log = logs.append  # type: ignore[method-assign]
    task.wake_from_power_saving_if_needed = lambda: False  # type: ignore[method-assign]
    task.is_power_saving_mode = (  # type: ignore[method-assign]
        lambda *_args, **_kwargs: pytest.fail("未唤醒时不应额外复核")
    )

    assert task.check_runtime_status("power")

    task.wake_from_power_saving_if_needed = lambda: True  # type: ignore[method-assign]
    task.is_power_saving_mode = lambda *_args, **_kwargs: False  # type: ignore[method-assign]
    assert task.check_runtime_status("power")
    assert "省电模式已唤醒，复核通过" in logs


def test_check_runtime_status_returns_false_when_power_remains_active() -> None:
    task = _RuntimeStatusTask()
    logs: list[str] = []
    task._log = logs.append  # type: ignore[method-assign]
    task.wake_from_power_saving_if_needed = lambda: True  # type: ignore[method-assign]
    task.is_power_saving_mode = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    task.recover_health_if_needed = (  # type: ignore[method-assign]
        lambda **_kwargs: pytest.fail("省电复核失败后不应继续检查血量")
    )

    assert not task.check_runtime_status("power", "health")
    assert logs == ["省电模式唤醒后复核仍未通过"]


def test_check_runtime_status_health_failure_returns_false_but_stop_propagates() -> None:
    task = _RuntimeStatusTask()
    logs: list[str] = []
    task._log = logs.append  # type: ignore[method-assign]

    def raise_recovery_error(*, context: str = "") -> None:
        raise RuntimeError("meditation failed")

    task.recover_health_if_needed = raise_recovery_error  # type: ignore[method-assign]
    assert not task.check_runtime_status("health")
    assert logs == ["状态检测血量恢复失败：meditation failed"]

    def raise_stop(*, context: str = "") -> None:
        raise StepStopException("Stop requested")

    task.recover_health_if_needed = raise_stop  # type: ignore[method-assign]
    with pytest.raises(StepStopException):
        task.check_runtime_status("health")


def test_check_runtime_status_health_unknown_is_accepted_by_existing_recovery() -> None:
    task = _RuntimeStatusTask()
    contexts: list[str] = []
    task._log = lambda _message: None  # type: ignore[method-assign]
    task.recover_health_if_needed = (  # type: ignore[method-assign]
        lambda *, context="": contexts.append(context)
    )

    assert task.check_runtime_status("health")
    assert contexts == ["状态检测"]
