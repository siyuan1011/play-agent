import threading
import time

import numpy as np

from botCore import GameTask, StepStopException, step
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
        self.on_start_calls = 0

    def on_start(self):
        self.on_start_calls += 1

    @step(retry=0)
    def wait_until_paused(self):
        self.entered.set()
        self.wait(1000)


class FailingTask(GameTask):
    def __init__(self):
        super().__init__()
        self.calls = 0

    @step(retry=0)
    def fail(self):
        self.calls += 1
        raise RuntimeError("boom")


class RetryThenSucceedTask(GameTask):
    def __init__(self):
        super().__init__()
        self.before_start_calls = 0
        self.on_start_calls = 0
        self.calls = []

    def before_start(self):
        self.before_start_calls += 1
        self.calls.append("before_start")

    def on_start(self):
        self.on_start_calls += 1
        self.calls.append("on_start")

    @step(retry=0)
    def first(self):
        self.calls.append("first")
        if self.on_start_calls < 3:
            raise RuntimeError("retry me")

    @step(retry=0)
    def second(self):
        self.calls.append("second")


class LifecycleFailureTask(GameTask):
    def __init__(self, failing_hook):
        super().__init__()
        self.failing_hook = failing_hook
        self.before_start_calls = 0
        self.on_start_calls = 0
        self.step_calls = 0
        self.on_finish_calls = 0

    def before_start(self):
        self.before_start_calls += 1
        if self.failing_hook == "before_start" and self.before_start_calls < 3:
            raise RuntimeError("before start failed")

    def on_start(self):
        self.on_start_calls += 1
        if self.failing_hook == "on_start" and self.on_start_calls < 3:
            raise RuntimeError("on start failed")

    @step(retry=0)
    def run_once(self):
        self.step_calls += 1
        if self.failing_hook == "step" and self.step_calls < 3:
            raise RuntimeError("step failed")

    def on_finish(self, results):
        self.on_finish_calls += 1
        if self.failing_hook == "on_finish" and self.on_finish_calls < 3:
            raise RuntimeError("finish failed")


class StepRetryExhaustionTask(GameTask):
    def __init__(self):
        super().__init__()
        self.on_start_calls = 0
        self.step_calls = 0

    def on_start(self):
        self.on_start_calls += 1

    @step(retry=1)
    def fail_after_step_retries(self):
        self.step_calls += 1
        raise RuntimeError("retry exhausted")


class SavedProgressRetryTask(GameTask):
    def __init__(self):
        super().__init__()
        self.on_start_calls = 0
        self.calls = []

    def on_start(self):
        self.on_start_calls += 1

    @step(retry=0)
    def first(self):
        self.calls.append("first")

    @step(retry=0)
    def second(self):
        self.calls.append("second")
        if self.on_start_calls == 1:
            raise RuntimeError("saved progress retry")


class PauseResumeTask(GameTask):
    def __init__(self):
        super().__init__()
        self.entered = threading.Event()
        self.pause_observed = threading.Event()
        self.on_start_calls = 0
        self.step_calls = 0

    def on_start(self):
        self.on_start_calls += 1

    @step(retry=0)
    def wait_once(self):
        self.step_calls += 1
        if self.step_calls == 1:
            self.entered.set()
            while not self.is_stopped():
                time.sleep(0.005)
            self.pause_observed.set()
            raise StepStopException("Pause requested")


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
    assert task.on_start_calls == 1


def test_queue_runner_retries_failed_task_then_continues_to_next_task():
    retry_task = RetryThenSucceedTask()
    next_task = LinearTask()
    runner = TaskQueueRunner(
        [retry_task, next_task],
        FakeADB(),  # type: ignore[arg-type]
        FakeVision(),  # type: ignore[arg-type]
    )

    results = runner.run()

    assert [result.success for result in results] == [False, False, True, True, True, True]
    assert retry_task.before_start_calls == 3
    assert retry_task.on_start_calls == 3
    assert retry_task.calls == [
        "before_start",
        "on_start",
        "first",
        "before_start",
        "on_start",
        "first",
        "before_start",
        "on_start",
        "first",
        "second",
    ]
    assert next_task.calls == ["first", "second"]
    assert runner.get_progress() == {"current_task_index": 2, "current_step_index": 0}


def test_queue_runner_skips_task_after_three_failed_attempts():
    failing_task = FailingTask()
    next_task = LinearTask()
    runner = TaskQueueRunner(
        [failing_task, next_task],
        FakeADB(),  # type: ignore[arg-type]
        FakeVision(),  # type: ignore[arg-type]
    )

    results = runner.run()

    assert [result.success for result in results] == [False, False, False, True, True]
    assert failing_task.calls == 3
    assert runner.get_progress() == {"current_task_index": 2, "current_step_index": 0}
    assert next_task.calls == ["first", "second"]


def test_queue_runner_retries_lifecycle_failures():
    expected_calls = {
        "before_start": (3, 1, 1, 1),
        "on_start": (3, 3, 1, 1),
        "step": (3, 3, 3, 1),
        "on_finish": (3, 3, 3, 3),
    }

    for failing_hook, calls in expected_calls.items():
        task = LifecycleFailureTask(failing_hook)
        runner = make_runner(task)

        results = runner.run()

        assert (
            task.before_start_calls,
            task.on_start_calls,
            task.step_calls,
            task.on_finish_calls,
        ) == calls
        assert runner.get_progress() == {"current_task_index": 1, "current_step_index": 0}
        if failing_hook == "step":
            assert [result.success for result in results] == [False, False, True]
        else:
            assert [result.success for result in results] == [True] * task.step_calls


def test_queue_runner_retries_task_only_after_step_retries_are_exhausted(monkeypatch):
    monkeypatch.setattr("botCore.execution.time.sleep", lambda _: None)
    task = StepRetryExhaustionTask()
    runner = make_runner(task)

    results = runner.run()

    assert [result.success for result in results] == [False, False, False]
    assert task.on_start_calls == 3
    assert task.step_calls == 6
    assert runner.get_progress() == {"current_task_index": 1, "current_step_index": 0}


def test_queue_runner_retry_restarts_from_step_zero_after_saved_progress_failure():
    snapshots = []
    task = SavedProgressRetryTask()
    runner = make_runner(task, lambda progress: snapshots.append(progress.copy()))

    runner.load_progress({"current_task_index": 0, "current_step_index": 1})
    results = runner.run()

    assert [result.success for result in results] == [False, True, True]
    assert task.calls == ["second", "first", "second"]
    assert task.on_start_calls == 2
    saved_step = snapshots.index({"current_task_index": 0, "current_step_index": 1})
    assert {"current_task_index": 0, "current_step_index": 0} in snapshots[saved_step + 1 :]
    assert runner.get_progress() == {"current_task_index": 1, "current_step_index": 0}


def test_queue_runner_pause_resume_keeps_current_task_attempt():
    task = PauseResumeTask()
    runner = make_runner(task)
    thread = threading.Thread(target=runner.run)

    thread.start()
    assert task.entered.wait(timeout=1.0)
    runner.pause()
    assert task.pause_observed.wait(timeout=1.0)
    runner.resume()
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert task.on_start_calls == 1
    assert task.step_calls == 2
    assert runner.get_progress() == {"current_task_index": 1, "current_step_index": 0}
