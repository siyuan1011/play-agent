"""悬赏任务 - 接取高奖励悬赏并复用现有玩法流程。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from botCore import ImageMatchResult, StepStopException, step
from botCore.execution import DslStepExecutor, resolve_step_jump

from ymjh_bot.task.RCFB_task import RCFBTask
from ymjh_bot.ym_game_task import YmGameTask


BountyCategory = Literal["聚义平冤", "江湖纪事"]
BountyAction = Literal["接取", "前往", "未知"]


@dataclass(frozen=True, slots=True)
class BountyCardSnapshot:
    """One fixed card slot read from a bounty-panel screenshot."""

    slot_index: int
    category: BountyCategory | None
    reward_glyph_count: int
    reward_eligible: bool
    action: BountyAction
    action_center: tuple[int, int] | None
    category_score: float = 0.0
    action_score: float = 0.0


@dataclass(frozen=True, slots=True)
class BountyPanelSnapshot:
    """Visual state derived from one bounty-panel screenshot."""

    screenshot: np.ndarray
    visible: bool
    daily_complete: bool
    cards: tuple[BountyCardSnapshot, ...] = ()

    @property
    def pending_cards(self) -> tuple[BountyCardSnapshot, ...]:
        return tuple(card for card in self.cards if card.action == "前往")

    @property
    def acceptable_cards(self) -> tuple[BountyCardSnapshot, ...]:
        return tuple(
            card
            for card in self.cards
            if card.action == "接取" and card.category is not None and card.reward_eligible
        )


class XSRWTask(YmGameTask):
    """一梦江湖悬赏任务。"""

    task_key = "XSRW"
    task_name = "悬赏任务"
    task_description = "接取悬赏盒子 100 以上任务并自动完成聚义平冤/日常副本"
    auto_recover_health = False
    DEFER_FOREGROUND_WAKE_TO_ON_START = True
    LEAVE_TEAM_ON_START = True
    STARTUP_CLOSE_SETTLE_WAIT_MS = 1000

    ICON_BOUNTY = str(YmGameTask.TEMPLATES_DIR / "icon_xsrw_bounty.png")
    TEXT_PANEL_TITLE = str(YmGameTask.TEMPLATES_DIR / "text_xsrw_panel_title.png")
    BTN_REFRESH = str(YmGameTask.TEMPLATES_DIR / "btn_xsrw_refresh.png")
    BTN_ACCEPT = str(YmGameTask.TEMPLATES_DIR / "btn_xsrw_accept.png")
    BTN_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_xsrw_forward.png")
    TEXT_DEPOSIT_NOTICE = str(
        YmGameTask.TEMPLATES_DIR / "text_xsrw_deposit_notice.png"
    )
    TEXT_CATEGORY_JYPY = str(YmGameTask.TEMPLATES_DIR / "text_xsrw_jypy.png")
    TEXT_CATEGORY_JHJS = str(YmGameTask.TEMPLATES_DIR / "text_xsrw_jhjs.png")
    TEXT_CHALLENGE_VICTORY = str(
        YmGameTask.TEMPLATES_DIR / "text_xsrw_challenge_victory.png"
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
    BTN_DAILY_FIND_TEAM = str(
        YmGameTask.TEMPLATES_DIR / "btn_xsrw_daily_find_team.png"
    )
    TEXT_DAILY_TEAM_LIST = str(
        YmGameTask.TEMPLATES_DIR / "text_xsrw_daily_team_list.png"
    )
    BTN_DAILY_JOIN_TEAM = str(
        YmGameTask.TEMPLATES_DIR / "btn_xsrw_daily_join_team.png"
    )
    BTN_DAILY_TEAM_REFRESH = str(
        YmGameTask.TEMPLATES_DIR / "btn_xsrw_daily_team_refresh.png"
    )
    BTN_DAILY_EXIT_SOLO = str(
        YmGameTask.TEMPLATES_DIR / "btn_xsrw_daily_exit_solo.png"
    )

    CARD_LEFTS = (260, 483, 705, 928)
    CARD_WIDTH = 215
    ROI_BOUNTY_ENTRY = (940, 0, 240, 110)
    ROI_PANEL_TITLE = (250, 105, 250, 70)
    ROI_REFRESH = (950, 105, 180, 70)
    ROI_TODAY_PROGRESS = (140, 506, 80, 30)
    ROI_DEPOSIT_NOTICE = (300, 250, 650, 180)
    ROI_CHALLENGE_VICTORY = (400, 100, 480, 180)
    ROI_DAILY_PANEL_TITLE = (0, 0, 260, 80)
    ROI_DAILY_CHALLENGE = (1040, 600, 220, 110)
    ROI_DAILY_CONFIRM = (930, 530, 270, 130)
    ROI_DAILY_FIND_TEAM = (870, 600, 230, 110)
    ROI_DAILY_TEAM_LIST = (740, 0, 190, 80)
    ROI_DAILY_JOIN_ACTIONS = (1160, 100, 100, 520)
    ROI_DAILY_TEAM_REFRESH = (1120, 640, 160, 80)
    ROI_DAILY_EXIT_SOLO = (700, 440, 300, 130)
    CARD_CATEGORY_Y = 178
    CARD_CATEGORY_HEIGHT = 48
    CARD_REWARD_X_OFFSET = 130
    CARD_REWARD_Y = 392
    CARD_REWARD_WIDTH = 64
    CARD_REWARD_HEIGHT = 35
    CARD_ACTION_X_OFFSET = 45
    CARD_ACTION_Y = 478
    CARD_ACTION_WIDTH = 140
    CARD_ACTION_HEIGHT = 60

    PANEL_THRESHOLD = 0.60
    ENTRY_THRESHOLD = 0.90
    REFRESH_THRESHOLD = 0.90
    CATEGORY_THRESHOLD = 0.75
    ACTION_THRESHOLD = 0.80
    DARK_GLYPH_MAX_GRAY = 145
    DARK_GLYPH_MIN_COLUMN_PIXELS = 2
    DARK_GLYPH_MIN_WIDTH = 3
    DARK_GLYPH_MIN_AREA = 12
    MIN_ELIGIBLE_REWARD_GLYPHS = 4  # x + at least three digits
    DAILY_COMPLETE_GLYPHS = 5  # 10/10; every 0..9 state has four glyphs

    ROUND_TASK_LIMIT = 4
    MAX_NO_PROGRESS_REFRESHES = 30
    PANEL_OPEN_TIMEOUT_MS = 15000
    PANEL_POLL_INTERVAL_MS = 300
    PANEL_OPEN_SETTLE_MS = 1200
    ACCEPT_SETTLE_MS = 800
    DEPOSIT_NOTICE_THRESHOLD = 0.90
    DEPOSIT_CONFIRM_POINT = (855, 508)
    DEPOSIT_CONFIRM_SETTLE_MS = 800
    REFRESH_SETTLE_MS = 900
    FORWARD_SETTLE_MS = 1500
    CHALLENGE_VICTORY_THRESHOLD = 0.90
    CHALLENGE_TIMEOUT_MS = 600000
    CHALLENGE_POLL_INTERVAL_MS = 1000
    CHALLENGE_VICTORY_EXIT_POINT = (640, 600)
    CHALLENGE_VICTORY_EXIT_SETTLE_MS = 2000
    DAILY_PANEL_THRESHOLD = 0.90
    DAILY_CHALLENGE_THRESHOLD = 0.90
    DAILY_CONFIRM_THRESHOLD = 0.90
    DAILY_TEAM_THRESHOLD = 0.90
    DAILY_JOIN_THRESHOLD = 0.85
    DAILY_SOLO_EXIT_THRESHOLD = 0.90
    DAILY_ENTRY_TIMEOUT_MS = 15000
    DAILY_ENTRY_SETTLE_MS = 5000
    DAILY_TEAM_JOIN_ROUNDS = 5
    DAILY_TEAM_MAX_APPLICATIONS_PER_ROUND = 4
    DAILY_TEAM_APPLICATION_WAIT_MS = 60000
    DAILY_TEAM_QUICK_CONFIRM_MS = 1500
    DAILY_TEAM_APPLICATION_POLL_MS = 1000
    DAILY_TEAM_LIST_SETTLE_MS = 1200
    DAILY_TEAM_LIST_CLOSE_POINT = (1234, 30)
    DAILY_TASK_WAIT_TIMEOUT_MS = 300000
    DAILY_SOLO_RAID_TIMEOUT_MS = 14400000

    RCFB_DELEGATE_STEPS = ("leave_team_after_completion",)

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._active_delegate: YmGameTask | None = None

    def reset_startup_state(self) -> None:
        self._active_delegate = None

    def stop(self) -> None:
        """Propagate queue stop/pause requests to the active delegated flow."""
        super().stop()
        if self._active_delegate is not None:
            self._active_delegate.stop()

    @step(retry=1, timeout_ms=None)
    def run_bounty_flow(self) -> None:
        """Run accept/execute/verify rounds until today's bounty work is done."""
        snapshot = self.open_bounty_panel(refresh=True)

        while not self.is_stopped():
            if snapshot.pending_cards:
                snapshot = self.execute_pending_bounties(snapshot)
                continue

            if snapshot.daily_complete:
                self._log("悬赏今日接取已达 10/10，且面板中不存在待完成任务")
                return

            snapshot = self.acquire_bounty_round(snapshot)
            if snapshot.pending_cards:
                snapshot = self.execute_pending_bounties(snapshot)
                continue

            if snapshot.daily_complete:
                self._log("悬赏今日接取已达 10/10，且面板中不存在待完成任务")
                return

            debug_path = self.save_debug_screenshot("xsrw_round_without_pending")
            raise RuntimeError(f"悬赏接取轮次结束但没有待完成任务，已保存截图：{debug_path}")

        raise StepStopException("Stop requested")

    def leave_team_if_present(self) -> None:
        """Normalize startup state without failing when already unteamed."""
        try:
            self.leave_team(timeout_ms=5000, wait_after_click_ms=1000)
        except StepStopException:
            raise
        except Exception as exc:
            self._log(f"悬赏启动退队检查未完成，按未组队继续：{exc}")

    def open_bounty_panel(self, *, refresh: bool) -> BountyPanelSnapshot:
        """Open the bounty panel from any Activity category and optionally refresh it."""
        snapshot = self.read_bounty_panel()
        if not snapshot.visible:
            self.open_activity_panel(wait_after_open_ms=2500)
            entry = self._wait_binary_match(
                self.ICON_BOUNTY,
                mode="light_foreground",
                threshold=self.ENTRY_THRESHOLD,
                roi=self.ROI_BOUNTY_ENTRY,
                timeout_ms=self.PANEL_OPEN_TIMEOUT_MS,
            )
            if not entry.found or entry.center is None:
                debug_path = self.save_debug_screenshot("xsrw_entry_missing")
                raise RuntimeError(f"活动面板未找到悬赏入口，已保存截图：{debug_path}")

            self._log("点击活动面板悬赏入口")
            self.tap(*entry.center)
            self.wait(self.PANEL_OPEN_SETTLE_MS)
            snapshot = self._wait_bounty_panel(timeout_ms=self.PANEL_OPEN_TIMEOUT_MS)

        if refresh:
            return self.refresh_bounty_panel(snapshot)
        return snapshot

    def refresh_bounty_panel(
        self,
        snapshot: BountyPanelSnapshot | None = None,
    ) -> BountyPanelSnapshot:
        """Refresh the panel and return the new canonical visual state."""
        current = snapshot or self.read_bounty_panel()
        if not current.visible:
            current = self.open_bounty_panel(refresh=False)

        match = self._binary_match(
            current.screenshot,
            self.BTN_REFRESH,
            mode="otsu_dark",
            threshold=self.REFRESH_THRESHOLD,
            roi=self.ROI_REFRESH,
        )
        if not match.found or match.center is None:
            debug_path = self.save_debug_screenshot("xsrw_refresh_missing")
            raise RuntimeError(f"悬赏面板未找到刷新按钮，已保存截图：{debug_path}")

        self._log("刷新悬赏任务状态")
        self.tap(*match.center)
        self.wait(self.REFRESH_SETTLE_MS)
        return self._wait_bounty_panel(timeout_ms=self.PANEL_OPEN_TIMEOUT_MS)

    def read_bounty_panel(self, screenshot: np.ndarray | None = None) -> BountyPanelSnapshot:
        """Read panel/card state from exactly one screenshot."""
        image = self.screenshot() if screenshot is None else screenshot
        panel_match = self._binary_match(
            image,
            self.TEXT_PANEL_TITLE,
            mode="otsu_dark",
            threshold=self.PANEL_THRESHOLD,
            roi=self.ROI_PANEL_TITLE,
        )
        if not panel_match.found:
            return BountyPanelSnapshot(
                screenshot=image,
                visible=False,
                daily_complete=False,
            )

        cards = tuple(
            self._read_bounty_card(image, slot_index, left)
            for slot_index, left in enumerate(self.CARD_LEFTS)
        )
        return BountyPanelSnapshot(
            screenshot=image,
            visible=True,
            daily_complete=self._is_daily_complete(image),
            cards=cards,
        )

    def acquire_bounty_round(
        self,
        snapshot: BountyPanelSnapshot,
    ) -> BountyPanelSnapshot:
        """Fill one round to four pending cards or stop early at the daily cap."""
        current = snapshot
        no_progress = 0

        while not self.is_stopped():
            pending_count = len(current.pending_cards)
            if current.daily_complete or pending_count >= self.ROUND_TASK_LIMIT:
                self._log(
                    f"本轮悬赏接取结束：待完成 {pending_count}/{self.ROUND_TASK_LIMIT}"
                    + ("，今日已达上限" if current.daily_complete else "")
                )
                return current

            candidates = current.acceptable_cards
            if not candidates:
                no_progress += 1
                if no_progress >= self.MAX_NO_PROGRESS_REFRESHES:
                    debug_path = self.save_debug_screenshot("xsrw_no_eligible_bounty")
                    raise RuntimeError(
                        f"连续 {self.MAX_NO_PROGRESS_REFRESHES} 次刷新未找到盒子 100 以上悬赏，"
                        f"已保存截图：{debug_path}"
                    )
                self._log(
                    "当前四个卡位没有可接取的盒子 100 以上悬赏，"
                    f"刷新重试 {no_progress}/{self.MAX_NO_PROGRESS_REFRESHES}"
                )
                current = self.refresh_bounty_panel(current)
                continue

            selected = candidates[0]
            success, current = self.attempt_accept_bounty(current, selected)
            if success:
                no_progress = 0
                self._log(
                    f"已确认接取第 {selected.slot_index + 1} 卡位"
                    f"{selected.category}悬赏（奖励字符段={selected.reward_glyph_count}）"
                )
            else:
                no_progress += 1
                self._log(
                    f"第 {selected.slot_index + 1} 卡位接取状态未确认，"
                    f"继续刷新检查 {no_progress}/{self.MAX_NO_PROGRESS_REFRESHES}"
                )

            if no_progress >= self.MAX_NO_PROGRESS_REFRESHES:
                debug_path = self.save_debug_screenshot("xsrw_accept_no_progress")
                raise RuntimeError(
                    f"悬赏接取连续 {self.MAX_NO_PROGRESS_REFRESHES} 次没有进展，"
                    f"已保存截图：{debug_path}"
                )

        raise StepStopException("Stop requested")

    def attempt_accept_bounty(
        self,
        before: BountyPanelSnapshot,
        card: BountyCardSnapshot,
    ) -> tuple[bool, BountyPanelSnapshot]:
        """Click one accept action and always refresh before returning."""
        if card.action != "接取" or card.action_center is None:
            raise ValueError("Only a confirmed accept card can be clicked")
        if card.category is None or not card.reward_eligible:
            raise ValueError("Refusing to click an unknown or low-reward bounty")

        before_pending = len(before.pending_cards)
        immediate_success = False
        refreshed: BountyPanelSnapshot | None = None

        try:
            self._log(
                f"点击第 {card.slot_index + 1} 卡位接取："
                f"{card.category}，奖励字符段={card.reward_glyph_count}"
            )
            self.tap(*card.action_center)
            self.wait(self.ACCEPT_SETTLE_MS)
            immediate = self.read_bounty_panel()
            if not immediate.visible and self.confirm_bounty_deposit_if_visible(
                immediate.screenshot,
            ):
                immediate = self.read_bounty_panel()
            immediate_success = self._accept_transition_confirmed(
                before_pending,
                card.slot_index,
                immediate,
            )
        finally:
            # The game can accept, reject, or race another player's claim.
            # Always make the next decision from a freshly refreshed panel.
            refreshed = self.refresh_bounty_panel()

        assert refreshed is not None
        success = immediate_success or len(refreshed.pending_cards) > before_pending
        return success, refreshed

    def confirm_bounty_deposit_if_visible(
        self,
        screenshot: np.ndarray | None = None,
    ) -> bool:
        """Confirm the deposit only after the bounty-specific notice is visible."""
        image = self.screenshot() if screenshot is None else screenshot
        match = self._binary_match(
            image,
            self.TEXT_DEPOSIT_NOTICE,
            mode="light_foreground",
            threshold=self.DEPOSIT_NOTICE_THRESHOLD,
            roi=self.ROI_DEPOSIT_NOTICE,
        )
        if not match.found:
            return False

        self._log("检测到悬赏押金确认，点击右侧押金按钮")
        self.click_point(*self.DEPOSIT_CONFIRM_POINT, offset=0)
        self.wait(self.DEPOSIT_CONFIRM_SETTLE_MS)
        return True

    def execute_pending_bounties(
        self,
        snapshot: BountyPanelSnapshot,
    ) -> BountyPanelSnapshot:
        """Execute pending cards until a refreshed panel has none left."""
        current = snapshot
        while current.pending_cards and not self.is_stopped():
            card = current.pending_cards[0]
            if card.category is None or card.action_center is None:
                debug_path = self.save_debug_screenshot("xsrw_pending_unknown")
                raise RuntimeError(f"待完成悬赏类型或前往按钮无法确认，已保存截图：{debug_path}")

            self._log(f"开始执行待完成悬赏：{card.category}")
            self.tap(*card.action_center)
            self.wait(self.FORWARD_SETTLE_MS)
            self._run_category_delegate(card.category)
            current = self.open_bounty_panel(refresh=True)
            remaining = sum(
                1 for pending in current.pending_cards if pending.category == card.category
            )
            if remaining:
                self._log(f"{card.category}仍有 {remaining} 个待完成悬赏，继续执行")
            else:
                self._log(f"{card.category}待完成悬赏已清空")

        if self.is_stopped():
            raise StepStopException("Stop requested")
        return current

    def _run_category_delegate(self, category: BountyCategory) -> None:
        if category == "聚义平冤":
            self.run_jypy_bounty_challenge()
            return
        if category != "江湖纪事":
            raise ValueError(f"Unsupported bounty category: {category}")

        joined_team = self.enter_daily_bounty_dungeon()
        delegate: YmGameTask = RCFBTask()
        delegate._screen_resolution = self._screen_resolution
        delegate.setup(
            self._adb,
            self._vision,
            self._logger,
            self._event_callback,
            verbose=self._verbose,
        )
        delegate.reset_startup_state()
        self._active_delegate = delegate
        try:
            self.wait_for_daily_bounty_task(delegate)
            self.run_daily_bounty_raid_flow(
                delegate,
                timeout_ms=(
                    delegate.TASK_FLOW_TIMEOUT_MS
                    if joined_team
                    else self.DAILY_SOLO_RAID_TIMEOUT_MS
                ),
            )
            if joined_team:
                self._execute_delegate_steps(
                    delegate,
                    self.RCFB_DELEGATE_STEPS,
                    category,
                )
            else:
                self.leave_daily_bounty_solo(delegate)
        finally:
            self._active_delegate = None

    def enter_daily_bounty_dungeon(self) -> bool:
        """Prefer a matching team, falling back to a direct solo challenge."""
        if self.try_join_daily_bounty_team():
            return True

        self._log("限定时间内未加入江湖纪事队伍，回到副本页使用单人挑战兜底")
        self.click_point(*self.DAILY_TEAM_LIST_CLOSE_POINT, offset=0)
        self.wait(self.DAILY_TEAM_LIST_SETTLE_MS)
        self.enter_daily_bounty_solo()
        return False

    def try_join_daily_bounty_team(self) -> bool:
        """Apply to visible teams for the exact dungeon selected by the bounty."""
        panel = self._wait_binary_match(
            self.TEXT_DAILY_PANEL_TITLE,
            mode="light_foreground",
            threshold=self.DAILY_PANEL_THRESHOLD,
            roi=self.ROI_DAILY_PANEL_TITLE,
            timeout_ms=self.DAILY_ENTRY_TIMEOUT_MS,
        )
        if not panel.found:
            debug_path = self.save_debug_screenshot("xsrw_daily_panel_missing")
            raise RuntimeError(f"江湖纪事悬赏未进入日常副本面板，已保存截图：{debug_path}")

        find_team = self._wait_binary_match(
            self.BTN_DAILY_FIND_TEAM,
            mode="otsu_dark",
            threshold=self.DAILY_TEAM_THRESHOLD,
            roi=self.ROI_DAILY_FIND_TEAM,
            timeout_ms=self.DAILY_ENTRY_TIMEOUT_MS,
        )
        if not find_team.found or find_team.center is None:
            debug_path = self.save_debug_screenshot("xsrw_daily_find_team_missing")
            raise RuntimeError(f"日常副本面板未找到寻找队伍按钮，已保存截图：{debug_path}")

        self._log("打开江湖纪事悬赏对应副本的队伍列表")
        self.tap(*find_team.center)
        team_list = self._wait_binary_match(
            self.TEXT_DAILY_TEAM_LIST,
            mode="light_foreground",
            threshold=self.DAILY_TEAM_THRESHOLD,
            roi=self.ROI_DAILY_TEAM_LIST,
            timeout_ms=self.DAILY_ENTRY_TIMEOUT_MS,
        )
        if not team_list.found:
            debug_path = self.save_debug_screenshot("xsrw_daily_team_list_missing")
            raise RuntimeError(f"未能确认日常副本队伍列表，已保存截图：{debug_path}")

        for round_index in range(1, self.DAILY_TEAM_JOIN_ROUNDS + 1):
            screenshot = self.screenshot()
            join_matches = self._vision.match_all_templates(
                screenshot,
                self.BTN_DAILY_JOIN_TEAM,
                threshold=self.DAILY_JOIN_THRESHOLD,
                roi=self.scale_roi(self.ROI_DAILY_JOIN_ACTIONS),
            )
            join_matches.sort(key=lambda match: match.center[1] if match.center else 9999)
            visible_join_matches = [
                match
                for match in join_matches[: self.DAILY_TEAM_MAX_APPLICATIONS_PER_ROUND]
                if match.center is not None
            ]
            if visible_join_matches:
                for application_index, match in enumerate(visible_join_matches, start=1):
                    self._log(
                        f"申请加入江湖纪事悬赏队伍 "
                        f"{round_index}/{self.DAILY_TEAM_JOIN_ROUNDS}-"
                        f"{application_index}/{len(visible_join_matches)}"
                    )
                    assert match.center is not None
                    self.tap(*match.center)
                    if self._wait_daily_team_follow_confirm(
                        timeout_ms=self.DAILY_TEAM_QUICK_CONFIRM_MS,
                    ):
                        self._log("已加入江湖纪事悬赏队伍并确认跟随")
                        return True

                if self._wait_daily_team_follow_confirm():
                    self._log("已加入江湖纪事悬赏队伍并确认跟随")
                    return True
            else:
                self._log(
                    f"当前未找到可申请的江湖纪事队伍 "
                    f"{round_index}/{self.DAILY_TEAM_JOIN_ROUNDS}"
                )

            refreshed = self._binary_match(
                self.screenshot(),
                self.BTN_DAILY_TEAM_REFRESH,
                mode="otsu_dark",
                threshold=self.DAILY_TEAM_THRESHOLD,
                roi=self.ROI_DAILY_TEAM_REFRESH,
            )
            if refreshed.found and refreshed.center is not None:
                self.tap(*refreshed.center)
                self.wait(self.DAILY_TEAM_LIST_SETTLE_MS)

        return False

    def _wait_daily_team_follow_confirm(self, *, timeout_ms: int | None = None) -> bool:
        deadline = self._make_deadline(timeout_ms or self.DAILY_TEAM_APPLICATION_WAIT_MS)
        while not self._is_deadline_expired(deadline):
            if self.confirm_center_modal_ok_if_visible(
                "江湖纪事悬赏入队跟随",
                wait_after_click_ms=2000,
            ):
                return True
            self.wait(self.DAILY_TEAM_APPLICATION_POLL_MS)
        return False

    def enter_daily_bounty_solo(self) -> None:
        """Enter the selected daily dungeon without a team as a final fallback."""
        confirm = self._wait_binary_match(
            self.BTN_DAILY_CONFIRM,
            mode="otsu_dark",
            threshold=self.DAILY_CONFIRM_THRESHOLD,
            roi=self.ROI_DAILY_CONFIRM,
            timeout_ms=1000,
        )
        if not confirm.found:
            panel = self._wait_binary_match(
                self.TEXT_DAILY_PANEL_TITLE,
                mode="light_foreground",
                threshold=self.DAILY_PANEL_THRESHOLD,
                roi=self.ROI_DAILY_PANEL_TITLE,
                timeout_ms=self.DAILY_ENTRY_TIMEOUT_MS,
            )
            if not panel.found:
                debug_path = self.save_debug_screenshot("xsrw_daily_panel_missing")
                raise RuntimeError(f"江湖纪事悬赏未进入日常副本面板，已保存截图：{debug_path}")

            challenge = self._wait_binary_match(
                self.BTN_DAILY_CHALLENGE,
                mode="otsu_dark",
                threshold=self.DAILY_CHALLENGE_THRESHOLD,
                roi=self.ROI_DAILY_CHALLENGE,
                timeout_ms=self.DAILY_ENTRY_TIMEOUT_MS,
            )
            if not challenge.found or challenge.center is None:
                debug_path = self.save_debug_screenshot("xsrw_daily_challenge_missing")
                raise RuntimeError(f"日常副本面板未找到挑战按钮，已保存截图：{debug_path}")

            self._log("点击江湖纪事悬赏日常副本挑战")
            self.tap(*challenge.center)
            confirm = self._wait_binary_match(
                self.BTN_DAILY_CONFIRM,
                mode="otsu_dark",
                threshold=self.DAILY_CONFIRM_THRESHOLD,
                roi=self.ROI_DAILY_CONFIRM,
                timeout_ms=self.DAILY_ENTRY_TIMEOUT_MS,
            )

        if not confirm.found or confirm.center is None:
            debug_path = self.save_debug_screenshot("xsrw_daily_confirm_missing")
            raise RuntimeError(f"日常副本挑战未出现确认按钮，已保存截图：{debug_path}")

        self._log("确认进入江湖纪事悬赏日常副本")
        self.tap(*confirm.center)
        self.wait(self.DAILY_ENTRY_SETTLE_MS)

    def wait_for_daily_bounty_task(self, delegate: RCFBTask) -> None:
        """Wait for the bounty dungeon tracker without rematching a different target."""
        if delegate.wait_for_dungeon_task(timeout_ms=self.DAILY_TASK_WAIT_TIMEOUT_MS):
            self._log("检测到江湖纪事悬赏副本任务追踪")
            return

        delegate.leave_team_if_present()
        debug_path = self.save_debug_screenshot("xsrw_daily_task_missing")
        raise RuntimeError(
            f"江湖纪事悬赏进入后未出现副本任务追踪，已退队并保存截图：{debug_path}"
        )

    def leave_daily_bounty_solo(self, delegate: RCFBTask) -> None:
        """Leave a solo dungeon using the right-side exit action."""
        if not delegate.click_template_if_available(
            delegate.ICON_DUNGEON_EXIT,
            timeout_ms=delegate.DUNGEON_EXIT_ACTION_TIMEOUT_MS,
            description="悬赏单人副本退出图标",
            threshold=delegate.DUNGEON_EXIT_THRESHOLD,
            roi=delegate.ROI_DUNGEON_EXIT,
            wait_after_click_ms=500,
        ):
            debug_path = self.save_debug_screenshot("xsrw_daily_solo_exit_missing")
            raise RuntimeError(f"悬赏单人副本未找到退出图标，已保存截图：{debug_path}")

        if not self.click_template_if_available(
            self.BTN_DAILY_EXIT_SOLO,
            timeout_ms=delegate.DUNGEON_EXIT_ACTION_TIMEOUT_MS,
            description="悬赏单人副本离开按钮",
            threshold=self.DAILY_SOLO_EXIT_THRESHOLD,
            roi=self.ROI_DAILY_EXIT_SOLO,
            wait_after_click_ms=0,
        ):
            debug_path = self.save_debug_screenshot("xsrw_daily_solo_exit_button_missing")
            raise RuntimeError(f"悬赏单人副本未找到离开副本按钮，已保存截图：{debug_path}")

        self._log("已点击离开悬赏单人副本，等待传送结束")
        delegate.wait_for_dungeon_transfer_complete(timeout_ms=60000)

    def run_daily_bounty_raid_flow(
        self,
        delegate: RCFBTask,
        *,
        timeout_ms: int | None = None,
    ) -> None:
        """Push solo/team dungeon trackers while tolerating battle-hidden sidebars."""
        deadline = self._make_deadline(timeout_ms or delegate.TASK_FLOW_TIMEOUT_MS)
        last_heartbeat_at = 0.0

        while not self._is_deadline_expired(deadline):
            if self.is_stopped() or delegate.is_stopped():
                raise StepStopException("Stop requested")

            if delegate.is_dungeon_transfer_out_visible():
                self._log("检测到江湖纪事悬赏副本传出倒计时")
                return

            if delegate.click_current_dungeon_task_if_visible():
                last_heartbeat_at = 0.0
                continue

            now = time.perf_counter()
            if last_heartbeat_at <= 0 or (now - last_heartbeat_at) * 1000 >= 30000:
                self._log("江湖纪事悬赏副本处于战斗/过图阶段，等待任务追踪恢复")
                last_heartbeat_at = now
            self.wait(delegate.TASK_FLOW_RETRY_WAIT_MS)

        debug_path = self.save_debug_screenshot("xsrw_daily_raid_timeout")
        raise RuntimeError(f"江湖纪事悬赏副本执行超时，已保存截图：{debug_path}")

    def run_jypy_bounty_challenge(self) -> None:
        """Wait for the direct bounty challenge and close its victory screen."""
        deadline = self._make_deadline(self.CHALLENGE_TIMEOUT_MS)
        while not self._is_deadline_expired(deadline):
            if self.is_stopped():
                raise StepStopException("Stop requested")

            screenshot = self.screenshot()
            victory = self._vision.match_template(
                screenshot,
                self.TEXT_CHALLENGE_VICTORY,
                threshold=self.CHALLENGE_VICTORY_THRESHOLD,
                roi=self.scale_roi(self.ROI_CHALLENGE_VICTORY),
            )
            if victory.found:
                self._log("检测到聚义平冤悬赏挑战胜利，退出结算页")
                self.click_point(*self.CHALLENGE_VICTORY_EXIT_POINT, offset=0)
                self.wait(self.CHALLENGE_VICTORY_EXIT_SETTLE_MS)
                return

            panel = self.read_bounty_panel(screenshot)
            if panel.visible:
                self._log("聚义平冤悬赏挑战已自动返回接取面板")
                return

            self.wait(self.CHALLENGE_POLL_INTERVAL_MS)

        debug_path = self.save_debug_screenshot("xsrw_jypy_challenge_timeout")
        raise RuntimeError(f"聚义平冤悬赏挑战等待胜利超时，已保存截图：{debug_path}")

    def _execute_delegate_steps(
        self,
        delegate: YmGameTask,
        step_names: tuple[str, ...],
        category: BountyCategory,
    ) -> None:
        all_steps = {name: (func, meta) for name, func, meta in delegate.get_steps()}
        missing = [name for name in step_names if name not in all_steps]
        if missing:
            raise RuntimeError(f"{category}复用步骤不存在：{', '.join(missing)}")

        steps = [(name, *all_steps[name]) for name in step_names]
        executor = DslStepExecutor(
            should_stop=lambda: self.is_stopped() or delegate.is_stopped(),
            emit=lambda message: self._log(f"{category}子流程 {message}"),
        )
        step_index = 0
        while step_index < len(steps):
            if self.is_stopped() or delegate.is_stopped():
                raise StepStopException("Stop requested")

            name, func, meta = steps[step_index]
            delegate._current_step_index = step_index
            self._log(f"{category}子流程步骤开始：{name}")
            result = executor.execute(delegate, name, func, meta)
            if self._logger:
                self._logger.log_step_result(f"xsrw_{category}_{name}", result)
            if not result.success:
                if self.is_stopped() or delegate.is_stopped():
                    raise StepStopException("Stop requested")
                raise RuntimeError(f"{category}子流程步骤 {name} 失败：{result.reason}")
            self._log(f"{category}子流程步骤完成：{name}")

            if delegate._jump_target:
                target = delegate._jump_target
                delegate._jump_target = None
                jump = resolve_step_jump(target, steps, step_index)
                if jump.message:
                    self._log(f"{category}子流程 {jump.message}")
                if jump.end_loop:
                    return
                step_index = jump.next_index
                continue

            step_index += 1

    def _read_bounty_card(
        self,
        screenshot: np.ndarray,
        slot_index: int,
        left: int,
    ) -> BountyCardSnapshot:
        category_roi = (
            left,
            self.CARD_CATEGORY_Y,
            self.CARD_WIDTH,
            self.CARD_CATEGORY_HEIGHT,
        )
        jypy_match = self._binary_match(
            screenshot,
            self.TEXT_CATEGORY_JYPY,
            mode="light_foreground",
            threshold=self.CATEGORY_THRESHOLD,
            roi=category_roi,
        )
        daily_match = self._binary_match(
            screenshot,
            self.TEXT_CATEGORY_JHJS,
            mode="light_foreground",
            threshold=self.CATEGORY_THRESHOLD,
            roi=category_roi,
        )
        category: BountyCategory | None = None
        category_score = max(jypy_match.score, daily_match.score)
        if jypy_match.found and jypy_match.score >= daily_match.score:
            category = "聚义平冤"
        elif daily_match.found:
            category = "江湖纪事"

        action_roi = (
            left + self.CARD_ACTION_X_OFFSET,
            self.CARD_ACTION_Y,
            self.CARD_ACTION_WIDTH,
            self.CARD_ACTION_HEIGHT,
        )
        accept_match = self._binary_match(
            screenshot,
            self.BTN_ACCEPT,
            mode="otsu_dark",
            threshold=self.ACTION_THRESHOLD,
            roi=action_roi,
        )
        forward_match = self._binary_match(
            screenshot,
            self.BTN_FORWARD,
            mode="otsu_dark",
            threshold=self.ACTION_THRESHOLD,
            roi=action_roi,
        )
        action: BountyAction = "未知"
        action_center: tuple[int, int] | None = None
        action_score = max(accept_match.score, forward_match.score)
        if accept_match.found and accept_match.score >= forward_match.score:
            action = "接取"
            action_center = accept_match.center
        elif forward_match.found:
            action = "前往"
            action_center = forward_match.center

        reward_roi = (
            left + self.CARD_REWARD_X_OFFSET,
            self.CARD_REWARD_Y,
            self.CARD_REWARD_WIDTH,
            self.CARD_REWARD_HEIGHT,
        )
        reward_glyph_count = self.count_reward_glyph_runs(screenshot, reward_roi)
        return BountyCardSnapshot(
            slot_index=slot_index,
            category=category,
            reward_glyph_count=reward_glyph_count,
            reward_eligible=reward_glyph_count >= self.MIN_ELIGIBLE_REWARD_GLYPHS,
            action=action,
            action_center=action_center,
            category_score=category_score,
            action_score=action_score,
        )

    def _is_daily_complete(self, screenshot: np.ndarray) -> bool:
        return (
            self.count_otsu_dark_glyph_runs(screenshot, self.ROI_TODAY_PROGRESS)
            >= self.DAILY_COMPLETE_GLYPHS
        )

    @classmethod
    def count_reward_glyph_runs(
        cls,
        screenshot: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> int:
        """Count the brown fixed-font reward glyphs without recognizing text."""
        x, y, width, height = roi
        crop = screenshot[y : y + height, x : x + width]
        if crop.size == 0:
            return 0

        if crop.ndim == 2:
            bgr = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
        else:
            bgr = crop[:, :, :3]
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # Reward text keeps the same brown hue while the translucent panel can
        # make its background either very light or almost black.  Derive the
        # saturation cutoff from the stable leading ``x`` glyph, then count
        # shapes only; no character value is decoded.
        base_mask = (
            (hsv[:, :, 0] >= 5)
            & (hsv[:, :, 0] <= 35)
            & (hsv[:, :, 2] >= 35)
            & (hsv[:, :, 2] <= 180)
        )
        leading = hsv[:, 4:19, 1][base_mask[:, 4:19]]
        if leading.size == 0:
            return 0
        saturation_cutoff = max(30, int(np.percentile(leading, 90) * 0.60))
        mask = base_mask & (hsv[:, :, 1] >= saturation_cutoff)
        return cls._count_glyph_runs_from_mask(mask, min_start_column=4)

    @classmethod
    def count_otsu_dark_glyph_runs(
        cls,
        screenshot: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> int:
        """Count dark progress glyphs against either opaque or translucent panels."""
        x, y, width, height = roi
        crop = screenshot[y : y + height, x : x + width]
        if crop.size == 0:
            return 0
        if crop.ndim == 2:
            gray = crop
        else:
            gray = cv2.cvtColor(crop[:, :, :3], cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU,
        )
        return cls._count_glyph_runs_from_mask(binary > 0)

    @classmethod
    def count_dark_glyph_runs(
        cls,
        screenshot: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> int:
        """Count fixed-threshold dark glyphs in a controlled test/image region."""
        x, y, width, height = roi
        crop = screenshot[y : y + height, x : x + width]
        if crop.size == 0:
            return 0
        if crop.ndim == 2:
            gray = crop
        else:
            gray = cv2.cvtColor(crop[:, :, :3], cv2.COLOR_BGR2GRAY)
        return cls._count_glyph_runs_from_mask(gray < cls.DARK_GLYPH_MAX_GRAY)

    @classmethod
    def _count_glyph_runs_from_mask(
        cls,
        mask: np.ndarray,
        *,
        min_start_column: int = 0,
    ) -> int:
        active_columns = np.flatnonzero(
            np.count_nonzero(mask, axis=0) >= cls.DARK_GLYPH_MIN_COLUMN_PIXELS
        )
        if active_columns.size == 0:
            return 0

        runs: list[tuple[int, int]] = []
        start = previous = int(active_columns[0])
        for column in active_columns[1:]:
            current = int(column)
            if current > previous + 1:
                runs.append((start, previous))
                start = current
            previous = current
        runs.append((start, previous))

        valid_runs = 0
        for start, end in runs:
            run_width = end - start + 1
            run_area = int(np.count_nonzero(mask[:, start : end + 1]))
            if (
                start >= min_start_column
                and run_width >= cls.DARK_GLYPH_MIN_WIDTH
                and run_area >= cls.DARK_GLYPH_MIN_AREA
            ):
                valid_runs += 1
        return valid_runs

    @staticmethod
    def _accept_transition_confirmed(
        before_pending: int,
        slot_index: int,
        after: BountyPanelSnapshot,
    ) -> bool:
        if not after.visible:
            return False
        if len(after.pending_cards) > before_pending:
            return True
        return any(
            card.slot_index == slot_index and card.action == "前往"
            for card in after.cards
        )

    def _wait_bounty_panel(self, *, timeout_ms: int) -> BountyPanelSnapshot:
        deadline = self._make_deadline(timeout_ms)
        last = self.read_bounty_panel()
        while not last.visible and not self._is_deadline_expired(deadline):
            self.wait(self.PANEL_POLL_INTERVAL_MS)
            last = self.read_bounty_panel()
        if last.visible:
            return last

        debug_path = self.save_debug_screenshot("xsrw_panel_missing")
        raise RuntimeError(f"未能确认悬赏接取面板，已保存截图：{debug_path}")

    def _wait_binary_match(
        self,
        template: str,
        *,
        mode: Literal["otsu_dark", "light_foreground"],
        threshold: float,
        roi: tuple[int, int, int, int],
        timeout_ms: int,
    ) -> ImageMatchResult:
        deadline = self._make_deadline(timeout_ms)
        last = ImageMatchResult(False, 0.0, None, None)
        while not self._is_deadline_expired(deadline):
            last = self._binary_match(
                self.screenshot(),
                template,
                mode=mode,
                threshold=threshold,
                roi=roi,
            )
            if last.found:
                return last
            self.wait(self.PANEL_POLL_INTERVAL_MS)
        return last

    def _binary_match(
        self,
        screenshot: np.ndarray,
        template: str,
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

    def on_finish(self, results: list) -> None:
        success_count = sum(1 for result in results if result.success)
        self._log("=" * 40)
        self._log(f"悬赏任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
