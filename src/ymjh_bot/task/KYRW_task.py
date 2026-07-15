"""课业任务 - Python DSL 实现。"""

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class KyrwTask(YmGameTask):
    """一梦江湖悟禅课业任务。"""

    task_key = "KYRW"
    task_name = "课业任务"
    task_description = "悟禅课业任务自动执行"

    BTN_WUCHAN_ACTIVITY_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_activity_wuchan_forward.png")
    BTN_WUCHAN_COURSE_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_panel_course_forward.png")
    BTN_NPC_WUCHAN = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_npc_wuchan.png")
    BTN_NPC_COURSE = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_npc_course.png")
    BTN_NPC_ACTION_TEMPLATES = [BTN_NPC_WUCHAN, BTN_NPC_COURSE]
    BTN_DIALOG_NEXT = str(YmGameTask.TEMPLATES_DIR / "btn_dialog_next.png")
    TEXT_COURSE_SIDEBAR = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_course_sidebar.png")
    TEXT_COURSE_SHIMEN_SIDEBAR = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_shimen_sidebar.png")
    COURSE_SIDEBAR_TEMPLATES = [TEXT_COURSE_SIDEBAR, TEXT_COURSE_SHIMEN_SIDEBAR]
    TEXT_EXISTING_COURSE_TOAST = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_existing_course_toast.png")
    TEXT_COURSE_COMPLETE = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_complete.png")
    ROUTE_MALL = str(YmGameTask.TEMPLATES_DIR / "route_mall.png")
    ROUTE_STALL = str(YmGameTask.TEMPLATES_DIR / "route_stall.png")
    BTN_ONE_KEY_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_one_key_submit.png")
    BTN_VIEW_ALL_SERVER = str(YmGameTask.TEMPLATES_DIR / "btn_view_all_server.png")
    BTN_MALL_BUY_AREA = str(YmGameTask.TEMPLATES_DIR / "btn_mall_buy_area.png")
    BTN_BUY = str(YmGameTask.TEMPLATES_DIR / "btn_buy.png")
    BTN_MODAL_CANCEL = str(YmGameTask.TEMPLATES_DIR / "btn_modal_cancel.png")

    # 固定坐标点 (设计分辨率 1280x720 下)
    POINT_WUCHAN_ACTIVITY_FORWARD = (215, 276)
    POINT_WUCHAN_COURSE_FORWARD = (276, 498)
    POINT_NPC_TALK = (1005, 465)
    POINT_NPC_ACTION = (1100, 465)
    POINT_COURSE_CARD_DEFAULT = (354, 265)
    POINT_TASK_LIST_SCROLL_START = (190, 360)
    POINT_TASK_LIST_SCROLL_END = (190, 170)
    POINT_DIALOG_NEXT = (1230, 690)
    POINT_MALL_BUY = (949, 663)
    POINT_COMPLETE_OK = (854, 508)

    ROI_ACTIVITY_WUCHAN = (120, 210, 220, 115)
    ROI_WUCHAN_COURSE = (175, 440, 205, 110)
    ROI_NPC_ACTION = (900, 400, 360, 130)
    ROI_TASK_LIST = (40, 135, 330, 430)
    ROI_EXISTING_COURSE_TOAST = (450, 300, 420, 90)
    ROI_DIALOG_NEXT = (1180, 640, 100, 80)
    ROI_ROUTE_PANEL = (330, 120, 880, 520)
    ROI_TRADE_ACTION = (520, 440, 330, 120)
    ROI_MALL_BUY = (800, 610, 290, 100)
    ROI_ONE_KEY_SUBMIT = (900, 330, 340, 160)
    ROI_COMPLETE = (350, 250, 600, 220)
    ROI_REFRESH_CANCEL = (300, 450, 250, 120)

    TASK_FLOW_TIMEOUT_MS = 900000
    MAX_ITEM_ACQUIRE_ROUNDS = 60
    MAX_STALL_BUY_RETRIES = 2
    MAX_ALL_SERVER_BUY_RETRIES = 2
    MAX_NPC_ACCEPT_RECOVERY = 2
    TRADE_BUY_THRESHOLD = 0.7
    IDLE_ACTION_LIMIT = 4

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._item_acquire_rounds = 0
        self._npc_accept_recoveries = 0

    def reset_startup_state(self) -> None:
        """Reset per-run counters before the shared startup cleanup."""
        self._item_acquire_rounds = 0
        self._npc_accept_recoveries = 0

    def after_startup_panel_close(self) -> None:
        """Close the course completion dialog after each startup cleanup pass."""
        self.close_completion_dialog_if_visible()

    @step(retry=1, timeout_ms=60000)
    def resume_existing_course(self) -> None:
        """接取前优先查找已布置的课业任务。"""
        self.close_all_panels(timeout_ms=3000)
        if self.click_course_task_from_sidebar(max_scrolls=5, required=False):
            self._log("检测到已布置课业任务，跳过接取流程")
            self.jump_to("run_course_flow")

        self._log("未发现已布置课业任务，继续活动接取流程")
        self.close_all_panels(timeout_ms=3000)

    @step(retry=3, timeout_ms=30000)
    def open_wuchan_activity(self) -> None:
        """打开活动-江湖并点击悟禅前往。"""
        self.open_activity_panel(
            "江湖",
            wait_after_category_ms=2000,
        )

        if self.wait_find_image_in_roi(
            self.BTN_WUCHAN_ACTIVITY_FORWARD,
            self.ROI_ACTIVITY_WUCHAN,
            timeout_ms=5000,
            description="活动页悟禅前往按钮",
            threshold=0.9,
        ):
            self.click(offset=0)
        else:
            self._log("未识别到活动页悟禅前往按钮，使用固定坐标点击")
            self.click_point(self.POINT_WUCHAN_ACTIVITY_FORWARD[0], self.POINT_WUCHAN_ACTIVITY_FORWARD[1], offset=0)
        self.wait(1500)

    @step(retry=3, timeout_ms=30000)
    def enter_course_from_wuchan_panel(self) -> None:
        """在悟禅面板点击课业前往。"""
        if self.wait_find_image_in_roi(
            self.BTN_WUCHAN_COURSE_FORWARD,
            self.ROI_WUCHAN_COURSE,
            timeout_ms=10000,
            description="悟禅面板课业前往按钮",
            threshold=0.9,
        ):
            self.click(offset=0)
        else:
            self._log("未识别到悟禅面板课业前往按钮，使用固定坐标点击")
            self.click_point(self.POINT_WUCHAN_COURSE_FORWARD[0], self.POINT_WUCHAN_COURSE_FORWARD[1], offset=0)
        self.wait(1500)

    @step(retry=1, timeout_ms=None)
    def auto_pathfinding_to_npc(self) -> None:
        """等待接取前自动寻路结束。"""
        self.wait_auto_pathfinding()

    @step(retry=3, timeout_ms=180000)
    def accept_or_open_course_panel(self) -> None:
        """在普照对话中进入课业面板，并处理已布置课业提示。"""
        if not self.click_npc_course_action_if_visible(timeout_ms=6000, wait_after_click_ms=1200):
            self._log("未识别到NPC悟禅按钮，使用固定坐标点击课业动作")

        self.click_point(self.POINT_NPC_ACTION[0], self.POINT_NPC_ACTION[1], offset=0)
        self.wait(2000)

        if self.try_continue_after_course_panel_opened():
            return

        self._log("未进入课业面板，尝试先点击NPC对话按钮")
        self.click_point(self.POINT_NPC_TALK[0], self.POINT_NPC_TALK[1], offset=0)
        self.wait(1500)
        self.click_point(self.POINT_NPC_ACTION[0], self.POINT_NPC_ACTION[1], offset=0)
        self.wait(2000)

        if self.try_continue_after_course_panel_opened():
            return

        self.close_all_panels(timeout_ms=3000)
        if self.click_course_task_from_sidebar(max_scrolls=5, required=False):
            self.jump_to("run_course_flow")

        if self._npc_accept_recoveries < self.MAX_NPC_ACCEPT_RECOVERY:
            self._npc_accept_recoveries += 1
            self._log("进入课业面板失败，重新从悟禅活动入口接取")
            self.close_all_panels(timeout_ms=3000)
            self.jump_to("open_wuchan_activity")

        self._log("进入课业面板后未检测到可执行课业，按当前不可接取或已完成处理")
        self.jump_to_end()

    def try_continue_after_course_panel_opened(self) -> bool:
        """Continue once the course panel may have opened."""
        if self.cancel_refresh_confirm_if_visible():
            self.jump_to("resume_existing_course")

        if self.try_select_default_course_card():
            self.jump_to("run_course_flow")

        return False

    def click_npc_course_action_if_visible(
        self,
        *,
        timeout_ms: int,
        wait_after_click_ms: int = 1500,
    ) -> bool:
        """Click the NPC course action button when it is visible."""
        if not self.wait_find_image_in_roi(
            self.BTN_NPC_ACTION_TEMPLATES,
            self.ROI_NPC_ACTION,
            timeout_ms=timeout_ms,
            description="NPC 课业动作按钮",
            threshold=0.85,
        ):
            return False

        self._log("点击NPC课业动作按钮")
        self.click(offset=0)
        self.wait(wait_after_click_ms)
        return True

    @step(retry=1, timeout_ms=TASK_FLOW_TIMEOUT_MS)
    def run_course_flow(self) -> None:
        """循环执行当前课业，处理对话、寻路、物品获取和提交。"""
        deadline = self._make_deadline(self.TASK_FLOW_TIMEOUT_MS)
        idle_actions = 0

        while not self._is_deadline_expired(deadline):
            if self.close_completion_dialog_if_visible():
                return

            if self.cancel_refresh_confirm_if_visible():
                idle_actions = 0
                continue

            if self.handle_submit_panel_if_visible():
                idle_actions = 0
                continue

            if self.handle_acquire_route_panel_if_visible():
                idle_actions = 0
                continue

            if self.handle_trade_panel_if_visible():
                idle_actions = 0
                continue

            if self.click_npc_course_action_if_visible(timeout_ms=600):
                idle_actions = 0
                continue

            if self.click_dialog_next_if_visible():
                idle_actions = 0
                continue

            self.wait_auto_pathfinding(timeout_ms=30000)

            if self.close_completion_dialog_if_visible():
                return

            if self.handle_submit_panel_if_visible():
                idle_actions = 0
                continue

            if self.handle_acquire_route_panel_if_visible():
                idle_actions = 0
                continue

            if self.handle_trade_panel_if_visible():
                idle_actions = 0
                continue

            if self.click_npc_course_action_if_visible(timeout_ms=600):
                idle_actions = 0
                continue

            if self.click_dialog_next_if_visible():
                idle_actions = 0
                continue

            self.close_transient_panels(max_attempts=2)
            if self.click_course_task_from_sidebar(max_scrolls=2, required=False):
                idle_actions += 1
                if idle_actions >= self.IDLE_ACTION_LIMIT:
                    raise RuntimeError("连续点击课业追踪未出现新流程")
                continue

            self._log("任务栏未找到课业追踪，默认课业执行完成")
            return

        raise RuntimeError("课业任务执行流程超时")

    @step(retry=1, timeout_ms=30000)
    def verify_completion(self) -> None:
        """验证课业追踪已消失。"""
        self.close_all_panels()
        if self.find_course_task_in_sidebar(max_scrolls=2, panels=("任务", "江湖")):
            raise RuntimeError("课业完成验证失败：任务栏仍存在课业追踪")
        self._log("完成验证：任务栏已无课业追踪")

    def try_select_default_course_card(self) -> bool:
        """Click the visible course card and handle the current-course toast if it appears."""
        if not self.find_image_once([self.BTN_CLOSE, self.BTN_PANE_CLOSE], threshold=0.8):
            return False

        self._log("点击默认课业卡片")
        self.click_point(self.POINT_COURSE_CARD_DEFAULT[0], self.POINT_COURSE_CARD_DEFAULT[1], offset=0)
        self.wait(1000)

        if self.find_image_once(
            self.TEXT_EXISTING_COURSE_TOAST,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_EXISTING_COURSE_TOAST),
        ):
            self._log("检测到已有当前布置课业，关闭面板后继续执行")
            self.close_all_panels(timeout_ms=3000)
            return True

        self.close_all_panels(timeout_ms=3000)
        return self.click_course_task_from_sidebar(max_scrolls=5, required=False)

    def click_course_task_from_sidebar(self, *, max_scrolls: int, required: bool) -> bool:
        """Find and click the course task in the left sidebar."""
        if not self.find_course_task_in_sidebar(max_scrolls=max_scrolls, panels=("任务", "江湖")):
            if required:
                self._log("任务栏未找到课业任务")
            return False

        self._log("点击任务栏课业任务")
        self.click(offset=0)
        self.wait(1500)
        return True

    def find_course_task_in_sidebar(self, *, max_scrolls: int, panels: tuple[str, ...]) -> bool:
        """Find the course task text in any supported task panel."""
        self.ensure_left_task_sidebar_visible()
        for panel in panels:
            try:
                self.switch_task_panel(panel, timeout_ms=2500, threshold=0.8)
            except Exception as exc:
                self._log(f"切换任务面板 {panel} 失败：{exc}")
                continue

            for attempt in range(max_scrolls + 1):
                if self.wait_find_image_in_roi(
                    self.COURSE_SIDEBAR_TEMPLATES,
                    self.ROI_TASK_LIST,
                    timeout_ms=1000,
                    description="任务栏课业任务",
                    threshold=0.85,
                    interval_ms=300,
                ):
                    return True

                if attempt < max_scrolls:
                    self._log(f"任务栏未找到课业任务，向下翻页 {attempt + 1}/{max_scrolls}")
                    self.scroll_task_list_down()

        return False

    def ensure_left_task_sidebar_visible(self) -> None:
        """Open only the compact left task sidebar without changing panels."""
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

    def handle_acquire_route_panel_if_visible(self) -> bool:
        """Handle supported item acquisition route panels."""
        if not self.is_acquire_route_panel_visible():
            return False

        self._item_acquire_rounds += 1
        if self._item_acquire_rounds > self.MAX_ITEM_ACQUIRE_ROUNDS:
            raise RuntimeError("课业物品获取次数超过安全上限")

        self._log(f"检测到课业物品获取途径面板，开始第 {self._item_acquire_rounds} 次获取")
        if self.try_mall_route():
            return True
        if self.try_stall_route():
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
        if self.click_course_task_from_sidebar(max_scrolls=2, required=False):
            return self.wait_acquire_route_panel_visible(timeout_ms=5000)
        return False

    def wait_acquire_route_panel_visible(self, timeout_ms: int = 3000) -> bool:
        """Wait until any supported acquire route appears."""
        return self.wait_find_image_in_roi(
            [self.ROUTE_MALL, self.ROUTE_STALL],
            self.ROI_ROUTE_PANEL,
            timeout_ms=timeout_ms,
            description="课业物品获取途径面板",
            threshold=0.8,
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
            self.click(offset=0)
            self.wait(1500)
            self.confirm_purchase_if_needed()

        return True

    def handle_submit_panel_if_visible(self) -> bool:
        """Submit the final task item when the one-key submit panel appears."""
        if not self.click_template_if_available(
            self.BTN_ONE_KEY_SUBMIT,
            timeout_ms=600,
            description="课业一键提交按钮",
            roi=self.ROI_ONE_KEY_SUBMIT,
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            return False

        self.confirm_submit_if_needed()
        self.wait(1500)
        return True

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

    def close_completion_dialog_if_visible(self) -> bool:
        """Close the final course completion dialog when it is visible."""
        if not self.find_image(
            self.TEXT_COURSE_COMPLETE,
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
        self.click(offset=0)
        self.wait(wait_after_click_ms)
        return True

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"课业任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
