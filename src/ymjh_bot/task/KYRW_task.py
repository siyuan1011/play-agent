"""课业任务 - Python DSL 实现。"""

from botCore import step

from ymjh_bot.ym_game_task import TaskSidebarStateError, YmGameTask


class KYRWTask(YmGameTask):
    """一梦江湖课业任务。"""

    task_key = "KYRW"
    task_name = "课业任务"
    task_description = "课业任务自动执行"

    BTN_KEYE_ACTIVITY_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_forward.png")
    BTN_KEYE_ENTRY_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_panel_keye_forward.png")
    BTN_NPC_KEYE_ACTION_TEMPLATES = [
        str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_npc_wuchan.png"),
        str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_npc_keye.png"),
    ]
    BTN_DIALOG_NEXT = str(YmGameTask.TEMPLATES_DIR / "btn_dialog_next.png")
    BTN_KEYE_USE = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_shiyong.png")
    TEXT_KEYE_PREFIX = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_keye.png")
    TEXT_ZHISHA_PREFIX = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_zhisha.png")
    KEYE_SIDEBAR_TEMPLATES = [
        TEXT_KEYE_PREFIX,
        TEXT_ZHISHA_PREFIX,
    ]
    TEXT_EXISTING_KEYE_TOAST = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_existing_keye_toast.png")
    TEXT_KEYE_COMPLETE = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_complete.png")
    ROUTE_MALL = str(YmGameTask.TEMPLATES_DIR / "route_mall.png")
    ROUTE_STALL = str(YmGameTask.TEMPLATES_DIR / "route_stall.png")
    BTN_ONE_KEY_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_one_key_submit.png")
    BTN_VIEW_ALL_SERVER = str(YmGameTask.TEMPLATES_DIR / "btn_view_all_server.png")
    BTN_MALL_BUY_AREA = str(YmGameTask.TEMPLATES_DIR / "btn_mall_buy_area.png")
    BTN_BUY = str(YmGameTask.TEMPLATES_DIR / "btn_buy.png")
    BTN_MODAL_CANCEL = str(YmGameTask.TEMPLATES_DIR / "btn_modal_cancel.png")

    # 固定坐标点 (设计分辨率 1280x720 下)
    POINT_KEYE_ACTIVITY_FORWARD = (215, 276)
    POINT_KEYE_ENTRY_FORWARD = (276, 498)
    POINT_NPC_TALK = (1005, 465)
    POINT_NPC_ACTION = (1100, 465)
    POINT_KEYE_CARD_DEFAULT = (354, 265)
    POINT_TASK_LIST_SCROLL_START = (190, 360)
    POINT_TASK_LIST_SCROLL_END = (190, 170)
    POINT_DIALOG_NEXT = (1230, 690)
    POINT_MALL_BUY = (949, 663)
    POINT_COMPLETE_OK = (854, 508)

    ROI_KEYE_ACTIVITY_ENTRY = (120, 210, 220, 115)
    ROI_KEYE_ENTRY = (175, 440, 205, 110)
    ROI_NPC_ACTION = (900, 400, 360, 130)
    ROI_TASK_LIST = (40, 135, 330, 430)
    ROI_EXISTING_KEYE_TOAST = (450, 300, 420, 90)
    ROI_DIALOG_NEXT = (1180, 640, 100, 80)
    ROI_DIALOG_CONFIRM = (900, 400, 360, 120)
    ROI_ROUTE_PANEL = (330, 120, 880, 520)
    ROI_TRADE_ACTION = (520, 440, 330, 120)
    ROI_MALL_BUY = (800, 610, 290, 100)
    ROI_ONE_KEY_SUBMIT = (900, 330, 340, 240)
    ROI_COMPLETE = (350, 250, 600, 220)
    ROI_REFRESH_CANCEL = (300, 450, 250, 120)

    TASK_FLOW_TIMEOUT_MS = 900000
    AUTO_PATHFIND_TO_NPC_TIMEOUT_MS = 120000
    AUTO_PATHFIND_TO_NPC_ATTEMPTS = 2
    ENTER_KEYE_STEP_TIMEOUT_MS = 390000
    MAX_ITEM_ACQUIRE_ROUNDS = 60
    MAX_STALL_BUY_RETRIES = 2
    MAX_ALL_SERVER_BUY_RETRIES = 2
    MAX_NPC_ACCEPT_RECOVERY = 2
    TRADE_BUY_THRESHOLD = 0.7
    KEYE_FLOW_IDLE_WAIT_MS = 1000
    KEYE_TASK_MISSING_CONFIRMATIONS = 3
    KEYE_FLOW_STATE_HANDLED = "handled"
    KEYE_FLOW_STATE_IDLE = "idle"

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._item_acquire_rounds = 0
        self._npc_accept_recoveries = 0

    def reset_startup_state(self) -> None:
        """Reset per-run counters before the shared startup cleanup."""
        self._item_acquire_rounds = 0
        self._npc_accept_recoveries = 0

    def after_startup_panel_close(self) -> None:
        """Close the keye completion dialog after each startup cleanup pass."""
        self.close_keye_completion_dialog_if_visible()

    @step(retry=1, timeout_ms=60000)
    def resume_existing_keye(self) -> None:
        """接取前优先查找已布置的课业任务。"""
        self.close_all_panels(timeout_ms=0)
        if self.click_keye_task_from_sidebar(max_scrolls=5, required=False):
            self._log("检测到已布置课业任务，跳过接取流程")
            self.jump_to("run_keye_flow")

        self._log("未发现已布置课业任务，继续活动接取流程")

    @step(retry=3, timeout_ms=30000)
    def open_keye_activity(self) -> None:
        """打开活动-江湖并点击课业活动入口。"""
        self.open_activity_panel(
            "江湖",
            wait_after_category_ms=2000,
        )

        if self.wait_image_appear(
            self.BTN_KEYE_ACTIVITY_FORWARD,
            timeout_ms=5000,
            threshold=0.9,
            roi=self.scale_roi(self.ROI_KEYE_ACTIVITY_ENTRY),
        ):
            self.click(offset=0)
        else:
            self._log("未识别到活动页课业入口，使用固定坐标点击")
            self.click_point(
                self.POINT_KEYE_ACTIVITY_FORWARD[0],
                self.POINT_KEYE_ACTIVITY_FORWARD[1],
                offset=0,
            )
        self.wait(1500)

    @step(retry=0, timeout_ms=ENTER_KEYE_STEP_TIMEOUT_MS)
    def enter_keye_from_activity_panel(self) -> None:
        """在课业活动面板点击课业前往，并等待自动寻路结束。"""
        if self.wait_image_appear(
            self.BTN_KEYE_ENTRY_FORWARD,
            timeout_ms=10000,
            threshold=0.9,
            roi=self.scale_roi(self.ROI_KEYE_ENTRY),
        ):
            self.click(offset=0)
        else:
            self._log("未识别到课业面板前往按钮，使用固定坐标点击")
            self.click_point(
                self.POINT_KEYE_ENTRY_FORWARD[0],
                self.POINT_KEYE_ENTRY_FORWARD[1],
                offset=0,
            )
        self.wait(1500)

        self._log("等待接取前自动寻路结束")
        for attempt in range(1, self.AUTO_PATHFIND_TO_NPC_ATTEMPTS + 1):
            if self.wait_auto_pathfinding(timeout_ms=self.AUTO_PATHFIND_TO_NPC_TIMEOUT_MS):
                self._log("接取前自动寻路已结束")
                return
            if attempt < self.AUTO_PATHFIND_TO_NPC_ATTEMPTS:
                self._log(
                    "接取前自动寻路尚未结束，"
                    f"重试等待 {attempt + 1}/{self.AUTO_PATHFIND_TO_NPC_ATTEMPTS}"
                )

        self._log("接取前自动寻路等待超时")
        raise RuntimeError("接取前自动寻路等待超时")

    @step(retry=3, timeout_ms=180000)
    def accept_or_open_keye_panel(self) -> None:
        """在普照对话中进入课业面板，并处理已布置课业提示。"""
        if not self.click_npc_keye_action_if_visible(timeout_ms=6000, wait_after_click_ms=1200):
            self._log("未识别到NPC课业动作按钮，使用固定坐标点击课业动作")

        self.click_point(self.POINT_NPC_ACTION[0], self.POINT_NPC_ACTION[1], offset=0)
        self.wait(2000)

        if self.try_continue_after_keye_panel_opened():
            return

        self._log("未进入课业面板，尝试先点击NPC对话按钮")
        self.click_point(self.POINT_NPC_TALK[0], self.POINT_NPC_TALK[1], offset=0)
        self.wait(1500)
        self.click_point(self.POINT_NPC_ACTION[0], self.POINT_NPC_ACTION[1], offset=0)
        self.wait(2000)

        if self.try_continue_after_keye_panel_opened():
            return

        self.close_all_panels(timeout_ms=3000)
        if self.click_keye_task_from_sidebar(max_scrolls=5, required=False):
            self.jump_to("run_keye_flow")

        if self._npc_accept_recoveries < self.MAX_NPC_ACCEPT_RECOVERY:
            self._npc_accept_recoveries += 1
            self._log("进入课业面板失败，重新从课业活动入口接取")
            self.close_all_panels(timeout_ms=3000)
            self.jump_to("open_keye_activity")

        raise RuntimeError("进入课业面板后未检测到可执行课业，且接取恢复次数已耗尽")

    def try_continue_after_keye_panel_opened(self) -> bool:
        """Continue once the keye panel may have opened."""
        if self.cancel_refresh_confirm_if_visible():
            self.jump_to("resume_existing_keye")

        if self.try_select_default_keye_card():
            self.jump_to("run_keye_flow")

        return False

    def click_npc_keye_action_if_visible(
        self,
        *,
        timeout_ms: int,
        wait_after_click_ms: int = 1500,
    ) -> bool:
        """Click the NPC keye action button when it is visible."""
        if not self.wait_image_appear(
            self.BTN_NPC_KEYE_ACTION_TEMPLATES,
            timeout_ms=timeout_ms,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_NPC_ACTION),
        ):
            return False

        self._log("点击NPC课业动作按钮")
        self.click(offset=0)
        self.wait(wait_after_click_ms)
        return True

    def _handle_keye_flow_state_once(self) -> str:
        """Handle one stable keye screen and return its resulting state."""
        if self.close_keye_completion_dialog_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.cancel_refresh_confirm_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.click_keye_use_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.handle_submit_panel_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.handle_acquire_route_panel_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.handle_trade_panel_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.click_dialog_confirm_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.click_npc_keye_action_if_visible(timeout_ms=600):
            return self.KEYE_FLOW_STATE_HANDLED
        if self.click_dialog_next_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        return self.KEYE_FLOW_STATE_IDLE

    @step(retry=1, timeout_ms=TASK_FLOW_TIMEOUT_MS)
    def run_keye_flow(self) -> None:
        """循环执行当前课业，处理对话、寻路、物品获取和提交。"""
        deadline = self._make_deadline(self.TASK_FLOW_TIMEOUT_MS)
        missing_confirmations = 0

        while not self._is_deadline_expired(deadline):
            if not self.wait_auto_pathfinding(timeout_ms=30000):
                self._debug("课业自动寻路或过图尚未稳定，继续等待")
                continue

            state = self._handle_keye_flow_state_once()
            if state == self.KEYE_FLOW_STATE_HANDLED:
                missing_confirmations = 0
                continue

            if self.click_keye_task_from_sidebar(max_scrolls=2, required=False):
                missing_confirmations = 0
                continue

            missing_confirmations += 1
            self._log(
                "任务栏暂未找到课业追踪，继续确认完成状态 "
                f"({missing_confirmations}/{self.KEYE_TASK_MISSING_CONFIRMATIONS})"
            )
            if missing_confirmations >= self.KEYE_TASK_MISSING_CONFIRMATIONS:
                self._log("课业追踪已稳定消失，进入完成验证")
                return

            remaining_ms = self._remaining_ms(deadline)
            if remaining_ms > 0:
                self.wait(min(self.KEYE_FLOW_IDLE_WAIT_MS, remaining_ms))

        debug_path = self.save_debug_screenshot("kyrw_keye_flow_timeout")
        raise RuntimeError(f"课业任务执行流程超时，已保存截图：{debug_path}")

    @step(retry=1, timeout_ms=60000)
    def verify_completion(self) -> None:
        """验证活动页的课业入口已消失。"""
        self.close_all_panels()
        self.open_activity_panel(
            "江湖",
            wait_after_category_ms=2000,
        )

        if self.wait_image_appear(
            self.BTN_KEYE_ACTIVITY_FORWARD,
            timeout_ms=5000,
            threshold=0.9,
            roi=self.scale_roi(self.ROI_KEYE_ACTIVITY_ENTRY),
        ):
            self._log("完成验证：活动页仍存在课业入口，继续接取课业")
            self.jump_to("open_keye_activity")

        self._log("完成验证：活动页课业入口已消失")

    def try_select_default_keye_card(self) -> bool:
        """Click the visible keye card and handle the existing-keye toast if it appears."""
        if not self.find_image_once([self.BTN_CLOSE, self.BTN_PANE_CLOSE], threshold=0.8):
            return False

        self._log("点击默认课业卡片")
        self.click_point(self.POINT_KEYE_CARD_DEFAULT[0], self.POINT_KEYE_CARD_DEFAULT[1], offset=0)
        self.wait(1000)

        if self.click_dialog_next_if_visible():
            self._log("课业卡片已进入剧情，继续执行课业流程")
            return True

        if self.find_image_once(
            self.TEXT_EXISTING_KEYE_TOAST,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_EXISTING_KEYE_TOAST),
        ):
            self._log("检测到已有当前布置课业，关闭面板后继续执行")
            self.close_all_panels(timeout_ms=3000)
            return True

        self.close_all_panels(timeout_ms=3000)
        return self.click_keye_task_from_sidebar(max_scrolls=5, required=False)

    def click_keye_task_from_sidebar(self, *, max_scrolls: int, required: bool) -> bool:
        """Find and click the keye task in the left sidebar."""
        if not self.find_keye_task_in_sidebar(max_scrolls=max_scrolls):
            if required:
                self._log("任务栏未找到课业任务")
            return False

        self._log("点击任务栏课业任务")
        self.click(offset=0)
        self.wait(1500)
        return True

    def find_keye_task_in_sidebar(self, *, max_scrolls: int) -> bool:
        """Find the keye task text in the Jianghu task panel."""
        self.ensure_left_task_sidebar_visible()
        self._confirm_keye_sidebar_jianghu()

        for attempt in range(max_scrolls + 1):
            if self.wait_image_appear(
                self.KEYE_SIDEBAR_TEMPLATES,
                timeout_ms=1000,
                threshold=0.85,
                interval_ms=300,
                roi=self.scale_roi(self.ROI_TASK_LIST),
            ):
                return True

            if attempt < max_scrolls:
                self._log(f"任务栏未找到课业任务，向下翻页 {attempt + 1}/{max_scrolls}")
                self.scroll_task_list_down()
                self._confirm_keye_sidebar_jianghu()

        return False

    def _confirm_keye_sidebar_jianghu(self) -> None:
        """Confirm that keye sidebar scanning remains on the Jianghu tab."""
        try:
            self.switch_task_panel("江湖", timeout_ms=6000, threshold=0.8)
        except TaskSidebarStateError as exc:
            self._log(f"切换任务面板 江湖 失败：{exc}")
            raise TaskSidebarStateError(
                "课业任务不存在前置检查不完整：江湖任务页签未成功确认并扫描"
            ) from exc

    def ensure_left_task_sidebar_visible(self) -> None:
        """Compatibility wrapper around the shared verified sidebar opener."""
        self.ensure_task_sidebar_open(timeout_ms=6000, threshold=0.85)

    def scroll_task_list_down(self) -> None:
        """Scroll the task list down to reveal lower entries."""
        start = self.POINT_TASK_LIST_SCROLL_START
        end = self.POINT_TASK_LIST_SCROLL_END
        self.swipe(start[0], start[1], end[0], end[1], duration_ms=350)
        self.wait(800)

    def handle_acquire_route_panel_if_visible(self) -> bool:
        """Handle supported item acquisition route panels."""
        if not self.is_acquire_route_panel_visible():
            return False

        self._item_acquire_rounds += 1
        if self._item_acquire_rounds > self.MAX_ITEM_ACQUIRE_ROUNDS:
            raise RuntimeError("课业物品获取次数超过安全上限")

        self._log(f"检测到课业物品获取途径面板，开始第 {self._item_acquire_rounds} 次获取")
        if self.try_mall_route():
            self.handle_submit_panel_if_visible(timeout_ms=1500)
            return True
        if self.try_stall_route():
            self.handle_submit_panel_if_visible(timeout_ms=1500)
            return True

        self.close_transient_panels()
        raise RuntimeError("课业物品未找到支持的获取途径")

    def is_acquire_route_panel_visible(self) -> bool:
        """Return whether any supported item acquisition route appears."""
        return self.find_image(
            [self.ROUTE_MALL, self.ROUTE_STALL],
            threshold=0.8,
            roi=self.scale_roi(self.ROI_ROUTE_PANEL),
        )

    def ensure_acquire_route_panel_open(self) -> bool:
        """Ensure the acquire-route panel is currently visible."""
        if self.is_acquire_route_panel_visible():
            return True
        if self.click_keye_task_from_sidebar(max_scrolls=2, required=False):
            return self.wait_acquire_route_panel_visible(timeout_ms=5000)
        return False

    def wait_acquire_route_panel_visible(self, timeout_ms: int = 3000) -> bool:
        """Wait until any supported acquire route appears."""
        return self.wait_image_appear(
            [self.ROUTE_MALL, self.ROUTE_STALL],
            timeout_ms=timeout_ms,
            threshold=0.8,
            roi=self.scale_roi(self.ROI_ROUTE_PANEL),
        )

    def try_mall_route(self) -> bool:
        """Buy the selected task item from mall using the default quantity."""
        if not self.ensure_acquire_route_panel_open():
            return False
        if not self.click_template_if_available(
            self.ROUTE_MALL,
            timeout_ms=800,
            description="商城购买路径",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.85,
            wait_after_click_ms=2000,
        ):
            return False

        if not self.buy_from_mall_default_quantity():
            self._log("商城未找到默认购买按钮")
            self.close_transient_panels()
            return False

        return True

    def buy_from_mall_default_quantity(self) -> bool:
        """Click the mall buy area once without changing item quantity."""
        if self.click_template_if_available(
            self.BTN_MALL_BUY_AREA,
            timeout_ms=5000,
            description="商城默认数量购买按钮",
            roi=self.ROI_MALL_BUY,
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            return True

        self._log("未识别到商城默认数量购买按钮，使用固定坐标点击")
        self.click_point(self.POINT_MALL_BUY[0], self.POINT_MALL_BUY[1], offset=0)
        self.wait(1500)
        return True

    def try_stall_route(self) -> bool:
        """Buy the selected task item from local stall or all-server stall."""
        if not self.ensure_acquire_route_panel_open():
            return False
        if not self.click_template_if_available(
            self.ROUTE_STALL,
            timeout_ms=800,
            description="摆摊购买路径",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.8,
            wait_after_click_ms=2500,
        ):
            return False

        for _ in range(self.MAX_STALL_BUY_RETRIES):
            if self.buy_from_current_trade_panel("摆摊购买按钮", timeout_ms=2500):
                return True

        if not self.click_template_if_available(
            self.BTN_VIEW_ALL_SERVER,
            timeout_ms=2500,
            description="查看全服按钮",
            roi=self.ROI_TRADE_ACTION,
            threshold=0.85,
            wait_after_click_ms=2500,
        ):
            self._log("摆摊未找到商品，且未出现查看全服按钮")
            self.close_transient_panels()
            return False

        for _ in range(self.MAX_ALL_SERVER_BUY_RETRIES):
            if self.buy_from_current_trade_panel("全服摆摊购买按钮", timeout_ms=3000):
                return True

        self._log("本服/全服摆摊均未找到可购买商品")
        self.close_transient_panels()
        raise RuntimeError("本服/全服摆摊均未找到可购买商品")

    def handle_trade_panel_if_visible(self) -> bool:
        """Handle an already-open trade panel."""
        if self.buy_from_current_trade_panel("自动打开的交易购买按钮", timeout_ms=600):
            self.handle_submit_panel_if_visible(timeout_ms=1500)
            return True

        if not self.click_template_if_available(
            self.BTN_VIEW_ALL_SERVER,
            timeout_ms=600,
            description="自动打开的查看全服按钮",
            roi=self.ROI_TRADE_ACTION,
            threshold=0.85,
            wait_after_click_ms=2500,
        ):
            return False

        if self.buy_from_current_trade_panel("自动打开的全服摆摊购买按钮", timeout_ms=3000):
            self.handle_submit_panel_if_visible(timeout_ms=1500)
            return True

        self._log("自动打开的全服摆摊未找到可购买商品")
        self.close_transient_panels()
        return True

    def buy_from_current_trade_panel(self, description: str, *, timeout_ms: int) -> bool:
        """Click Buy in the current trade panel and confirm the secondary prompt if needed."""
        if not self.click_template_if_available(
            self.BTN_BUY,
            timeout_ms=timeout_ms,
            description=description,
            roi=self.ROI_TRADE_ACTION,
            threshold=self.TRADE_BUY_THRESHOLD,
            wait_after_click_ms=1500,
        ):
            return False

        confirmed = self.confirm_purchase_if_needed()
        if not confirmed and self.wait_image_appear(
            self.BTN_BUY,
            timeout_ms=800,
            threshold=self.TRADE_BUY_THRESHOLD,
            interval_ms=300,
            roi=self.scale_roi(self.ROI_TRADE_ACTION),
        ):
            self._log("购买按钮点击后仍可见，重试点击")
            self.click(offset=0)
            self.wait(1500)
            self.confirm_purchase_if_needed()

        return True

    def handle_submit_panel_if_visible(self, *, timeout_ms: int = 600) -> bool:
        """Submit the final task item when the one-key submit panel appears."""
        if not self.click_template_if_available(
            self.BTN_ONE_KEY_SUBMIT,
            timeout_ms=timeout_ms,
            description="课业一键提交按钮",
            roi=self.ROI_ONE_KEY_SUBMIT,
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            return False

        self.confirm_submit_if_needed()
        self.wait(1500)
        return True

    def click_dialog_confirm_if_visible(self) -> bool:
        """Click the required dialogue confirm button before the generic next arrow."""
        return self.click_template_if_available(
            self.BTN_OK,
            timeout_ms=600,
            description="课业剧情确定按钮",
            roi=self.ROI_DIALOG_CONFIRM,
            threshold=0.85,
            wait_after_click_ms=1500,
        )

    def click_dialog_next_if_visible(self) -> bool:
        """Click the lower-right story/dialogue next arrow when visible."""
        if not self.click_template_if_available(
            self.BTN_DIALOG_NEXT,
            timeout_ms=600,
            description="剧情继续箭头",
            roi=self.ROI_DIALOG_NEXT,
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            return False
        return True

    def click_keye_use_if_visible(self) -> bool:
        """Click the keye Use button when it appears anywhere on screen."""
        return self.click_template_if_available(
            self.BTN_KEYE_USE,
            timeout_ms=600,
            description="课业使用按钮",
            threshold=0.85,
            wait_after_click_ms=1500,
        )

    def close_keye_completion_dialog_if_visible(self) -> bool:
        """Close the final keye completion dialog when it is visible."""
        if not self.find_image(
            self.TEXT_KEYE_COMPLETE,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_COMPLETE),
        ):
            return False

        self._log("检测到课业完成对话，点击确定")
        self.click_point(self.POINT_COMPLETE_OK[0], self.POINT_COMPLETE_OK[1], offset=0)
        self.wait(1000)
        return True

    def cancel_refresh_confirm_if_visible(self) -> bool:
        """Cancel the Flying Snow Sword refresh prompt to avoid consuming items."""
        if not self.find_image_once(
            self.BTN_MODAL_CANCEL,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_REFRESH_CANCEL),
        ):
            return False

        self._log("检测到课业刷新消耗确认，点击取消")
        self.click(offset=0)
        self.wait(1000)
        return True

    def confirm_purchase_if_needed(self) -> bool:
        """Confirm a purchase prompt if present."""
        return self.click_template_if_available(
            self.BTN_MODAL_OK,
            timeout_ms=2000,
            description="购买二次确认按钮",
            threshold=0.85,
            wait_after_click_ms=2000,
        )

    def confirm_submit_if_needed(self) -> bool:
        """Confirm a task-submit prompt if present."""
        return self.click_template_if_available(
            [self.BTN_MODAL_OK, self.BTN_OK],
            timeout_ms=3000,
            description="课业提交确认按钮",
            threshold=0.85,
            wait_after_click_ms=1500,
        )

    def close_transient_panels(self, max_attempts: int = 4) -> bool:
        """Close temporary panels after acquisition actions."""
        closed = False
        for _ in range(max_attempts):
            if self.wait_image_appear([self.BTN_CLOSE, self.BTN_PANE_CLOSE], timeout_ms=800, threshold=0.8):
                self.click(offset=0)
                self.wait(1000)
                closed = True
                continue
            break
        return closed

    def click_template_if_available(
        self,
        template: str | list[str],
        *,
        timeout_ms: int | None,
        description: str,
        threshold: float = 0.8,
        wait_after_click_ms: int = 1000,
        roi: tuple[int, int, int, int] | None = None,
    ) -> bool:
        """Click a template if it appears within an optional design-resolution ROI."""
        scaled_roi = None if roi is None else self.scale_roi(roi)
        found = self.wait_image_appear(
            template,
            timeout_ms=timeout_ms,
            threshold=threshold,
            roi=scaled_roi,
        )

        if not found:
            return False

        self._log(f"点击{description}")
        self.click(offset=0)
        self.wait(wait_after_click_ms)
        return True

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"课业任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
