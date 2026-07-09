import pytest

from botCore import load_task_class
from botCore.task import StepJumpException
from ymjh_bot.task.KYRW_task import KyrwTask


class FakeKyrwTask(KyrwTask):
    def __init__(
        self,
        *,
        click_template_results: list[bool] | None = None,
        find_once_results: list[bool] | None = None,
        find_image_results: list[bool] | None = None,
        course_click_results: list[bool] | None = None,
        route_visible_results: list[bool] | None = None,
        route_open_results: list[bool] | None = None,
        confirm_results: list[bool] | None = None,
        wait_roi_results: list[bool] | None = None,
    ):
        super().__init__()
        self.click_template_results = click_template_results or []
        self.find_once_results = find_once_results or []
        self.find_image_results = find_image_results or []
        self.course_click_results = course_click_results or []
        self.route_visible_results = route_visible_results or []
        self.route_open_results = route_open_results or []
        self.confirm_results = confirm_results or []
        self.wait_roi_results = wait_roi_results or []
        self.click_template_calls = []
        self.find_once_calls = []
        self.find_image_calls = []
        self.course_click_calls = []
        self.close_panel_calls = []
        self.open_activity_calls = []
        self.clicked_points = []
        self.click_count = 0
        self.wait_calls = []
        self.close_transient_calls = 0
        self.logs = []

    def close_all_panels(self, templates=None, *, timeout_ms=5000, wait_after_click_ms=500):
        self.close_panel_calls.append((templates, timeout_ms, wait_after_click_ms))

    def open_activity_panel(
        self,
        category=None,
        category_name=None,
        *,
        timeout_ms=30000,
        wait_after_open_ms=2000,
        wait_after_category_ms=0,
    ) -> None:
        self.open_activity_calls.append(
            (category, category_name, timeout_ms, wait_after_open_ms, wait_after_category_ms)
        )

    def click_course_task_from_sidebar(self, *, max_scrolls: int, required: bool) -> bool:
        self.course_click_calls.append((max_scrolls, required))
        return self.course_click_results.pop(0) if self.course_click_results else False

    def click_template_if_available(
        self,
        template,
        *,
        timeout_ms,
        description,
        threshold=0.8,
        wait_after_click_ms=1000,
        roi=None,
    ):
        self.click_template_calls.append(
            (template, timeout_ms, description, threshold, wait_after_click_ms, roi)
        )
        return self.click_template_results.pop(0) if self.click_template_results else False

    def find_image_once(
        self,
        template,
        *,
        threshold=0.8,
        roi=None,
        log_found=False,
        log_missing=False,
    ):
        self.find_once_calls.append((template, threshold, roi))
        return self.find_once_results.pop(0) if self.find_once_results else False

    def find_image(self, template, threshold=0.8, roi=None) -> bool:
        self.find_image_calls.append((template, threshold, roi))
        return self.find_image_results.pop(0) if self.find_image_results else False

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
        return self.wait_roi_results.pop(0) if self.wait_roi_results else False

    def is_acquire_route_panel_visible(self) -> bool:
        return self.route_visible_results.pop(0) if self.route_visible_results else False

    def ensure_acquire_route_panel_open(self) -> bool:
        return self.route_open_results.pop(0) if self.route_open_results else True

    def confirm_purchase_if_needed(self) -> bool:
        return self.confirm_results.pop(0) if self.confirm_results else True

    def confirm_submit_if_needed(self) -> bool:
        return self.confirm_results.pop(0) if self.confirm_results else True

    def close_transient_panels(self, max_attempts: int = 4) -> bool:
        self.close_transient_calls += 1
        return True

    def click(self, offset: int = 3) -> None:
        self.click_count += 1

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_kyrw_task_loads_with_expected_metadata():
    task_cls = load_task_class("src/ymjh_bot/task/KYRW_task.py")

    assert task_cls.__name__ == "KyrwTask"
    assert task_cls.task_key == "KYRW"
    assert task_cls.task_name == "课业任务"


def test_kyrw_task_steps_follow_planned_order():
    assert [name for name, _, _ in KyrwTask.get_steps()] == [
        "close_all",
        "resume_existing_course",
        "open_wuchan_activity",
        "enter_course_from_wuchan_panel",
        "auto_pathfinding_to_npc",
        "accept_or_open_course_panel",
        "run_course_flow",
        "verify_completion",
    ]


