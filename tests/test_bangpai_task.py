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
        find_image_results: list[bool] | None = None,
        switch_panel_error: RuntimeError | None = None,
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
        self.find_image_results = find_image_results or []
        self.switch_panel_error = switch_panel_error
        self.switch_panel_calls = []
        self.roi_calls = []
        self.scroll_calls = 0
        self.swipe_calls = []
        self.completion_dialog_calls = 0
        self.close_panel_calls = []
        self.open_activity_calls = []
        self.close_transient_calls = 0
        self.click_template_calls = []
        self.click_template_intervals = []
        self.find_image_calls = []
        self.route_panel_calls = 0
        self.confirm_calls = 0
        self.auto_path_waits = []
        self.clicked_points = []
        self.click_count = 0
        self.wait_calls = []
        self.logs = []

    def switch_task_panel(
        self,
        panel: str,
        *,
        timeout_ms: int = 3000,
        threshold: float = 0.8,
        wait_after_click_ms: int = 500,
    ) -> None:
        self.switch_panel_calls.append((panel, timeout_ms, threshold, wait_after_click_ms))
        if self.switch_panel_error is not None:
            raise self.switch_panel_error

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
        super().scroll_task_list_down()

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
        self.swipe_calls.append((x1, y1, x2, y2, duration_ms))

    def close_all_panels(self, templates=None, *, timeout_ms=5000, wait_after_click_ms=500, max_attempts=None):
        self.close_panel_calls.append((templates, timeout_ms, wait_after_click_ms, max_attempts))

    def find_image(self, template, *, threshold=0.8, roi=None):
        self.find_image_calls.append((template, threshold, roi))
        if self.find_image_results:
            return self.find_image_results.pop(0)
        return False

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
        interval_ms=500,
    ):
        self.click_template_calls.append(
            (template, timeout_ms, description, threshold, wait_after_click_ms, roi)
        )
        self.click_template_intervals.append(interval_ms)
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


class FlowProbeBPRWTask(FakeBPRWTask):
    def __init__(self):
        super().__init__(deadline_expired_results=[False, True])
        self.state_calls = []
        self.sidebar_calls = 0

    def close_completion_dialog_if_visible(self) -> bool:
        self.state_calls.append("completion")
        return False

    def handle_submit_panel_if_visible(self) -> bool:
        self.state_calls.append("submit")
        return False

    def handle_trade_panel_if_visible(self) -> bool:
        self.state_calls.append("trade")
        return False

    def handle_acquire_route_panel_if_visible(self) -> bool:
        self.state_calls.append("acquire")
        return False

    def click_bangpai_task_from_sidebar(self, *, max_scrolls: int, required: bool) -> bool:
        self.sidebar_calls += 1
        return False


def test_on_start_wakes_only_when_power_saving_mode_is_visible():
    task = FakeBPRWTask(power_saving_results=[True])

    task.on_start()

    assert task.clicked_points == [
        (task.POINT_RIGHT_JOYSTICK_CENTER[0], task.POINT_RIGHT_JOYSTICK_CENTER[1], 0)
    ]
    assert task.close_panel_calls == [
        (None, 5000, 500, None),
        (None, 5000, 500, None),
    ]
    assert task.completion_dialog_calls == 2
    assert "检测到省电模式，点击右下角摇杆中心唤醒" in task.logs


def test_on_start_does_not_wake_when_power_saving_mode_is_missing():
    task = FakeBPRWTask(power_saving_results=[False])

    task.on_start()

    assert task.clicked_points == []
    assert task.close_panel_calls == [(None, 5000, 500, None)]
    assert task.completion_dialog_calls == 1


def test_on_start_closes_completion_dialog_without_power_wake():
    task = FakeBPRWTask(
        completion_dialog_results=[True],
        power_saving_results=[False],
    )

    task.on_start()

    assert task.clicked_points == [(task.POINT_DIALOG_NEXT[0], task.POINT_DIALOG_NEXT[1], 0)]
    assert "检测到帮派任务完成对话，点击继续" in task.logs


