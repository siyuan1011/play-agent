import pytest

from botCore import load_task_class
from botCore.task import StepJumpException
from ymjh_bot.task.ZGWX_task import ZGWXTask


class FakeZGWXTask(ZGWXTask):
    def __init__(
        self,
        *,
        roi_results: list[bool] | None = None,
        image_results: list[bool] | None = None,
        missing_results: list[bool] | None = None,
        power_saving_results: list[bool] | None = None,
    ):
        super().__init__()
        self.roi_results = roi_results or []
        self.image_results = image_results or []
        self.missing_results = missing_results or []
        self.power_saving_results = power_saving_results or []
        self.roi_calls = []
        self.image_calls = []
        self.missing_calls = []
        self.panel_calls = []
        self.click_count = 0
        self.wait_calls = []
        self.logs = []
        self.wake_calls = 0

    def wait_find_image_in_roi(
        self,
        template,
        roi,
        *,
        timeout_ms,
        description,
        threshold=0.8,
        interval_ms=500,
    ):
        self.roi_calls.append((template, roi, timeout_ms, description, threshold, interval_ms))
        return self.roi_results.pop(0)

    def close_all_panels(self, templates=None, *, timeout_ms=5000, wait_after_click_ms=500) -> None:
        self.panel_calls.append(("close_all_panels", templates, timeout_ms, wait_after_click_ms))

    def open_activity_panel(
        self,
        category=None,
        category_name=None,
        *,
        timeout_ms=30000,
        wait_after_open_ms=2000,
        wait_after_category_ms=0,
    ) -> None:
        self.panel_calls.append(
            (
                "open_activity_panel",
                category,
                category_name,
                timeout_ms,
                wait_after_open_ms,
                wait_after_category_ms,
            )
        )

    def wake_from_power_saving_if_needed(self) -> bool:
        self.wake_calls += 1
        return self.power_saving_results.pop(0) if self.power_saving_results else False

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.image_calls.append((template, timeout_ms, threshold, interval_ms))
        return self.image_results.pop(0)

    def wait_image_missing(
        self,
        template,
        timeout_ms=10000,
        threshold=0.8,
        missing_threshold=3,
        callback=None,
        interval_ms=500,
    ):
        self.missing_calls.append((template, timeout_ms, threshold, missing_threshold, interval_ms))
        return self.missing_results.pop(0)

    def click(self, offset: int = 3) -> None:
        self.click_count += 1

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_zgwx_task_loads_with_expected_metadata():
    task_cls = load_task_class("src/ymjh_bot/task/ZGWX_task.py")

    assert task_cls.__name__ == "ZGWXTask"
    assert task_cls.task_key == "ZGWX"
    assert task_cls.task_name == "坐观万象"


def test_zgwx_task_steps_follow_planned_order():
    assert [name for name, _, _ in ZGWXTask.get_steps()] == [
        "open_youli_activity",
        "wait_meditation_start",
        "wait_meditation_complete",
        "verify_completion",
    ]


def test_zgwx_task_disables_health_recovery_guard():
    assert ZGWXTask.auto_recover_health is False


def test_on_start_wakes_power_saving_and_cleans_again():
    task = FakeZGWXTask(power_saving_results=[True])

    task.on_start()

    assert task.panel_calls == [
        ("close_all_panels", None, 5000, 500),
        ("close_all_panels", None, 5000, 500),
    ]
    assert task.wake_calls == 1
    assert task.wait_calls == [1000]


def test_open_youli_activity_clicks_zgwx_forward_button():
    task = FakeZGWXTask(roi_results=[True])

    task.open_youli_activity()

    assert task.panel_calls == [
        (
            "open_activity_panel",
            "游历",
            None,
            30000,
            2000,
            2000,
        )
    ]
    assert task.roi_calls == [
        (
            task.BTN_ACTIVITY_FORWARD,
            task.ROI_ZGWX_FORWARD,
            3000,
            "活动页坐观万象前往按钮",
            task.FORWARD_THRESHOLD,
            500,
        )
    ]
    assert task.click_count == 1
    assert task.wait_calls == [1500]


def test_open_youli_activity_jumps_to_verify_when_forward_missing():
    task = FakeZGWXTask(roi_results=[False])

    with pytest.raises(StepJumpException) as exc_info:
        task.open_youli_activity()

    assert exc_info.value.target == "verify_completion"
    assert task.click_count == 0
    assert "未找到坐观万象前往按钮，默认当前不可接取或已完成" in task.logs


def test_wait_meditation_start_waits_for_countdown_template():
    task = FakeZGWXTask(image_results=[True])

    task.wait_meditation_start()

    assert task.image_calls == [
        (
            task.ICON_MEDITATING,
            180000,
            0.9,
            5000,
        )
    ]
    assert "检测到修炼中倒计时，坐观万象开始修炼" in task.logs


def test_wait_meditation_start_raises_when_countdown_missing():
    task = FakeZGWXTask(image_results=[False])

    with pytest.raises(RuntimeError, match="坐观万象修炼开始等待超时"):
        task.wait_meditation_start()


def test_wait_meditation_complete_uses_stable_missing_threshold():
    task = FakeZGWXTask(missing_results=[True])

    task.wait_meditation_complete()

    assert task.missing_calls == [
        (
            task.ICON_MEDITATING,
            900000,
            0.9,
            3,
            5000,
        )
    ]
    assert "检测到修炼中倒计时消失，坐观万象修炼结束" in task.logs


def test_wait_meditation_complete_raises_when_countdown_remains():
    task = FakeZGWXTask(missing_results=[False])

    with pytest.raises(RuntimeError, match="坐观万象修炼完成等待超时"):
        task.wait_meditation_complete()


def test_verify_completion_accepts_missing_forward_button():
    task = FakeZGWXTask(roi_results=[False])

    task.verify_completion()

    assert task.panel_calls == [
        ("close_all_panels", None, 5000, 500),
        (
            "open_activity_panel",
            "游历",
            None,
            30000,
            2000,
            2000,
        ),
    ]
    assert task.click_count == 0
    assert "完成验证：活动页已无坐观万象前往按钮" in task.logs


def test_verify_completion_raises_when_forward_button_remains():
    task = FakeZGWXTask(roi_results=[True])

    with pytest.raises(RuntimeError, match="坐观万象完成验证失败"):
        task.verify_completion()
