from __future__ import annotations

import pytest

from botCore import GameTask, StepStopException, step
from botCore.execution import DslStepExecutor
from ymjh_bot.runner.account_role_switcher import AccountRoleSwitcher
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner
from ymjh_bot.task.BPRW_task import BPRWTask
from ymjh_bot.task.CGSS_task import CGSSTask
from ymjh_bot.task.HSLJ_task import HSLJTask
from ymjh_bot.task.JHXS_task import JHXSTask
from ymjh_bot.task.JHYXB_task import JHYXBTask
from ymjh_bot.task.JYPY_task import JYPYTask
from ymjh_bot.task.KYRW_task import KYRWTask
from ymjh_bot.task.MKSY_task import MKSYTask
from ymjh_bot.task.MRYG_task import MRYGTask
from ymjh_bot.task.PZSY_task import PZSYTask
from ymjh_bot.task.QDYX_task import StartTask
from ymjh_bot.task.RCFB_task import RCFBTask
from ymjh_bot.task.SHRW_task import SHRWTask
from ymjh_bot.task.XSRW_task import XSRWTask
from ymjh_bot.task.ZGWX_task import ZGWXTask
from ymjh_bot.ym_game_task import YmGameTask


class _HealthTask(YmGameTask):
    task_name = "血量测试"


class _RetryTask(GameTask):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []

    @step(retry=1, timeout_ms=None)
    def fail_once_per_attempt(self) -> None:
        self.events.append("step")
        raise RuntimeError("step failed")

    def before_retry(
        self,
        retry_scope: str,
        failure: Exception | str | None = None,
    ) -> None:
        self.events.append(f"before:{retry_scope}")

    def after_retry_recovery(
        self,
        retry_scope: str,
        failure: Exception | str | None = None,
    ) -> None:
        self.events.append(f"after:{retry_scope}")


class _CustomYmRetryTask(_HealthTask):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []

    @step(retry=1, timeout_ms=None)
    def fail_once_per_attempt(self) -> None:
        self.events.append("step")
        raise RuntimeError("step failed")

    def before_retry(
        self,
        retry_scope: str,
        failure: Exception | str | None = None,
    ) -> None:
        self.events.append(f"custom-before:{retry_scope}")

    def _run_health_precheck(self, context: str) -> None:
        self.events.append(f"health:{context}")


def _health_task_with_ratio(
    ratio: float | None,
) -> tuple[_HealthTask, list[str]]:
    task = _HealthTask()
    logs: list[str] = []
    task._log = logs.append  # type: ignore[method-assign]
    task.collapse_chat_if_open = lambda: None  # type: ignore[method-assign]
    task.find_image = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    task.detect_health_ratio = lambda: ratio  # type: ignore[method-assign]
    return task, logs


def test_all_visible_queue_tasks_enable_health_recovery_by_default() -> None:
    queue_task_classes = (
        BPRWTask,
        CGSSTask,
        HSLJTask,
        JHXSTask,
        JHYXBTask,
        JYPYTask,
        KYRWTask,
        MKSYTask,
        MRYGTask,
        PZSYTask,
        StartTask,
        RCFBTask,
        SHRWTask,
        XSRWTask,
        ZGWXTask,
    )

    assert all(task_class.auto_recover_health for task_class in queue_task_classes)
    assert not AccountRoleSwitcher.auto_recover_health


def test_task_start_runs_one_health_precheck_but_steps_do_not() -> None:
    task = _HealthTask()
    precheck_contexts: list[str] = []
    task._log = lambda _message: None  # type: ignore[method-assign]
    task.close_all_panels = lambda *args, **kwargs: None  # type: ignore[method-assign]
    task.after_startup_panel_close = lambda: None  # type: ignore[method-assign]
    task.wake_from_power_saving_if_needed = lambda: False  # type: ignore[method-assign]
    task._run_health_precheck = precheck_contexts.append  # type: ignore[method-assign]

    task.on_start()
    task.before_step("anything", {})

    assert precheck_contexts == ["任务启动"]