def test_purchase_dialog_hook_closes_leftover_purchase_dialog():
    task = FakeBPRWTask(
        find_image_results=[True],
        power_saving_results=[False],
    )

    assert task.close_purchase_dialog_if_needed()

    assert task.find_image_calls == [
        (
            [task.BTN_CLOSE, task.BTN_PANE_CLOSE],
            0.85,
            task.scale_roi(task.ROI_PURCHASE_DIALOG_CLOSE),
        )
    ]
    assert task.click_count == 1
    assert task.wait_calls == [1000]
    assert task.close_panel_calls == []
    assert "关闭额外挑战次数购买弹窗" in task.logs


def test_find_bangpai_task_in_sidebar_scrolls_until_found():
    task = FakeBPRWTask(roi_results=[False, False, True])

    assert task.find_bangpai_task_in_sidebar(max_scrolls=2)

    assert task.switch_panel_calls == [("江湖", 3000, 0.8, 500)]
    assert task.roi_calls[0][0] == task.SIDEBAR_BANGPAI_TASK_TEMPLATES
    assert task.scroll_calls == 2
    assert len(task.roi_calls) == 3


def test_bangpai_task_list_scroll_uses_sidebar_coordinates():
    task = FakeBPRWTask()

    task.scroll_task_list_down()

    assert task.swipe_calls == [(190, 360, 190, 170, 350)]
    assert task.wait_calls == [800]


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


def test_find_bangpai_task_in_sidebar_stops_when_jianghu_panel_cannot_be_confirmed():
    task = FakeBPRWTask(switch_panel_error=RuntimeError("未能打开任务侧栏"))

    with pytest.raises(RuntimeError, match="未能打开任务侧栏"):
        task.find_bangpai_task_in_sidebar(max_scrolls=0)

    assert task.switch_panel_calls == [("江湖", 3000, 0.8, 500)]
    assert task.clicked_points == []
    assert task.roi_calls == []
    assert task.scroll_calls == 0
    assert task.click_count == 0


def test_click_bangpai_task_from_sidebar_switches_to_jianghu_before_click():
    task = FakeBPRWTask(roi_results=[True])

    assert task.click_bangpai_task_from_sidebar(max_scrolls=0, required=True)

    assert task.switch_panel_calls == [("江湖", 3000, 0.8, 500)]
    assert task.click_count == 1
    assert task.wait_calls == [task.SIDEBAR_TASK_CLICK_SETTLE_MS]


def test_click_bangpai_task_from_sidebar_confirms_popup_when_visible():
    task = FakeBPRWTask(roi_results=[True], click_template_results=[True])

    assert task.click_bangpai_task_from_sidebar(max_scrolls=0, required=True)

    assert task.click_template_calls == [
        (task.BTN_MODAL_OK, 2000, "任务栏帮派任务弹框确定按钮", 0.85, 1000, None),
    ]


def test_start_accepted_task_skips_when_no_bangpai_tracker_is_visible():
    task = FakeBPRWTask(roi_results=[False] * 6)

    with pytest.raises(StepJumpException) as exc_info:
        task.start_accepted_task()

    assert exc_info.value.target == StepJumpException.JUMP_TO_END
    assert "接取后未检测到帮派任务追踪，按当前不可执行或已完成处理" in task.logs


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


def test_reset_startup_state_allows_warehouse_check_for_new_run():
    task = FakeBPRWTask()
    task._warehouse_item_checked = True

    task.reset_startup_state()

    assert task._warehouse_item_checked is False


def test_accept_task_skips_when_account_is_not_in_bangpai():
    task = FakeBPRWTask(find_image_results=[True])

    with pytest.raises(StepJumpException) as exc_info:
        task.accept_task()

    assert exc_info.value.target == StepJumpException.JUMP_TO_END
    assert task.find_image_calls == [
        (
            task.TITLE_BANGPAI_LIST,
            0.85,
            task.scale_roi(task.ROI_BANGPAI_LIST_TITLE),
        )
    ]
    assert "检测到当前未加入帮派，跳过帮派任务" in task.logs


