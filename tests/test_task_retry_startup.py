from __future__ import annotations

from botCore import GameTask, step
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner, TaskRunStatus


class _StepRetryTask(GameTask):
    task_name = "步骤重试启动测试"

    def __init__(self) -> None:
        super().__init__()
        self.start_count = 0
        self.step_count = 0

    def on_start(self) -> None:
        self.start_count += 1

    @step(retry=1, timeout_ms=None)
    def fail_once(self) -> None:
        self.step_count += 1
        if self.step_count == 1:
            raise RuntimeError("首次步骤执行失败")


class _FullRetryTask(GameTask):
    task_name = "完整重试启动测试"

    def __init__(self) -> None:
        super().__init__()
        self.start_count = 0
        self.step_count = 0

    def on_start(self) -> None:
        self.start_count += 1

    @step(retry=0, timeout_ms=None)
    def fail_first_attempt(self) -> None:
        self.step_count += 1
        if self.step_count == 1:
            raise RuntimeError("首次完整任务执行失败")


def test_step_retry_does_not_repeat_on_start() -> None:
    task = _StepRetryTask()
    runner = TaskQueueRunner([task], None, None)  # type: ignore[arg-type]

    _, status = runner._run_task_with_retries(task)

    assert status is TaskRunStatus.COMPLETED
    assert task.start_count == 1
    assert task.step_count == 2


def test_full_task_retry_repeats_on_start() -> None:
    task = _FullRetryTask()
    runner = TaskQueueRunner([task], None, None)  # type: ignore[arg-type]

    _, status = runner._run_task_with_retries(task)

    assert status is TaskRunStatus.COMPLETED
    assert task.start_count == 2
    assert task.step_count == 2
