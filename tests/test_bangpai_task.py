import pytest

from botCore.task import StepJumpException
from ymjh_bot.task.BPRW_task import BPRWTask


class FakeBPRWTask(BPRWTask):
    def __init__(
        self,
        *,
        roi_results: list[bool] | None = None,
        click_template_results: list[bool] | None = None,
        acquire_visible_results: list[bool] | None = None,
        route_panel_results: list[bool] | None = None,
        power_saving_results: list[bool] | None = None,
        confirm_results: list[bool] | None = None,
        completion_dialog_results: list[bool] | None = None,
        deadline_expired_results: list[bool] | None = None,
    ):
        super().__init__()
        self.roi_results = roi_results or []
        self.click_template_results = click_template_results or []
        self.acquire_visible_results = acquire_visible_results or []
        self.route_panel_results = route_panel_results or []
        self.power_saving_results = power_saving_results or []
        self.confirm_results = confirm_results or []
        self.completion_dialog_results = completion_dialog_results or []
        self.deadline_expired_results = deadline_expired_results
        self.ensure_sidebar_calls = 0
        self.switch_panel_calls = []
        self.roi_calls = []
        self.scroll_calls = 0
        self.completion_dialog_calls = 0
        self.close_panel_calls = []
        self.open_activity_calls = []
        self.close_transient_calls = 0
        self.click_template_calls = []
        self.route_panel_calls = 0
        self.confirm_calls = 0
        self.auto_path_waits = []
        self.clicked_points = []
        self.click_count = 0
        self.wait_calls = []
        self.logs = []

    def ensure_left_task_sidebar_visible(self) -> None:
        self.ensure_sidebar_calls += 1

    def switch_task_panel(
        self,
        panel: str,
        *,
        timeout_ms: int = 3000,
        threshold: float = 0.8,
        wait_after_click_ms: int = 500,
    ) -> None:
        self.switch_panel_calls.append((panel, timeout_ms, threshold, wait_after_click_ms))

    def _make_deadline(self, timeout_ms):
        if self.deadline_expired_results is None:
            return super()._make_deadline(timeout_ms)
        return object()

    def _is_deadline_expired(self, deadline):
        if self.deadline_expired_results is None:
            return super()._is_deadline_expired(deadline)
        if self.deadline_expired_results:
            return self.deadline_expired_results.pop(0)
        return False

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

    def scroll_task_list_down(self) -> None:
        self.scroll_calls += 1

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

    def is_power_saving_mode(self) -> bool:
        if self.power_saving_results:
            return self.power_saving_results.pop(0)
        return False

    def close_completion_dialog_if_visible(self) -> bool:
        self.completion_dialog_calls += 1
        if not self.completion_dialog_results:
            return False
        if not self.completion_dialog_results.pop(0):
            return False
        self.logs.append("检测到帮派任务完成对话，点击继续")
        self.click_point(self.POINT_DIALOG_NEXT[0], self.POINT_DIALOG_NEXT[1], offset=0)
        self.wait(1000)
        return True

    def click(self, offset: int = 3) -> None:
        self.click_count += 1

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def is_acquire_route_panel_visible(self) -> bool:
        if self.acquire_visible_results:
            return self.acquire_visible_results.pop(0)
        return False

    def ensure_acquire_route_panel_open(self) -> bool:
        self.route_panel_calls += 1
        if self.route_panel_results:
            return self.route_panel_results.pop(0)
        return True

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
        if not self.click_template_results:
            return False
        return self.click_template_results.pop(0)

    def close_transient_panels(self, max_attempts: int = 4) -> bool:
        self.close_transient_calls += 1
        return True

    def confirm_purchase_if_needed(self) -> bool:
        self.confirm_calls += 1
        if self.confirm_results:
            return self.confirm_results.pop(0)
        return True

    def wait_auto_pathfinding(self, **kwargs) -> None:
        self.auto_path_waits.append(kwargs)

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_close_all_wakes_only_when_power_saving_mode_is_visible():
    task = FakeBPRWTask(power_saving_results=[True])

    task.close_all()

    assert task.clicked_points == [
        (task.POINT_RIGHT_JOYSTICK_CENTER[0], task.POINT_RIGHT_JOYSTICK_CENTER[1], 0)
    ]
    assert task.close_panel_calls == [
        (None, 5000, 500),
        (None, 5000, 500),
    ]
    assert task.completion_dialog_calls == 2
    assert "检测到省电模式，点击右下角摇杆中心唤醒" in task.logs


