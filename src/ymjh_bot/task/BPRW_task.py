"""帮派任务 - Python DSL 实现。"""

from botCore import step

from ymjh_bot.ym_game_task import TaskSidebarStateError, YmGameTask


class BPRWTask(YmGameTask):
    """一梦江湖帮派任务。"""

    task_key = "BPRW"
    task_name = "帮派任务"
    task_description = "帮派任务自动执行"

    BTN_BANGPAI_TASK_ENTRY = str(YmGameTask.TEMPLATES_DIR / "btn_bangpai_task_entry.png")
    BTN_BANGPAI_TASK_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_activity_forward.png")
    BTN_BANGPAI_TASK_ACCEPT = str(YmGameTask.TEMPLATES_DIR / "btn_bangpai_task_accept.png")
    TITLE_BANGPAI_LIST = str(YmGameTask.TEMPLATES_DIR / "text_BPRW_bangpai_list_title.png")
    TEXT_BANGPAI_FEAST_GUESTS = str(YmGameTask.TEMPLATES_DIR / "text_bangpai_feast_guests.png")
    TEXT_BANGPAI_CONSTRUCTION = str(YmGameTask.TEMPLATES_DIR / "text_bangpai_construction.png")
    TEXT_BANGPAI_SCOUT_ENEMY = str(YmGameTask.TEMPLATES_DIR / "text_bangpai_scout_enemy.png")
    TEXT_BANGPAI_EMERGENCY_RESCUE = str(
        YmGameTask.TEMPLATES_DIR / "text_bangpai_emergency_rescue.png"
    )
    TEXT_BANGPAI_JINLING_ESCORT = str(YmGameTask.TEMPLATES_DIR / "text_bangpai_jinling_escort.png")
    TEXT_BANGPAI_RETURN = str(YmGameTask.TEMPLATES_DIR / "text_bangpai_return.png")
    SIDEBAR_BANGPAI_TASK_TITLE_BY_TEMPLATE = {
        TEXT_BANGPAI_FEAST_GUESTS: "大宴宾客",
        TEXT_BANGPAI_CONSTRUCTION: "帮派建设",
        TEXT_BANGPAI_SCOUT_ENEMY: "刺探敌情",
        TEXT_BANGPAI_EMERGENCY_RESCUE: "紧急救援",
        TEXT_BANGPAI_JINLING_ESCORT: "金陵护送",
        TEXT_BANGPAI_RETURN: "回帮复命",
    }
    SIDEBAR_BANGPAI_TASK_TEMPLATES = list(SIDEBAR_BANGPAI_TASK_TITLE_BY_TEMPLATE)
    SIDEBAR_BANGPAI_RETURN_TITLE = "回帮复命"
    ROUTE_WAREHOUSE = str(YmGameTask.TEMPLATES_DIR / "route_bangpai_warehouse.png")
    ROUTE_MALL = str(YmGameTask.TEMPLATES_DIR / "route_mall.png")
    ROUTE_STALL = str(YmGameTask.TEMPLATES_DIR / "route_stall.png")
    BTN_WAREHOUSE_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_warehouse_submit.png")
    BTN_MALL_BUY_AREA = str(YmGameTask.TEMPLATES_DIR / "btn_mall_buy_area.png")
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
    ROI_MALL_BUY = (800, 610, 290, 100)
    ROI_TRADE_ACTION = (520, 440, 330, 120)
    ROI_ONE_KEY_SUBMIT = (900, 330, 340, 160)
    ROI_TASK_COMPLETE = (40, 570, 650, 90)
    ROI_PURCHASE_DIALOG_CLOSE = (850, 130, 170, 110)
    POINT_TASK_LIST_SCROLL_START = (190, 360)
    POINT_TASK_LIST_SCROLL_END = (190, 260)
    POINT_DIALOG_NEXT = (1230, 690)

    CLOSE_ALL_MAX_ATTEMPTS = 8
    DEFER_FOREGROUND_WAKE_TO_ON_START = True
    TASK_FLOW_TIMEOUT_MS = 900000
    TASK_TRANSITION_TIMEOUT_MS = 120000
    TASK_ENTRY_STEP_TIMEOUT_MS = 180000
    TASK_FLOW_RETRY_WAIT_MS = 3000
    SIDEBAR_TASK_CLICK_SETTLE_MS = 3000
    TASK_LIST_SCROLL_DURATION_MS = 1000
    TASK_LIST_SCROLL_SETTLE_MS = 500
    ACQUIRE_ROUTE_OPEN_SETTLE_MS = 3500
    FLOW_DETECTION_INTERVAL_MS = 1000
    TRADE_ACTION_SETTLE_MS = 2500
    TRADE_BUY_THRESHOLD = 0.7

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._warehouse_item_checked = False

    def reset_startup_state(self) -> None:
        """Reset per-run item acquisition state before startup cleanup."""
        self._warehouse_item_checked = False

    def after_startup_panel_close(self) -> None:
        """Close the Bangpai completion dialog after each startup cleanup pass."""
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

    @step(retry=1, timeout_ms=TASK_ENTRY_STEP_TIMEOUT_MS)
    def resume_existing_task(self) -> None:
        """接取前优先查找已接取的帮派任务。"""
        self.switch_task_panel("江湖")
        task_title = self.click_bangpai_task_from_sidebar(max_scrolls=5, required=False)
        if task_title is not None:
            self.handle_clicked_bangpai_task(task_title)
            self._log("检测到已接取帮派任务，跳过接取流程")
            self.jump_to("run_task_flow")
        self._log("未发现已接取帮派任务，继续接取流程")

    @step(retry=3, timeout_ms=30000)
    def open_bangpai_activity(self) -> None:
        """打开活动界面、切换帮派页签并点击帮派任务前往按钮。"""
        self.open_activity_panel("帮派", wait_after_open_ms=3000)
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

    @step(retry=1, timeout_ms=TASK_ENTRY_STEP_TIMEOUT_MS)
    def auto_pathfinding(self) -> None:
        """等待接取前自动寻路结束。"""
        self.wait_bangpai_task_transition("接取前自动寻路")

    @step(retry=3, timeout_ms=180000)
    def accept_task(self) -> None:
        """接取帮派任务。"""
        if self.is_bangpai_list_visible():
            self._log("检测到当前未加入帮派，跳过帮派任务")
            self.jump_to_end()

        try:
            if not self.wait_image_appear(
                self.BTN_BANGPAI_TASK_ACCEPT,
                timeout_ms=120000,
            ):
                raise RuntimeError("未找到NPC 帮派任务按钮")
        except RuntimeError:
            if self.is_bangpai_list_visible():
                self._log("检测到当前未加入帮派，跳过帮派任务")
                self.jump_to_end()
            raise
        self.click()
        self.wait(1500)

        if not self.wait_image_appear(self.BTN_OK, timeout_ms=10000):
            raise RuntimeError("未找到帮派任务确认按钮")
        self.click()
        self.wait(1500)

    def is_bangpai_list_visible(self) -> bool:
        """Return whether the account is on the guild-join list instead of a guild task dialog."""
        return self.find_image(
            self.TITLE_BANGPAI_LIST,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_BANGPAI_LIST_TITLE),
        )

    @step(retry=3, timeout_ms=TASK_ENTRY_STEP_TIMEOUT_MS)
    def start_accepted_task(self) -> None:
        """接取后从任务栏启动帮派任务。"""
        task_title = self.click_bangpai_task_from_sidebar(max_scrolls=5, required=True)
        if task_title is not None:
            self.handle_clicked_bangpai_task(task_title)
            return

        if self.is_bangpai_list_visible():
            self._log("检测到当前未加入帮派，跳过帮派任务")
        else:
            self._log("接取后未检测到帮派任务追踪，按当前不可执行或已完成处理")
        self.jump_to_end()

    @step(retry=1, timeout_ms=TASK_FLOW_TIMEOUT_MS)
    def run_task_flow(self) -> None:
        """循环执行帮派任务，处理第五环任务物品。"""
        deadline = self._make_deadline(self.TASK_FLOW_TIMEOUT_MS)
        while not self._is_deadline_expired(deadline):
            if self.close_completion_dialog_if_visible():
                return

            if (
                self.handle_submit_panel_if_visible()
                or self.handle_trade_panel_if_visible()
                or self.handle_acquire_route_panel_if_visible()
            ):
                self.wait(self.TASK_FLOW_RETRY_WAIT_MS)
                continue

            task_title = self.click_bangpai_task_from_sidebar(max_scrolls=2, required=False)
            if task_title is not None:
                self.handle_clicked_bangpai_task(task_title)
            else:
                self._log("有效江湖任务栏暂未找到帮派任务，等待后重试")
            self.wait(self.TASK_FLOW_RETRY_WAIT_MS)

        raise RuntimeError("帮派任务执行流程超时：未检测到完成对话或明确任务追踪消失")

    def click_bangpai_task_from_sidebar(
        self,
        *,
        max_scrolls: int,
        required: bool,
    ) -> str | None:
        """Find and click the BPRW task in the Jianghu task sidebar."""
        task_title = self.find_bangpai_task_in_sidebar(max_scrolls=max_scrolls)
        if task_title is None:
            if required:
                self._log("任务栏未找到帮派任务")
            return None

        self._log(f"点击任务栏帮派任务：{task_title}")
        self.click()
        self.wait(self.SIDEBAR_TASK_CLICK_SETTLE_MS)
        self.confirm_sidebar_task_popup_if_needed()
        return task_title

    def find_bangpai_task_in_sidebar(self, max_scrolls: int = 5) -> str | None:
        """在已确认的江湖任务侧栏中查找帮派任务。"""
        for attempt in range(max_scrolls + 1):
            self._ensure_bangpai_sidebar_ready()
            task_title = self.wait_bangpai_task_title_in_sidebar(
                timeout_ms=1200,
                threshold=0.8,
                interval_ms=300,
            )
            if task_title is not None:
                return task_title

            if attempt < max_scrolls:
                self._ensure_bangpai_sidebar_ready()
                self._log(
                    "已确认江湖任务侧栏，本页未找到帮派任务，"
                    f"向下翻页 {attempt + 1}/{max_scrolls}"
                )
                self.scroll_task_list_down()

        return None

    def _ensure_bangpai_sidebar_ready(self) -> None:
        """Confirm the Jianghu sidebar before any fixed-coordinate scan or scroll."""
        try:
            self.switch_task_panel("江湖", timeout_ms=6000, threshold=0.8)
        except TaskSidebarStateError as exc:
            self._log(f"帮派任务侧栏状态不可用，停止本轮扫描：{exc}")
            raise

    def wait_bangpai_task_title_in_sidebar(
        self,
        *,
        timeout_ms: int,
        threshold: float,
        interval_ms: int,
    ) -> str | None:
        """Return the exact BPRW sidebar title while preserving its click center."""
        deadline = self._make_deadline(timeout_ms)
        roi = self.scale_roi(self.ROI_TASK_LIST)
        while not self._is_deadline_expired(deadline):
            match = self._vision.match_template(
                self.screenshot(),
                self.SIDEBAR_BANGPAI_TASK_TEMPLATES,
                threshold=threshold,
                roi=roi,
            )
            self._last_match_score = match.score
            if match.found and match.center and match.template_path:
                task_title = self.SIDEBAR_BANGPAI_TASK_TITLE_BY_TEMPLATE.get(match.template_path)
                if task_title is not None:
                    self._last_match_center = match.center
                    self._debug(
                        f"识别到帮派任务标题：{task_title} "
                        f"(score={match.score:.3f}, center={match.center})"
                    )
                    return task_title

            self._last_match_center = None
            self.wait(interval_ms)

        self._log("已确认江湖任务侧栏，本页未找到帮派任务六标题")
        return None

    def handle_clicked_bangpai_task(self, task_title: str) -> bool:
        """Advance a clicked tracker according to its exact BPRW title."""
        self.wait_bangpai_task_transition(f"点击帮派任务“{task_title}”后")
        if task_title == self.SIDEBAR_BANGPAI_RETURN_TITLE:
            return self.handle_return_task_item_after_click()
        return True

    def wait_bangpai_task_transition(self, description: str) -> None:
        """Wait for pathfinding/loading to settle or fail before any sidebar operation."""
        if self.wait_auto_pathfinding(timeout_ms=self.TASK_TRANSITION_TIMEOUT_MS):
            return
        screenshot_path = self.save_debug_screenshot("bangpai_task_transition_timeout")
        raise RuntimeError(f"{description}等待自动寻路或过图结束超时，已保存截图：{screenshot_path}")

    def handle_return_task_item_after_click(self) -> bool:
        """Submit or acquire the final task item opened by Return to Guild."""
        self._log("检测到回帮复命，优先处理第五环任务物品")
        if self.handle_submit_panel_if_visible():
            return True
        if self.handle_trade_panel_if_visible():
            return True
        if self.handle_acquire_route_panel_if_visible():
            return True

        self._log("回帮复命已点击，暂未出现任务物品提交或获取面板")
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

    def scroll_task_list_down(self) -> None:
        """Drag the task list slowly to reveal lower entries without fling momentum."""
        start = self.POINT_TASK_LIST_SCROLL_START
        end = self.POINT_TASK_LIST_SCROLL_END
        self.swipe(
            start[0],
            start[1],
            end[0],
            end[1],
            duration_ms=self.TASK_LIST_SCROLL_DURATION_MS,
        )
        self.wait(self.TASK_LIST_SCROLL_SETTLE_MS)

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

        if not self._warehouse_item_checked:
            self._log("检测到帮派任务物品获取途径面板，优先尝试帮派仓库")
            if self.try_warehouse_route(route_panel_ready=True):
                return True
        else:
            self._log("本轮已检查帮派仓库，跳过重复检测")

        self._log("帮派仓库无法提交，改走商城购买")
        if self.try_mall_route():
            return True

        self._log("商城无法购买，改走摆摊购买")
        if self.try_stall_route():
            return True

        self._log("帮派任务物品无法通过仓库、商城或摆摊获取，关闭面板并结束本轮执行")
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
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
        ):
            return False

        self.confirm_submit_if_needed()
        self.wait_bangpai_task_transition("提交帮派任务物品后")
        return True

    def try_warehouse_route(self, *, route_panel_ready: bool = False) -> bool:
        """Try to submit the requested item from gang warehouse."""
        if not route_panel_ready and not self.ensure_acquire_route_panel_open():
            return False

        if not self.click_template_if_available(
            self.ROUTE_WAREHOUSE,
            timeout_ms=1000,
            description="帮派仓库获取途径",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.8,
            wait_after_click_ms=self.ACQUIRE_ROUTE_OPEN_SETTLE_MS,
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
        ):
            return False

        self._warehouse_item_checked = True
        if self.click_template_if_available(
            self.BTN_WAREHOUSE_SUBMIT,
            timeout_ms=3000,
            description="帮派仓库提交按钮",
            roi=self.ROI_WAREHOUSE_SUBMIT,
            threshold=0.85,
            wait_after_click_ms=2000,
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
        ):
            self.close_transient_panels()
            return True

        self._log("帮派仓库未找到可提交物品")
        self.close_transient_panels()
        return False

    def try_mall_route(self) -> bool:
        """Buy the requested item from mall using the default quantity."""
        if not self.ensure_acquire_route_panel_open():
            return False

        if not self.click_template_if_available(
            self.ROUTE_MALL,
            timeout_ms=1000,
            description="商城购买获取途径",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.8,
            wait_after_click_ms=self.ACQUIRE_ROUTE_OPEN_SETTLE_MS,
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
        ):
            return False

        if not self.click_template_if_available(
            self.BTN_MALL_BUY_AREA,
            timeout_ms=5000,
            description="商城默认数量购买按钮",
            roi=self.ROI_MALL_BUY,
            threshold=0.85,
            wait_after_click_ms=self.TRADE_ACTION_SETTLE_MS,
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
        ):
            self._log("商城未找到默认购买按钮")
            self.close_transient_panels()
            return False

        self.confirm_purchase_if_needed()
        self.close_transient_panels()
        return True

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
            wait_after_click_ms=self.ACQUIRE_ROUTE_OPEN_SETTLE_MS,
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
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
            wait_after_click_ms=self.ACQUIRE_ROUTE_OPEN_SETTLE_MS,
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
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
        if self.buy_from_current_trade_panel("自动打开的交易购买按钮", timeout_ms=1000):
            return True

        if not self.click_template_if_available(
            self.BTN_VIEW_ALL_SERVER,
            timeout_ms=1000,
            description="自动打开的查看全服按钮",
            roi=self.ROI_TRADE_ACTION,
            threshold=0.85,
            wait_after_click_ms=self.ACQUIRE_ROUTE_OPEN_SETTLE_MS,
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
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
            wait_after_click_ms=self.TRADE_ACTION_SETTLE_MS,
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
        ):
            return False

        confirmed = self.confirm_purchase_if_needed()
        if not confirmed and self.find_image(
            self.BTN_BUY,
            threshold=self.TRADE_BUY_THRESHOLD,
            roi=self.scale_roi(self.ROI_TRADE_ACTION),
        ):
            self._log("购买按钮点击后仍可见，重试点击")
            self.click()
            self.wait(self.TRADE_ACTION_SETTLE_MS)
            self.confirm_purchase_if_needed()

        self.close_transient_panels()
        return True

    def ensure_acquire_route_panel_open(self) -> bool:
        """Ensure the task item acquisition route panel is visible."""
        if self.is_acquire_route_panel_visible():
            return True

        task_title = self.click_bangpai_task_from_sidebar(max_scrolls=2, required=False)
        if task_title is None:
            return False

        self.wait_bangpai_task_transition(f"重新点击帮派任务“{task_title}”后")
        if task_title != self.SIDEBAR_BANGPAI_RETURN_TITLE:
            self._log(f"重新打开物品获取途径时任务已切换为：{task_title}")
            return False

        return self.wait_acquire_route_panel_visible(timeout_ms=5000)

    def wait_acquire_route_panel_visible(self, timeout_ms: int = 3000) -> bool:
        """Wait until any supported acquisition route appears."""
        return self.wait_find_image_in_roi(
            [self.ROUTE_WAREHOUSE, self.ROUTE_MALL, self.ROUTE_STALL],
            self.ROI_ROUTE_PANEL,
            timeout_ms=timeout_ms,
            description="帮派任务物品获取途径面板",
            threshold=0.8,
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
        )

    def is_acquire_route_panel_visible(self) -> bool:
        """Return whether the task item acquisition route panel is visible."""
        return self.find_image(
            [self.ROUTE_WAREHOUSE, self.ROUTE_MALL, self.ROUTE_STALL],
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
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
        )

    def confirm_submit_if_needed(self) -> bool:
        """Confirm a secondary task-submit prompt if present."""
        return self.click_template_if_available(
            [self.BTN_MODAL_OK, self.BTN_OK],
            timeout_ms=3000,
            description="帮派任务提交确认按钮",
            threshold=0.85,
            wait_after_click_ms=1500,
            interval_ms=self.FLOW_DETECTION_INTERVAL_MS,
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
        interval_ms: int = 500,
    ) -> bool:
        """Click a template if it appears within an optional design-resolution ROI."""
        if roi is None:
            found = self.wait_image_appear(
                template,
                timeout_ms=timeout_ms,
                threshold=threshold,
                interval_ms=interval_ms,
            )
        else:
            found = self.wait_find_image_in_roi(
                template,
                roi,
                timeout_ms=timeout_ms,
                description=description,
                threshold=threshold,
                interval_ms=interval_ms,
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
