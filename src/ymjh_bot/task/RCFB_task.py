"""日常副本任务 - Python DSL 实现。"""

from __future__ import annotations

import time

import cv2
import numpy as np

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class RichangFubenTask(YmGameTask):
    """一梦江湖日常副本任务。"""

    task_key = "RCFB"
    task_name = "日常副本"
    task_description = "匹配江湖纪事日常副本，跟随队伍完成后自动退队"
    auto_recover_health = False
    LEAVE_TEAM_ON_START = True
    STARTUP_CLOSE_SETTLE_WAIT_MS = 1000

    BTN_DIALOG_NEXT = str(YmGameTask.TEMPLATES_DIR / "btn_dialog_next.png")

    POINT_TEAM_AUTO_MATCH = (990, 669)
    POINT_QUICK_CATEGORY_JIANGHU = (180, 210)
    POINT_TASK_LIST_SCROLL_START = (190, 520)
    POINT_TASK_LIST_SCROLL_END = (190, 220)

    ROI_TASK_LIST = (40, 135, 330, 430)
    ROI_DIALOG_NEXT = (1180, 640, 100, 80)

    DUNGEON_TASK_THRESHOLD = 0.78
    DUNGEON_TASK_VERIFY_TIMEOUT_MS = 300000
    DUNGEON_TASK_POLL_INTERVAL_MS = 3000
    MATCH_WAIT_POLL_INTERVAL_MS = 2000
    MATCH_WAIT_HEARTBEAT_MS = 30000
    TASK_FLOW_TIMEOUT_MS = 1800000
    TASK_FLOW_RETRY_WAIT_MS = 3000
    TASK_MISSING_CONFIRMATIONS = 3
    SIDEBAR_SCROLL_COUNT = 2
    IDLE_TRACKER_CLICK_LIMIT = 6
    DEFER_FOREGROUND_WAKE_TO_ON_START = True

    @step(retry=3, timeout_ms=60000)
    def start_daily_match(self) -> None:
        """打开队伍面板，选择每日日常并点击自动匹配。"""
        self.start_daily_auto_match()

    @step(retry=0, timeout_ms=None)
    def wait_team_follow(self) -> None:
        """无限等待匹配入队弹框，并确认进入队伍跟随。"""
        self.wait_for_team_follow_confirm()

    @step(retry=0, timeout_ms=None)
    def wait_dungeon_task(self) -> None:
        """等待左侧任务-江湖出现副本任务；5 分钟未出现则退队重组。"""
        if self.wait_for_dungeon_task(timeout_ms=self.DUNGEON_TASK_VERIFY_TIMEOUT_MS):
            self._log("检测到江湖副本任务，确认已进入副本流程")
            return

        debug_path = self.save_debug_screenshot("rcfb_dungeon_task_missing")
        self._log(f"5 分钟未检测到江湖副本任务，退队重组；现场截图：{debug_path}")
        self.leave_team_if_present()
        self.start_daily_auto_match()
        self.jump_to("wait_team_follow")

    @step(retry=1, timeout_ms=TASK_FLOW_TIMEOUT_MS)
    def run_daily_raid_flow(self) -> None:
        """持续推动副本任务，直到任务追踪稳定消失。"""
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

            if self.click_dungeon_task_from_sidebar(max_scrolls=self.SIDEBAR_SCROLL_COUNT, required=False):
                missing_confirmations = 0
                idle_tracker_clicks += 1
                if idle_tracker_clicks >= self.IDLE_TRACKER_CLICK_LIMIT:
                    self._log("连续点击副本任务追踪未出现新流程，执行一轮自动战斗保底")
                    self.auto_battle(interval_ms=250)
                    idle_tracker_clicks = 0
                continue

            idle_tracker_clicks = 0
            missing_confirmations += 1
            self._log(f"任务栏暂未找到副本任务追踪，继续确认完成状态 ({missing_confirmations})")
            if missing_confirmations >= self.TASK_MISSING_CONFIRMATIONS:
                self._log("副本任务追踪已稳定消失，判断副本完成")
                return
            self.wait(self.TASK_FLOW_RETRY_WAIT_MS)

        debug_path = self.save_debug_screenshot("rcfb_task_flow_timeout")
        raise RuntimeError(f"日常副本任务执行流程超时，已保存截图：{debug_path}")

    @step(retry=1, timeout_ms=60000)
    def leave_team_after_completion(self) -> None:
        """副本完成后退出队伍。"""
        self.leave_team_if_present()
        self.close_all_panels(timeout_ms=3000)

    def start_daily_auto_match(self) -> None:
        """Select daily raid in convenient teaming and start auto match."""
        self.open_quick_team_panel(timeout_ms=5000, wait_after_click_ms=1000)
        self.select_daily_raid_quick_target(wait_after_click_ms=800)
        if not self.click_template_if_available(
            self.BTN_TEAM_AUTO_MATCH,
            timeout_ms=5000,
            description="日常副本自动匹配按钮",
            threshold=0.9,
            roi=self.ROI_TEAM_QUICK_ACTIONS,
            wait_after_click_ms=1000,
        ):
            self._log("未识别到日常副本自动匹配按钮，使用固定坐标点击")
            self.click_point(self.POINT_TEAM_AUTO_MATCH[0], self.POINT_TEAM_AUTO_MATCH[1], offset=0)
            self.wait(1000)

        self.confirm_center_modal_ok_if_visible("日常副本自动匹配", wait_after_click_ms=1000)
        self._log("已开始江湖纪事日常副本自动匹配")

    def select_daily_raid_quick_target(self, *, wait_after_click_ms: int = 800) -> None:
        """Select the Jianghu Chronicle category used by daily dungeon matching."""
        if not self.click_template_if_available(
            [
                self.TEXT_TEAM_QUICK_CATEGORY_JIANGHU,
                self.TEXT_TEAM_QUICK_CATEGORY_JIANGHU_ACTIVE,
            ],
            timeout_ms=3000,
            description="便捷组队分类 江湖纪事",
            threshold=0.82,
            roi=self.ROI_TEAM_QUICK_LEFT_PANEL,
            wait_after_click_ms=wait_after_click_ms,
        ):
            self._log("未识别到江湖纪事分类，使用固定坐标点击")
            self.click_point(
                self.POINT_QUICK_CATEGORY_JIANGHU[0],
                self.POINT_QUICK_CATEGORY_JIANGHU[1],
                offset=0,
            )
            self.wait(wait_after_click_ms)

        self._log("已选择便捷组队分类：江湖纪事")

    def wait_for_team_follow_confirm(self) -> None:
        """Wait indefinitely for the team-follow confirmation dialog."""
        last_heartbeat_at = 0.0
        while not self.is_stopped():
            if self.confirm_center_modal_ok_if_visible("入队跟随确认", wait_after_click_ms=2000):
                self._log("已确认入队跟随")
                return

            now = time.perf_counter()
            if last_heartbeat_at <= 0 or (now - last_heartbeat_at) * 1000 >= self.MATCH_WAIT_HEARTBEAT_MS:
                if self.confirm_already_in_team():
                    return
                self._debug("日常副本匹配入队等待中...")
                last_heartbeat_at = now
            self.wait(self.MATCH_WAIT_POLL_INTERVAL_MS)

        raise RuntimeError("日常副本匹配等待被停止")

    def confirm_already_in_team(self) -> bool:
        """Return true when auto matching has already put the role into a team."""
        try:
            self.open_team_panel(timeout_ms=2500, wait_after_click_ms=800)
            if not self.is_in_team():
                return False
            self._log("检测到已处于队伍中，继续进入副本任务检测")
            self.close_all_panels(timeout_ms=2000)
            return True
        except Exception as exc:
            self._log(f"队伍状态确认未完成，继续等待入队弹框：{exc}")
            return False

    def wait_for_dungeon_task(self, *, timeout_ms: int) -> bool:
        """Wait until the Jianghu task tab shows a daily dungeon tracker."""
        deadline = self._make_deadline(timeout_ms)
        while not self._is_deadline_expired(deadline):
            if self.find_dungeon_task_in_sidebar(max_scrolls=self.SIDEBAR_SCROLL_COUNT):
                return True
            self._log("暂未检测到江湖副本任务，继续等待入本...")
            self.wait(self.DUNGEON_TASK_POLL_INTERVAL_MS)
        return False

    def click_dungeon_task_from_sidebar(self, *, max_scrolls: int, required: bool) -> bool:
        """Find and click the daily dungeon tracker in the left task sidebar."""
        if not self.find_dungeon_task_in_sidebar(max_scrolls=max_scrolls):
            if required:
                self._log("任务栏未找到副本任务")
            return False

        self._log("点击任务栏副本任务")
        self.click(offset=0)
        self.wait(1500)
        self.confirm_center_modal_ok_if_visible("任务栏副本任务弹框")
        return True

    def find_dungeon_task_in_sidebar(self, max_scrolls: int = 2) -> bool:
        """Find the daily dungeon tracker in the task Jianghu tab, scrolling if needed."""
        self.collapse_chat_if_open()
        try:
            self.switch_task_panel("江湖", timeout_ms=2500, threshold=0.8)
        except Exception as exc:
            self._log(f"切换任务面板江湖失败：{exc}")
            return False

        for attempt in range(max_scrolls + 1):
            if self.find_dungeon_task_candidate():
                return True

            if attempt < max_scrolls:
                self._log(f"任务栏未找到副本任务，向下翻页 {attempt + 1}/{max_scrolls}")
                self.scroll_task_list_down()

        return False

    def find_dungeon_task_candidate(self) -> bool:
        """Detect a dungeon tracker using the visual text-block fallback."""
        return self.find_sidebar_text_block_candidate()

    def find_sidebar_text_block_candidate(self) -> bool:
        """Heuristic fallback for game-rendered task text when no exact template exists."""
        screenshot = self.screenshot()
        x, y, width, height = self.scale_roi(self.ROI_TASK_LIST)
        region = screenshot[y : y + height, x : x + width]
        if region.size == 0:
            return False

        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        # Task labels in the sidebar are usually bright green/gold/white text over a dark panel.
        bright = hsv[:, :, 2] > 150
        saturated = hsv[:, :, 1] > 35
        mask = np.logical_and(bright, saturated).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates: list[tuple[int, int, int, int]] = []
        for contour in contours:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            if cw < 8 or ch < 8:
                continue
            if cw * ch < 80:
                continue
            candidates.append((cx, cy, cw, ch))

        if len(candidates) >= 3:
            left = min(cx for cx, _, _, _ in candidates)
            top = min(cy for _, cy, _, _ in candidates)
            right = max(cx + cw for cx, _, cw, _ in candidates)
            bottom = max(cy + ch for _, cy, _, ch in candidates)
            self._last_match_center = (x + (left + right) // 2, y + (top + bottom) // 2)
            self._last_match_score = 1.0
            self._log("通过任务栏文字块候选检测到副本任务追踪")
            return True

        self._last_match_center = None
        self._last_match_score = 0.0
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
            description="副本剧情继续箭头",
            threshold=0.85,
            roi=self.ROI_DIALOG_NEXT,
            wait_after_click_ms=1200,
        )

    def leave_team_if_present(self) -> None:
        """Leave any existing team, but do not fail when already unteamed."""
        try:
            self.leave_team(timeout_ms=5000, wait_after_click_ms=1000)
        except Exception as exc:
            self._log(f"退队检查未完成，按未组队继续：{exc}")

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"日常副本任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