def test_close_all_does_not_wake_when_power_saving_mode_is_missing():
    task = FakeBPRWTask(power_saving_results=[False])

    task.close_all()

    assert task.clicked_points == []
    assert task.close_panel_calls == [(None, 5000, 500)]
    assert task.completion_dialog_calls == 1


def test_close_all_closes_completion_dialog_without_power_wake():
    task = FakeBPRWTask(
        completion_dialog_results=[True],
        power_saving_results=[False],
    )

    task.close_all()

    assert task.clicked_points == [(task.POINT_DIALOG_NEXT[0], task.POINT_DIALOG_NEXT[1], 0)]
    assert "检测到帮派任务完成对话，点击继续" in task.logs


def test_find_bangpai_task_in_sidebar_scrolls_until_found():
    task = FakeBPRWTask(roi_results=[False, False, True])

    assert task.find_bangpai_task_in_sidebar(max_scrolls=2)

    assert task.switch_panel_calls == [("江湖", 3000, 0.8, 500)]
    assert task.roi_calls[0][0] == task.SIDEBAR_BANGPAI_TASK_TEMPLATES
    assert task.scroll_calls == 2
    assert len(task.roi_calls) == 3


def test_find_bangpai_task_in_sidebar_matches_daily_keyword_template():
    task = FakeBPRWTask(roi_results=[True])

    assert task.find_bangpai_task_in_sidebar(max_scrolls=0)

    assert task.roi_calls == [
        (
            task.SIDEBAR_BANGPAI_TASK_TEMPLATES,
            task.ROI_TASK_LIST,
            1200,
            "任务栏帮派任务或日常环",
            0.7,
            300,
        )
    ]


def test_click_bangpai_task_from_sidebar_switches_to_jianghu_before_click():
    task = FakeBPRWTask(roi_results=[True])

    assert task.click_bangpai_task_from_sidebar(max_scrolls=0, required=True)

    assert task.switch_panel_calls == [("江湖", 3000, 0.8, 500)]
    assert task.click_count == 1


def test_click_bangpai_task_from_sidebar_confirms_popup_when_visible():
    task = FakeBPRWTask(roi_results=[True], click_template_results=[True])

    assert task.click_bangpai_task_from_sidebar(max_scrolls=0, required=True)

    assert task.click_template_calls == [
        (task.BTN_MODAL_OK, 2000, "任务栏帮派任务弹框确定按钮", 0.85, 1000, None),
    ]


def test_resume_existing_task_clicks_and_jumps_to_run_flow():
    task = FakeBPRWTask(roi_results=[True])

    with pytest.raises(StepJumpException) as exc_info:
        task.resume_existing_task()

    assert exc_info.value.target == "run_task_flow"
    assert task.click_count == 1
    assert "检测到已接取帮派任务，跳过接取流程" in task.logs


def test_resume_existing_task_continues_when_sidebar_task_missing():
    task = FakeBPRWTask(roi_results=[False, False, False, False, False, False])

    task.resume_existing_task()

    assert task.click_count == 0
    assert task.scroll_calls == 5
    assert "未发现已接取帮派任务，关闭任务面板并继续接取流程" in task.logs


def test_task_item_flow_submits_from_warehouse_before_stall():
    task = FakeBPRWTask(
        acquire_visible_results=[True],
        click_template_results=[True, True],
    )

    assert task.handle_acquire_route_panel_if_visible()

    assert task.click_template_calls == [
        (task.ROUTE_WAREHOUSE, 1000, "帮派仓库获取途径", 0.8, 2000, task.ROI_ROUTE_PANEL),
        (task.BTN_WAREHOUSE_SUBMIT, 3000, "帮派仓库提交按钮", 0.85, 2000, task.ROI_WAREHOUSE_SUBMIT),
    ]
    assert task.close_transient_calls == 1


