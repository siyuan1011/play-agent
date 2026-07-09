from pathlib import Path

import pytest

from botCore import load_task_class
from botCore.task import StepJumpException
from botCore.vision import load_image
from ymjh_bot.task.MKSY_task import MenkeSheyanTask
from ymjh_bot.ui.task_queue_window import is_visible_task_class


class FakeMenkeSheyanTask(MenkeSheyanTask):
    def __init__(
        self,
        roi_results: list[bool] | None = None,
        image_results: list[bool] | None = None,
        click_template_results: list[bool] | None = None,
        route_panel_results: list[bool] | None = None,
        start_enabled: bool = False,
        banquet_panel_visible: bool = False,
    ):
        super().__init__()
        self.roi_results = roi_results or []
        self.image_results = image_results or []
        self.click_template_results = click_template_results or []
        self.route_panel_results = route_panel_results or []
        self.start_enabled = start_enabled
        self.banquet_panel_visible = banquet_panel_visible
        self.roi_calls = []
        self.image_calls = []
        self.click_template_calls = []
        self.route_panel_calls = 0
        self.return_calls = 0
        self.acquire_calls = []
        self.clicked_points = []
        self.click_count = 0
        self.wait_calls = []
        self.panel_calls = []
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
    ):
        self.roi_calls.append((template, roi, timeout_ms, description, threshold, interval_ms))
        return self.roi_results.pop(0)

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.image_calls.append((template, timeout_ms, threshold))
        return self.image_results.pop(0)

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
        return self.click_template_results.pop(0)

    def ensure_route_panel_open(self):
        self.route_panel_calls += 1
        if self.route_panel_results:
            return self.route_panel_results.pop(0)
        return True

    def return_to_banquet_panel(self, max_attempts: int = 4):
        self.return_calls += 1
        return True

    def acquire_selected_item(self, slot_index: int) -> None:
        self.acquire_calls.append(slot_index)

    def is_start_banquet_enabled(self) -> bool:
        return self.start_enabled

    def is_banquet_panel_visible(self) -> bool:
        return self.banquet_panel_visible

    def click(self, offset: int = 3) -> None:
        self.click_count += 1

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def close_all_panels(self) -> None:
        self.panel_calls.append(("close_all_panels",))

    def open_activity_panel(self, category=None, *, wait_after_open_ms: int = 2000, **kwargs) -> None:
        self.panel_calls.append(("open_activity_panel", category, wait_after_open_ms))

    def _log(self, message: str) -> None:
        self.logs.append(message)


class ScreenshotMenkeSheyanTask(MenkeSheyanTask):
    def __init__(self, screenshot_path: Path):
        super().__init__()
        self.image = load_image(screenshot_path)
        self.logs = []

    def screenshot(self):
        return self.image

    def _log(self, message: str) -> None:
        self.logs.append(message)


def test_menke_sheyan_task_loads_and_is_visible():
    task_file = Path("src/ymjh_bot/task/MKSY_task.py")

    task_cls = load_task_class(task_file)

    assert task_cls.__name__ == "MenkeSheyanTask"
    assert is_visible_task_class(task_cls)
    assert task_cls.task_key == "MKSY"
    assert task_cls.task_name == "门客设宴"


def test_menke_sheyan_step_order():
    steps = [name for name, _, _ in MenkeSheyanTask.get_steps()]

    assert steps == [
        "close_all",
        "open_bangpai_activity",
        "open_guest_list",
        "choose_guest",
        "auto_pathfinding",
        "invite_banquet",
        "process_banquet_items",
        "start_banquet_if_ready",
        "verify_completion",
    ]


def test_open_guest_list_jumps_to_verify_when_entry_missing():
    task = FakeMenkeSheyanTask([False])

    with pytest.raises(StepJumpException) as exc_info:
        task.open_guest_list()

    assert exc_info.value.target == "verify_completion"
    assert task.click_count == 0
    assert "未找到门客设宴入口，默认门客设宴当前不可接取或已完成" in task.logs


def test_open_guest_list_clicks_activity_forward_button():
    task = FakeMenkeSheyanTask([True, True])

    task.open_guest_list()

    assert task.roi_calls == [
        (
            task.BTN_MENKE_SHEYAN_ENTRY,
            task.ROI_MENKE_SHEYAN_ENTRY,
            3000,
            "活动页门客设宴入口",
            0.8,
            500,
        ),
        (
            task.BTN_ACTIVITY_FORWARD,
            task.ROI_MENKE_SHEYAN_ENTRY,
            5000,
            "活动页门客设宴前往按钮",
            0.8,
            500,
        ),
    ]
    assert task.click_count == 1
    assert task.wait_calls == [1500]


