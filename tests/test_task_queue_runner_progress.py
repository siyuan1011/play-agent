import threading
import time

import numpy as np
import pytest

from botCore import GameTask, step
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner


class FakeADB:
    serial = "fake"

    def ensure_device(self):
        return None

    def get_screen_size(self):
        return 1280, 720

    def screenshot(self):
        return np.zeros((720, 1280, 3), dtype=np.uint8)


class FakeVision:
    pass


class LinearTask(GameTask):
    def __init__(self):
        super().__init__()
        self.calls = []

    @step(retry=0)
    def first(self):
        self.calls.append("first")

    @step(retry=0)
    def second(self):
        self.calls.append("second")


class WaitingTask(GameTask):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()

    @step(retry=0)
    def wait_until_paused(self):
        self.entered.set()
        self.wait(1000)


class FailingTask(GameTask):
    @step(retry=0)
    def fail(self):
        raise RuntimeError("boom")


def make_runner(task, progress_callback=None):
    return TaskQueueRunner(
        [task],
        FakeADB(),  # type: ignore[arg-type]
        FakeVision(),  # type: ignore[arg-type]
        progress_callback=progress_callback,
    )


def test_queue_runner_load_progress_resumes_from_saved_step():
    task = LinearTask()
    runner = make_runner(task)

    runner.load_progress({"current_task_index": 0, "current_step_index": 1})
    results = runner.run()

    assert [r.success for r in results] == [True]
    assert task.calls == ["second"]
    assert runner.get_progress() == {"current_task_index": 1, "current_step_index": 0}


def test_queue_runner_emits_progress_before_steps():
    snapshots = []
    task = LinearTask()
    runner = make_runner(task, lambda progress: snapshots.append(progress.copy()))

    runner.run()

    assert {"current_task_index": 0, "current_step_index": 0} in snapshots
    assert {"current_task_index": 0, "current_step_index": 1} in snapshots
    assert snapshots[-1] == {"current_task_index": 1, "current_step_index": 0}


def test_queue_runner_pause_keeps_current_progress():
    task = WaitingTask()
    runner = make_runner(task)
    thread = threading.Thread(target=runner.run)

    thread.start()
    assert task.entered.wait(timeout=1.0)
    runner.pause()
    time.sleep(0.05)

    assert runner.get_progress() == {"current_task_index": 0, "current_step_index": 0}

    runner.stop()
    thread.join(timeout=1.0)
    assert not thread.is_alive()


def test_queue_runner_stops_on_failed_step_without_advancing_task():
    failing_task = FailingTask()
    next_task = LinearTask()
    runner = TaskQueueRunner(
        [failing_task, next_task],
        FakeADB(),  # type: ignore[arg-type]
        FakeVision(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="任务 .* 步骤 fail 执行失败：boom"):
        runner.run()

    assert runner.get_progress() == {"current_task_index": 0, "current_step_index": 0}
    assert next_task.calls == []
