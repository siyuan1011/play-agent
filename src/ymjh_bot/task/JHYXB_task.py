"""江湖英雄榜任务 - Python DSL 实现。"""

from __future__ import annotations

import time

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class JianghuYingxiongbangTask(YmGameTask):
    """一梦江湖江湖英雄榜任务。"""

    task_key = "JHYXB"
    task_name = "江湖英雄榜"
    task_description = "江湖英雄榜匹配并领取首战宝箱"
    auto_recover_health = False
    RETURN_TO_SAFE_ZONE_ON_START = True
    DEFER_FOREGROUND_WAKE_TO_ON_START = True
    STARTUP_CLOSE_SETTLE_WAIT_MS = 1000
    SAFE_ZONE_RETURN_FAILURE_LOG = "返回鸡鸣寺安全区未完成，继续从当前界面打开江湖英雄榜：{error}"

    BTN_JHYXB_ACTIVITY_OPEN = str(YmGameTask.TEMPLATES_DIR / "btn_jhyxb_activity_open.png")
    BTN_JHYXB_MATCH = str(YmGameTask.TEMPLATES_DIR / "btn_jhyxb_match.png")
    TITLE_JHYXB = str(YmGameTask.TEMPLATES_DIR / "text_JHYXB_title.png")
    ICON_JHYXB_FIRST_WIN = str(YmGameTask.TEMPLATES_DIR / "icon_jhyxb_first_win.png")
    ICON_JHYXB_FIRST_WIN_READY = str(YmGameTask.TEMPLATES_DIR / "icon_jhyxb_first_win_ready.png")
    ICON_JHYXB_FIRST_WIN_CHEST = str(YmGameTask.TEMPLATES_DIR / "icon_jhyxb_first_win_chest.png")
    TEXT_JHYXB_CHALLENGE_ZERO = str(YmGameTask.TEMPLATES_DIR / "text_jhyxb_challenge_zero.png")
    BTN_JHYXB_READY = str(YmGameTask.TEMPLATES_DIR / "text_ready.png")
    BTN_JHYXB_RESULT_EXIT: str | None = None

    # 固定坐标点 (设计分辨率 1280x720 下)
    POINT_JHYXB_MATCH = (1076, 584)
    POINT_FIRST_BATTLE_CHEST = (433, 585)
    POINT_FIRST_BATTLE_REWARD_DIALOG_DISMISS = (1190, 690)
    POINT_JHYXB_READY = (640, 97)
    POINT_DIRECTION_JOYSTICK_FORWARD = (105, 385)

    ROI_PANEL_TITLE = (170, 45, 260, 75)
    ROI_MATCH_BUTTON = (950, 520, 230, 120)
    ROI_FIRST_BATTLE_CHEST = (385, 535, 105, 90)
    ROI_CHALLENGE_ZERO = (880, 560, 60, 55)
    ROI_RESULT_EXIT_BUTTON = (380, 420, 520, 240)

    DEFAULT_CHALLENGE_COUNT = 5
    CLOSE_ALL_MAX_ATTEMPTS = 12
    MATCH_POLL_INTERVAL_MS = 3000
    MATCH_READY_TIMEOUT_MS = 60000
    RESULT_TIMEOUT_MS = 360000
    MATCH_WAIT_POLL_INTERVAL_MS = 1000
    MATCH_WAIT_HEARTBEAT_MS = 10000
    BATTLE_FORWARD_MS = 3000
    AUTO_BATTLE_INTERVAL_MS = 250
    MATCH_READY_STATE_READY = "ready"
    BATTLE_FINISH_RESULT_PANEL = "result_panel"
    BATTLE_FINISH_RETURNED_PANEL = "jhyxb_panel"
    FIRST_BATTLE_REWARD_STATE_CLAIMED = "claimed"
    FIRST_BATTLE_REWARD_STATE_READY = "ready"
    FIRST_BATTLE_REWARD_STATE_INITIAL = "initial"
    FIRST_BATTLE_REWARD_STATE_UNKNOWN = "unknown"

    @step(retry=0, timeout_ms=60000)
    def open_jhyxb_panel(self) -> None:
        """通过活动-纷争打开江湖英雄榜面板。"""
        self._open_jhyxb_panel_via_activity()

    @step(retry=0, timeout_ms=None)
    def use_all_challenges(self) -> None:
        """点击匹配按钮，默认消耗 5 次挑战次数。"""
        for index in range(1, self.DEFAULT_CHALLENGE_COUNT + 1):
            self._log(f"开始第 {index}/{self.DEFAULT_CHALLENGE_COUNT} 次江湖英雄榜匹配")
            self.ensure_jhyxb_panel_ready(timeout_ms=10000)
            if self.is_challenge_count_zero():
                self._log("检测到江湖英雄榜挑战次数已用完，停止匹配循环")
                return
            match_deadline = self.click_match_button()
            self.run_match_battle(index, match_deadline=match_deadline)

    @step(retry=1, timeout_ms=60000)
    def claim_first_battle_chest(self) -> bool:
        """领取每日首战宝箱奖励，并确认宝箱已变为领取状态。"""
        self.ensure_jhyxb_panel_ready(timeout_ms=10000)
        reward_state, scores = self.detect_first_battle_reward_state()

        if reward_state == self.FIRST_BATTLE_REWARD_STATE_CLAIMED:
            self._log("江湖英雄榜首战宝箱已领取")
            return True

        if reward_state == self.FIRST_BATTLE_REWARD_STATE_INITIAL:
            self._log("江湖英雄榜首战宝箱尚未达成，跳过领取")
            return False

        if reward_state == self.FIRST_BATTLE_REWARD_STATE_READY:
            self._log("点击江湖英雄榜可领取首战宝箱")
            self.click(offset=0)
        else:
            debug_path = self.save_debug_screenshot("jhyxb_first_battle_reward_unknown")
            self._log(
                "未识别到江湖英雄榜首战宝箱状态："
                f"initial={scores['initial']:.3f}，"
                f"ready={scores['ready']:.3f}，"
                f"claimed={scores['claimed']:.3f}，"
                f"调试截图：{debug_path}"
            )
            if not self.is_first_battle_reward_claim_context_safe():
                self._log("首战宝箱状态未知且江湖英雄榜面板不稳定，跳过保底领取")
                return False

            self._log("首战宝箱状态未知，使用保底坐标尝试领取")
            self.click_point(self.POINT_FIRST_BATTLE_CHEST[0], self.POINT_FIRST_BATTLE_CHEST[1], offset=0)

        if self.confirm_first_battle_reward_claimed():
            self._log("江湖英雄榜首战宝箱领取完成")
            return True

        debug_path = self.save_debug_screenshot("jhyxb_first_battle_reward_claim_failed")
        raise RuntimeError(f"江湖英雄榜首战宝箱领取后未确认已领取状态，已保存截图：{debug_path}")

    def _open_jhyxb_panel_via_activity(self) -> None:
        """通过已验证的活动-纷争面板打开江湖英雄榜。"""
        self.open_activity_panel(
            "纷争",
            wait_after_open_ms=2500,
            wait_after_category_ms=1500,
        )

        if not self.wait_find_image_in_roi(
            self.BTN_JHYXB_ACTIVITY_OPEN,
            (720, 500, 240, 120),
            timeout_ms=5000,
            description="活动页江湖英雄榜打开按钮",
            threshold=0.85,
        ):
            debug_path = self.save_debug_screenshot("jhyxb_activity_open_missing")
            raise RuntimeError(f"活动-纷争未找到江湖英雄榜打开按钮，已保存截图：{debug_path}")

        self._log("点击活动页江湖英雄榜打开按钮")
        self.click(offset=0)
        self.wait(2000)

        if not self.ensure_jhyxb_panel_visible(timeout_ms=5000):
            debug_path = self.save_debug_screenshot("jhyxb_panel_open_failed")
            raise RuntimeError(f"未进入江湖英雄榜面板，已保存截图：{debug_path}")

    def ensure_jhyxb_panel_ready(self, *, timeout_ms: int) -> None:
        """确保江湖英雄榜面板可见；必要时重新打开。"""
        if self.ensure_jhyxb_panel_visible(timeout_ms=timeout_ms):
            return

        self._log("江湖英雄榜面板不可见，尝试从主界面重新打开")
        self.close_all_panels(timeout_ms=1500, max_attempts=6)
        self._open_jhyxb_panel_via_activity()

    def close_purchase_dialog_if_needed(self) -> bool:
        """关闭额外挑战购买弹窗，避免误点其后的面板关闭按钮。"""
        if not self.find_image(
            [self.BTN_CLOSE, self.BTN_PANE_CLOSE],
            threshold=0.85,
            roi=self.scale_roi((850, 130, 140, 100)),
        ):
            return False

        self._log("关闭江湖英雄榜购买挑战次数弹窗")
        self.click(offset=0)
        self.wait(1000)
        return True

    def ensure_jhyxb_panel_visible(self, *, timeout_ms: int) -> bool:
        """等待江湖英雄榜面板标题出现。"""
        return self.wait_find_image_in_roi(
            self.TITLE_JHYXB,
            self.ROI_PANEL_TITLE,
            timeout_ms=timeout_ms,
            description="江湖英雄榜面板",
            threshold=0.85,
            interval_ms=500,
        )

    def is_jhyxb_panel_visible(self) -> bool:
        """返回江湖英雄榜面板当前是否可见。"""
        return self.find_image(
            self.TITLE_JHYXB,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_PANEL_TITLE),
        )

    def click_match_button(self) -> float:
        """点击面板匹配按钮，并开始五分钟匹配倒计时。"""
        if self.wait_find_image_in_roi(
            self.BTN_JHYXB_MATCH,
            self.ROI_MATCH_BUTTON,
            timeout_ms=5000,
            description="江湖英雄榜匹配按钮",
            threshold=0.85,
        ):
            self._log("点击江湖英雄榜匹配按钮")
            self.click(offset=0)
        else:
            self._log("未识别到匹配按钮模板，使用固定坐标点击")
            self.click_point(self.POINT_JHYXB_MATCH[0], self.POINT_JHYXB_MATCH[1], offset=0)

        return self._make_deadline(self.MATCH_READY_TIMEOUT_MS)

    def is_challenge_count_zero(self) -> bool:
        """返回剩余挑战次数是否可见为零。"""
        return self.find_image(
            self.TEXT_JHYXB_CHALLENGE_ZERO,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_CHALLENGE_ZERO),
        )

    def detect_first_battle_reward_state(self) -> tuple[str, dict[str, float]]:
        """识别首战宝箱状态，并保留分数供诊断使用。"""
        scores = {"claimed": 0.0, "ready": 0.0, "initial": 0.0}
        if self.is_first_battle_reward_claimed():
            scores["claimed"] = getattr(self, "_last_match_score", 0.0)
            return self.FIRST_BATTLE_REWARD_STATE_CLAIMED, scores
        scores["claimed"] = getattr(self, "_last_match_score", 0.0)

        if self.is_first_battle_reward_ready():
            scores["ready"] = getattr(self, "_last_match_score", 0.0)
            return self.FIRST_BATTLE_REWARD_STATE_READY, scores
        scores["ready"] = getattr(self, "_last_match_score", 0.0)

        if self.is_first_battle_reward_initial():
            scores["initial"] = getattr(self, "_last_match_score", 0.0)
            return self.FIRST_BATTLE_REWARD_STATE_INITIAL, scores
        scores["initial"] = getattr(self, "_last_match_score", 0.0)
        return self.FIRST_BATTLE_REWARD_STATE_UNKNOWN, scores

    def is_first_battle_reward_claimed(self) -> bool:
        """返回首战宝箱是否已领取。"""
        return self.find_image_once(
            self.ICON_JHYXB_FIRST_WIN_CHEST,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_FIRST_BATTLE_CHEST),
        )

    def is_first_battle_reward_ready(self) -> bool:
        """返回首战宝箱当前是否可领取。"""
        return self.find_image_once(
            self.ICON_JHYXB_FIRST_WIN_READY,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_FIRST_BATTLE_CHEST),
        )

    def is_first_battle_reward_initial(self) -> bool:
        """返回首战宝箱是否仍不可领取。"""
        return self.find_image_once(
            self.ICON_JHYXB_FIRST_WIN,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_FIRST_BATTLE_CHEST),
        )

    def is_first_battle_reward_claim_context_safe(self) -> bool:
        """返回面板是否已足够稳定，可进行坐标兜底点击。"""
        return self.is_jhyxb_panel_visible_quiet()

    def confirm_first_battle_reward_claimed(self) -> bool:
        """关闭奖励遮罩，并确认宝箱已领取状态。"""
        self.wait(1500)
        self.close_reward_dialogs(max_attempts=3, include_close_buttons=False)
        self._log("关闭江湖英雄榜首战奖励面板")
        self.click_point(
            self.POINT_FIRST_BATTLE_REWARD_DIALOG_DISMISS[0],
            self.POINT_FIRST_BATTLE_REWARD_DIALOG_DISMISS[1],
            offset=0,
        )
        self.wait(1000)

        if not self.ensure_jhyxb_panel_visible(timeout_ms=10000):
            return False

        return self.wait_find_image_in_roi(
            self.ICON_JHYXB_FIRST_WIN_CHEST,
            self.ROI_FIRST_BATTLE_CHEST,
            timeout_ms=2500,
            description="江湖英雄榜已领取首战宝箱",
            threshold=0.85,
        )

    def run_match_battle(self, match_index: int, *, match_deadline: float | None = None) -> None:
        """完成一场已匹配的江湖英雄榜战斗，并返回排行榜面板。"""
        self._battle_result_deadline: float | None = None
        ready_state = self.click_ready_button(match_index, deadline=match_deadline)
        if ready_state == self.MATCH_READY_STATE_READY:
            self.walk_forward_for_battle(self.BATTLE_FORWARD_MS)
            finish_state = self.wait_until_battle_complete(
                match_index,
                deadline=self._battle_result_deadline,
            )
        else:
            finish_state = ready_state

        if finish_state == self.BATTLE_FINISH_RESULT_PANEL:
            self.click_result_panel_exit()
        else:
            self._log(f"第 {match_index} 次战斗已回到江湖英雄榜面板，跳过结果面板退出点击")

        if not self.ensure_jhyxb_panel_visible(timeout_ms=30000):
            raise RuntimeError("战斗退出后未回到江湖英雄榜面板")

    def click_ready_button(self, match_index: int, *, deadline: float | None = None) -> str:
        """等待准备就绪、匹配完成或返回面板。"""
        if deadline is None:
            deadline = self._make_deadline(self.MATCH_READY_TIMEOUT_MS)
        last_heartbeat_at = 0.0

        while not self._is_deadline_expired(deadline):
            if self.confirm_match_leave_team_dialog_if_needed("江湖英雄榜"):
                last_heartbeat_at = 0.0
                continue

            if self.is_ready_button_visible():
                self._log("点击江湖英雄榜准备按钮")
                self.click(offset=0)
                self._battle_result_deadline = self._make_deadline(self.RESULT_TIMEOUT_MS)
                self.wait(1000)
                return self.MATCH_READY_STATE_READY

            if self.is_result_panel_visible_quiet():
                self._log(f"第 {match_index} 次匹配在等待准备时已出现结果面板")
                return self.BATTLE_FINISH_RESULT_PANEL

            if self.is_jhyxb_panel_visible_quiet():
                if self.is_challenge_count_zero_quiet():
                    self._log(f"第 {match_index} 次匹配后检测到挑战次数已用完")
                    return self.BATTLE_FINISH_RETURNED_PANEL
                if self.is_match_button_visible_quiet():
                    self._log(f"第 {match_index} 次匹配已回到江湖英雄榜面板")
                    return self.BATTLE_FINISH_RETURNED_PANEL

            now = time.perf_counter()
            if last_heartbeat_at <= 0 or (now - last_heartbeat_at) * 1000 >= self.MATCH_WAIT_HEARTBEAT_MS:
                self._debug(f"第 {match_index} 次江湖英雄榜匹配/准备等待中...")
                last_heartbeat_at = now
            self.wait(self.MATCH_WAIT_POLL_INTERVAL_MS)

        debug_path = self.save_debug_screenshot(f"jhyxb_match_{match_index}_ready_timeout")
        raise RuntimeError(f"第 {match_index} 次江湖英雄榜匹配/准备等待超时，已保存截图：{debug_path}")

    def is_ready_button_visible(self) -> bool:
        """无冗余未命中日志地返回准备按钮是否可见。"""
        return self.find_image_once(
            self.BTN_JHYXB_READY,
            threshold=0.85,
            roi=self.scale_roi((520, 40, 240, 120)),
        )

    def is_match_button_visible_quiet(self) -> bool:
        """返回面板是否已恢复到可点击匹配状态。"""
        return self.find_image_once(
            self.BTN_JHYXB_MATCH,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_MATCH_BUTTON),
        )

    def is_jhyxb_panel_visible_quiet(self) -> bool:
        """无冗余未命中日志地返回排行榜面板是否可见。"""
        return self.find_image_once(
            self.TITLE_JHYXB,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_PANEL_TITLE),
        )

    def is_challenge_count_zero_quiet(self) -> bool:
        """无冗余未命中日志地返回挑战次数是否为零。"""
        return self.find_image_once(
            self.TEXT_JHYXB_CHALLENGE_ZERO,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_CHALLENGE_ZERO),
        )

    def is_result_panel_visible_quiet(self) -> bool:
        """无冗余未命中日志地返回结果面板是否可见。"""
        if not self.BTN_JHYXB_RESULT_EXIT:
            return False
        return self.find_image_once(
            self.BTN_JHYXB_RESULT_EXIT,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_RESULT_EXIT_BUTTON),
        )

    def walk_forward_for_battle(self, duration_ms: int) -> None:
        """在战斗中向前移动，无需通过干净主场景检查。"""
        start = self.POINT_DIRECTION_JOYSTICK_CENTER
        end = self.POINT_DIRECTION_JOYSTICK_FORWARD
        self._log(f"江湖英雄榜战斗中向前走 {duration_ms}ms")
        self.swipe(start[0], start[1], end[0], end[1], duration_ms=duration_ms)

    def wait_until_battle_complete(self, match_index: int, *, deadline: float | None = None) -> str:
        """自动战斗，直到结果面板出现或返回排行榜面板。"""
        if deadline is None:
            deadline = self._make_deadline(self.RESULT_TIMEOUT_MS)
        missing_template_logged = False
        while not self._is_deadline_expired(deadline):
            if self.is_result_panel_visible():
                self._log(f"第 {match_index} 次战斗结果面板已出现")
                return self.BATTLE_FINISH_RESULT_PANEL

            if self.is_jhyxb_panel_visible():
                self._log(f"第 {match_index} 次战斗已返回江湖英雄榜面板")
                return self.BATTLE_FINISH_RETURNED_PANEL

            if not self.BTN_JHYXB_RESULT_EXIT and not missing_template_logged:
                self._log("结果面板退出按钮模板尚未生成，将持续自动战斗并在超时时保存截图")
                missing_template_logged = True

            self.auto_battle(interval_ms=self.AUTO_BATTLE_INTERVAL_MS)

            if self.is_result_panel_visible():
                self._log(f"第 {match_index} 次战斗结果面板已出现")
                return self.BATTLE_FINISH_RESULT_PANEL

            if self.is_jhyxb_panel_visible():
                self._log(f"第 {match_index} 次战斗已返回江湖英雄榜面板")
                return self.BATTLE_FINISH_RETURNED_PANEL

        debug_path = self.save_debug_screenshot(f"jhyxb_result_{match_index}_timeout")
        raise RuntimeError(f"第 {match_index} 次江湖英雄榜战斗结果等待超时，已保存截图：{debug_path}")

    def is_result_panel_visible(self) -> bool:
        """返回战后结果面板是否可见。"""
        if not self.BTN_JHYXB_RESULT_EXIT:
            return False
        return self.find_image(
            self.BTN_JHYXB_RESULT_EXIT,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_RESULT_EXIT_BUTTON),
        )

    def click_result_panel_exit(self) -> None:
        """点击战后结果面板中的退出按钮。"""
        if not self.BTN_JHYXB_RESULT_EXIT:
            self._log("结果面板退出按钮模板尚未配置，跳过模板点击")
            return

        if not self.wait_find_image_in_roi(
            self.BTN_JHYXB_RESULT_EXIT,
            self.ROI_RESULT_EXIT_BUTTON,
            timeout_ms=10000,
            description="江湖英雄榜结果面板退出按钮",
            threshold=0.85,
        ):
            raise RuntimeError("未找到江湖英雄榜结果面板退出按钮")

        self._log("点击江湖英雄榜结果面板退出按钮")
        self.click(offset=0)
        self.wait(3000)

    def close_reward_dialogs(self, max_attempts: int = 4, *, include_close_buttons: bool = True) -> bool:
        """若出现奖励或确认弹窗则关闭。"""
        closed = False
        for _ in range(max_attempts):
            if self.wait_image_appear([self.BTN_MODAL_OK, self.BTN_OK], timeout_ms=800, threshold=0.85):
                self._log("点击奖励/确认弹窗按钮")
                self.click(offset=0)
                self.wait(1000)
                closed = True
                continue

            if not include_close_buttons:
                break

            if self.wait_image_appear([self.BTN_CLOSE, self.BTN_PANE_CLOSE], timeout_ms=800, threshold=0.8):
                self._log("关闭奖励/临时弹窗")
                self.click(offset=0)
                self.wait(1000)
                closed = True
                continue

            break

        return closed

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"江湖英雄榜任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
