from pathlib import Path

import numpy as np

from botCore import GameTask, step
from botCore.execution import DslStepExecutor
from botCore.vision import VisionEngine, load_image
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner
from ymjh_bot.ym_game_task import YmGameTask


class ScriptedEscapeTask(YmGameTask):
    def __init__(
        self,
        *,
        menu_results=None,
        visible_item_results=None,
        item_results=None,
        confirm_results=None,
    ):
        super().__init__()
        self.menu_results = list(menu_results or [])
        self.visible_item_results = list(visible_item_results or [])
        self.item_results = list(item_results or [])
        self.confirm_results = list(confirm_results or [])
        self.wait_find_calls = []
        self.find_calls = []
        self.clicks = []
        self.waits = []
        self.cleanup_calls = []
        self.logs = []

    def wait_find_image_in_roi(
        self,
        template,
        roi,
        *,
        timeout_ms,
        description,
        threshold=0.8,
        interval_ms=500,
    ) -> bool:
        self.wait_find_calls.append(
            (template, roi, timeout_ms, description, threshold, interval_ms)
        )
        if template == [self.BTN_QUICK_MENU_FLOWER, self.BTN_QUICK_MENU_FLOWER_NEW]:
            found = self.menu_results.pop(0) if self.menu_results else False
            center = (55, 664)
        elif template == self.BTN_ESCAPE_STUCK:
            found = self.item_results.pop(0) if self.item_results else False
            center = (296, 508)
        elif template == self.BTN_MODAL_OK:
            found = self.confirm_results.pop(0) if self.confirm_results else False
            center = (854, 508)
        else:
            found = False
            center = None
        self._last_match_center = center if found else None
        return found

    def find_image(self, template, threshold=0.8, roi=None) -> bool:
        self.find_calls.append((template, threshold, roi))
        if template != self.BTN_ESCAPE_STUCK:
            self._last_match_center = None
            return False
        found = self.visible_item_results.pop(0) if self.visible_item_results else False
        self._last_match_center = (296, 508) if found else None
        return found

    def click(self, offset: int = 3) -> None:
        self.clicks.append((self._last_match_center, offset))

    def wait(self, ms) -> None:
        self.waits.append(ms)

    def close_all_panels(self, *args, **kwargs) -> None:
        self.cleanup_calls.append((args, kwargs))

    def _log(self, message: str) -> None:
        self.logs.append(message)


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


class RetryHookTask(GameTask):
    task_name = "重试钩子"

    def __init__(self, *, fail_count: int, hook_error: bool = False):
        super().__init__()
        self.fail_count = fail_count
        self.hook_error = hook_error
        self.run_calls = 0
        self.retry_calls = []
        self.events = []

    def on_start(self) -> None:
        self.events.append("start")

    def before_retry(self, retry_scope, failure=None) -> None:
        self.retry_calls.append((retry_scope, str(failure)))
        self.events.append(f"retry:{retry_scope}")
        if self.hook_error:
            raise RuntimeError("recovery failed")

    @step(retry=0)
    def run_once(self):
        self.run_calls += 1
        self.events.append("run")
        if self.run_calls <= self.fail_count:
            raise RuntimeError("original failure")


def make_queue_runner(task, event_callback=None):
    return TaskQueueRunner(
        [task],
        FakeADB(),  # type: ignore[arg-type]
        FakeVision(),  # type: ignore[arg-type]
        event_callback=event_callback,
    )


def test_escape_stuck_missing_menu_never_clicks_and_cleans_up_once():
    task = ScriptedEscapeTask(menu_results=[False, False])

    assert not task.try_escape_stuck()

    assert task.clicks == []
    assert task.cleanup_calls == [
        ((), {"timeout_ms": task.ESCAPE_STUCK_CLEANUP_TIMEOUT_MS})
    ]
    assert all("未识别到菜单按钮" in log for log in (task.logs[0], task.logs[-1]))