def test_choose_guest_clicks_invite_forward_button():
    task = FakeMenkeSheyanTask([True])

    task.choose_guest()

    assert task.roi_calls == [
        (
            task.BTN_MENKE_INVITE_FORWARD,
            task.ROI_MENKE_INVITE_BUTTONS,
            10000,
            "门客列表前往邀约按钮",
            0.8,
            500,
        )
    ]
    assert task.click_count == 1
    assert task.wait_calls == [1500]


def test_choose_guest_jumps_to_verify_when_invite_forward_missing():
    task = FakeMenkeSheyanTask([False])

    with pytest.raises(StepJumpException) as exc_info:
        task.choose_guest()

    assert exc_info.value.target == "verify_completion"
    assert task.click_count == 0
    assert "未找到门客列表前往邀约按钮，默认当前不可邀约或未进入门客列表" in task.logs


def test_choose_guest_jumps_to_items_when_banquet_panel_is_already_open():
    task = FakeMenkeSheyanTask(banquet_panel_visible=True)

    with pytest.raises(StepJumpException) as exc_info:
        task.choose_guest()

    assert exc_info.value.target == "process_banquet_items"
    assert task.roi_calls == []
    assert "检测到已在门客设宴物品面板，跳过邀约流程" in task.logs


def test_invite_banquet_clicks_confirm_invite_and_waits_for_panel():
    task = FakeMenkeSheyanTask(image_results=[True, True, True])

    task.invite_banquet()

    assert task.image_calls == [
        (task.BTN_MENKE_BANQUET_INVITE, 120000, 0.8),
        (task.BTN_MENKE_CONFIRM_INVITE, 30000, 0.8),
        ([task.BTN_MENKE_GET_ITEM, task.BTN_MENKE_ONE_KEY_SUBMIT, task.BTN_MENKE_START_ACTIVE], 30000, 0.8),
    ]
    assert task.click_count == 2
    assert task.wait_calls == [1500, 1500]


def test_process_selected_item_clicks_one_key_submit():
    task = FakeMenkeSheyanTask(click_template_results=[True])

    task.process_selected_item(1)

    assert task.click_template_calls == [
        (task.BTN_MENKE_ONE_KEY_SUBMIT, 800, "一键提交按钮", 0.85, 1500, task.ROI_BANQUET_ACTION)
    ]
    assert task.acquire_calls == []


def test_process_selected_item_uses_get_button_when_one_key_missing():
    task = FakeMenkeSheyanTask(click_template_results=[False, True, False])

    task.process_selected_item(2)

    assert task.click_template_calls == [
        (task.BTN_MENKE_ONE_KEY_SUBMIT, 800, "一键提交按钮", 0.85, 1500, task.ROI_BANQUET_ACTION),
        (task.BTN_MENKE_GET_ITEM, 800, "获取按钮", 0.85, 800, task.ROI_BANQUET_ACTION),
        (task.BTN_MENKE_ONE_KEY_SUBMIT, 1500, "获取后一键提交按钮", 0.85, 1500, task.ROI_BANQUET_ACTION),
    ]
    assert task.acquire_calls == [2]


def test_recommended_warehouse_route_submits_when_available():
    task = FakeMenkeSheyanTask(click_template_results=[True, True])

    assert task.try_recommended_warehouse_route()

    assert task.click_template_calls == [
        (
            task.ROUTE_MENKE_WAREHOUSE_RECOMMENDED,
            800,
            "推荐帮派仓库",
            0.8,
            1500,
            task.ROI_ROUTE_PANEL,
        ),
        (
            task.BTN_MENKE_WAREHOUSE_SUBMIT,
            2500,
            "帮派仓库提交按钮",
            0.85,
            1500,
            task.ROI_WAREHOUSE_SUBMIT,
        ),
    ]
    assert task.return_calls == 1


def test_recommended_warehouse_route_closes_when_submit_missing():
    task = FakeMenkeSheyanTask(click_template_results=[True, False])

    assert not task.try_recommended_warehouse_route()

    assert task.return_calls == 1
    assert "帮派仓库无可提交物品，继续其他获取路径" in task.logs


