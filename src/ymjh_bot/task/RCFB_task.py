"""日常副本任务 - Python DSL 实现。"""

from __future__ import annotations

from typing import Literal

import numpy as np

from botCore import ImageMatchResult, StepStopException, step

from ymjh_bot.ym_game_task import TaskSidebarStateError, YmGameTask


class RCFBTask(YmGameTask):
    """一梦江湖日常副本任务。"""

    task_key = "RCFB"
    task_name = "日常副本"
    task_description = "创建单人队伍进入江湖纪事日常副本，完成后自动退队"
    auto_recover_health = False
    LEAVE_TEAM_ON_START = True
    STARTUP_CLOSE_SETTLE_WAIT_MS = 1000

    TEXT_DAILY_DUNGEON_TRACKERS = [
        str(YmGameTask.TEMPLATES_DIR / "text_rcfb_daily_tracker_dark.png"),
        str(YmGameTask.TEMPLATES_DIR / "text_rcfb_daily_tracker_light.png"),
    ]
    TEXT_DUNGEON_TRANSFER_OUT = str(YmGameTask.TEMPLATES_DIR / "text_rcfb_chuangchu.png")
    ICON_DUNGEON_EXIT = str(YmGameTask.TEMPLATES_DIR / "icon_exit.png")
    BTN_DUNGEON_EXIT_TEAM = str(YmGameTask.TEMPLATES_DIR / "btn_rcfb_exit_team.png")
    TAB_DUNGEON_HANGUP_ACTIVE = (
        str(YmGameTask.TEMPLATES_DIR / "tab_dungeon_hangup_active_dark.png"),
        str(YmGameTask.TEMPLATES_DIR / "tab_dungeon_hangup_active_light.png"),
    )
    TEXT_DAILY_PANEL_TITLE = str(
        YmGameTask.TEMPLATES_DIR / "text_xsrw_daily_panel_title.png"
    )
    BTN_DAILY_CHALLENGE = str(
        YmGameTask.TEMPLATES_DIR / "btn_xsrw_daily_challenge.png"
    )
    BTN_DAILY_CONFIRM = str(
        YmGameTask.TEMPLATES_DIR / "btn_xsrw_daily_confirm.png"
    )

    POINT_ACTIVITY_DAILY_ENTRY = (888, 580)
    POINT_TASK_LIST_SCROLL_START = (190, 520)
    POINT_TASK_LIST_SCROLL_END = (190, 220)

    ROI_DUNGEON_EXIT = (960, 155, 85, 85)
    ROI_DUNGEON_HANGUP_ACTIVE = (145, 0, 105, 40)
    ROI_DAILY_PANEL_TITLE = (0, 0, 260, 80)
    ROI_DAILY_CHALLENGE = (1040, 600, 220, 110)
    ROI_DAILY_CONFIRM = (930, 530, 270, 130)

    DUNGEON_TASK_THRESHOLD = 0.78
    DUNGEON_TRANSFER_OUT_THRESHOLD = 0.85
    DUNGEON_EXIT_THRESHOLD = 0.9
    DUNGEON_EXIT_TEAM_THRESHOLD = 0.9
    DUNGEON_HANGUP_ACTIVE_THRESHOLD = 0.95
    DUNGEON_HANGUP_FALLBACK_THRESHOLD = 0.82
    DUNGEON_HANGUP_CYAN_RATIO_THRESHOLD = 0.15
    DAILY_PANEL_THRESHOLD = 0.90
    DAILY_CHALLENGE_THRESHOLD = 0.90
    DAILY_CONFIRM_THRESHOLD = 0.75
    DAILY_ENTRY_TIMEOUT_MS = 15000
    DAILY_ENTRY_SETTLE_MS = 5000
    DAILY_ENTRY_VERIFY_TIMEOUT_MS = 10000
    DAILY_ENTRY_VERIFY_POLL_MS = 500
    DAILY_ENTRY_MAX_ATTEMPTS = 2
    DAILY_ACTIVITY_SETTLE_MS = 1500
    DAILY_ACTIVITY_ENTRY_ATTEMPTS = 2
    DAILY_PANEL_POLL_INTERVAL_MS = 300
    DUNGEON_TASK_POLL_INTERVAL_MS = 3000
    DAILY_START_TIMEOUT_MS = 300000
    TASK_FLOW_TIMEOUT_MS = 1800000
    TASK_FLOW_RETRY_WAIT_MS = 5000
    TASK_MISSING_CONFIRMATIONS = 6
    SIDEBAR_SCROLL_COUNT = 2
    DUNGEON_TRACKER_CLICK_INTERVAL_MS = 5000
    DUNGEON_HANGUP_VERIFY_INTERVAL_MS = 15000
    DUNGEON_HANGUP_MAX_CONSECUTIVE_FAILURES = 3
    DUNGEON_EXIT_ACTION_TIMEOUT_MS = 5000
    DUNGEON_EXIT_MAX_ATTEMPTS = 3
    DUNGEON_AUTO_TRANSFER_TIMEOUT_MS = 330000
    DUNGEON_TRANSFER_POLL_INTERVAL_MS = 500
    DUNGEON_TRANSFER_STABLE_CONFIRMATIONS = 3
    DUNGEON_ACTIVE_EXIT_TIMEOUT_MS = 60000
    DUNGEON_FAILURE_PANEL_CLEANUP_TIMEOUT_MS = 5000
    DUNGEON_OUTSIDE_VERIFY_TIMEOUT_MS = 8000
    DUNGEON_OUTSIDE_VERIFY_INTERVAL_MS = 300
    DUNGEON_OUTSIDE_STABLE_CONFIRMATIONS = 3
    DEFER_FOREGROUND_WAKE_TO_ON_START = True

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._dungeon_entry_confirmed = False
        self._dungeon_completion_confirmed = False

    def reset_startup_state(self) -> None:
        """Reset tracked dungeon state for each task run."""
        self._dungeon_entry_confirmed = False
        self._dungeon_completion_confirmed = False

    def mark_dungeon_entered(self) -> None:
        """Record that an explicit dungeon tracker confirmed entry."""
        self._dungeon_entry_confirmed = True
        self._dungeon_completion_confirmed = False

    def mark_dungeon_completed(self) -> None:
        """Record that the explicit transfer-out countdown confirmed completion."""
        self._dungeon_entry_confirmed = True
        self._dungeon_completion_confirmed = True

    def mark_dungeon_exited(self) -> None:
        """Clear dungeon state only after the outside scene is verified."""
        self._dungeon_entry_confirmed = False
        self._dungeon_completion_confirmed = False

    @step(retry=3, timeout_ms=DAILY_START_TIMEOUT_MS)
    def start_daily_match(self) -> None:
        """Create a one-player team and directly challenge the daily dungeon."""
        self.create_team("日常", min_member_count=1)
        self.close_all_panels(timeout_ms=self.DUNGEON_FAILURE_PANEL_CLEANUP_TIMEOUT_MS)
        self.open_daily_dungeon_panel()
        self.enter_daily_dungeon_challenge()

    @step(retry=0, timeout_ms=None)
    def wait_dungeon_task(self) -> None:
        """Wait for the tracker that proves the self-created team entered."""
        if self.wait_for_dungeon_task(timeout_ms=300000):
            self.mark_dungeon_entered()
            self._log("检测到江湖副本任务，确认已进入副本流程")
            return

        debug_path = self.save_debug_screenshot("rcfb_dungeon_task_missing")
        raise RuntimeError(
            "自建单人队伍挑战后 5 分钟未出现日常副本追踪，"
            f"已保存截图：{debug_path}"
        )

    @step(retry=0, timeout_ms=TASK_FLOW_TIMEOUT_MS)
    def run_daily_raid_flow(self) -> None:
        """Monitor hangup state until the daily dungeon explicitly completes."""
        self.monitor_dungeon_hangup_flow(
            timeout_ms=self.TASK_FLOW_TIMEOUT_MS,
            context="日常副本",
            hangup_failure_screenshot_prefix="rcfb_hangup_state_failed",
            timeout_screenshot_prefix="rcfb_task_flow_timeout",
        )

    def monitor_dungeon_hangup_flow(
        self,
        *,
        timeout_ms: int,
        context: str,
        hangup_failure_screenshot_prefix: str,
        timeout_screenshot_prefix: str,
    ) -> None:
        """Keep a dungeon in hangup mode without resetting an active battle state."""
        if timeout_ms <= 0:
            raise ValueError("副本挂机监控超时时间必须大于 0")
        if not self._dungeon_entry_confirmed:
            raise RuntimeError(f"未确认进入{context}，禁止启动挂机监控")

        deadline = self._make_deadline(timeout_ms)
        consecutive_failures = 0
        verification_pending = False
        hangup_confirmed = False
        outside_stable_confirmations = 0

        while not self._is_deadline_expired(deadline):
            if self.is_stopped():
                raise StepStopException("Stop requested")

            if self.is_dungeon_transfer_out_visible():
                self.mark_dungeon_completed()
                self._log(f"检测到{context}传出倒计时，判断副本完成")
                return

            if self.wake_from_power_saving_if_needed():
                self._log(f"{context}挂机监控已唤醒省电模式，重新识别挂机状态")
                if self.is_dungeon_transfer_out_visible():
                    self.mark_dungeon_completed()
                    self._log(f"检测到{context}传出倒计时，判断副本完成")
                    return

            if self.is_dungeon_outside_main_frame():
                outside_stable_confirmations += 1
                self._debug(
                    f"{context}自动传出后主界面稳定确认 "
                    f"({outside_stable_confirmations}/"
                    f"{self.DUNGEON_OUTSIDE_STABLE_CONFIRMATIONS})"
                )
                if (
                    outside_stable_confirmations
                    >= self.DUNGEON_OUTSIDE_STABLE_CONFIRMATIONS
                ):
                    self.mark_dungeon_completed()
                    self._log(
                        f"未捕获到{context}传出倒计时，"
                        "但已连续确认副本出口消失且回到主界面，"
                        "判断副本已自动传出完成"
                    )
                    return
            else:
                outside_stable_confirmations = 0

            if self.is_dungeon_hangup_active():
                if not hangup_confirmed or verification_pending or consecutive_failures:
                    self._log(f"检测到{context}左上角挂机高亮，等待副本完成")
                hangup_confirmed = True
                verification_pending = False
                consecutive_failures = 0
            else:
                if verification_pending:
                    consecutive_failures += 1
                    self._log(
                        f"{context}挂机状态复核失败 "
                        f"{consecutive_failures}/"
                        f"{self.DUNGEON_HANGUP_MAX_CONSECUTIVE_FAILURES}"
                    )
                    if (
                        consecutive_failures
                        >= self.DUNGEON_HANGUP_MAX_CONSECUTIVE_FAILURES
                    ):
                        debug_path = self.save_debug_screenshot(
                            hangup_failure_screenshot_prefix
                        )
                        raise RuntimeError(
                            f"{context}连续 "
                            f"{self.DUNGEON_HANGUP_MAX_CONSECUTIVE_FAILURES} 次"
                            f"未检测到左上角挂机高亮，已保存截图：{debug_path}"
                        )

                attempt = consecutive_failures + 1
                clicked = self.click_current_dungeon_task_if_visible(
                    wait_after_click_ms=0,
                )
                if clicked:
                    self._log(
                        f"{context}未检测到挂机高亮，已点击当前副本任务追踪 "
                        f"{attempt}/{self.DUNGEON_HANGUP_MAX_CONSECUTIVE_FAILURES}"
                    )
                else:
                    self._log(
                        f"{context}未检测到挂机高亮，且当前任务追踪不可见；"
                        f"等待复核 {attempt}/"
                        f"{self.DUNGEON_HANGUP_MAX_CONSECUTIVE_FAILURES}"
                    )
                verification_pending = True

            remaining_ms = self._remaining_ms(deadline)
            if remaining_ms > 0:
                self.wait(min(self.DUNGEON_HANGUP_VERIFY_INTERVAL_MS, remaining_ms))

        debug_path = self.save_debug_screenshot(timeout_screenshot_prefix)
        raise RuntimeError(f"{context}执行超时，已保存截图：{debug_path}")

    @step(retry=0, timeout_ms=420000)
    def leave_team_after_completion(self) -> None:
        """副本完成后选择退本退队，并等待传送回到稳定主界面。"""
        if not self._dungeon_entry_confirmed:
            self._log("当前流程未确认进入副本，仅清理残留面板和队伍")
            self.normalize_outside_dungeon_after_failure()
            return

        self.exit_team_dungeon_strict(
            allow_auto_transfer=self._dungeon_completion_confirmed,
            screenshot_prefix="rcfb_exit_team_button_missing",
        )

    def cleanup_after_failure(
        self,
        failure: Exception | str | None = None,
    ) -> None:
        """Leave a confirmed dungeon before the queue retries or advances."""
        self._log(f"日常副本失败，开始安全清理现场：{failure}")
        self.wake_from_power_saving_if_needed()
        self.close_all_panels(timeout_ms=self.DUNGEON_FAILURE_PANEL_CLEANUP_TIMEOUT_MS)

        if self._dungeon_entry_confirmed or self.detect_and_mark_dungeon_scene():
            self.exit_team_dungeon_strict(
                allow_auto_transfer=self._dungeon_completion_confirmed,
                screenshot_prefix="rcfb_failure_exit_missing",
            )
            return

        self.normalize_outside_dungeon_after_failure(panels_already_closed=True)

    def detect_and_mark_dungeon_scene(self) -> bool:
        """Recognize explicit dungeon controls and update tracked state."""
        if self.is_dungeon_transfer_out_visible():
            self.mark_dungeon_completed()
            return True

        in_dungeon = (
            self.is_dungeon_exit_team_dialog_visible()
            or self.is_dungeon_exit_visible()
        )
        if in_dungeon:
            self.mark_dungeon_entered()
        return in_dungeon

    def normalize_outside_dungeon_after_failure(
        self,
        *,
        panels_already_closed: bool = False,
    ) -> None:
        """Normalize a failed pre-entry scene and strictly verify the main scene."""
        if not panels_already_closed:
            self.wake_from_power_saving_if_needed()
            self.close_all_panels(
                timeout_ms=self.DUNGEON_FAILURE_PANEL_CLEANUP_TIMEOUT_MS
            )

        if not self.wait_for_verified_outside_dungeon():
            if self.detect_and_mark_dungeon_scene():
                raise RuntimeError("清理未入本现场时检测到副本界面，必须执行专用退本")
            debug_path = self.save_debug_screenshot("rcfb_failure_scene_unknown")
            raise RuntimeError(f"副本失败清理后未确认主界面，已保存截图：{debug_path}")

        self.finish_verified_outside_dungeon_cleanup()

    def wait_for_verified_outside_dungeon(self, *, timeout_ms: int | None = None) -> bool:
        """Require a stable main HUD with no dungeon-only exit controls."""
        effective_timeout_ms = (
            self.DUNGEON_OUTSIDE_VERIFY_TIMEOUT_MS
            if timeout_ms is None
            else timeout_ms
        )
        deadline = self._make_deadline(effective_timeout_ms)
        stable_confirmations = 0

        while not self._is_deadline_expired(deadline):
            if self.wake_from_power_saving_if_needed():
                self._log("副本外主界面复核已唤醒省电模式")
                stable_confirmations = 0

            if self.is_dungeon_outside_main_frame():
                stable_confirmations += 1
                if stable_confirmations >= self.DUNGEON_OUTSIDE_STABLE_CONFIRMATIONS:
                    return True
            else:
                stable_confirmations = 0

            remaining_ms = self._remaining_ms(deadline)
            if remaining_ms > 0:
                self.wait(min(self.DUNGEON_OUTSIDE_VERIFY_INTERVAL_MS, remaining_ms))

        return False

    def finish_verified_outside_dungeon_cleanup(self) -> None:
        """Leave a residual team and re-confirm the stable outside scene."""
        self.leave_team(timeout_ms=5000, wait_after_click_ms=1000)
        self.close_all_panels(timeout_ms=self.DUNGEON_FAILURE_PANEL_CLEANUP_TIMEOUT_MS)
        if not self.wait_for_verified_outside_dungeon():
            debug_path = self.save_debug_screenshot("rcfb_failure_main_not_ready")
            raise RuntimeError(f"副本失败退队后未确认主界面，已保存截图：{debug_path}")
        self.mark_dungeon_exited()

    def exit_team_dungeon_strict(
        self,
        *,
        allow_auto_transfer: bool,
        screenshot_prefix: str,
    ) -> None:
        """Exit a team dungeon and require a verified stable main scene."""
        self.wake_from_power_saving_if_needed()
        exit_team_clicked = self.click_dungeon_exit_team_with_retries()

        if exit_team_clicked:
            self._log("已点击退本退队，等待传送结束")
            transfer_timeout_ms = self.DUNGEON_ACTIVE_EXIT_TIMEOUT_MS
        elif self.wait_for_verified_outside_dungeon():
            self._log("未找到退本按钮，但已连续确认处于副本外主界面")
            self.finish_verified_outside_dungeon_cleanup()
            return
        elif allow_auto_transfer:
            debug_path = self.save_debug_screenshot(screenshot_prefix)
            self._log(
                f"连续 {self.DUNGEON_EXIT_MAX_ATTEMPTS} 次未能点击退本退队，"
                f"副本已确认完成，等待自动传出；现场截图：{debug_path}"
            )
            transfer_timeout_ms = self.DUNGEON_AUTO_TRANSFER_TIMEOUT_MS
        else:
            debug_path = self.save_debug_screenshot(screenshot_prefix)
            raise RuntimeError(
                "副本尚未确认完成且未能点击退本退队，"
                f"禁止依赖自动传出；已保存截图：{debug_path}"
            )

        self.wait_for_dungeon_transfer_complete(timeout_ms=transfer_timeout_ms)
        if not exit_team_clicked:
            self._log("副本已自动传出，严格检查并退出残留队伍")
            self.finish_verified_outside_dungeon_cleanup()
            return
        self.mark_dungeon_exited()

    def click_dungeon_exit_team_with_retries(self) -> bool:
        """Try to open the dungeon-exit dialog and click leave-dungeon-and-team."""
        for attempt in range(1, self.DUNGEON_EXIT_MAX_ATTEMPTS + 1):
            if self.click_visible_dungeon_exit_team_button():
                self._log("检测到已打开的副本退出弹框，点击退本退队")
                return True

            exit_clicked = self.click_template_if_available(
                self.ICON_DUNGEON_EXIT,
                timeout_ms=self.DUNGEON_EXIT_ACTION_TIMEOUT_MS,
                description="副本退出图标",
                threshold=self.DUNGEON_EXIT_THRESHOLD,
                roi=self.ROI_DUNGEON_EXIT,
                wait_after_click_ms=500,
            )
            if exit_clicked and self.click_template_if_available(
                self.BTN_DUNGEON_EXIT_TEAM,
                timeout_ms=self.DUNGEON_EXIT_ACTION_TIMEOUT_MS,
                description="退本退队按钮",
                threshold=self.DUNGEON_EXIT_TEAM_THRESHOLD,
                roi=(300, 440, 700, 130),
                wait_after_click_ms=0,
            ):
                return True

            if exit_clicked:
                self._log(
                    f"第 {attempt}/{self.DUNGEON_EXIT_MAX_ATTEMPTS} 次点击退出图标后"
                    "未出现退本退队按钮"
                )
            else:
                self._log(
                    f"第 {attempt}/{self.DUNGEON_EXIT_MAX_ATTEMPTS} 次未找到副本退出图标"
                )

        return False

    def click_visible_dungeon_exit_team_button(self) -> bool:
        """Click an exit-team action that is already visible without toggling the dialog."""
        if not self.is_dungeon_exit_team_dialog_visible():
            return False

        self.click(offset=0)
        return True

    def is_dungeon_exit_team_dialog_visible(self) -> bool:
        """Return whether the team-dungeon exit action is already visible."""
        return self.find_image_once(
            self.BTN_DUNGEON_EXIT_TEAM,
            threshold=self.DUNGEON_EXIT_TEAM_THRESHOLD,
            roi=self.scale_roi((300, 440, 700, 130)),
        )

    def open_daily_dungeon_panel(self) -> None:
        """Open Jianghu Chronicle from Activity and verify its challenge panel."""
        if self.is_daily_dungeon_panel_visible(timeout_ms=0):
            return

        self.open_activity_panel(
            "江湖",
            wait_after_open_ms=self.DAILY_ACTIVITY_SETTLE_MS,
        )
        for attempt in range(1, self.DAILY_ACTIVITY_ENTRY_ATTEMPTS + 1):
            self._log(
                "点击活动面板江湖纪事入口 "
                f"{attempt}/{self.DAILY_ACTIVITY_ENTRY_ATTEMPTS}"
            )
            self.click_point(*self.POINT_ACTIVITY_DAILY_ENTRY, offset=0)
            self.wait(self.DAILY_ACTIVITY_SETTLE_MS)
            if self.is_daily_dungeon_panel_visible(
                timeout_ms=self.DAILY_ENTRY_TIMEOUT_MS,
            ):
                return

        debug_path = self.save_debug_screenshot("rcfb_daily_panel_missing")
        raise RuntimeError(f"未能打开江湖纪事日常副本面板，已保存截图：{debug_path}")

    def enter_daily_dungeon_challenge(self) -> None:
        """Challenge the selected daily dungeon as leader of the one-player team."""
        for attempt in range(1, self.DAILY_ENTRY_MAX_ATTEMPTS + 1):
            confirm = self._wait_daily_binary_match(
                self.BTN_DAILY_CONFIRM,
                mode="otsu_dark",
                threshold=self.DAILY_CONFIRM_THRESHOLD,
                roi=self.ROI_DAILY_CONFIRM,
                timeout_ms=1000,
            )
            if not confirm.found:
                if not self.is_daily_dungeon_panel_visible(
                    timeout_ms=self.DAILY_ENTRY_TIMEOUT_MS,
                ):
                    debug_path = self.save_debug_screenshot(
                        "rcfb_daily_panel_before_challenge_missing"
                    )
                    raise RuntimeError(
                        "单人队伍挑战前日常副本面板不存在，"
                        f"已保存截图：{debug_path}"
                    )

                challenge = self._wait_daily_binary_match(
                    self.BTN_DAILY_CHALLENGE,
                    mode="otsu_dark",
                    threshold=self.DAILY_CHALLENGE_THRESHOLD,
                    roi=self.ROI_DAILY_CHALLENGE,
                    timeout_ms=self.DAILY_ENTRY_TIMEOUT_MS,
                )
                if not challenge.found or challenge.center is None:
                    debug_path = self.save_debug_screenshot(
                        "rcfb_daily_challenge_missing"
                    )
                    raise RuntimeError(
                        f"日常副本面板未找到挑战按钮，已保存截图：{debug_path}"
                    )

                self._log("单人队伍点击江湖纪事日常副本挑战")
                self.tap(*challenge.center)
                confirm = self._wait_daily_binary_match(
                    self.BTN_DAILY_CONFIRM,
                    mode="otsu_dark",
                    threshold=self.DAILY_CONFIRM_THRESHOLD,
                    roi=self.ROI_DAILY_CONFIRM,
                    timeout_ms=self.DAILY_ENTRY_TIMEOUT_MS,
                )

            if not confirm.found or confirm.center is None:
                debug_path = self.save_debug_screenshot("rcfb_daily_confirm_missing")
                raise RuntimeError(
                    f"日常副本挑战未出现确认按钮，已保存截图：{debug_path}"
                )

            self._log(
                "单人队伍确认进入江湖纪事日常副本，"
                f"等待页面切换 {attempt}/{self.DAILY_ENTRY_MAX_ATTEMPTS}"
            )
            self.tap(*confirm.center)
            self.wait(self.DAILY_ENTRY_SETTLE_MS)
            if self.wait_for_daily_dungeon_panel_close():
                self._log("日常副本选择页已消失，等待任务追踪确认真实入本")
                return

            if attempt < self.DAILY_ENTRY_MAX_ATTEMPTS:
                self._log("进入确认后仍停留日常副本选择页，重新挑战一次")

        debug_path = self.save_debug_screenshot("rcfb_daily_entry_transition_failed")
        raise RuntimeError(
            "单人队伍确认后仍停留日常副本选择页，"
            f"已保存截图：{debug_path}"
        )

    def is_daily_dungeon_panel_visible(self, *, timeout_ms: int) -> bool:
        """Return whether the Jianghu Chronicle challenge panel is visible."""
        return self._wait_daily_binary_match(
            self.TEXT_DAILY_PANEL_TITLE,
            mode="light_foreground",
            threshold=self.DAILY_PANEL_THRESHOLD,
            roi=self.ROI_DAILY_PANEL_TITLE,
            timeout_ms=timeout_ms,
        ).found

    def wait_for_daily_dungeon_panel_close(self) -> bool:
        """Wait until the challenge panel disappears after entry confirmation."""
        deadline = self._make_deadline(self.DAILY_ENTRY_VERIFY_TIMEOUT_MS)
        while not self._is_deadline_expired(deadline):
            if self.wake_from_power_saving_if_needed():
                self._log("单人队伍入本复核已唤醒省电模式")

            if not self._daily_binary_match(
                self.screenshot(),
                self.TEXT_DAILY_PANEL_TITLE,
                mode="light_foreground",
                threshold=self.DAILY_PANEL_THRESHOLD,
                roi=self.ROI_DAILY_PANEL_TITLE,
            ).found:
                return True

            remaining_ms = self._remaining_ms(deadline)
            if remaining_ms > 0:
                self.wait(min(self.DAILY_ENTRY_VERIFY_POLL_MS, remaining_ms))
        return False

    def _wait_daily_binary_match(
        self,
        template: str | list[str] | tuple[str, ...],
        *,
        mode: Literal["otsu_dark", "light_foreground"],
        threshold: float,
        roi: tuple[int, int, int, int],
        timeout_ms: int,
    ) -> ImageMatchResult:
        deadline = self._make_deadline(timeout_ms)
        last = self._daily_binary_match(
            self.screenshot(),
            template,
            mode=mode,
            threshold=threshold,
            roi=roi,
        )
        while not last.found and not self._is_deadline_expired(deadline):
            remaining_ms = self._remaining_ms(deadline)
            if remaining_ms > 0:
                self.wait(min(self.DAILY_PANEL_POLL_INTERVAL_MS, remaining_ms))
            last = self._daily_binary_match(
                self.screenshot(),
                template,
                mode=mode,
                threshold=threshold,
                roi=roi,
            )
        return last

    def _daily_binary_match(
        self,
        screenshot: np.ndarray,
        template: str | list[str] | tuple[str, ...],
        *,
        mode: Literal["otsu_dark", "light_foreground"],
        threshold: float,
        roi: tuple[int, int, int, int],
    ) -> ImageMatchResult:
        return self._vision.match_binary_template(
            screenshot,
            template,
            mode=mode,
            threshold=threshold,
            roi=self.scale_roi(roi),
        )

    def wait_for_dungeon_task(self, *, timeout_ms: int) -> bool:
        """Wait until the task tab shows a daily dungeon tracker."""
        deadline = self._make_deadline(timeout_ms)
        valid_scan_count = 0
        last_sidebar_error: TaskSidebarStateError | None = None

        while not self._is_deadline_expired(deadline):
            try:
                found = self.find_dungeon_task_in_sidebar(max_scrolls=self.SIDEBAR_SCROLL_COUNT)
            except TaskSidebarStateError as exc:
                last_sidebar_error = exc
                self._log(f"副本过渡期任务侧栏暂不可用，稍后重试：{exc}")
            else:
                valid_scan_count += 1
                if found:
                    return True
                self._log("有效任务侧栏扫描暂未找到江湖副本任务，继续等待入本...")

            remaining_ms = self._remaining_ms(deadline)
            if remaining_ms > 0:
                self.wait(min(self.DUNGEON_TASK_POLL_INTERVAL_MS, remaining_ms))

        if valid_scan_count == 0 and last_sidebar_error is not None:
            self._log("5 分钟内未完成过一次有效任务侧栏扫描，重新抛出最后一个侧栏异常")
            raise last_sidebar_error

        self._log("最终有效任务侧栏扫描始终未找到副本追踪")
        return False

    def is_dungeon_transfer_out_visible(self) -> bool:
        """Return whether the explicit dungeon-completion countdown is visible."""
        return self.find_image_once(
            self.TEXT_DUNGEON_TRANSFER_OUT,
            threshold=self.DUNGEON_TRANSFER_OUT_THRESHOLD,
            roi=self.scale_roi((900, 170, 110, 60)),
        )

    def is_dungeon_hangup_active(self) -> bool:
        """Recognize the highlighted hangup tab across bright and dim scenes."""
        screenshot = self.screenshot()
        match = self._vision.match_template(
            screenshot,
            self.TAB_DUNGEON_HANGUP_ACTIVE,
            threshold=self.DUNGEON_HANGUP_FALLBACK_THRESHOLD,
            roi=self.scale_roi(self.ROI_DUNGEON_HANGUP_ACTIVE),
        )
        self._last_match_score = match.score
        if not match.found or match.center is None:
            self._last_match_center = None
            return False

        if match.score >= self.DUNGEON_HANGUP_ACTIVE_THRESHOLD:
            self._last_match_center = match.center
            return True

        x, y, width, height = self.scale_roi(self.ROI_DUNGEON_HANGUP_ACTIVE)
        crop = screenshot[y : y + height, x : x + width].astype("int16")
        if crop.size == 0:
            self._last_match_center = None
            return False

        blue = crop[:, :, 0]
        green = crop[:, :, 1]
        red = crop[:, :, 2]
        cyan_ratio = float(
            (
                (blue > red + 20)
                & (green > red + 20)
                & (green > 70)
            ).mean()
        )
        if cyan_ratio >= self.DUNGEON_HANGUP_CYAN_RATIO_THRESHOLD:
            self._last_match_center = match.center
            self._debug(
                "通过青色高亮复核确认副本挂机已开启 "
                f"(template={match.score:.3f}, cyan={cyan_ratio:.3f})"
            )
            return True

        self._last_match_center = None
        return False

    def is_dungeon_exit_visible(self) -> bool:
        """Return whether the top-right dungeon exit control is visible."""
        return self.find_image_once(
            self.ICON_DUNGEON_EXIT,
            threshold=self.DUNGEON_EXIT_THRESHOLD,
            roi=self.scale_roi(self.ROI_DUNGEON_EXIT),
        )

    def is_dungeon_outside_main_frame(self) -> bool:
        """Use one screenshot to prove the dungeon already auto-transferred out."""
        screenshot = self.screenshot()
        dungeon_markers = (
            (
                self.TEXT_DUNGEON_TRANSFER_OUT,
                self.DUNGEON_TRANSFER_OUT_THRESHOLD,
                self.scale_roi((900, 170, 110, 60)),
            ),
            (
                self.BTN_DUNGEON_EXIT_TEAM,
                self.DUNGEON_EXIT_TEAM_THRESHOLD,
                self.scale_roi((300, 440, 700, 130)),
            ),
            (
                self.ICON_DUNGEON_EXIT,
                self.DUNGEON_EXIT_THRESHOLD,
                self.scale_roi(self.ROI_DUNGEON_EXIT),
            ),
        )
        for template, threshold, roi in dungeon_markers:
            if self._vision.match_template(
                screenshot,
                template,
                threshold=threshold,
                roi=roi,
            ).found:
                return False

        calendar_match = self._vision.match_template(
            screenshot,
            self.TEXT_JIANGHU_CALENDAR,
            threshold=self.JIANGHU_CALENDAR_MARKER_THRESHOLD,
            roi=self.scale_roi(self.ROI_JIANGHU_CALENDAR_MARKER),
        )
        if calendar_match.found:
            return False

        for state_name, _, templates in self._login_state_targets(True):
            match = self._vision.match_template(screenshot, templates, threshold=0.8)
            if not match.found:
                continue
            self._last_match_score = match.score
            self._last_match_center = match.center
            return state_name == self.LOGIN_STATE_MAIN

        self._last_match_center = None
        return False

    def click_current_dungeon_task_if_visible(
        self,
        *,
        wait_after_click_ms: int | None = None,
    ) -> bool:
        """Click the visible tracker without opening, switching, or scrolling the sidebar."""
        if wait_after_click_ms is not None and wait_after_click_ms < 0:
            raise ValueError("任务追踪点击后等待时间不能小于 0")
        if not self.find_dungeon_task_candidate():
            return False

        self._log("点击当前任务栏副本任务")
        self.click(offset=0)
        effective_wait_ms = (
            self.DUNGEON_TRACKER_CLICK_INTERVAL_MS
            if wait_after_click_ms is None
            else wait_after_click_ms
        )
        if effective_wait_ms > 0:
            self.wait(effective_wait_ms)
        return True

    def wait_for_dungeon_transfer_complete(self, *, timeout_ms: int) -> None:
        """Wait until dungeon-only controls disappear and the main scene is stable."""
        deadline = self._make_deadline(timeout_ms)
        stable_confirmations = 0

        while not self._is_deadline_expired(deadline):
            if self.is_stopped():
                raise StepStopException("Stop requested")

            exit_visible = self.is_dungeon_exit_visible()
            transfer_out_visible = self.is_dungeon_transfer_out_visible()
            main_ready = False
            if not exit_visible and not transfer_out_visible:
                main_ready = self.is_game_main_ready(timeout_ms=0, threshold=0.8)

            if main_ready:
                stable_confirmations += 1
                self._debug(
                    "退本后主界面稳定确认 "
                    f"({stable_confirmations}/{self.DUNGEON_TRANSFER_STABLE_CONFIRMATIONS})"
                )
                if stable_confirmations >= self.DUNGEON_TRANSFER_STABLE_CONFIRMATIONS:
                    self._log("退本传送完成，已回到稳定主界面")
                    return
            else:
                stable_confirmations = 0

            remaining_ms = self._remaining_ms(deadline)
            if remaining_ms > 0:
                self.wait(min(self.DUNGEON_TRANSFER_POLL_INTERVAL_MS, remaining_ms))

        debug_path = self.save_debug_screenshot("rcfb_dungeon_transfer_timeout")
        raise RuntimeError(f"退本后等待传送结束超时，已保存截图：{debug_path}")

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
        """Find the ``[副本]日常·`` tracker in the task tab, scrolling if needed."""
        self.collapse_chat_if_open()
        self.switch_task_panel("任务", timeout_ms=6000, threshold=0.8)

        for attempt in range(max_scrolls + 1):
            if self.find_dungeon_task_candidate():
                return True

            if attempt < max_scrolls:
                self._log(f"任务栏未找到副本任务，向下翻页 {attempt + 1}/{max_scrolls}")
                self.scroll_task_list_down()

        return False

    def find_dungeon_task_candidate(self) -> bool:
        """Detect the stable daily-dungeon title prefix across dark and light cards."""
        if not self.find_image(
            self.TEXT_DAILY_DUNGEON_TRACKERS,
            threshold=self.DUNGEON_TASK_THRESHOLD,
            roi=self.scale_roi((40, 135, 270, 430)),
        ):
            return False

        self._log(
            "通过任务栏标题 [副本]日常· 检测到副本任务追踪 "
            f"(score={self._last_match_score:.3f})"
        )
        return True

    def scroll_task_list_down(self) -> None:
        """Scroll the task list down to reveal lower tracker entries."""
        start = self.POINT_TASK_LIST_SCROLL_START
        end = self.POINT_TASK_LIST_SCROLL_END
        self.swipe(start[0], start[1], end[0], end[1], duration_ms=350)
        self.wait(800)

    def leave_team_if_present(self) -> None:
        """Leave any existing team, but do not fail when already unteamed."""
        try:
            self.leave_team(timeout_ms=5000, wait_after_click_ms=1000)
        except StepStopException:
            raise
        except Exception as exc:
            self._log(f"退队检查未完成，按未组队继续：{exc}")

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"日常副本任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
