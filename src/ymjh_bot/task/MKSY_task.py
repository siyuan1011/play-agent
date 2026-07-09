"""门客设宴任务 - Python DSL 实现。"""

from botCore import step

from ymjh_bot.task.banquet import BanquetAcquireMixin
from ymjh_bot.ym_game_task import YmGameTask


class MenkeSheyanTask(BanquetAcquireMixin, YmGameTask):
    """一梦江湖门客设宴任务。"""

    task_key = "MKSY"
    task_name = "门客设宴"
    task_description = "门客设宴自动邀约"

    BTN_ACTIVITY_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_bangpai_task_forward.png")
    BTN_MENKE_SHEYAN_ENTRY = str(YmGameTask.TEMPLATES_DIR / "btn_menke_sheyan_entry.png")
    BTN_MENKE_INVITE_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_menke_invite_forward.png")
    BTN_MENKE_BANQUET_INVITE = str(YmGameTask.TEMPLATES_DIR / "btn_menke_banquet_invite.png")
    BTN_MENKE_CONFIRM_INVITE = str(YmGameTask.TEMPLATES_DIR / "btn_menke_confirm_invite.png")
    BTN_MENKE_GET_ITEM = str(YmGameTask.TEMPLATES_DIR / "btn_menke_get_item.png")
    BTN_MENKE_ONE_KEY_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_menke_one_key_submit.png")
    BTN_MENKE_START_ACTIVE = str(YmGameTask.TEMPLATES_DIR / "btn_menke_start_active.png")
    ROUTE_MENKE_WAREHOUSE_RECOMMENDED = str(YmGameTask.TEMPLATES_DIR / "route_menke_warehouse_recommended.png")
    ROUTE_MENKE_MALL = str(YmGameTask.TEMPLATES_DIR / "route_menke_mall.png")
    ROUTE_MENKE_STALL = str(YmGameTask.TEMPLATES_DIR / "route_menke_stall.png")
    BTN_MENKE_WAREHOUSE_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_menke_warehouse_submit.png")
    BTN_MENKE_VIEW_ALL_SERVER = str(YmGameTask.TEMPLATES_DIR / "btn_menke_view_all_server.png")
    BTN_MENKE_MALL_BUY_AREA = str(YmGameTask.TEMPLATES_DIR / "btn_menke_mall_buy_area.png")
    BTN_BUY = str(YmGameTask.TEMPLATES_DIR / "btn_buy.png")
    BTN_BANQUET_GET_ITEM = BTN_MENKE_GET_ITEM
    BTN_BANQUET_ONE_KEY_SUBMIT = BTN_MENKE_ONE_KEY_SUBMIT
    BTN_BANQUET_START_ACTIVE = BTN_MENKE_START_ACTIVE
    BANQUET_NAME = "门客设宴"

    # 固定坐标点 (设计分辨率 1280x720 下)
    ROI_MENKE_SHEYAN_ENTRY = (150, 470, 210, 145)
    ROI_MENKE_INVITE_BUTTONS = (780, 135, 170, 520)
    ROI_BANQUET_ACTION = (960, 530, 210, 100)
    ROI_START_BANQUET_BUTTON = (242, 570, 155, 63)
    ROI_ROUTE_PANEL = (560, 70, 660, 480)
    ROI_WAREHOUSE_SUBMIT = (760, 530, 230, 115)
    ROI_TRADE_ACTION = (520, 440, 330, 120)
    ROI_MALL_BUY = (800, 610, 290, 100)

    POINT_BANQUET_ITEM_SLOTS = (
        (608, 264),
        (762, 264),
        (917, 264),
        (1070, 264),
        (608, 428),
        (762, 428),
        (917, 428),
        (1070, 428),
    )
    POINT_START_BANQUET = (319, 601)

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._started_banquet = False

    def on_start(self) -> None:
        """任务开始前准备。"""
        self._started_banquet = False
        self._log("=" * 40)
        self._log("门客设宴任务开始")
        self._log("=" * 40)

    @step(retry=1, timeout_ms=30000)
    def close_all(self) -> None:
        """关闭所有弹窗，回到游戏主界面。"""
        self.close_all_panels()
        self.wait(1000)

    @step(retry=3, timeout_ms=30000)
    def open_bangpai_activity(self) -> None:
        """打开活动界面并切换到帮派页签。"""
        self.open_activity_panel("帮派", wait_after_open_ms=3000)

    @step(retry=3, timeout_ms=30000)
    def open_guest_list(self) -> None:
        """点击门客设宴入口，打开门客邀约列表。"""
        if not self.wait_find_image_in_roi(
            self.BTN_MENKE_SHEYAN_ENTRY,
            self.ROI_MENKE_SHEYAN_ENTRY,
            timeout_ms=3000,
            description="活动页门客设宴入口",
        ):
            self._log("未找到门客设宴入口，默认门客设宴当前不可接取或已完成")
            self.jump_to("verify_completion")

        if not self.wait_find_image_in_roi(
            self.BTN_ACTIVITY_FORWARD,
            self.ROI_MENKE_SHEYAN_ENTRY,
            timeout_ms=5000,
            description="活动页门客设宴前往按钮",
        ):
            raise RuntimeError("未找到活动页门客设宴前往按钮")
        self.click()
        self.wait(1500)

    @step(retry=3, timeout_ms=30000)
    def choose_guest(self) -> None:
        """选择任意一个可见门客，点击前往邀约。"""
        if self.is_banquet_panel_visible():
            self._log("检测到已在门客设宴物品面板，跳过邀约流程")
            self.jump_to("process_banquet_items")

        if not self.wait_find_image_in_roi(
            self.BTN_MENKE_INVITE_FORWARD,
            self.ROI_MENKE_INVITE_BUTTONS,
            timeout_ms=10000,
            description="门客列表前往邀约按钮",
        ):
            self._log("未找到门客列表前往邀约按钮，默认当前不可邀约或未进入门客列表")
            self.jump_to("verify_completion")
        self.click()
        self.wait(1500)

    @step(retry=1, timeout_ms=None)
    def auto_pathfinding(self) -> None:
        """等待自动寻路结束。"""
        self.wait_auto_pathfinding()

    @step(retry=3, timeout_ms=180000)
    def invite_banquet(self) -> None:
        """在 NPC 对话中点击邀请赴宴，并确认邀约。"""
        self.require_image(self.BTN_MENKE_BANQUET_INVITE, timeout_ms=120000, description="NPC 邀请赴宴按钮")
        self.click()
        self.wait(1500)

        self.require_image(self.BTN_MENKE_CONFIRM_INVITE, timeout_ms=30000, description="确认邀约按钮")
        self.click()
        self.wait(1500)

        if not self.wait_image_appear(
            [self.BTN_MENKE_GET_ITEM, self.BTN_MENKE_ONE_KEY_SUBMIT, self.BTN_MENKE_START_ACTIVE],
            timeout_ms=30000,
            threshold=0.8,
        ):
            raise RuntimeError("未进入门客设宴物品面板")

    @step(retry=1, timeout_ms=240000)
    def process_banquet_items(self) -> None:
        """逐个处理设宴面板中的任务物品。"""
        super().process_banquet_items()

    @step(retry=1, timeout_ms=30000)
    def start_banquet_if_ready(self) -> None:
        """如果开始设宴按钮已可用，则提交任务。"""
        if self.try_start_banquet_once():
            self._started_banquet = True
            return

        self._log("物品不足，跳过开始设宴")

    @step(retry=1, timeout_ms=60000)
    def verify_completion(self) -> None:
        """回到活动-帮派页验证门客设宴是否已完成。"""
        self.close_all_panels()
        self.open_activity_panel("帮派", wait_after_open_ms=3000)

        if not self.wait_find_image_in_roi(
            self.BTN_MENKE_SHEYAN_ENTRY,
            self.ROI_MENKE_SHEYAN_ENTRY,
            timeout_ms=3000,
            description="活动页门客设宴入口",
        ):
            self._log("完成验证：活动页已无门客设宴入口")
            return

        self._log("完成验证：活动页仍存在门客设宴入口，进入列表确认邀约状态")
        if not self.wait_find_image_in_roi(
            self.BTN_ACTIVITY_FORWARD,
            self.ROI_MENKE_SHEYAN_ENTRY,
            timeout_ms=5000,
            description="活动页门客设宴前往按钮",
        ):
            self._log("完成验证：入口存在但未找到前往按钮，默认不可继续邀约")
            return

        self.click()
        self.wait(1500)
        if self.is_banquet_panel_visible():
            message = "完成验证：仍回到门客设宴物品面板，任务未完成"
            if self._started_banquet:
                raise RuntimeError(message)
            self._log(message)
            return

        if self.wait_find_image_in_roi(
            self.BTN_MENKE_INVITE_FORWARD,
            self.ROI_MENKE_INVITE_BUTTONS,
            timeout_ms=5000,
            description="门客列表前往邀约按钮",
        ):
            message = "完成验证：仍可前往邀约，门客设宴未完成"
            if self._started_banquet:
                raise RuntimeError(message)
            self._log(message)
            return

        self._log("完成验证：未发现可继续邀约的门客设宴")

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"门客设宴任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