def test_task_item_flow_submits_from_warehouse_before_mall_and_stall():
    task = FakeBPRWTask(
        acquire_visible_results=[True],
        click_template_results=[True, True],
    )

    assert task.handle_acquire_route_panel_if_visible()

    assert task.click_template_calls == [
        (
            task.ROUTE_WAREHOUSE,
            1000,
            "帮派仓库获取途径",
            0.8,
            task.ACQUIRE_ROUTE_OPEN_SETTLE_MS,
            task.ROI_ROUTE_PANEL,
        ),
        (task.BTN_WAREHOUSE_SUBMIT, 3000, "帮派仓库提交按钮", 0.85, 2000, task.ROI_WAREHOUSE_SUBMIT),
    ]
    assert task.click_template_intervals == [task.FLOW_DETECTION_INTERVAL_MS] * 2
    assert task.route_panel_calls == 0
    assert task.close_transient_calls == 1


def test_task_item_flow_uses_mall_after_warehouse_has_no_item():
    task = FakeBPRWTask(
        acquire_visible_results=[True],
        click_template_results=[True, False, True, True],
    )

    assert task.handle_acquire_route_panel_if_visible()

    assert task.click_template_calls == [
        (
            task.ROUTE_WAREHOUSE,
            1000,
            "帮派仓库获取途径",
            0.8,
            task.ACQUIRE_ROUTE_OPEN_SETTLE_MS,
            task.ROI_ROUTE_PANEL,
        ),
        (task.BTN_WAREHOUSE_SUBMIT, 3000, "帮派仓库提交按钮", 0.85, 2000, task.ROI_WAREHOUSE_SUBMIT),
        (
            task.ROUTE_MALL,
            1000,
            "商城购买获取途径",
            0.8,
            task.ACQUIRE_ROUTE_OPEN_SETTLE_MS,
            task.ROI_ROUTE_PANEL,
        ),
        (
            task.BTN_MALL_BUY_AREA,
            5000,
            "商城默认数量购买按钮",
            0.85,
            task.TRADE_ACTION_SETTLE_MS,
            task.ROI_MALL_BUY,
        ),
    ]
    assert task.click_template_intervals == [task.FLOW_DETECTION_INTERVAL_MS] * 4
    assert task.confirm_calls == 1
    assert task.close_transient_calls == 2


def test_task_item_flow_checks_warehouse_only_once_across_repeated_acquire_panels():
    task = FakeBPRWTask(
        acquire_visible_results=[True, True],
        click_template_results=[True, False, True, True, True, True],
    )

    assert task.handle_acquire_route_panel_if_visible()
    assert task.handle_acquire_route_panel_if_visible()

    assert [call[0] for call in task.click_template_calls].count(task.ROUTE_WAREHOUSE) == 1
    assert [call[0] for call in task.click_template_calls].count(task.BTN_WAREHOUSE_SUBMIT) == 1
    assert [call[0] for call in task.click_template_calls].count(task.ROUTE_MALL) == 2
    assert "本轮已检查帮派仓库，跳过重复检测" in task.logs


def test_warehouse_check_is_not_consumed_when_route_does_not_open():
    task = FakeBPRWTask(click_template_results=[False])

    assert not task.try_warehouse_route(route_panel_ready=True)

    assert task._warehouse_item_checked is False
    assert [call[0] for call in task.click_template_calls] == [task.ROUTE_WAREHOUSE]


