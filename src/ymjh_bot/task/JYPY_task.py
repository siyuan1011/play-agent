"""聚义平冤任务 - Python DSL 实现。"""

from __future__ import annotations

import time

from botCore import step

from ymjh_bot.ym_game_task import TaskSidebarStateError, YmGameTask


class JYPYTask(YmGameTask):
    """一梦江湖聚义平冤任务。"""

    task_key = "JYPY"
    task_name = "聚义平冤"
    task_description = "聚义平冤便捷组队并跟随完成任务"
    auto_recover_health = False
    RETURN_TO_SAFE_ZONE_ON_START = True
    DEFER_FOREGROUND_WAKE_TO_ON_START = True
    LEAVE_TEAM_ON_START = True
    STARTUP_CLOSE_SETTLE_WAIT_MS = 1000
    SAFE_ZONE_RETURN_FAILURE_LOG = "返回安全区未完成，保持当前主界面继续：{error}"

    BTN_ACTIVITY_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_activity_forward.png")
    BTN_DIALOG_NEXT = str(YmGameTask.TEMPLATES_DIR / "btn_dialog_next.png")
    TEXT_JYPY_SIDEBAR = str(YmGameTask.TEMPLATES_DIR / "text_jypy_sidebar_chapter.png")

    POINT_NPC_ACTION = (980, 465)
    POINT_NPC_DIALOG_CONFIRM = (1096, 466)
    POINT_NPC_QUICK_TEAM = (1096, 390)
    POINT_TEAM_AUTO_MATCH = (990, 669)
    POINT_TASK_LIST_SCROLL_START = (190, 520)
    POINT_TASK_LIST_SCROLL_END = (190, 220)

    ACTIVITY_FORWARD_THRESHOLD = 0.7
    SIDEBAR_TASK_THRESHOLD = 0.8
    TASK_FLOW_TIMEOUT_MS = 1800000
    TASK_FLOW_RETRY_WAIT_MS = 3000
    MATCH_WAIT_POLL_INTERVAL_MS = 2000
    MATCH_WAIT_HEARTBEAT_MS = 30000
    ARRIVE_MIN_WAIT_MS = 25000
    TASK_MISSING_CONFIRMATIONS = 3
    IDLE_TRACKER_CLICK_LIMIT = 5

    @step(retry=3, timeout_ms=30000)
    def open_hangdang_activity(self) -> None:
        """打开活动界面并切换到行当页签。"""
        self.open_hangdang_activity_panel()

    @step(retry=3, timeout_ms=30000)
    def start_auto_pathfinding(self) -> None:
        """点击活动页聚义平冤前往按钮。"""
        if not self.is_activity_forward_visible(timeout_ms=5000):
            self._log("未找到活动页聚义平冤前往按钮，默认今日入口已消失")
            self.jump_to("verify_completion")

        self._log("点击活动页聚义平冤前往按钮")
        self.click(offset=0)
        self.wait(1500)

    @step(retry=1, timeout_ms=None)
    def wait_arrive_npc(self) -> None:
        """等待自动寻路到达聚义平冤 NPC。"""
        self._log(f"聚义平冤前往后保底等待 {self.ARRIVE_MIN_WAIT_MS}ms")
        self.wait(self.ARRIVE_MIN_WAIT_MS)
        self.wait_auto_pathfinding(timeout_ms=600000)
        self.wait(1000)

    @step(retry=3, timeout_ms=180000)
    def enter_quick_team(self) -> None:
        """对话 NPC 并进入聚义平冤便捷组队。"""
        if not self.is_quick_team_panel_open():
            self.open_quick_team_from_npc_menu()
        self.start_quick_match()

    @step(retry=0, timeout_ms=None)
    def wait_team_follow(self) -> None:
        """无限等待匹配入队弹框，并确认进入队伍跟随。"""
        self.wait_for_team_follow_confirm()

    @step(retry=1, timeout_ms=TASK_FLOW_TIMEOUT_MS)
    def run_jypy_flow(self) -> None:
        """等待并推动聚义平冤任务追踪，直到任务栏追踪消失。"""
        deadline = self._make_deadline(self.TASK_FLOW_TIMEOUT_MS)
        missing_confirmations = 0
        idle_tracker_clicks = 0

        while not self._is_deadline_expired(deadline):
            if self.click_dialog_next_if_visible():
                missing_confirmations = 0
                idle_tracker_clicks = 0
                continue

            self.wait_auto_pathfinding(timeout_ms=30000)

            if self.click_dialog_next_if_visible():
                missing_confirmations = 0
                idle_tracker_clicks = 0
                continue

            if self.click_jypy_task_from_sidebar(max_scrolls=2, required=False):
                missing_confirmations = 0
                idle_tracker_clicks += 1
                if idle_tracker_clicks >= self.IDLE_TRACKER_CLICK_LIMIT:
                    self._log("连续点击聚义任务追踪未出现新流程，执行一轮自动战斗/交互保底")
                    self.auto_battle(interval_ms=250)
                    idle_tracker_clicks = 0
                continue

            idle_tracker_clicks = 0
            missing_confirmations += 1
            self._log(f"任务栏暂未找到聚义平冤追踪，继续确认完成状态 ({missing_confirmations})")
            if missing_confirmations >= self.TASK_MISSING_CONFIRMATIONS:
                self._log("聚义平冤任务追踪已稳定消失")
                return
            self.wait(self.TASK_FLOW_RETRY_WAIT_MS)

        debug_path = self.save_debug_screenshot("jypy_task_flow_timeout")
        raise RuntimeError(f"聚义平冤任务执行流程超时，已保存截图：{debug_path}")

    @step(retry=1, timeout_ms=60000)
    def verify_completion(self) -> None:
        """验证活动-行当页聚义平冤入口已消失。"""
        self.close_all_panels()
        self.collapse_chat_if_open()
        self.open_hangdang_activity_panel(wait_after_category_ms=2000)

        if self.is_activity_forward_visible(timeout_ms=3000):
            debug_path = self.save_debug_screenshot("jypy_verify_entry_still_visible")
            raise RuntimeError(f"聚义平冤完成验证失败：活动入口仍存在，已保存截图：{debug_path}")

        self._log("完成验证：活动-行当页聚义平冤入口已消失")

    def leave_team_if_present(self) -> None:
        """Leave any existing team, but do not fail when the role is already unteamed."""
        try:
            self.leave_team(timeout_ms=5000, wait_after_click_ms=1000)
        except Exception as exc:
            self._log(f"退队检查未完成，按未组队继续：{exc}")

    def open_hangdang_activity_panel(self, *, wait_after_category_ms: int = 1500) -> None:
        """Open and verify Activity - Hangdang through the shared safe flow."""
        self.open_activity_panel(
            "行当",
            wait_after_open_ms=2500,
            wait_after_category_ms=wait_after_category_ms,
        )

    def is_activity_forward_visible(self, *, timeout_ms: int) -> bool:
        """Return whether the JYPY forward button is visible in Activity - Hangdang."""
        return self.wait_find_image_in_roi(
            self.BTN_ACTIVITY_FORWARD,
            (560, 410, 240, 130),
            timeout_ms=timeout_ms,
            description="活动页聚义平冤前往按钮",
            threshold=self.ACTIVITY_FORWARD_THRESHOLD,
            interval_ms=500,
        )

    def open_quick_team_from_npc_menu(self) -> None:
        """Click through the NPC dialogue/menu until convenient teaming is requested."""
        self._log("点击 NPC 对话入口")
        self.click_point(self.POINT_NPC_ACTION[0], self.POINT_NPC_ACTION[1], offset=0)
        self.wait(1500)

        if self.click_template_if_available(
            self.BTN_OK,
            timeout_ms=2500,
            description="NPC 确认按钮",
            threshold=0.85,
            roi=(900, 400, 360, 130),
            wait_after_click_ms=1500,
        ):
            self._log("已确认 NPC 初始对话")

        self._log("再次点击 NPC 对话入口，打开聚义平冤菜单")
        self.click_point(self.POINT_NPC_ACTION[0], self.POINT_NPC_ACTION[1], offset=0)
        self.wait(1500)

        self._log("点击 NPC 菜单便捷组队")
        self.click_point(self.POINT_NPC_QUICK_TEAM[0], self.POINT_NPC_QUICK_TEAM[1], offset=0)
        self.wait(2000)

    def start_quick_match(self) -> None:
        """Select JYPY in convenient teaming and start auto match."""
        if not self.is_quick_team_panel_open():
            self._log("NPC 便捷组队未直接打开列表，改用通用便捷组队入口")
            self.quick_team(self.TEAM_TARGET_JUYI_PINGYUAN, wait_after_click_ms=1000)
            return

        self.select_quick_team_target(self.TEAM_TARGET_JUYI_PINGYUAN, wait_after_click_ms=800)
        if not self.click_template_if_available(
            self.BTN_TEAM_AUTO_MATCH,
            timeout_ms=5000,
            description="聚义平冤自动匹配按钮",
            threshold=0.9,
            roi=self.ROI_TEAM_QUICK_ACTIONS,
            wait_after_click_ms=1000,
        ):
            self._log("未识别到聚义平冤自动匹配按钮，使用固定坐标点击")
            self.click_point(self.POINT_TEAM_AUTO_MATCH[0], self.POINT_TEAM_AUTO_MATCH[1], offset=0)
            self.wait(1000)

        self.confirm_center_modal_ok_if_visible("便捷组队自动匹配")
        self._log("已开始聚义平冤便捷组队自动匹配")

    def wait_for_team_follow_confirm(self) -> None:
        """Wait indefinitely for the team-follow confirmation dialog."""
        last_heartbeat_at = 0.0
        while not self.is_stopped():
            if self.confirm_center_modal_ok_if_visible("入队跟随确认", wait_after_click_ms=2000):
                self._log("已确认入队跟随")
                return

            now = time.perf_counter()
            if last_heartbeat_at <= 0 or (now - last_heartbeat_at) * 1000 >= self.MATCH_WAIT_HEARTBEAT_MS:
                self._debug("聚义平冤匹配入队等待中...")
                last_heartbeat_at = now
            self.wait(self.MATCH_WAIT_POLL_INTERVAL_MS)

        raise RuntimeError("聚义平冤匹配等待被停止")

    def click_jypy_task_from_sidebar(self, *, max_scrolls: int, required: bool) -> bool:
        """Find and click the JYPY tracker in the left task sidebar."""
        if not self.find_jypy_task_in_sidebar(max_scrolls=max_scrolls):
            if required:
                self._log("任务栏未找到聚义平冤任务")
            return False

        self._log("点击任务栏聚义平冤任务")
        self.click(offset=0)
        self.wait(1500)
        self.confirm_center_modal_ok_if_visible("任务栏聚义平冤弹框")
        return True

    def find_jypy_task_in_sidebar(self, max_scrolls: int = 5) -> bool:
        """Find the JYPY tracker in task/sidebar tabs, scrolling if needed."""
        self.collapse_chat_if_open()
        panel_errors: list[TaskSidebarStateError] = []
        for panel in ("任务", "江湖"):
            try:
                self.switch_task_panel(panel, timeout_ms=6000, threshold=0.8)
            except TaskSidebarStateError as exc:
                self._log(f"切换任务面板 {panel} 失败：{exc}")
                panel_errors.append(exc)
                continue

            for attempt in range(max_scrolls + 1):
                if self.wait_find_image_in_roi(
                    self.TEXT_JYPY_SIDEBAR,
                    (40, 135, 330, 430),
                    timeout_ms=1200,
                    description="任务栏聚义平冤追踪",
                    threshold=self.SIDEBAR_TASK_THRESHOLD,
                    interval_ms=300,
                ):
                    return True

                if attempt < max_scrolls:
                    self._log(f"任务栏未找到聚义平冤追踪，向下翻页 {attempt + 1}/{max_scrolls}")
                    self.scroll_task_list_down()

        if panel_errors:
            raise TaskSidebarStateError(
                "聚义平冤任务不存在前置检查不完整：至少一个任务页签未成功确认并扫描"
            ) from panel_errors[0]
        return False

    def scroll_task_list_down(self) -> None:
        """Scroll the task list down to reveal lower tracker entries."""
        start = self.POINT_TASK_LIST_SCROLL_START
        end = self.POINT_TASK_LIST_SCROLL_END
        self.swipe(start[0], start[1], end[0], end[1], duration_ms=350)
        self.wait(800)

    def click_dialog_next_if_visible(self) -> bool:
        """Click the lower-right dialogue continue arrow when visible."""
        return self.click_template_if_available(
            self.BTN_DIALOG_NEXT,
            timeout_ms=600,
            description="聚义平冤剧情继续箭头",
            threshold=0.85,
            roi=(1180, 640, 100, 80),
            wait_after_click_ms=1200,
        )

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"聚义平冤任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
