"""破阵设宴任务 - Python DSL 实现。"""

from botCore import step

from ymjh_bot.task.banquet import BanquetAcquireMixin
from ymjh_bot.ym_game_task import YmGameTask


class PozhenSheyanTask(BanquetAcquireMixin, YmGameTask):
    """一梦江湖破阵设宴任务。"""

    task_key = "PZSY"
    task_name = "破阵设宴"
    task_description = "破阵设宴自动邀约"

    BTN_ACTIVITY_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_activity_forward.png")
    BTN_POZHEN_SHEYAN_ENTRY = str(YmGameTask.TEMPLATES_DIR / "btn_pozhen_sheyan_entry.png")
    BTN_POZHEN_GET_ITEM = str(YmGameTask.TEMPLATES_DIR / "btn_pozhen_get_item.png")
    BTN_POZHEN_ONE_KEY_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_pozhen_one_key_submit.png")
    BTN_POZHEN_SUBMIT_5_TAB = str(YmGameTask.TEMPLATES_DIR / "btn_pozhen_submit_5_tab.png")
    BTN_POZHEN_SUBMIT_6_TAB = str(YmGameTask.TEMPLATES_DIR / "btn_pozhen_submit_6_tab.png")
    BTN_MENKE_INVITE_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_menke_invite_forward.png")
    BTN_MENKE_BANQUET_INVITE = str(YmGameTask.TEMPLATES_DIR / "btn_menke_banquet_invite.png")
    BTN_MENKE_CONFIRM_INVITE = str(YmGameTask.TEMPLATES_DIR / "btn_menke_confirm_invite.png")
    BTN_BANQUET_GET_ITEM = BTN_POZHEN_GET_ITEM
    BTN_BANQUET_ONE_KEY_SUBMIT = BTN_POZHEN_ONE_KEY_SUBMIT
    BANQUET_NAME = "破阵设宴"
    START_BANQUET_BRIGHTNESS_THRESHOLD = 120.0

    # 固定坐标点 (设计分辨率 1280x720 下)
    ROI_POZHEN_SHEYAN_ENTRY = (540, 230, 260, 160)
    ROI_POZHEN_INVITE_BUTTONS = (780, 135, 170, 520)
    ROI_BANQUET_ACTION = (960, 530, 210, 110)
    ROI_START_BANQUET_BUTTON = (210, 570, 190, 65)
    ROI_SUBMIT_5_TAB = (110, 365, 215, 65)
    ROI_SUBMIT_6_TAB = (295, 365, 205, 65)

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
    POINT_START_BANQUET = (304, 602)
    POINT_SUBMIT_5_TAB = (215, 396)
    POINT_SUBMIT_6_TAB = (396, 396)

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._started_banquet = False

    def before_start(self) -> None:
        """Wake the game from power-saving mode before the common startup guard."""
        if self.is_game_foreground() and self.detect_login_state(include_modal_controls=True) is None:
            self.wake_from_power_saving_if_needed()
        super().before_start()

    def on_start(self) -> None:
        """任务开始前准备。"""
        self._started_banquet = False
        self._log("=" * 40)
        self._log("破阵设宴任务开始")
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
    def open_pozhen_list(self) -> None:
        """点击破阵设宴入口，打开破阵邀约列表。"""
        if not self.wait_find_image_in_roi(
            self.BTN_POZHEN_SHEYAN_ENTRY,
            self.ROI_POZHEN_SHEYAN_ENTRY,
            timeout_ms=3000,
            description="活动页破阵设宴入口",
        ):
            self._log("未找到破阵设宴入口，默认破阵设宴当前不可接取或已完成")
            self.jump_to_end()

        if not self.wait_find_image_in_roi(
            self.BTN_ACTIVITY_FORWARD,
            self.ROI_POZHEN_SHEYAN_ENTRY,
            timeout_ms=5000,
            description="活动页破阵设宴前往按钮",
        ):
            raise RuntimeError("未找到活动页破阵设宴前往按钮")
        self.click()
        self.wait(1500)

    @step(retry=3, timeout_ms=30000)
    def choose_guest(self) -> None:
        """选择任意一个可见门客，点击前往邀约。"""
        if self.is_banquet_panel_visible():
            self._log("检测到已在破阵设宴物品面板，跳过邀约流程")
            self.jump_to("process_banquet_items")

        if not self.wait_find_image_in_roi(
            self.BTN_MENKE_INVITE_FORWARD,
            self.ROI_POZHEN_INVITE_BUTTONS,
            timeout_ms=10000,
            description="破阵列表前往邀约按钮",
        ):
            self._log("未找到破阵列表前往邀约按钮，默认当前不可邀约或未进入破阵列表")
            self.jump_to_end()
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
            [
                self.BTN_POZHEN_GET_ITEM,
                self.BTN_POZHEN_ONE_KEY_SUBMIT,
                self.BTN_POZHEN_SUBMIT_5_TAB,
                self.BTN_POZHEN_SUBMIT_6_TAB,
            ],
            timeout_ms=30000,
            threshold=0.8,
        ):
            raise RuntimeError("未进入破阵设宴物品面板")

    @step(retry=1, timeout_ms=240000)
    def process_banquet_items(self) -> None:
        """默认按提交 6 道菜逐个处理设宴面板中的任务物品。"""
        self.select_submit_six_dishes()
        super().process_banquet_items()

    @step(retry=1, timeout_ms=30000)
    def start_banquet_if_ready(self) -> None:
        """如果开始设宴按钮已可用，则提交任务；否则回退提交 5 道菜重试。"""
        if self.try_start_banquet_once():
            self._started_banquet = True
            return

        self._log("提交6道菜暂不可开始，切换提交5道菜重试")
        self.select_submit_five_dishes()
        if self.try_start_banquet_once():
            self._started_banquet = True
            return

        self._log("物品不足，跳过开始设宴")

    @step(retry=1, timeout_ms=60000)
    def verify_completion(self) -> None:
        """回到活动-帮派页验证破阵设宴是否已完成。"""
        self.close_all_panels()
        self.open_activity_panel("帮派", wait_after_open_ms=3000)

        if not self.wait_find_image_in_roi(
            self.BTN_POZHEN_SHEYAN_ENTRY,
            self.ROI_POZHEN_SHEYAN_ENTRY,
            timeout_ms=3000,
            description="活动页破阵设宴入口",
        ):
            self._log("完成验证：活动页已无破阵设宴入口")
            return

        self._log("完成验证：活动页仍存在破阵设宴入口，进入列表确认邀约状态")
        if not self.wait_find_image_in_roi(
            self.BTN_ACTIVITY_FORWARD,
            self.ROI_POZHEN_SHEYAN_ENTRY,
            timeout_ms=5000,
            description="活动页破阵设宴前往按钮",
        ):
            self._log("完成验证：入口存在但未找到前往按钮，默认不可继续邀约")
            return

        self.click()
        self.wait(1500)
        if self.is_banquet_panel_visible():
            message = "完成验证：仍回到破阵设宴物品面板，任务未完成"
            if self._started_banquet:
                raise RuntimeError(message)
            self._log(message)
            return

        if self.wait_find_image_in_roi(
            self.BTN_MENKE_INVITE_FORWARD,
            self.ROI_POZHEN_INVITE_BUTTONS,
            timeout_ms=5000,
            description="破阵列表前往邀约按钮",
        ):
            message = "完成验证：仍可前往邀约，破阵设宴未完成"
            if self._started_banquet:
                raise RuntimeError(message)
            self._log(message)
            return

        self._log("完成验证：未发现可继续邀约的破阵设宴")

    def select_submit_six_dishes(self) -> None:
        """Select the 6-dish banquet tier."""
        self._log("选择提交6道菜")
        self.click_point(self.POINT_SUBMIT_6_TAB[0], self.POINT_SUBMIT_6_TAB[1], offset=0)
        self.wait(800)

    def select_submit_five_dishes(self) -> None:
        """Select the 5-dish banquet tier."""
        self._log("选择提交5道菜")
        self.click_point(self.POINT_SUBMIT_5_TAB[0], self.POINT_SUBMIT_5_TAB[1], offset=0)
        self.wait(800)

    def is_banquet_panel_visible(self) -> bool:
        """Return whether the main Pozhen banquet item panel is visible."""
        return (
            self.find_image(self.BTN_POZHEN_GET_ITEM, threshold=0.8, roi=self.scale_roi(self.ROI_BANQUET_ACTION))
            or self.find_image(
                self.BTN_POZHEN_ONE_KEY_SUBMIT,
                threshold=0.8,
                roi=self.scale_roi(self.ROI_BANQUET_ACTION),
            )
            or self.find_image(self.BTN_POZHEN_SUBMIT_5_TAB, threshold=0.75, roi=self.scale_roi(self.ROI_SUBMIT_5_TAB))
            or self.find_image(self.BTN_POZHEN_SUBMIT_6_TAB, threshold=0.75, roi=self.scale_roi(self.ROI_SUBMIT_6_TAB))
        )

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"破阵设宴任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