def test_mall_route_buys_from_mall_area():
    task = FakeMenkeSheyanTask(click_template_results=[True, True, False, True])

    assert task.try_mall_route()

    assert task.click_template_calls == [
        (task.ROUTE_MENKE_MALL, 800, "商城购买路径", 0.8, 2000, task.ROI_ROUTE_PANEL),
        (task.BTN_MENKE_MALL_BUY_AREA, 5000, "商城购买按钮", 0.85, 1500, task.ROI_MALL_BUY),
        (task.BTN_BUY, 1200, "商城购买确认按钮", 0.85, 1500, task.ROI_TRADE_ACTION),
        (task.BTN_MODAL_OK, 2000, "购买二次确认按钮", 0.85, 2000, None),
    ]
    assert task.return_calls == 1


def test_stall_route_checks_all_server_and_skips_when_still_missing():
    task = FakeMenkeSheyanTask(click_template_results=[True, False, True, False])

    assert not task.try_stall_route()

    assert task.click_template_calls == [
        (task.ROUTE_MENKE_STALL, 800, "摆摊购买路径", 0.8, 2500, task.ROI_ROUTE_PANEL),
        (task.BTN_BUY, 4000, "摆摊购买按钮", 0.85, 1500, task.ROI_TRADE_ACTION),
        (task.BTN_MENKE_VIEW_ALL_SERVER, 2500, "查看全服按钮", 0.85, 2500, task.ROI_TRADE_ACTION),
        (task.BTN_BUY, 5000, "全服摆摊购买按钮", 0.85, 1500, task.ROI_TRADE_ACTION),
    ]
    assert task.return_calls == 1
    assert "全服摆摊仍未找到可购买商品" in task.logs


def test_stall_route_confirms_secondary_purchase_prompt():
    task = FakeMenkeSheyanTask(click_template_results=[True, True, True])

    assert task.try_stall_route()

    assert task.click_template_calls == [
        (task.ROUTE_MENKE_STALL, 800, "摆摊购买路径", 0.8, 2500, task.ROI_ROUTE_PANEL),
        (task.BTN_BUY, 4000, "摆摊购买按钮", 0.85, 1500, task.ROI_TRADE_ACTION),
        (task.BTN_MODAL_OK, 2000, "购买二次确认按钮", 0.85, 2000, None),
    ]
    assert task.return_calls == 1


def test_start_banquet_if_ready_clicks_enabled_start_button():
    task = FakeMenkeSheyanTask(click_template_results=[True], start_enabled=True)

    task.start_banquet_if_ready()

    assert task.clicked_points == [(319, 601, 0)]
    assert task.wait_calls == [1500]
    assert task.click_template_calls == [
        (task.BTN_MODAL_OK, 3000, "开始设宴确认按钮", 0.85, 2000, None)
    ]
    assert task._started_banquet


def test_start_banquet_if_ready_skips_when_disabled():
    task = FakeMenkeSheyanTask(start_enabled=False)

    task.start_banquet_if_ready()

    assert task.clicked_points == []
    assert not task._started_banquet
    assert "物品不足，跳过开始设宴" in task.logs


def test_verify_completion_accepts_missing_activity_entry():
    task = FakeMenkeSheyanTask([False])

    task.verify_completion()

    assert task.panel_calls == [
        ("close_all_panels",),
        ("open_activity_panel", "帮派", 3000),
    ]
    assert task.click_count == 0
    assert "完成验证：活动页已无门客设宴入口" in task.logs


def test_verify_completion_raises_when_started_but_invite_still_available():
    task = FakeMenkeSheyanTask([True, True, True])
    task._started_banquet = True

    with pytest.raises(RuntimeError, match="仍可前往邀约"):
        task.verify_completion()

    assert task.click_count == 1
    assert task.wait_calls == [1500]


def test_verify_completion_logs_when_not_started_but_invite_still_available():
    task = FakeMenkeSheyanTask([True, True, True])

    task.verify_completion()

    assert task.click_count == 1
    assert "完成验证：仍可前往邀约，门客设宴未完成" in task.logs


def test_start_banquet_enabled_uses_brightness_not_template_only():
    root = Path(__file__).resolve().parents[1]
    prefix = "\u95e8\u5ba2\u8bbe\u5bb4"

    disabled = ScreenshotMenkeSheyanTask(root / "screenshots" / f"{prefix}7.png")
    enabled = ScreenshotMenkeSheyanTask(root / "screenshots" / f"{prefix}7-1.png")

    assert not disabled.is_start_banquet_enabled()
    assert enabled.is_start_banquet_enabled()
