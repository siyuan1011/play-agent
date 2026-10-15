"""破阵设宴任务 - Python DSL 实现。"""

from botCore import step

from ymjh_bot.task.banquet import BanquetAcquireMixin
from ymjh_bot.ym_game_task import YmGameTask


class PZSYTask(BanquetAcquireMixin, YmGameTask):
    """一梦江湖破阵设宴任务。"""

    task_key = "PZSY"
    task_name = "破阵设宴"
    task_description = "破阵设宴自动邀约"
    DEFER_FOREGROUND_WAKE_TO_ON_START = True
    STARTUP_CLOSE_SETTLE_WAIT_MS = 1000

    BTN_ACTIVITY_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_activity_forward.png")
    BTN_POZHEN_SHEYAN_ENTRY = str(YmGameTask.TEMPLATES_DIR / "btn_pozhen_sheyan_entry.png")
    BTN_POZHEN_GET_ITEM = str(YmGameTask.TEMPLATES_DIR / "btn_pozhen_get_item.png")
    BTN_POZHEN_ONE_KEY_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_pozhen_one_key_submit.png")
    BTN_POZHEN_SUBMIT_5_TAB = str(YmGameTask.TEMPLATES_DIR / "btn_pozhen_submit_5_tab.png")
    BTN_POZHEN_SUBMIT_6_TAB = str(YmGameTask.TEMPLATES_DIR / "btn_pozhen_submit_6_tab.png")
    BTN_MENKE_BANQUET_INVITE = str(YmGameTask.TEMPLATES_DIR / "btn_menke_banquet_invite.png")
    BTN_MENKE_CONFIRM_INVITE = str(YmGameTask.TEMPLATES_DIR / "btn_menke_confirm_invite.png")
    BTN_BANQUET_GET_ITEM = BTN_POZHEN_GET_ITEM
    BTN_BANQUET_ONE_KEY_SUBMIT = BTN_POZHEN_ONE_KEY_SUBMIT
    BANQUET_NAME = "破阵设宴"
    BANQUET_INVITE_TIMEOUT_MS = 180000
    START_BANQUET_BRIGHTNESS_THRESHOLD = 120.0

    # 固定坐标点 (设计分辨率 1280x720 下)
    ROI_POZHEN_SHEYAN_ENTRY = (540, 230, 260, 160)
    ROI_BANQUET_ACTION = (960, 530, 210, 110)
    ROI_START_BANQUET_BUTTON = (210, 570, 190, 65)

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

    def reset_startup_state(self) -> None:
        """在通用启动清理前重置宴席状态。"""
        super().reset_startup_state()
        self._started_banquet = False

    @step(retry=3, timeout_ms=30000)
    def open_bangpai_activity(self) -> None:
        """打开活动界面并切换到帮派页签。"""
        self.open_activity_panel("帮派", wait_after_open_ms=3000)

    @step(retry=3, timeout_ms=30000)
    def start_pozhen_navigation(self) -> None:
        """点击活动页前往按钮，开始前往破阵设宴 NPC。"""
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

    @step(retry=0, timeout_ms=240000)
    def invite_banquet(self) -> None:
        """等待寻路抵达，在 NPC 对话中邀请赴宴并确认。"""
        entry_state = self.wait_for_banquet_entry()  # 抵达后识别出的物品面板或 NPC 邀约入口。
        if entry_state == "panel":
            self._log("检测到已在破阵设宴物品面板，跳过邀约流程")
            self.jump_to("process_banquet_items")

        self.click()
        self.wait(1500)

        if not self.wait_image_appear(
            self.BTN_MENKE_CONFIRM_INVITE,
            timeout_ms=self.BANQUET_CONFIRM_TIMEOUT_MS,
        ):
            self._raise_banquet_invite_failure(
                "未找到确认邀约按钮",
                "invite_confirm_missing",
            )
        self.click()
        self.wait(1500)

        if not self.wait_image_appear(
            self.TEXT_BANQUET_PANEL_TITLE,
            timeout_ms=self.BANQUET_PANEL_TIMEOUT_MS,
            threshold=self.BANQUET_PANEL_TITLE_THRESHOLD,
            roi=self.scale_roi(self.ROI_BANQUET_PANEL_TITLE),
        ):
            self._raise_banquet_invite_failure(
                "未进入破阵设宴物品面板",
                "item_panel_missing",
            )

    @step(retry=1, timeout_ms=240000)
    def process_banquet_items(self) -> None:
        """逐个处理破阵设宴面板中的八个任务物品。"""
        super().process_banquet_items()

    @step(retry=1, timeout_ms=30000)
    def start_banquet_if_ready(self) -> None:
        """处理八个槽位后，检查开始设宴按钮是否可用。"""
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

        self._log("完成验证：活动页仍存在破阵设宴入口，检查前往按钮")
        if not self.wait_find_image_in_roi(
            self.BTN_ACTIVITY_FORWARD,
            self.ROI_POZHEN_SHEYAN_ENTRY,
            timeout_ms=5000,
            description="活动页破阵设宴前往按钮",
        ):
            self._log("完成验证：入口存在但未找到前往按钮，默认不可继续邀约")
            return

        message = "完成验证：活动页仍可前往破阵设宴，任务未完成"
        if self._started_banquet:
            raise RuntimeError(message)
        self._log(message)

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"破阵设宴任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