def test_task_item_flow_falls_back_to_stall_and_all_server_then_stops():
    task = FakeBPRWTask(
        acquire_visible_results=[True],
        click_template_results=[True, False, True, False, True, False, True, False],
    )

    with pytest.raises(StepJumpException) as exc_info:
        task.handle_acquire_route_panel_if_visible()

    assert exc_info.value.target == StepJumpException.JUMP_TO_END
    assert [call[0] for call in task.click_template_calls] == [
        task.ROUTE_WAREHOUSE,
        task.BTN_WAREHOUSE_SUBMIT,
        task.ROUTE_MALL,
        task.BTN_MALL_BUY_AREA,
        task.ROUTE_STALL,
        task.BTN_BUY,
        task.BTN_VIEW_ALL_SERVER,
        task.BTN_BUY,
    ]
    assert task.click_template_calls[4][4] == task.ACQUIRE_ROUTE_OPEN_SETTLE_MS
    assert task.click_template_calls[5][4] == task.TRADE_ACTION_SETTLE_MS
    assert task.click_template_calls[6][4] == task.ACQUIRE_ROUTE_OPEN_SETTLE_MS
    assert task.click_template_calls[7][4] == task.TRADE_ACTION_SETTLE_MS
    assert task.click_template_intervals == [task.FLOW_DETECTION_INTERVAL_MS] * 8
    assert task.close_transient_calls == 4
    assert "帮派任务物品无法通过仓库、商城或摆摊获取，关闭面板并结束本轮执行" in task.logs


def test_acquire_route_panel_detection_includes_mall_with_reduced_polling():
    task = FakeBPRWTask(roi_results=[True])

    assert task.wait_acquire_route_panel_visible(timeout_ms=5000)

    assert task.roi_calls == [
        (
            [task.ROUTE_WAREHOUSE, task.ROUTE_MALL, task.ROUTE_STALL],
            task.ROI_ROUTE_PANEL,
            5000,
            "帮派任务物品获取途径面板",
            0.8,
            task.FLOW_DETECTION_INTERVAL_MS,
        )
    ]


def test_buy_retries_when_button_still_visible_after_no_confirm():
    task = FakeBPRWTask(
        click_template_results=[True],
        confirm_results=[False, False],
        find_image_results=[True],
    )

    assert task.buy_from_current_trade_panel("摆摊购买按钮", timeout_ms=4000)

    assert task.click_template_calls == [
        (
            task.BTN_BUY,
            4000,
            "摆摊购买按钮",
            task.TRADE_BUY_THRESHOLD,
            task.TRADE_ACTION_SETTLE_MS,
            task.ROI_TRADE_ACTION,
        ),
    ]
    assert task.click_template_intervals == [task.FLOW_DETECTION_INTERVAL_MS]
    assert task.find_image_calls == [
        (
            task.BTN_BUY,
            task.TRADE_BUY_THRESHOLD,
            task.scale_roi(task.ROI_TRADE_ACTION),
        ),
    ]
    assert task.roi_calls == []
    assert task.click_count == 1
    assert task.wait_calls == [task.TRADE_ACTION_SETTLE_MS]
    assert task.confirm_calls == 2
    assert "购买按钮点击后仍可见，重试点击" in task.logs


def test_submit_panel_clicks_one_key_submit_and_confirms():
    task = FakeBPRWTask(click_template_results=[True, True])

    assert task.handle_submit_panel_if_visible()

    assert task.click_template_calls == [
        (task.BTN_ONE_KEY_SUBMIT, 600, "帮派任务一键提交按钮", 0.85, 1500, task.ROI_ONE_KEY_SUBMIT),
        ([task.BTN_MODAL_OK, task.BTN_OK], 3000, "帮派任务提交确认按钮", 0.85, 1500, None),
    ]
    assert task.click_template_intervals == [task.FLOW_DETECTION_INTERVAL_MS] * 2


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


def test_run_task_flow_checks_each_state_once_per_cycle():
    task = FlowProbeBPRWTask()

    with pytest.raises(RuntimeError, match="帮派任务执行流程超时"):
        task.run_task_flow()

    assert task.state_calls == ["completion", "submit", "trade", "acquire"]
    assert task.sidebar_calls == 1
    assert task.wait_calls == [task.TASK_FLOW_RETRY_WAIT_MS]


def test_run_task_flow_times_out_instead_of_succeeding_after_idle_sidebar_clicks():
    task = FakeBPRWTask(
        roi_results=[True, True, True],
        deadline_expired_results=[False, False, False, True],
    )

    with pytest.raises(RuntimeError, match="帮派任务执行流程超时"):
        task.run_task_flow()

    assert task.click_count == 3
    assert "连续点击左侧帮派任务未出现新流程，继续等待完成信号" in task.logs
