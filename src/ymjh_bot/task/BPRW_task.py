"""帮派任务 - Python DSL 实现。"""

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class BPRWTask(YmGameTask):
    """一梦江湖帮派任务。"""

    task_key = "BPRW"
    task_name = "帮派任务"
    task_description = "帮派任务自动执行"

    BTN_BANGPAI_TASK_ENTRY = str(YmGameTask.TEMPLATES_DIR / "btn_bangpai_task_entry.png")
    BTN_BANGPAI_TASK_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_activity_forward.png")
    BTN_BANGPAI_TASK_ACCEPT = str(YmGameTask.TEMPLATES_DIR / "btn_bangpai_task_accept.png")
    TITLE_BANGPAI_LIST = str(YmGameTask.TEMPLATES_DIR / "text_BPRW_bangpai_list_title.png")
    TEXT_BANGPAI = str(YmGameTask.TEMPLATES_DIR / "text_bangpai.png")
    TEXT_BANGPAI_DAILY = str(YmGameTask.TEMPLATES_DIR / "text_bangpai_daily.png")
    SIDEBAR_BANGPAI_TASK_TEMPLATES = [TEXT_BANGPAI, TEXT_BANGPAI_DAILY]
    ROUTE_WAREHOUSE = str(YmGameTask.TEMPLATES_DIR / "route_bangpai_warehouse.png")
    ROUTE_STALL = str(YmGameTask.TEMPLATES_DIR / "route_stall.png")
    BTN_WAREHOUSE_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_warehouse_submit.png")
    BTN_VIEW_ALL_SERVER = str(YmGameTask.TEMPLATES_DIR / "btn_view_all_server.png")
    BTN_ONE_KEY_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_bangpai_one_key_submit.png")
    BTN_BUY = str(YmGameTask.TEMPLATES_DIR / "btn_buy.png")
    TEXT_TASK_COMPLETE = str(YmGameTask.TEMPLATES_DIR / "text_bangpai_task_complete.png")

    # 固定坐标点 (设计分辨率 1280x720 下)
    ROI_BANGPAI_TASK_CARD = (130, 230, 240, 140)
    ROI_BANGPAI_LIST_TITLE = (95, 110, 230, 90)
    ROI_TASK_LIST = (40, 135, 330, 430)
    ROI_ROUTE_PANEL = (720, 120, 480, 500)
    ROI_WAREHOUSE_SUBMIT = (760, 530, 230, 115)
    ROI_TRADE_ACTION = (520, 440, 330, 120)
    ROI_ONE_KEY_SUBMIT = (900, 330, 340, 160)
    ROI_TASK_COMPLETE = (40, 570, 650, 90)
    ROI_PURCHASE_DIALOG_CLOSE = (850, 130, 170, 110)
    POINT_TASK_LIST_SCROLL_START = (190, 520)
    POINT_TASK_LIST_SCROLL_END = (190, 220)
    POINT_DIALOG_NEXT = (1230, 690)

    CLOSE_ALL_MAX_ATTEMPTS = 8
    TASK_FLOW_TIMEOUT_MS = 900000
    TASK_FLOW_RETRY_WAIT_MS = 3000
    TASK_IDLE_CLICK_LIMIT = 3
    TRADE_BUY_THRESHOLD = 0.7

    def before_start(self) -> None:
        """Avoid waking foreground power-saving mode before close_all owns that check."""
        if not self.auto_ensure_game_started:
            return
        if self.is_game_foreground():
            self._log("检测到游戏已在前台，省电唤醒交给 close_all")
            return
        self.ensure_game_started()

    def on_start(self) -> None:
        """任务开始前准备。"""
        self._log("=" * 40)
        self._log("帮派任务开始")
        self._log("=" * 40)

    @step(retry=1, timeout_ms=30000)
    def close_all(self) -> None:
        """关闭所有弹窗，回到游戏主界面。"""
        self.close_purchase_dialog_if_needed()
        self.close_all_panels(max_attempts=self.CLOSE_ALL_MAX_ATTEMPTS)
        self.close_completion_dialog_if_visible()
        if self.wake_from_power_saving_if_needed():
            self.close_purchase_dialog_if_needed()
            self.close_all_panels(max_attempts=self.CLOSE_ALL_MAX_ATTEMPTS)
            self.close_completion_dialog_if_visible()

    def close_purchase_dialog_if_needed(self) -> bool:
        """Close a leftover PvP extra-challenge purchase dialog before generic panel closing."""
        if not self.find_image(
            [self.BTN_CLOSE, self.BTN_PANE_CLOSE],
            threshold=0.85,
            roi=self.scale_roi(self.ROI_PURCHASE_DIALOG_CLOSE),
        ):
            return False

        self._log("关闭额外挑战次数购买弹窗")
        self.click(offset=0)
        self.wait(1000)
        return True

    @step(retry=1, timeout_ms=60000)
    def resume_existing_task(self) -> None:
        """接取前优先查找已接取的帮派任务。"""
        self.close_all_panels(timeout_ms=3000)
        if self.click_bangpai_task_from_sidebar(max_scrolls=5, required=False):
            self._log("检测到已接取帮派任务，跳过接取流程")
            self.jump_to("run_task_flow")

        self._log("未发现已接取帮派任务，关闭任务面板并继续接取流程")
        self.close_all_panels(timeout_ms=3000)

    @step(retry=3, timeout_ms=30000)
    def open_bangpai_activity(self) -> None:
        """打开活动界面并切换到帮派页签。"""
        self.close_all_panels(timeout_ms=3000)
        self.open_activity_panel("帮派", wait_after_open_ms=3000)

    @step(retry=3, timeout_ms=30000)
    def start_auto_pathfinding(self) -> None:
        """点击帮派任务前往按钮，进入自动寻路。"""
        if not self.wait_find_image_in_roi(
            self.BTN_BANGPAI_TASK_ENTRY,
            self.ROI_BANGPAI_TASK_CARD,
            timeout_ms=3000,
            description="活动页帮派任务入口",
        ):
            self._log("未找到帮派任务入口，默认帮派任务已完成")
            self.jump_to_end()

        if not self.wait_find_image_in_roi(
            self.BTN_BANGPAI_TASK_FORWARD,
            self.ROI_BANGPAI_TASK_CARD,
            timeout_ms=5000,
            description="活动页帮派任务前往按钮",
        ):
            raise RuntimeError("未找到活动页帮派任务前往按钮")
        self.click()
        self.wait(1500)

    @step(retry=1, timeout_ms=None)
    def auto_pathfinding(self) -> None:
        """等待接取前自动寻路结束。"""
        self.wait_auto_pathfinding()

    @step(retry=3, timeout_ms=180000)
    def accept_task(self) -> None:
        """接取帮派任务。"""
        if self.is_bangpai_list_visible():
            self._log("检测到当前未加入帮派，跳过帮派任务")
            self.jump_to_end()

        try:
            self.require_image(self.BTN_BANGPAI_TASK_ACCEPT, timeout_ms=120000, description="NPC 帮派任务按钮")
        except RuntimeError:
            if self.is_bangpai_list_visible():
                self._log("检测到当前未加入帮派，跳过帮派任务")
                self.jump_to_end()
            raise
        self.click()
        self.wait(1500)

        self.require_image(self.BTN_OK, timeout_ms=10000, description="帮派任务确认按钮")
        self.click()
        self.wait(1500)

    def is_bangpai_list_visible(self) -> bool:
        """Return whether the account is on the guild-join list instead of a guild task dialog."""
        return self.find_image(
            self.TITLE_BANGPAI_LIST,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_BANGPAI_LIST_TITLE),
        )

    @step(retry=3, timeout_ms=60000)
    def start_accepted_task(self) -> None:
        """接取后从任务栏启动帮派任务。"""
        if not self.click_bangpai_task_from_sidebar(max_scrolls=5, required=True):
            raise RuntimeError("未找到任务栏帮派任务")

    @step(retry=1, timeout_ms=TASK_FLOW_TIMEOUT_MS)
    def run_task_flow(self) -> None:
        """循环执行帮派任务，处理第五环任务物品。"""
        deadline = self._make_deadline(self.TASK_FLOW_TIMEOUT_MS)
        idle_task_clicks = 0
        missing_task_confirmations = 0
        while not self._is_deadline_expired(deadline):
            if self.close_completion_dialog_if_visible():
                return

            if self.handle_submit_panel_if_visible():
                idle_task_clicks = 0
                missing_task_confirmations = 0
                continue

            if self.handle_trade_panel_if_visible():
                idle_task_clicks = 0
                missing_task_confirmations = 0
                continue

            if self.handle_acquire_route_panel_if_visible():
                idle_task_clicks = 0
                missing_task_confirmations = 0
                continue

            self.wait_auto_pathfinding(timeout_ms=30000)

            if self.handle_submit_panel_if_visible():
                idle_task_clicks = 0
                missing_task_confirmations = 0
                continue

            if self.handle_trade_panel_if_visible():
                idle_task_clicks = 0
                missing_task_confirmations = 0
                continue

            if self.handle_acquire_route_panel_if_visible():
                idle_task_clicks = 0
                missing_task_confirmations = 0
                continue

            self.close_transient_panels(max_attempts=2)
            if self.click_bangpai_task_from_sidebar(max_scrolls=2, required=False):
                missing_task_confirmations = 0
                idle_task_clicks += 1
                if idle_task_clicks >= self.TASK_IDLE_CLICK_LIMIT:
                    self._log("连续点击左侧帮派任务未出现新流程，继续等待完成信号")
                    idle_task_clicks = 0
                    self.wait(self.TASK_FLOW_RETRY_WAIT_MS)
                continue

            idle_task_clicks = 0
            missing_task_confirmations += 1
            self._log(f"江湖任务栏暂未找到帮派任务，继续等待完成信号 ({missing_task_confirmations})")
            self.wait(self.TASK_FLOW_RETRY_WAIT_MS)

        raise RuntimeError("帮派任务执行流程超时：未检测到完成对话或明确任务追踪消失")

    def click_bangpai_task_from_sidebar(self, *, max_scrolls: int, required: bool) -> bool:
        """Find and click the BPRW task in the Jianghu task sidebar."""
        if not self.find_bangpai_task_in_sidebar(max_scrolls=max_scrolls):
            if required:
                self._log("任务栏未找到帮派任务")
            return False

        self._log("点击任务栏帮派任务")
        self.click()
        self.wait(1500)
        self.confirm_sidebar_task_popup_if_needed()
        return True

    def find_bangpai_task_in_sidebar(self, max_scrolls: int = 5) -> bool:
        """Find Bangpai in the current left task sidebar, scrolling down if needed."""
        self.switch_task_panel("江湖")
        for attempt in range(max_scrolls + 1):
            if self.wait_find_image_in_roi(
                self.SIDEBAR_BANGPAI_TASK_TEMPLATES,
                self.ROI_TASK_LIST,
                timeout_ms=1200,
                description="任务栏帮派任务或日常环",
                threshold=0.7,
                interval_ms=300,
            ):
                return True

            if attempt < max_scrolls:
                self._log(f"任务栏未找到帮派任务，向下翻页 {attempt + 1}/{max_scrolls}")
                self.scroll_task_list_down()

        return False

    def confirm_sidebar_task_popup_if_needed(self) -> bool:
        """Confirm transient prompts that can appear after clicking a sidebar tracker."""
        if not self.click_template_if_available(
            self.BTN_MODAL_OK,
            timeout_ms=2000,
            description="任务栏帮派任务弹框确定按钮",
            threshold=0.85,
            wait_after_click_ms=1000,
        ):
            return False
        return True

    def ensure_left_task_sidebar_visible(self) -> None:
        """Open only the compact left task sidebar without switching task panels."""
        if self.find_image(self.ICON_TASK_ACTIVE, threshold=0.8):
            return

        self._log("左侧任务栏未展开，点击主界面任务栏")
        self.click_point(self.POINT_MAIN_TASK[0], self.POINT_MAIN_TASK[1])
        self.wait(800)

    def scroll_task_list_down(self) -> None:
        """Scroll the task list down to reveal lower entries."""
        start = self.POINT_TASK_LIST_SCROLL_START
        end = self.POINT_TASK_LIST_SCROLL_END
        self.swipe(start[0], start[1], end[0], end[1], duration_ms=350)
        self.wait(800)

    def close_completion_dialog_if_visible(self) -> bool:
        """Close the final Bangpai completion dialog when it is visible."""
        if not self.find_image(
            self.TEXT_TASK_COMPLETE,
            threshold=0.9,
            roi=self.scale_roi(self.ROI_TASK_COMPLETE),
        ):
            return False

        self._log("检测到帮派任务完成对话，点击继续")
        self.click_point(self.POINT_DIALOG_NEXT[0], self.POINT_DIALOG_NEXT[1], offset=0)
        self.wait(1000)
        return True

    def handle_acquire_route_panel_if_visible(self) -> bool:
        """Handle the item acquisition panel with warehouse-first priority."""
        if not self.is_acquire_route_panel_visible():
            return False

        self._log("检测到帮派任务物品获取途径面板，优先尝试帮派仓库")
        if self.try_warehouse_route():
            return True

        self._log("帮派仓库无法提交，改走摆摊购买")
        if self.try_stall_route():
            return True

        self._log("帮派任务物品无法通过仓库或摆摊获取，关闭面板并结束本轮执行")
        self.close_transient_panels()
        self.jump_to_end()
        return True

    def handle_submit_panel_if_visible(self) -> bool:
        """Submit the final task item when the one-key submit panel appears."""
        if not self.click_template_if_available(
            self.BTN_ONE_KEY_SUBMIT,
            timeout_ms=600,
            description="帮派任务一键提交按钮",
            roi=self.ROI_ONE_KEY_SUBMIT,
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            return False

        self.confirm_submit_if_needed()
        self.wait_auto_pathfinding(timeout_ms=120000)
        return True

    def try_warehouse_route(self) -> bool:
        """Try to submit the requested item from gang warehouse."""
        if not self.ensure_acquire_route_panel_open():
            return False

        if not self.click_template_if_available(
            self.ROUTE_WAREHOUSE,
            timeout_ms=1000,
            description="帮派仓库获取途径",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.8,
            wait_after_click_ms=2000,
        ):
            return False

        if self.click_template_if_available(
            self.BTN_WAREHOUSE_SUBMIT,
            timeout_ms=3000,
            description="帮派仓库提交按钮",
            roi=self.ROI_WAREHOUSE_SUBMIT,
            threshold=0.85,
            wait_after_click_ms=2000,
        ):
            self.close_transient_panels()
            return True

        self._log("帮派仓库未找到可提交物品")
        self.close_transient_panels()
        return False

    def try_stall_route(self) -> bool:
        """Try to buy the requested item from stall or all-server stall."""
        if not self.ensure_acquire_route_panel_open():
            return False

        if not self.click_template_if_available(
            self.ROUTE_STALL,
            timeout_ms=1000,
            description="摆摊购买获取途径",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.8,
            wait_after_click_ms=2500,
        ):
            return False

        if self.buy_from_current_trade_panel("摆摊购买按钮", timeout_ms=4000):
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

        if self.buy_from_current_trade_panel("全服摆摊购买按钮", timeout_ms=5000):
            return True

        self._log("全服摆摊仍未找到可购买商品")
        self.close_transient_panels()
        return False

    def handle_trade_panel_if_visible(self) -> bool:
        """Handle a trade panel that the game opens automatically."""
        if self.buy_from_current_trade_panel("自动打开的交易购买按钮", timeout_ms=600):
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

        if self.buy_from_current_trade_panel("自动打开的全服摆摊购买按钮", timeout_ms=5000):
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
        if not confirmed and self.wait_find_image_in_roi(
            self.BTN_BUY,
            self.ROI_TRADE_ACTION,
            timeout_ms=800,
            description=f"{description}点击后仍可见",
            threshold=self.TRADE_BUY_THRESHOLD,
            interval_ms=300,
        ):
            self._log("购买按钮点击后仍可见，重试点击")
            self.click()
            self.wait(1500)
            self.confirm_purchase_if_needed()

        self.close_transient_panels()
        return True

    def ensure_acquire_route_panel_open(self) -> bool:
        """Ensure the task item acquisition route panel is visible."""
        if self.is_acquire_route_panel_visible():
            return True

        if self.click_bangpai_task_from_sidebar(max_scrolls=2, required=False):
            return self.wait_acquire_route_panel_visible(timeout_ms=5000)

        return False

    def wait_acquire_route_panel_visible(self, timeout_ms: int = 3000) -> bool:
        """Wait until any supported acquisition route appears."""
        return self.wait_find_image_in_roi(
            [self.ROUTE_WAREHOUSE, self.ROUTE_STALL],
            self.ROI_ROUTE_PANEL,
            timeout_ms=timeout_ms,
            description="帮派任务物品获取途径面板",
            threshold=0.8,
        )

    def is_acquire_route_panel_visible(self) -> bool:
        """Return whether the task item acquisition route panel is visible."""
        return self.find_image(
            [self.ROUTE_WAREHOUSE, self.ROUTE_STALL],
            threshold=0.8,
            roi=self.scale_roi(self.ROI_ROUTE_PANEL),
        )

    def confirm_purchase_if_needed(self) -> bool:
        """Confirm the secondary purchase prompt if present."""
        return self.click_template_if_available(
            self.BTN_MODAL_OK,
            timeout_ms=2000,
            description="购买二次确认按钮",
            threshold=0.85,
            wait_after_click_ms=2000,
        )

    def confirm_submit_if_needed(self) -> bool:
        """Confirm a secondary task-submit prompt if present."""
        return self.click_template_if_available(
            [self.BTN_MODAL_OK, self.BTN_OK],
            timeout_ms=3000,
            description="帮派任务提交确认按钮",
            threshold=0.85,
            wait_after_click_ms=1500,
        )

    def close_transient_panels(self, max_attempts: int = 4) -> bool:
        """Close temporary panels after item acquisition actions."""
        closed = False
        for _ in range(max_attempts):
            if self.wait_image_appear([self.BTN_CLOSE, self.BTN_PANE_CLOSE], timeout_ms=800, threshold=0.8):
                self.click()
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
        if roi is None:
            found = self.wait_image_appear(template, timeout_ms=timeout_ms, threshold=threshold)
        else:
            found = self.wait_find_image_in_roi(
                template,
                roi,
                timeout_ms=timeout_ms,
                description=description,
                threshold=threshold,
            )

        if not found:
            return False

        self._log(f"点击{description}")
        self.click()
        self.wait(wait_after_click_ms)
        return True

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"帮派任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