def test_health_precheck_logs_normal_and_unrecognized_health_without_meditation() -> None:
    healthy_task, healthy_logs = _health_task_with_ratio(0.9)
    healthy_task.recover_health_if_needed(context="任务启动")

    assert healthy_logs == ["任务启动：血量正常：90.0%"]

    unknown_task, unknown_logs = _health_task_with_ratio(None)
    unknown_task.click = lambda *_args, **_kwargs: pytest.fail("不应开始打坐")  # type: ignore[method-assign]
    unknown_task.recover_health_if_needed(context="步骤重试")

    assert unknown_logs == ["步骤重试：血量无法识别，跳过自动打坐"]


def test_low_health_uses_existing_meditation_flow() -> None:
    task, logs = _health_task_with_ratio(0.5)
    clicks: list[str] = []
    task.click = lambda *_args, **_kwargs: clicks.append("emotion")  # type: ignore[method-assign]
    task.click_point = lambda *_args, **_kwargs: clicks.append("point")  # type: ignore[method-assign]
    task.wait = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    task.click_template_if_available = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    task.wait_health_full = lambda: True  # type: ignore[method-assign]
    task.collapse_emotion_panel_if_open = lambda **_kwargs: None  # type: ignore[method-assign]

    task.recover_health_if_needed(context="任务启动")

    assert clicks == ["emotion", "point", "point"]
    assert "任务启动：检测到血量较低：50.0%，开始打坐恢复" in logs
    assert logs[-1] == "血量已回满，退出打坐"


def test_health_precheck_swallows_failures_but_preserves_user_stop() -> None:
    task = _HealthTask()
    logs: list[str] = []
    task._log = logs.append  # type: ignore[method-assign]

    def raise_recovery_error(*, context: str = "") -> None:
        raise RuntimeError("meditation unavailable")

    task.recover_health_if_needed = raise_recovery_error  # type: ignore[method-assign]
    task._run_health_precheck("任务重试")

    assert logs == ["任务重试血量预检异常，跳过并继续执行：meditation unavailable"]

    def raise_stop(*, context: str = "") -> None:
        raise StepStopException()

    task.recover_health_if_needed = raise_stop  # type: ignore[method-assign]
    with pytest.raises(StepStopException):
        task._run_health_precheck("任务重试")


def test_health_recovery_timeout_reports_failure_without_blocking_the_task() -> None:
    task = _HealthTask()
    logs: list[str] = []
    task._log = logs.append  # type: ignore[method-assign]
    task._is_deadline_expired = lambda _deadline: True  # type: ignore[method-assign]

    assert not task.wait_health_full()
    assert logs == ["打坐回血超时，停止回血并继续任务"]


def test_step_retry_runs_post_recovery_hook_after_the_existing_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("botCore.execution.time.sleep", lambda _seconds: None)
    task = _RetryTask()
    executor = DslStepExecutor(should_stop=lambda: False, emit=lambda _message: None)

    result = executor.execute(
        task,
        "fail_once_per_attempt",
        _RetryTask.fail_once_per_attempt,
        _RetryTask.fail_once_per_attempt._step_meta,
    )

    assert not result.success
    assert task.events == ["step", "before:step", "after:step", "step"]


def test_step_retry_keeps_health_checks_when_a_ym_task_overrides_before_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("botCore.execution.time.sleep", lambda _seconds: None)
    task = _CustomYmRetryTask()
    executor = DslStepExecutor(should_stop=lambda: False, emit=lambda _message: None)

    executor.execute(
        task,
        "fail_once_per_attempt",
        _CustomYmRetryTask.fail_once_per_attempt,
        _CustomYmRetryTask.fail_once_per_attempt._step_meta,
    )

    assert task.events == [
        "step",
        "custom-before:step",
        "health:步骤重试",
        "step",
    ]


def test_task_retry_runs_post_recovery_hook_and_cleanup_recovery_does_not() -> None:
    task = _RetryTask()
    runner = TaskQueueRunner([task], object(), object())

    runner._run_before_retry_hook(task, "task failed")
    assert task.events == ["before:task", "after:task"]

    task.events.clear()
    runner._run_before_retry_hook(
        task,
        "cleanup failed",
        run_post_recovery_hook=False,
    )
    assert task.events == ["before:task"]