def test_resume_existing_course_clicks_sidebar_task_and_jumps_to_run_flow():
    task = FakeKyrwTask(course_click_results=[True])

    with pytest.raises(StepJumpException) as exc_info:
        task.resume_existing_course()

    assert exc_info.value.target == "run_course_flow"
    assert task.course_click_calls == [(5, False)]
    assert "检测到已布置课业任务，跳过接取流程" in task.logs


def test_course_panel_existing_course_toast_returns_to_run_flow_without_refresh():
    task = FakeKyrwTask(find_once_results=[True, True])

    assert task.try_select_default_course_card()

    assert task.clicked_points == [(task.POINT_COURSE_CARD_DEFAULT[0], task.POINT_COURSE_CARD_DEFAULT[1], 0)]
    assert task.close_panel_calls == [(None, 3000, 500)]
    assert task.course_click_calls == []
    assert "检测到已有当前布置课业，关闭面板后继续执行" in task.logs


def test_refresh_confirm_is_cancelled():
    task = FakeKyrwTask(find_once_results=[True])

    assert task.cancel_refresh_confirm_if_visible()

    assert task.click_count == 1
    assert "检测到课业刷新消耗确认，点击取消" in task.logs


def test_mall_purchase_uses_default_quantity_without_plus_clicks():
    task = FakeKyrwTask(click_template_results=[True])

    assert task.buy_from_mall_default_quantity()

    assert task.click_template_calls == [
        (
            task.BTN_MALL_BUY_AREA,
            5000,
            "商城默认数量购买按钮",
            0.85,
            1500,
            task.ROI_MALL_BUY,
        )
    ]
    assert task.clicked_points == []


def test_stall_route_buys_from_local_stall_when_available():
    task = FakeKyrwTask(click_template_results=[True, True])

    assert task.try_stall_route()

    assert task.click_template_calls == [
        (task.ROUTE_STALL, 800, "摆摊购买路径", 0.8, 2500, task.ROI_ROUTE_PANEL),
        (task.BTN_BUY, 2500, "摆摊购买按钮", task.TRADE_BUY_THRESHOLD, 1500, task.ROI_TRADE_ACTION),
    ]


def test_stall_route_checks_all_server_when_local_stall_has_no_goods():
    task = FakeKyrwTask(click_template_results=[True, False, False, True, True])

    assert task.try_stall_route()

    assert task.click_template_calls == [
        (task.ROUTE_STALL, 800, "摆摊购买路径", 0.8, 2500, task.ROI_ROUTE_PANEL),
        (task.BTN_BUY, 2500, "摆摊购买按钮", task.TRADE_BUY_THRESHOLD, 1500, task.ROI_TRADE_ACTION),
        (task.BTN_BUY, 2500, "摆摊购买按钮", task.TRADE_BUY_THRESHOLD, 1500, task.ROI_TRADE_ACTION),
        (task.BTN_VIEW_ALL_SERVER, 2500, "查看全服按钮", 0.85, 2500, task.ROI_TRADE_ACTION),
        (task.BTN_BUY, 3000, "全服摆摊购买按钮", task.TRADE_BUY_THRESHOLD, 1500, task.ROI_TRADE_ACTION),
    ]


def test_stall_route_raises_when_all_server_has_no_goods():
    task = FakeKyrwTask(click_template_results=[True, False, False, True, False, False])

    with pytest.raises(RuntimeError, match="本服/全服摆摊均未找到可购买商品"):
        task.try_stall_route()

    assert task.close_transient_calls == 1
    assert "本服/全服摆摊均未找到可购买商品" in task.logs


def test_acquire_route_stops_after_safety_limit():
    task = FakeKyrwTask(route_visible_results=[True])
    task._item_acquire_rounds = task.MAX_ITEM_ACQUIRE_ROUNDS

    with pytest.raises(RuntimeError, match="课业物品获取次数超过安全上限"):
        task.handle_acquire_route_panel_if_visible()


def test_submit_panel_clicks_one_key_submit_and_confirms():
    task = FakeKyrwTask(click_template_results=[True], confirm_results=[True])

    assert task.handle_submit_panel_if_visible()

    assert task.click_template_calls == [
        (task.BTN_ONE_KEY_SUBMIT, 600, "课业一键提交按钮", 0.85, 1500, task.ROI_ONE_KEY_SUBMIT)
    ]


def test_completion_dialog_clicks_ok_and_finishes():
    task = FakeKyrwTask(find_image_results=[True])

    assert task.close_completion_dialog_if_visible()

    assert task.clicked_points == [(task.POINT_COMPLETE_OK[0], task.POINT_COMPLETE_OK[1], 0)]
    assert "检测到课业完成对话，点击确定" in task.logs