def test_escape_stuck_missing_item_only_clicks_recognized_menu_centers():
    task = ScriptedEscapeTask(
        menu_results=[True, True, True, True],
        visible_item_results=[False, False],
        item_results=[False, False],
    )

    assert not task.try_escape_stuck()

    assert task.clicks == [((55, 664), 0), ((55, 664), 0)]
    assert task.cleanup_calls == [
        ((), {"timeout_ms": task.ESCAPE_STUCK_CLEANUP_TIMEOUT_MS})
    ]
    assert not any(center == (296, 508) for center, _ in task.clicks)


def test_escape_stuck_missing_confirmation_never_clicks_confirm_fallback():
    task = ScriptedEscapeTask(
        menu_results=[True, True, True, True],
        visible_item_results=[False, False],
        item_results=[True, True],
        confirm_results=[False, False],
    )

    assert not task.try_escape_stuck()

    assert task.clicks == [
        ((55, 664), 0),
        ((296, 508), 0),
        ((55, 664), 0),
        ((296, 508), 0),
    ]
    assert not any(center == (854, 508) for center, _ in task.clicks)
    assert len(task.cleanup_calls) == 1


def test_escape_stuck_success_uses_three_template_centers_and_waits_eight_seconds():
    task = ScriptedEscapeTask(
        menu_results=[True, True],
        visible_item_results=[False],
        item_results=[True],
        confirm_results=[True],
    )

    assert task.try_escape_stuck()

    assert task.clicks == [
        ((55, 664), 0),
        ((296, 508), 0),
        ((854, 508), 0),
    ]
    assert task.waits == [task.ESCAPE_STUCK_MENU_OPEN_WAIT_MS, task.ESCAPE_STUCK_COMPLETE_WAIT_MS]
    assert task.cleanup_calls == []


def test_escape_stuck_retries_full_flow_once_after_cleanup():
    task = ScriptedEscapeTask(
        menu_results=[False, True, True],
        visible_item_results=[False],
        item_results=[True],
        confirm_results=[True],
    )

    assert task.try_escape_stuck()

    assert task.clicks == [
        ((55, 664), 0),
        ((296, 508), 0),
        ((854, 508), 0),
    ]
    assert len(task.cleanup_calls) == 1


def test_escape_stuck_recognizes_already_open_item_without_toggling_menu():
    task = ScriptedEscapeTask(
        menu_results=[True],
        visible_item_results=[True],
        confirm_results=[True],
    )

    assert task.try_escape_stuck()

    assert task.clicks == [((296, 508), 0), ((854, 508), 0)]
    assert task.waits == [task.ESCAPE_STUCK_COMPLETE_WAIT_MS]


def test_escape_stuck_templates_match_both_menu_states_and_reject_noise():
    root = Path(__file__).resolve().parents[1]
    templates = root / "src" / "ymjh_bot" / "templates"
    engine = VisionEngine()

    def canvas_with(template_path, x, y):
        rng = np.random.default_rng(20260716)
        canvas = rng.integers(0, 256, (720, 1280, 3), dtype=np.uint8)
        template = load_image(template_path)
        height, width = template.shape[:2]
        canvas[y : y + height, x : x + width] = template
        return canvas

    menu_templates = [
        str(templates / "btn_quick_menu_flower.png"),
        str(templates / "btn_quick_menu_flower_new.png"),
    ]
    for template_name, x, y in (
        ("btn_quick_menu_flower.png", 34, 641),
        ("btn_quick_menu_flower_new.png", 34, 637),
    ):
        result = engine.match_template(
            canvas_with(templates / template_name, x, y),
            menu_templates,
            threshold=YmGameTask.ESCAPE_STUCK_MENU_THRESHOLD,
            roi=YmGameTask.ROI_QUICK_MENU_BUTTON,
        )
        assert result.found

    item_canvas = canvas_with(templates / "btn_escape_stuck.png", 251, 474)
    item_result = engine.match_template(
        item_canvas,
        str(templates / "btn_escape_stuck.png"),
        threshold=YmGameTask.ESCAPE_STUCK_ITEM_THRESHOLD,
        roi=YmGameTask.ROI_ESCAPE_STUCK_ITEM,
    )
    confirm_canvas = canvas_with(templates / "btn_modal_ok.png", 777, 477)
    confirm_result = engine.match_template(
        confirm_canvas,
        str(templates / "btn_modal_ok.png"),
        threshold=YmGameTask.ESCAPE_STUCK_CONFIRM_THRESHOLD,
        roi=YmGameTask.ROI_CENTER_MODAL_OK,
    )
    noise = np.random.default_rng(42).integers(0, 256, (720, 1280, 3), dtype=np.uint8)
    wrong_item_result = engine.match_template(
        noise,
        str(templates / "btn_escape_stuck.png"),
        threshold=YmGameTask.ESCAPE_STUCK_ITEM_THRESHOLD,
        roi=YmGameTask.ROI_ESCAPE_STUCK_ITEM,
    )
    wrong_confirm_result = engine.match_template(
        noise,
        str(templates / "btn_modal_ok.png"),
        threshold=YmGameTask.ESCAPE_STUCK_CONFIRM_THRESHOLD,
        roi=YmGameTask.ROI_CENTER_MODAL_OK,
    )

    assert item_result.found
    assert confirm_result.found
    assert not wrong_item_result.found
    assert not wrong_confirm_result.found