def test_task_item_flow_falls_back_to_stall_and_all_server_then_stops():
    task = FakeBPRWTask(
        acquire_visible_results=[True],
        click_template_results=[True, False, True, False, True, False],
    )

    with pytest.raises(StepJumpException) as exc_info:
        task.handle_acquire_route_panel_if_visible()

    assert exc_info.value.target == StepJumpException.JUMP_TO_END
    assert task.click_template_calls == [
        (task.ROUTE_WAREHOUSE, 1000, "帮派仓库获取途径", 0.8, 2000, task.ROI_ROUTE_PANEL),
        (task.BTN_WAREHOUSE_SUBMIT, 3000, "帮派仓库提交按钮", 0.85, 2000, task.ROI_WAREHOUSE_SUBMIT),
        (task.ROUTE_STALL, 1000, "摆摊购买获取途径", 0.8, 2500, task.ROI_ROUTE_PANEL),
        (task.BTN_BUY, 4000, "摆摊购买按钮", task.TRADE_BUY_THRESHOLD, 1500, task.ROI_TRADE_ACTION),
        (task.BTN_VIEW_ALL_SERVER, 2500, "查看全服按钮", 0.85, 2500, task.ROI_TRADE_ACTION),
        (task.BTN_BUY, 5000, "全服摆摊购买按钮", task.TRADE_BUY_THRESHOLD, 1500, task.ROI_TRADE_ACTION),
    ]
    assert task.close_transient_calls == 3
    assert "帮派任务物品无法通过仓库或摆摊获取，关闭面板并结束本轮执行" in task.logs


def test_buy_retries_when_button_still_visible_after_no_confirm():
    task = FakeBPRWTask(
        roi_results=[True],
        click_template_results=[True],
        confirm_results=[False, False],
    )

    assert task.buy_from_current_trade_panel("摆摊购买按钮", timeout_ms=4000)

    assert task.click_template_calls == [
        (task.BTN_BUY, 4000, "摆摊购买按钮", task.TRADE_BUY_THRESHOLD, 1500, task.ROI_TRADE_ACTION),
    ]
    assert task.roi_calls == [
        (
            task.BTN_BUY,
            task.ROI_TRADE_ACTION,
            800,
            "摆摊购买按钮点击后仍可见",
            task.TRADE_BUY_THRESHOLD,
            300,
        ),
    ]
    assert task.click_count == 1
    assert task.confirm_calls == 2
    assert "购买按钮点击后仍可见，重试点击" in task.logs


def test_submit_panel_clicks_one_key_submit_and_confirms():
    task = FakeBPRWTask(click_template_results=[True, True])

    assert task.handle_submit_panel_if_visible()

    assert task.click_template_calls == [
        (task.BTN_ONE_KEY_SUBMIT, 600, "帮派任务一键提交按钮", 0.85, 1500, task.ROI_ONE_KEY_SUBMIT),
        ([task.BTN_MODAL_OK, task.BTN_OK], 3000, "帮派任务提交确认按钮", 0.85, 1500, None),
    ]


def test_run_task_flow_times_out_when_sidebar_tracker_is_missing():
    task = FakeBPRWTask(
        roi_results=[False, False, False],
        deadline_expired_results=[False, True],
    )

    with pytest.raises(RuntimeError, match="帮派任务执行流程超时"):
        task.run_task_flow()

    assert task.switch_panel_calls == [("江湖", 3000, 0.8, 500)]
    assert task.scroll_calls == 2
    assert "江湖任务栏暂未找到帮派任务，继续等待完成信号 (1)" in task.logs


def test_run_task_flow_times_out_instead_of_succeeding_after_idle_sidebar_clicks():
    task = FakeBPRWTask(
        roi_results=[True, True, True],
        deadline_expired_results=[False, False, False, True],
    )

    with pytest.raises(RuntimeError, match="帮派任务执行流程超时"):
        task.run_task_flow()

    assert task.click_count == 3
    assert "连续点击左侧帮派任务未出现新流程，继续等待完成信号" in task.logs
