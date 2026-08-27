"""日常副本任务 - Python DSL 实现。"""

from __future__ import annotations

import time

from botCore import StepStopException, step

from ymjh_bot.ym_game_task import TaskSidebarStateError, YmGameTask


class RCFBTask(YmGameTask):
    """一梦江湖日常副本任务。"""

    task_key = "RCFB"
    task_name = "日常副本"
    task_description = "匹配江湖纪事日常副本，跟随队伍完成后自动退队"
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

    POINT_TEAM_AUTO_MATCH = (990, 669)
    POINT_QUICK_CATEGORY_JIANGHU = (180, 210)
    POINT_TASK_LIST_SCROLL_START = (190, 520)
    POINT_TASK_LIST_SCROLL_END = (190, 220)

    ROI_DUNGEON_EXIT = (960, 155, 85, 85)
    ROI_DUNGEON_HANGUP_ACTIVE = (145, 0, 105, 40)

    DUNGEON_TASK_THRESHOLD = 0.78
    DUNGEON_TRANSFER_OUT_THRESHOLD = 0.85
    DUNGEON_EXIT_THRESHOLD = 0.9
    DUNGEON_EXIT_TEAM_THRESHOLD = 0.9
    DUNGEON_HANGUP_ACTIVE_THRESHOLD = 0.95
    DUNGEON_TASK_POLL_INTERVAL_MS = 3000
    MATCH_WAIT_TIMEOUT_MS = 300000
    MATCH_WAIT_POLL_INTERVAL_MS = 1000
    MATCH_WAIT_HEARTBEAT_MS = 30000
    MAX_LEADER_REMATCHES = 3
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
    DEFER_FOREGROUND_WAKE_TO_ON_START = True

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._leader_rematch_count = 0

    def reset_startup_state(self) -> None:
        """Reset the abnormal-leader rematch counter for each task run."""
        self._leader_rematch_count = 0

    @step(retry=3, timeout_ms=MATCH_WAIT_TIMEOUT_MS)
    def start_daily_match(self) -> None:
        """开始日常副本匹配，并等待入队跟随确认弹框。"""
        self.start_daily_auto_match()
        self.wait_for_team_follow_confirm(timeout_ms=self.MATCH_WAIT_TIMEOUT_MS)

    @step(retry=0, timeout_ms=None)
    def wait_dungeon_task(self) -> None:
        """等待左侧任务页出现日常副本追踪；5 分钟未出现则退队重组。"""
        if self.wait_for_dungeon_task(timeout_ms=300000):
            self._log("检测到江湖副本任务，确认已进入副本流程")
            return

        debug_path = self.save_debug_screenshot("rcfb_dungeon_task_missing")
        self.leave_team_if_present()
        if self._leader_rematch_count >= self.MAX_LEADER_REMATCHES:
            self._log(
                "5 分钟未检测到江湖副本任务，异常队长重组已达到上限；"
                f"现场截图：{debug_path}"
            )
            raise RuntimeError(
                f"连续 {self.MAX_LEADER_REMATCHES + 1} 支队伍未出现日常副本追踪，"
                f"已退队并保存截图：{debug_path}"
            )

        self._leader_rematch_count += 1
        self._log(
            "5 分钟未检测到江湖副本任务，判定当前队长异常并退队，"
            f"重新匹配 {self._leader_rematch_count}/{self.MAX_LEADER_REMATCHES}；"
            f"现场截图：{debug_path}"
        )
        self.jump_to("start_daily_match")

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

        deadline = self._make_deadline(timeout_ms)
        consecutive_failures = 0
        verification_pending = False
        hangup_confirmed = False

        while not self._is_deadline_expired(deadline):
            if self.is_stopped():
                raise StepStopException("Stop requested")

            if self.is_dungeon_transfer_out_visible():
                self._log(f"检测到{context}传出倒计时，判断副本完成")
                return

            if self.wake_from_power_saving_if_needed():
                self._log(f"{context}挂机监控已唤醒省电模式，重新识别挂机状态")
                if self.is_dungeon_transfer_out_visible():
                    self._log(f"检测到{context}传出倒计时，判断副本完成")
                    return

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
        exit_team_clicked = False
        try:
            exit_team_clicked = self.click_dungeon_exit_team_with_retries()
        except StepStopException:
            raise
        except Exception as exc:
            self._log(f"副本退出识别异常，改为等待自动传出：{exc}")

        if exit_team_clicked:
            self._log("已点击退本退队，等待传送结束")
            transfer_timeout_ms = 60000
        else:
            try:
                debug_path = self.save_debug_screenshot("rcfb_exit_team_button_missing")
                self._log(
                    f"连续 {self.DUNGEON_EXIT_MAX_ATTEMPTS} 次未能点击退本退队，"
                    f"等待副本自动传出；现场截图：{debug_path}"
                )
            except Exception as exc:
                self._log(f"副本退出现场截图保存失败，继续等待自动传出：{exc}")
            transfer_timeout_ms = self.DUNGEON_AUTO_TRANSFER_TIMEOUT_MS

        try:
            self.wait_for_dungeon_transfer_complete(timeout_ms=transfer_timeout_ms)
        except StepStopException:
            raise
        except Exception as exc:
            self._log(
                f"副本退出等待未完成，不重跑已完成副本并尝试通用退队：{exc}"
            )
            self.leave_team_if_present()
            return

        if not exit_team_clicked:
            self._log("副本已自动传出，执行通用退队")
            self.leave_team_if_present()

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
        if not self.find_image_once(
            self.BTN_DUNGEON_EXIT_TEAM,
            threshold=self.DUNGEON_EXIT_TEAM_THRESHOLD,
            roi=self.scale_roi((300, 440, 700, 130)),
        ):
            return False

        self.click(offset=0)
        return True

    def start_daily_auto_match(self) -> None:
        """Select daily raid in convenient teaming and start auto match."""
        self.open_quick_team_panel(timeout_ms=5000, wait_after_click_ms=3000)
        self.select_daily_raid_quick_target(wait_after_click_ms=800)
        if not self.click_template_if_available(
            self.BTN_TEAM_AUTO_MATCH,
            timeout_ms=5000,
            description="日常副本自动匹配按钮",
            threshold=0.9,
            roi=self.ROI_TEAM_QUICK_ACTIONS,
            wait_after_click_ms=0,
        ):
            self._log("未识别到日常副本自动匹配按钮，使用固定坐标点击")
            self.click_point(self.POINT_TEAM_AUTO_MATCH[0], self.POINT_TEAM_AUTO_MATCH[1], offset=0)

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

    def wait_for_team_follow_confirm(self, *, timeout_ms: int) -> None:
        """Wait for the team-follow dialog until the matching deadline expires."""
        started_at = time.perf_counter()
        deadline = started_at + timeout_ms / 1000.0
        next_heartbeat_at = started_at + self.MATCH_WAIT_HEARTBEAT_MS / 1000.0

        while not self.is_stopped() and time.perf_counter() < deadline:
            if self.confirm_center_modal_ok_if_visible("入队跟随确认", wait_after_click_ms=0):
                self._log("已点击入队跟随确认")
                return

            now = time.perf_counter()
            if now >= next_heartbeat_at:
                if self.confirm_already_in_team():
                    return
                self._debug("日常副本匹配入队等待中...")
                next_heartbeat_at = now + self.MATCH_WAIT_HEARTBEAT_MS / 1000.0

            remaining_ms = max(0, int((deadline - now) * 1000))
            if remaining_ms > 0:
                self.wait(min(self.MATCH_WAIT_POLL_INTERVAL_MS, remaining_ms))

        if self.is_stopped():
            raise RuntimeError("日常副本匹配等待被停止")

        if self.confirm_already_in_team():
            return

        debug_path = self.save_debug_screenshot("rcfb_team_follow_timeout")
        cancelled = self.cancel_daily_match_after_timeout()
        cancel_result = "已取消匹配" if cancelled else "未能确认取消匹配"
        raise RuntimeError(
            f"日常副本匹配 5 分钟未检测到入队跟随确认弹框，{cancel_result}；"
            f"已保存截图：{debug_path}"
        )

    def confirm_already_in_team(self) -> bool:
        """Confirm real team membership when the follow dialog never appears."""
        panel_opened = False
        try:
            self.open_team_panel(timeout_ms=2500, wait_after_click_ms=800)
            panel_opened = True
            in_team = self.is_in_team()
            if in_team:
                self._log("检测到已处于队伍中，继续进入副本任务检测")
            return in_team
        except StepStopException:
            raise
        except Exception as exc:
            self._log(f"队伍状态确认未完成，继续等待入队弹框：{exc}")
            return False
        finally:
            if panel_opened:
                try:
                    self.close_all_panels(timeout_ms=2000)
                except StepStopException:
                    raise
                except Exception as exc:
                    self._log(f"队伍状态确认后关闭面板失败，继续后续检测：{exc}")

    def cancel_daily_match_after_timeout(self) -> bool:
        """Best-effort cancellation after the follow-dialog wait times out."""
        cancelled = False
        try:
            self.open_quick_team_panel(timeout_ms=5000, wait_after_click_ms=800)
            self.select_daily_raid_quick_target(wait_after_click_ms=500)
            cancelled = self.click_template_if_available(
                self.BTN_TEAM_CANCEL_MATCH,
                timeout_ms=2000,
                description="日常副本取消匹配按钮",
                threshold=0.9,
                roi=self.ROI_TEAM_QUICK_ACTIONS,
                wait_after_click_ms=800,
            )
            if cancelled:
                self._log("日常副本匹配超时，已点击取消匹配")
            else:
                self._log("日常副本匹配超时，未识别到取消匹配按钮")
        except Exception as exc:
            self._log(f"日常副本匹配超时，取消匹配检查未完成：{exc}")
        finally:
            try:
                self.close_all_panels(timeout_ms=2000)
            except Exception as exc:
                self._log(f"取消匹配后的面板清理未完成：{exc}")
        return cancelled

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
        """Return whether the complete top-left hangup tab is highlighted."""
        return self.find_image_once(
            self.TAB_DUNGEON_HANGUP_ACTIVE,
            threshold=self.DUNGEON_HANGUP_ACTIVE_THRESHOLD,
            roi=self.scale_roi(self.ROI_DUNGEON_HANGUP_ACTIVE),
        )

    def is_dungeon_exit_visible(self) -> bool:
        """Return whether the top-right dungeon exit control is visible."""
        return self.find_image_once(
            self.ICON_DUNGEON_EXIT,
            threshold=self.DUNGEON_EXIT_THRESHOLD,
            roi=self.scale_roi(self.ROI_DUNGEON_EXIT),
        )

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
