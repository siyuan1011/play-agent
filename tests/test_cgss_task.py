import pytest

from botCore import StepJumpException
from ymjh_bot.task.CGSS_task import CGSSTask


class FakeCGSSTask(CGSSTask):
    def __init__(
        self,
        *,
        image_results: list[bool] | None = None,
        missing_results: list[bool] | None = None,
        roi_results: list[bool] | None = None,
        find_results: list[bool] | None = None,
    ):
        super().__init__()
        self.image_results = image_results or []
        self.missing_results = missing_results or []
        self.roi_results = roi_results or []
        self.find_results = find_results or []
        self.image_calls = []
        self.missing_calls = []
        self.roi_calls = []
        self.find_calls = []
        self.click_count = 0
        self.clicked_points = []
        self.wait_calls = []
        self.panel_calls = []
        self.logs = []

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.image_calls.append((template, timeout_ms, threshold))
        result = self.image_results.pop(0)
        if callback:
            callback(result)
        return result

    def wait_image_missing(
        self,
        template,
        timeout_ms=10000,
        threshold=0.8,
        missing_threshold=3,
        callback=None,
        interval_ms=500,
    ):
        self.missing_calls.append((template, timeout_ms, threshold, missing_threshold))
        result = self.missing_results.pop(0)
        if callback:
            callback(True, 0)
        return result

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

    def find_image(self, template, threshold=0.8, roi=None) -> bool:
        self.find_calls.append((template, threshold, roi))
        return self.find_results.pop(0)

    def click(self, offset: int = 3) -> None:
        self.click_count += 1

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

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

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_chaguan_step_order_includes_completion_verification():
    steps = [name for name, _, _ in CGSSTask.get_steps()]

    assert steps == [
        "open_huodong",
        "auto_pathfinding",
        "enter_chaguan",
        "click_answer",
        "exit_chaguan",
        "verify_completion",
    ]


def test_chaguan_task_disables_health_recovery_guard():
    assert CGSSTask.auto_recover_health is False


def test_chaguan_answer_point_uses_right_answer_option_area():
    assert CGSSTask.POINT_ANSWER == (1232, 540)
    assert CGSSTask.ANSWER_CLICK_INTERVAL_MS == 3000


def test_chaguan_answer_step_has_no_timeout_limit():
    steps = {name: meta for name, _, meta in CGSSTask.get_steps()}

    assert steps["click_answer"]["timeout_ms"] is None


def test_open_huodong_clicks_chaguan_entry_from_activity_card():
    task = FakeCGSSTask(roi_results=[True])

    task.open_huodong()

    assert task.panel_calls == [
        ("open_activity_panel", "江湖", None, 30000, 2000, 2000),
    ]
    assert task.roi_calls == [
        (
            task.BTN_CHAGUANSHUOSHU_ENTRY,
            task.ROI_CHAGUANSHUOSHU_ENTRY,
            3000,
            "活动页茶馆说书入口",
            0.8,
            500,
        ),
    ]
    assert task.image_calls == []
    assert task.click_count == 1
    assert task.clicked_points == []
    assert task.wait_calls == [1500]


def test_open_huodong_jumps_to_end_when_chaguan_entry_is_missing():
    task = FakeCGSSTask(roi_results=[False])

    with pytest.raises(StepJumpException) as exc_info:
        task.open_huodong()

    assert exc_info.value.target == StepJumpException.JUMP_TO_END
    assert task.image_calls == []
    assert task.click_count == 0
    assert "未找到茶馆说书入口，默认茶馆说书当前不可接取或已完成" in task.logs


def test_enter_chaguan_raises_when_entry_button_is_missing():
    task = FakeCGSSTask(image_results=[False])

    with pytest.raises(RuntimeError, match="未找到进入茶馆按钮"):
        task.enter_chaguan()

    assert task.image_calls == [(task.BTN_JRCG, 30000, 0.8)]
    assert task.missing_calls == []
    assert task.click_count == 0


def test_enter_chaguan_clicks_entry_button_until_missing():
    task = FakeCGSSTask(image_results=[True], missing_results=[True])

    task.enter_chaguan()

    assert task.missing_calls == [(task.BTN_JRCG, 30000, 0.8, 3)]
    assert task.click_count == 1
    assert task.clicked_points == [(task.POINT_SEAT[0], task.POINT_SEAT[1], 3)]
    assert task.wait_calls == [1000, 1000]
    assert "已尝试点击茶馆入座" in task.logs


def test_enter_chaguan_raises_when_entry_button_stays_visible():
    task = FakeCGSSTask(image_results=[True], missing_results=[False])

    with pytest.raises(RuntimeError, match="进入茶馆按钮未消失"):
        task.enter_chaguan()

    assert task.click_count == 1


def test_click_answer_keeps_polling_third_option_until_exit_button_appears():
    task = FakeCGSSTask(find_results=[False, False, False, False, False, True])

    task.click_answer()

    assert task.clicked_points == [
        (task.POINT_ANSWER[0], task.POINT_ANSWER[1], 3),
        (task.POINT_ANSWER[0], task.POINT_ANSWER[1], 3),
        (task.POINT_ANSWER[0], task.POINT_ANSWER[1], 3),
        (task.POINT_ANSWER[0], task.POINT_ANSWER[1], 3),
        (task.POINT_ANSWER[0], task.POINT_ANSWER[1], 3),
    ]
    assert task.wait_calls == [task.ANSWER_CLICK_INTERVAL_MS] * 5
    assert task.find_calls == [
        (task.BTN_TCCG, 0.8, None),
        (task.BTN_TCCG, 0.8, None),
        (task.BTN_TCCG, 0.8, None),
        (task.BTN_TCCG, 0.8, None),
        (task.BTN_TCCG, 0.8, None),
        (task.BTN_TCCG, 0.8, None),
    ]
    assert "检测到退出茶馆按钮，停止答题" in task.logs


def test_click_answer_returns_immediately_when_exit_button_is_already_visible():
    task = FakeCGSSTask(find_results=[True])

    task.click_answer()

    assert task.clicked_points == []
    assert task.wait_calls == []
    assert task.find_calls == [(task.BTN_TCCG, 0.8, None)]


def test_exit_chaguan_clicks_exit_button_template():
    task = FakeCGSSTask(image_results=[True])

    task.exit_chaguan()

    assert task.image_calls == [(task.BTN_TCCG, None, 0.8)]
    assert task.click_count == 1
    assert task.clicked_points == []
    assert task.wait_calls == [2000]


def test_verify_completion_accepts_missing_activity_entry():
    task = FakeCGSSTask(roi_results=[False])

    task.verify_completion()

    assert task.panel_calls == [
        ("close_all_panels", None, 5000, 500),
        ("open_activity_panel", "江湖", None, 30000, 2000, 2000),
    ]
    assert task.roi_calls == [
        (
            task.BTN_CHAGUANSHUOSHU_ENTRY,
            task.ROI_CHAGUANSHUOSHU_ENTRY,
            3000,
            "活动页茶馆说书入口",
            0.8,
            500,
        ),
    ]
    assert task.image_calls == []
    assert "完成验证：活动页已无茶馆说书入口" in task.logs


def test_verify_completion_raises_when_activity_entry_remains():
    task = FakeCGSSTask(roi_results=[True])

    with pytest.raises(RuntimeError, match="茶馆说书完成验证失败：活动页仍存在茶馆说书入口"):
        task.verify_completion()
