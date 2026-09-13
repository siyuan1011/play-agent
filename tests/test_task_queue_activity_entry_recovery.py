from __future__ import annotations

from botCore import GameTask
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner, TaskRunStatus


class _ActivityEntryFailureTask(GameTask):
    task_name = "活动入口恢复测试"

    def __init__(self, failures: list[bool], *, recovery_raises: bool = False) -> None:
        super().__init__()
        self.failures = failures
        self.recovered = False
        self.recovery_raises = recovery_raises
        self.recovery_calls: list[str] = []

    def consume_activity_entry_failure(self) -> bool:
        return self.failures.pop(0)

    def can_recover_activity_entry_failure(self) -> bool:
        return not self.recovered

    def recover_activity_entry_failure(self, failure: str) -> None:
        self.recovery_calls.append(failure)
        self.recovered = True
        if self.recovery_raises:
            raise RuntimeError("restart failed")


def _runner(task: GameTask) -> TaskQueueRunner:
    runner = TaskQueueRunner([task], None, None)  # type: ignore[arg-type]
    runner._run_single_task = lambda _task: ([], False)  # type: ignore[method-assign]
    return runner


def test_activity_entry_failure_restarts_once_then_marks_second_failure_exhausted() -> None:
    task = _ActivityEntryFailureTask([True, True])
    runner = _runner(task)

    _, status = runner._run_task_with_retries(task)

    assert status is TaskRunStatus.RETRY_EXHAUSTED
    assert len(task.recovery_calls) == 1


def test_activity_entry_failure_at_normal_retry_limit_still_gets_one_full_retry() -> None:
    task = _ActivityEntryFailureTask([False, False, True, True])
    runner = _runner(task)

    _, status = runner._run_task_with_retries(task)

    assert status is TaskRunStatus.RETRY_EXHAUSTED
    assert len(task.recovery_calls) == 1


def test_failed_activity_entry_recovery_stops_queue_instead_of_retrying_normally() -> None:
    task = _ActivityEntryFailureTask([True], recovery_raises=True)
    runner = _runner(task)

    _, status = runner._run_task_with_retries(task)

    assert status is TaskRunStatus.RECOVERY_FAILED
    assert len(task.recovery_calls) == 1