def test_step_retry_calls_hook_only_before_an_actual_retry(monkeypatch):
    monkeypatch.setattr("botCore.execution.time.sleep", lambda _: None)
    task = RetryHookTask(fail_count=1)
    executor = DslStepExecutor(should_stop=lambda: False, emit=lambda _: None)

    result = executor.execute(task, "run_once", RetryHookTask.run_once, {"retry": 1})

    assert result.success
    assert task.events == ["run", "retry:step", "run"]
    assert task.retry_calls == [("step", "original failure")]


def test_step_final_failure_and_normal_success_do_not_call_retry_hook(monkeypatch):
    monkeypatch.setattr("botCore.execution.time.sleep", lambda _: None)
    executor = DslStepExecutor(should_stop=lambda: False, emit=lambda _: None)
    failing = RetryHookTask(fail_count=1)
    successful = RetryHookTask(fail_count=0)

    failed_result = executor.execute(failing, "run_once", RetryHookTask.run_once, {"retry": 0})
    success_result = executor.execute(successful, "run_once", RetryHookTask.run_once, {"retry": 1})

    assert not failed_result.success
    assert success_result.success
    assert failing.retry_calls == []
    assert successful.retry_calls == []


def test_step_retry_recovery_error_preserves_original_failure(monkeypatch):
    monkeypatch.setattr("botCore.execution.time.sleep", lambda _: None)
    messages = []
    task = RetryHookTask(fail_count=2, hook_error=True)
    executor = DslStepExecutor(should_stop=lambda: False, emit=messages.append)

    result = executor.execute(task, "run_once", RetryHookTask.run_once, {"retry": 1})

    assert not result.success
    assert result.reason == "original failure"
    assert any("Retry recovery error: recovery failed" in message for message in messages)


def test_whole_task_retry_calls_hook_before_restarting_from_task_start():
    task = RetryHookTask(fail_count=1)
    runner = make_queue_runner(task)

    results = runner.run()

    assert [result.success for result in results] == [False, True]
    assert task.events == ["start", "run", "retry:task", "start", "run"]
    assert task.retry_calls == [("task", "任务 重试钩子 步骤 run_once 执行失败：original failure")]


def test_normal_whole_task_never_calls_retry_hook():
    task = RetryHookTask(fail_count=0)
    runner = make_queue_runner(task)

    results = runner.run()

    assert [result.success for result in results] == [True]
    assert task.retry_calls == []


def test_whole_task_retry_recovery_error_does_not_replace_task_failure():
    messages = []
    task = RetryHookTask(fail_count=3, hook_error=True)
    runner = make_queue_runner(task, messages.append)

    results = runner.run()

    assert [result.reason for result in results] == ["original failure"] * 3
    assert task.retry_calls == [
        ("task", "任务 重试钩子 步骤 run_once 执行失败：original failure"),
        ("task", "任务 重试钩子 步骤 run_once 执行失败：original failure"),
    ]
    assert sum("异常重试前恢复失败，仍继续重试" in message for message in messages) == 2
