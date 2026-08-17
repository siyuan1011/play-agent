"""华山论剑任务 - Python DSL 实现。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class HSLJTask(YmGameTask):
    """一梦江湖华山论剑任务。"""

    task_key = "HSLJ"
    task_name = "华山论剑"
    task_description = "按配置完成华山论剑 1v1/3v3"
    auto_recover_health = False
    RETURN_TO_SAFE_ZONE_ON_START = True
    DEFER_FOREGROUND_WAKE_TO_ON_START = True
    STARTUP_CLOSE_SETTLE_WAIT_MS = 1000
    SAFE_ZONE_RETURN_FAILURE_LOG = "返回鸡鸣寺安全区未完成，继续从当前界面打开华山论剑：{error}"

    BTN_HSLJ_ACTIVITY_1V1 = str(YmGameTask.TEMPLATES_DIR / "btn_hslj_activity_1v1.png")
    BTN_HSLJ_ACTIVITY_OPEN = str(YmGameTask.TEMPLATES_DIR / "btn_open.png")
    TITLE_HSLJ = str(YmGameTask.TEMPLATES_DIR / "text_HSLJ_title.png")
    TAB_HSLJ_1V1_ACTIVE = str(YmGameTask.TEMPLATES_DIR / "tab_hslj_1v1_active.png")
    TAB_HSLJ_3V3_ACTIVE = str(YmGameTask.TEMPLATES_DIR / "tab_hslj_3v3_active.png")
    BTN_HSLJ_MATCH = str(YmGameTask.TEMPLATES_DIR / "btn_hslj_match.png")
    BTN_HSLJ_MATCH_3V3 = str(YmGameTask.TEMPLATES_DIR / "btn_hslj_match_3v3.png")
    BTN_HSLJ_MATCH_EXIT = str(YmGameTask.TEMPLATES_DIR / "btn_hslj_match_exit.png")
    BTN_HSLJ_MATCH_EXIT_3V3 = str(YmGameTask.TEMPLATES_DIR / "btn_hslj_match_exit_3v3.png")
    BTN_HSLJ_MATCH_TEMPLATES = [BTN_HSLJ_MATCH, BTN_HSLJ_MATCH_3V3]
    BTN_HSLJ_MATCH_EXIT_TEMPLATES = [BTN_HSLJ_MATCH_EXIT, BTN_HSLJ_MATCH_EXIT_3V3]
    BTN_HSLJ_READY_TEMPLATES = [str(YmGameTask.TEMPLATES_DIR / "text_ready.png")]
    ICON_HSLJ_FIRST_WIN = str(YmGameTask.TEMPLATES_DIR / "icon_hslj_first_win.png")
    ICON_HSLJ_FIRST_WIN_READY = str(YmGameTask.TEMPLATES_DIR / "icon_hslj_first_win_ready.png")
    ICON_HSLJ_FIRST_WIN_CHEST = str(YmGameTask.TEMPLATES_DIR / "icon_hslj_first_win_chest.png")
    TEXT_HSLJ_EXIT = str(YmGameTask.TEMPLATES_DIR / "text_exit.png")
    TEXT_HSLJ_MATCH_SUCCESS = str(YmGameTask.TEMPLATES_DIR / "text_hslj_match_success.png")

    # 固定坐标点 (设计分辨率 1280x720 下)
    POINT_ACTIVITY_HSLJ_ICON = (220, 222)
    POINT_ACTIVITY_HSLJ_OPEN = (835, 462)
    POINT_TAB_1V1 = (1118, 170)
    POINT_TAB_3V3 = (1118, 270)
    POINT_HSLJ_MATCH = (952, 590)
    POINT_FIRST_WIN_CHEST = (954, 498)
    POINT_HSLJ_READY = (640, 97)

    ROI_PANEL_TITLE = (170, 45, 330, 80)
    ROI_SIDE_TABS = (1035, 115, 165, 285)
    ROI_MATCH_BUTTON = (850, 535, 220, 115)
    ROI_FIRST_WIN_CHEST = (900, 450, 130, 100)
    ROI_RESULT_EXIT_TEXT = (540, 630, 180, 80)
    ROI_HSLJ_TEMP_DIALOG_CLOSE = (1080, 210, 115, 100)

    DEFAULT_LUNJIAN_COUNT = 5
    MODE_1V1 = "1v1"
    MODE_3V3 = "3v3"
    STRATEGY_FIRST_WIN = "first_win"
    STRATEGY_INFINITE = "infinite"
    STRATEGY_FIXED_COUNT = "fixed_count"
    VALID_STRATEGIES = {
        STRATEGY_FIRST_WIN,
        STRATEGY_INFINITE,
        STRATEGY_FIXED_COUNT,
    }
    DEFAULT_MODE_SETTINGS: dict[str, dict[str, Any]] = {
        MODE_1V1: {"strategy": STRATEGY_FIRST_WIN, "count": DEFAULT_LUNJIAN_COUNT},
        MODE_3V3: {"strategy": STRATEGY_FIXED_COUNT, "count": DEFAULT_LUNJIAN_COUNT},
    }
    CLOSE_ALL_MAX_ATTEMPTS = 12
    MATCH_SETTLE_WAIT_MS = 2500
    MATCH_WAIT_POLL_INTERVAL_MS = 3000
    MATCH_WAIT_HEARTBEAT_MS = 10000
    MODE_SWITCH_MAX_ATTEMPTS = 3
    HSLJ_TEMP_DIALOG_CLOSE_THRESHOLD = 0.70
    HSLJ_REWARD_DIALOG_MAX_ATTEMPTS = 3
    BATTLE_FORWARD_MS = 5000
    AUTO_BATTLE_INTERVAL_MS = 250
    MATCH_READY_STATE_READY = "ready"
    BATTLE_FINISH_RESULT_PANEL = "result_panel"
    BATTLE_FINISH_RETURNED_PANEL = "hslj_panel"
    FIRST_WIN_REWARD_CLAIMED = "claimed"
    FIRST_WIN_REWARD_NOT_READY = "not_ready"
    FIRST_WIN_REWARD_BLOCKED = "blocked"

    def __init__(
        self,
        default_interval_ms: int | None = None,
        *,
        lunjian_count: int = DEFAULT_LUNJIAN_COUNT,
        lunjian_infinite: bool = False,
        hslj_settings: dict[str, Any] | None = None,
        mode_settings: dict[str, Any] | None = None,
        lunjian_modes: dict[str, Any] | None = None,
    ):
        super().__init__(default_interval_ms=default_interval_ms)
        settings = hslj_settings
        if settings is None:
            settings = mode_settings
        if settings is None:
            settings = lunjian_modes
        self.lunjian_mode_settings = self.normalize_mode_settings(
            settings,
            legacy_count=lunjian_count,
            legacy_infinite=lunjian_infinite,
        )
        # Backwards-compatible attributes used by older tests and callers.
        self.lunjian_count = self.mode_count(self.MODE_3V3)
        self.lunjian_infinite = self.mode_strategy(self.MODE_3V3) == self.STRATEGY_INFINITE

    @classmethod
    def normalize_mode_settings(
        cls,
        settings: Any,
        *,
        legacy_count: int = DEFAULT_LUNJIAN_COUNT,
        legacy_infinite: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """Normalize per-mode Huashan Lunjian strategy settings."""
        normalized = {
            mode: dict(defaults)
            for mode, defaults in cls.DEFAULT_MODE_SETTINGS.items()
        }
        if not isinstance(settings, dict):
            return cls.normalize_legacy_mode_settings(
                normalized,
                lunjian_count=legacy_count,
                lunjian_infinite=legacy_infinite,
            )

        if cls.MODE_1V1 in settings or cls.MODE_3V3 in settings:
            for mode, defaults in cls.DEFAULT_MODE_SETTINGS.items():
                normalized[mode] = cls.normalize_single_mode_setting(
                    settings.get(mode),
                    defaults=defaults,
                )
            return normalized

        return cls.normalize_legacy_mode_settings(
            normalized,
            lunjian_count=settings.get("lunjian_count", legacy_count),
            lunjian_infinite=bool(settings.get("infinite", legacy_infinite)),
        )

    @classmethod
    def normalize_single_mode_setting(
        cls,
        settings: Any,
        *,
        defaults: dict[str, Any],
    ) -> dict[str, Any]:
        """Normalize a single mode setting dictionary."""
        normalized = dict(defaults)
        if not isinstance(settings, dict):
            return normalized

        strategy = str(settings.get("strategy", normalized["strategy"]) or "").strip()
        if strategy not in cls.VALID_STRATEGIES:
            strategy = str(defaults["strategy"])
        normalized["strategy"] = strategy

        try:
            count = int(settings.get("count", normalized["count"]))
        except (TypeError, ValueError):
            count = int(defaults["count"])
        normalized["count"] = max(1, min(count, 9999))
        return normalized

    @classmethod
    def normalize_legacy_mode_settings(
        cls,
        normalized: dict[str, dict[str, Any]],
        *,
        lunjian_count: Any,
        lunjian_infinite: bool,
    ) -> dict[str, dict[str, Any]]:
        """Migrate legacy 3v3-only count/infinite settings."""
        try:
            count = int(lunjian_count)
        except (TypeError, ValueError):
            count = cls.DEFAULT_LUNJIAN_COUNT
        normalized[cls.MODE_3V3] = {
            "strategy": cls.STRATEGY_INFINITE if lunjian_infinite else cls.STRATEGY_FIXED_COUNT,
            "count": max(1, min(count, 9999)),
        }
        return normalized

    def mode_strategy(self, mode: str) -> str:
        """Return the configured strategy for a mode."""
        return str(self.lunjian_mode_settings[mode]["strategy"])

    def mode_count(self, mode: str) -> int:
        """Return the configured fixed count for a mode."""
        return int(self.lunjian_mode_settings[mode]["count"])

    @step(retry=3, timeout_ms=30000)
    def open_fenzheng_activity(self) -> None:
        """打开活动界面并切换到纷争页签。"""
        self.open_fenzheng_activity_panel()

    @step(retry=3, timeout_ms=30000)
    def open_panel(self) -> None:
        """从活动页安全打开华山论剑面板，不触发 1v1/3v3 默认匹配。"""
        self.open_hslj_from_activity()

    @step(retry=0, timeout_ms=None)
    def complete_1v1(self) -> None:
        """按配置完成 1v1 挑战。"""
        self.ensure_hslj_mode_ready_for_match(self.MODE_1V1)

        strategy = self.mode_strategy(self.MODE_1V1)
        if strategy == self.STRATEGY_FIRST_WIN:
            self.complete_mode_until_first_win(self.MODE_1V1)
            return

        if strategy == self.STRATEGY_INFINITE:
            self.complete_mode_infinite(self.MODE_1V1)
            return

        self.complete_mode_fixed_count(self.MODE_1V1)

    def complete_mode_until_first_win(self, mode: str) -> None:
        """Run a mode until the first-win chest is confirmed claimed."""
        match_index = 1
        while not self.is_stopped():
            first_state = self.resolve_first_win_reward(mode)
            if first_state == self.FIRST_WIN_REWARD_CLAIMED:
                self._log(f"检测到华山论剑 {mode} 首胜奖励已领取，跳过匹配")
                return

            self.ensure_hslj_mode_ready_for_match(mode)
            self._log(f"开始第 {match_index}/首胜 场华山论剑 {mode} 匹配")
            self.click_match_button()
            self.run_match_battle(mode, match_index)
            match_index += 1

        self._log(f"华山论剑 {mode} 首胜匹配已停止")

    def complete_mode_infinite(self, mode: str) -> None:
        """Run a mode until the task is stopped."""
        index = 1
        self._log(f"华山论剑 {mode} 无限匹配模式已启用")
        while not self.is_stopped():
            self._log(f"开始第 {index}/无限 场华山论剑 {mode} 匹配")
            self.ensure_hslj_mode_ready_for_match(mode)
            self.click_match_button()
            self.run_match_battle(mode, index)
            self.claim_first_win_reward(mode)
            index += 1
        self._log(f"华山论剑 {mode} 无限匹配已停止")

    def complete_mode_fixed_count(self, mode: str) -> None:
        """Run a mode for its configured fixed count."""
        count = self.mode_count(mode)
        for index in range(1, count + 1):
            if self.is_stopped():
                self._log(f"华山论剑 {mode} 固定次数匹配已停止")
                return
            self._log(f"开始第 {index}/{count} 场华山论剑 {mode} 匹配")
            self.ensure_hslj_mode_ready_for_match(mode)
            self.click_match_button()
            self.run_match_battle(mode, index)
            self.claim_first_win_reward(mode)

        self._log(f"已执行 {count} 场华山论剑 {mode}，按配置结束")

    @step(retry=1, timeout_ms=60000)
    def claim_first_win(self) -> None:
        """领取当前华山论剑模式首胜奖励。"""
        self.ensure_hslj_mode_ready_for_match(self.MODE_1V1)
        if not self.claim_first_win_reward(self.MODE_1V1):
            self._log("华山论剑 1v1 首胜奖励未确认领取")

    @step(retry=3, timeout_ms=30000)
    def switch_to_3v3(self) -> None:
        """切换到 3v3 页签。"""
        self.ensure_hslj_panel_ready(mode="3v3", timeout_ms=10000)
        self.settle_residual_state_before_mode_switch(self.MODE_3V3)
        self.settle_hslj_reward_dialogs()
        self.select_hslj_mode(self.MODE_3V3)

    @step(retry=0, timeout_ms=None)
    def complete_3v3_matches(self) -> None:
        """Complete configured 3v3 matches."""
        self.ensure_hslj_mode_ready_for_match(self.MODE_3V3)

        strategy = self.mode_strategy(self.MODE_3V3)
        if strategy == self.STRATEGY_FIRST_WIN:
            self.complete_mode_until_first_win(self.MODE_3V3)
            return

        if strategy == self.STRATEGY_INFINITE:
            self.complete_mode_infinite(self.MODE_3V3)
            return

        self.complete_mode_fixed_count(self.MODE_3V3)

    @step(retry=1, timeout_ms=10000)
    def final_cleanup(self) -> None:
        """任务结束前关闭临时弹窗。"""
        self.close_reward_dialogs(max_attempts=2)

    def open_fenzheng_activity_panel(self) -> None:
        """Open the activity panel and switch to the Fen Zheng tab."""
        self.open_activity_panel(
            "纷争",
            wait_after_open_ms=2500,
            wait_after_category_ms=1500,
        )

    def open_hslj_from_activity(self, mode: str | None = None) -> None:
        """Open Huashan Lunjian from Activity - Fen Zheng without clicking 1v1/3v3."""
        self.click_activity_hslj_icon()
        self.click_activity_hslj_open_button()
        self.wait(2000)
        if not self.ensure_hslj_panel_visible(timeout_ms=5000):
            raise RuntimeError("未进入华山论剑面板")

    def click_activity_hslj_icon(self) -> None:
        """Click the Huashan activity icon/card, not the 1v1 or 3v3 buttons."""
        if self.wait_find_image_in_roi(
            self.BTN_HSLJ_ACTIVITY_1V1,
            (105, 170, 250, 190),
            timeout_ms=5000,
            description="活动页华山论剑卡片",
            threshold=0.85,
        ):
            self._log("识别到活动页华山论剑卡片，点击上方图标")
        else:
            self._log("未识别到活动页华山论剑卡片模板，使用固定图标坐标点击")
        self.click_point(self.POINT_ACTIVITY_HSLJ_ICON[0], self.POINT_ACTIVITY_HSLJ_ICON[1], offset=0)
        self.wait(1000)

    def click_activity_hslj_open_button(self) -> None:
        """Click the Activity-page open button for Huashan Lunjian."""
        if self.wait_find_image_in_roi(
            self.BTN_HSLJ_ACTIVITY_OPEN,
            (730, 410, 210, 105),
            timeout_ms=5000,
            description="活动页华山论剑打开按钮",
            threshold=0.85,
        ):
            self._log("点击活动页华山论剑打开按钮")
            self.click(offset=0)
            return

        self._log("未识别到活动页华山论剑打开按钮模板，使用固定坐标点击")
        self.click_point(self.POINT_ACTIVITY_HSLJ_OPEN[0], self.POINT_ACTIVITY_HSLJ_OPEN[1], offset=0)

    def ensure_hslj_panel_ready(self, *, mode: str, timeout_ms: int) -> None:
        """Ensure the Huashan Lunjian panel is visible, reopening it if needed."""
        if self.ensure_hslj_panel_visible(timeout_ms=timeout_ms):
            return

        if self.resolve_hslj_transient_state(mode):
            return

        self._log("华山论剑面板不可见，尝试从主界面重新打开")
        self.close_all_panels(timeout_ms=1500, max_attempts=6)
        self.open_fenzheng_activity_panel()
        self.open_hslj_from_activity(mode)

    def ensure_hslj_mode_ready_for_match(self, mode: str) -> None:
        """Ensure the Huashan panel and target mode are ready before matching."""
        self.settle_hslj_reward_dialogs()
        self.ensure_hslj_panel_ready(mode=mode, timeout_ms=10000)
        if not self.is_hslj_mode_selected_quiet(mode):
            self.settle_hslj_reward_dialogs()
            self.select_hslj_mode(mode)

    def select_hslj_mode(self, mode: str) -> None:
        """Select the requested Huashan Lunjian right-side tab."""
        active_template, point, description = self._tab_mode_target(mode)
        for attempt in range(1, self.MODE_SWITCH_MAX_ATTEMPTS + 1):
            self._log(f"切换华山论剑到 {description} 页签，第 {attempt} 次")
            self.click_point(point[0], point[1], offset=0)
            self.wait(1500)

            if self.ensure_hslj_mode_selected(mode, timeout_ms=1200):
                self._log(f"华山论剑已在 {description} 页签")
                return

        debug_path = self.save_debug_screenshot(f"hslj_switch_{mode}_failed")
        raise RuntimeError(f"切换华山论剑 {description} 后未确认真实页签，已保存截图：{debug_path}")

    def ensure_hslj_panel_visible(self, *, timeout_ms: int) -> bool:
        """Wait for the Huashan Lunjian panel title."""
        return self.wait_find_image_in_roi(
            self.TITLE_HSLJ,
            self.ROI_PANEL_TITLE,
            timeout_ms=timeout_ms,
            description="华山论剑面板",
            threshold=0.85,
            interval_ms=500,
        )

    def ensure_hslj_mode_selected(self, mode: str, *, timeout_ms: int) -> bool:
        """Wait until the Huashan panel and requested mode tab are both stable."""
        deadline = self._make_deadline(timeout_ms)
        while not self._is_deadline_expired(deadline):
            if self.is_hslj_mode_selected_quiet(mode):
                return True
            self.wait(300)
        return False

    def is_hslj_mode_selected_quiet(self, mode: str) -> bool:
        """Return whether the requested Huashan mode tab is active and exclusive."""
        active_template, _, _ = self._tab_mode_target(mode)
        other_mode = self.MODE_3V3 if mode == self.MODE_1V1 else self.MODE_1V1
        other_template, _, _ = self._tab_mode_target(other_mode)
        if not self.is_hslj_panel_visible_quiet():
            return False
        if not self.find_image_once(
            active_template,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_SIDE_TABS),
        ):
            return False
        return not self.find_image_once(
            other_template,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_SIDE_TABS),
        )

    def is_hslj_panel_visible(self) -> bool:
        """Return whether the Huashan Lunjian panel is currently visible."""
        return self.find_image(
            self.TITLE_HSLJ,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_PANEL_TITLE),
        )

    def claim_first_win_reward(self, mode: str) -> bool:
        """Try once to claim the first-win reward for the current Huashan mode."""
        return self.resolve_first_win_reward(mode) == self.FIRST_WIN_REWARD_CLAIMED

    def resolve_first_win_reward(self, mode: str) -> str:
        """Resolve whether a first-win reward allows another match to start."""
        self.settle_hslj_reward_dialogs()
        if not self.is_first_win_claim_context_safe(mode):
            self._log(f"当前不在可领取华山论剑 {mode} 首胜奖励的稳定面板，跳过领取")
            return self.FIRST_WIN_REWARD_BLOCKED

        reward_state, scores = self.detect_first_win_reward_state()
        if reward_state == "claimed":
            self._log(f"华山论剑 {mode} 首胜奖励已领取")
            return self.FIRST_WIN_REWARD_CLAIMED

        if reward_state == "ready":
            self._log(f"点击华山论剑 {mode} 可领取首胜奖励")
            self.click(offset=0)
            if self.confirm_first_win_reward_claimed(mode):
                return self.FIRST_WIN_REWARD_CLAIMED
            return self.FIRST_WIN_REWARD_BLOCKED

        if reward_state == "initial":
            self._log(f"华山论剑 {mode} 首胜宝箱尚未可领取")
            return self.FIRST_WIN_REWARD_NOT_READY

        self._log(
            "未识别到华山论剑首胜宝箱状态："
            f"initial={scores['initial']:.3f}，"
            f"ready={scores['ready']:.3f}，"
            f"claimed={scores['claimed']:.3f}，"
            f"当前状态={self.describe_hslj_runtime_state(mode)}"
        )
        if not self.is_first_win_claim_context_safe(mode):
            self._log("首胜宝箱状态未知且当前面板不稳定，跳过保底坐标点击")
            return self.FIRST_WIN_REWARD_BLOCKED

        self._log("未识别到华山论剑首胜宝箱状态，使用保底坐标尝试领取")
        self.click_point(self.POINT_FIRST_WIN_CHEST[0], self.POINT_FIRST_WIN_CHEST[1], offset=0)
        if self.confirm_first_win_reward_claimed(mode):
            return self.FIRST_WIN_REWARD_CLAIMED
        return self.FIRST_WIN_REWARD_BLOCKED

    def is_first_win_claim_context_safe(self, mode: str) -> bool:
        """Return whether it is safe to read/click the first-win chest."""
        if self.is_ready_button_visible():
            return False
        if self.is_result_panel_visible_quiet():
            return False
        if self.is_match_success_visible_quiet():
            return False
        if not self.is_hslj_panel_visible_quiet():
            return False
        if mode in self.DEFAULT_MODE_SETTINGS and not self.is_hslj_mode_selected_quiet(mode):
            return False
        return True

    def detect_first_win_reward_state(self) -> tuple[str, dict[str, float]]:
        """Detect first-win chest state and keep scores for diagnostics."""
        scores = {"claimed": 0.0, "ready": 0.0, "initial": 0.0}
        if self.is_first_win_reward_claimed():
            scores["claimed"] = getattr(self, "_last_match_score", 0.0)
            return "claimed", scores
        scores["claimed"] = getattr(self, "_last_match_score", 0.0)

        if self.is_first_win_reward_ready():
            scores["ready"] = getattr(self, "_last_match_score", 0.0)
            return "ready", scores
        scores["ready"] = getattr(self, "_last_match_score", 0.0)

        if self.is_first_win_reward_initial():
            scores["initial"] = getattr(self, "_last_match_score", 0.0)
            return "initial", scores
        scores["initial"] = getattr(self, "_last_match_score", 0.0)
        return "unknown", scores

    def describe_hslj_runtime_state(self, mode: str) -> str:
        """Describe current visible Huashan runtime state for logs."""
        if self.is_ready_button_visible():
            return "ready"
        if self.is_result_panel_visible_quiet():
            return "result"
        if self.is_match_success_visible_quiet():
            return "match_success"
        if self.is_hslj_panel_visible_quiet():
            if mode in self.DEFAULT_MODE_SETTINGS and self.is_hslj_mode_selected_quiet(mode):
                return f"panel:{mode}"
            return "panel:unknown_mode"
        return "unknown"

    def confirm_first_win_reward_claimed(self, mode: str) -> bool:
        """Close reward dialogs and verify whether the first-win chest is claimed."""
        self.wait(1500)
        self.settle_hslj_reward_dialogs()

        if not self.is_hslj_mode_selected_quiet(mode):
            debug_path = self.save_debug_screenshot("hslj_reward_panel_missing")
            self._log(
                f"首胜奖励确认后华山论剑 {mode} 面板或页签丢失，"
                f"尝试恢复：{debug_path}"
            )
            self.ensure_hslj_mode_ready_for_match(mode)

        if self.wait_find_image_in_roi(
            self.ICON_HSLJ_FIRST_WIN_CHEST,
            self.ROI_FIRST_WIN_CHEST,
            timeout_ms=2500,
            description=f"华山论剑 {mode} 已领取首胜宝箱",
            threshold=0.85,
        ):
            self._log(f"华山论剑 {mode} 首胜奖励领取完成")
            return True

        self._log(f"华山论剑 {mode} 首胜奖励尚未确认领取")
        return False

    def is_first_win_reward_claimed(self) -> bool:
        """Return whether the first-win reward is already claimed."""
        return self.find_image_once(
            self.ICON_HSLJ_FIRST_WIN_CHEST,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_FIRST_WIN_CHEST),
        )

    def is_first_win_reward_ready(self) -> bool:
        """Return whether the first-win reward is ready to claim."""
        return self.find_image_once(
            self.ICON_HSLJ_FIRST_WIN_READY,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_FIRST_WIN_CHEST),
        )

    def is_first_win_reward_initial(self) -> bool:
        """Return whether the first-win reward chest is still in its initial state."""
        return self.find_image_once(
            self.ICON_HSLJ_FIRST_WIN,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_FIRST_WIN_CHEST),
        )

    def settle_residual_state_before_mode_switch(self, target_mode: str) -> None:
        """Clear leftover matching/ready/result state before switching into 3v3."""
        if target_mode != self.MODE_3V3:
            return

        if self.resolve_hslj_transient_state(self.MODE_1V1):
            return

        if (
            self.is_hslj_panel_visible_quiet()
            and not self.is_hslj_mode_selected_quiet(self.MODE_3V3)
            and self.is_match_cancel_button_visible_quiet()
        ):
            self._log("切换 3v3 前检测到非 3v3 残留匹配中状态，先取消匹配")
            if not self.cancel_current_match(self.MODE_1V1, 0):
                debug_path = self.save_debug_screenshot("hslj_residual_match_cancel_failed")
                raise RuntimeError(f"切换 3v3 前取消残留匹配失败，已保存截图：{debug_path}")

    def resolve_hslj_transient_state(self, mode: str) -> bool:
        """Resolve ready/result states and return whether the Huashan panel is visible."""
        if self.is_result_panel_visible_quiet():
            self._log("检测到华山论剑结果面板，先点击离开回到面板")
            self.click_result_panel_exit()
            return self.ensure_hslj_panel_visible(timeout_ms=30000)

        if self.is_ready_button_visible():
            self._log("检测到华山论剑准备态，先处理残留战斗再回到面板")
            finish_state = self.finish_ready_or_battle_state(mode)
            if finish_state == self.BATTLE_FINISH_RESULT_PANEL:
                self.click_result_panel_exit()
            return self.ensure_hslj_panel_visible(timeout_ms=30000)

        return False

    def finish_ready_or_battle_state(self, mode: str) -> str:
        """Click ready and finish a residual Huashan battle."""
        self.click(offset=0)
        self.wait(1000)
        self.walk_forward_for_battle(self.BATTLE_FORWARD_MS)
        return self.wait_until_battle_complete(mode, 0)

    def click_match_button(self) -> None:
        """Click the Huashan Lunjian match button."""
        if self.is_ready_button_visible():
            self._log("检测到华山论剑已进入准备态，跳过匹配按钮点击")
            return

        if self.is_result_panel_visible_quiet():
            self._log("检测到华山论剑已进入结果面板，跳过匹配按钮点击")
            return

        if self.is_match_success_visible_quiet():
            self._log("检测到华山论剑匹配成功过渡态，继续等待准备")
            return

        if self.wait_find_image_in_roi(
            self.BTN_HSLJ_MATCH_TEMPLATES,
            self.ROI_MATCH_BUTTON,
            timeout_ms=3000,
            description="华山论剑匹配按钮",
            threshold=0.85,
        ):
            self._log("点击华山论剑匹配按钮")
            self.click(offset=0)
            self.wait(self.MATCH_SETTLE_WAIT_MS)
            self.confirm_match_leave_team_dialog_if_needed("华山论剑")
            return

        match_score = getattr(self, "_last_match_score", 0.0)
        if self.wait_find_image_in_roi(
            self.BTN_HSLJ_MATCH_EXIT_TEMPLATES,
            self.ROI_MATCH_BUTTON,
            timeout_ms=1200,
            description="华山论剑取消匹配按钮",
            threshold=0.85,
            interval_ms=300,
        ):
            self._log("检测到华山论剑已在匹配中，继续等待准备")
            self.confirm_match_leave_team_dialog_if_needed("华山论剑")
            return

        exit_score = getattr(self, "_last_match_score", 0.0)
        self._log(f"华山论剑匹配状态未识别：匹配最高得分={match_score:.3f}，匹配中最高得分={exit_score:.3f}")
        debug_path = self.save_debug_screenshot("hslj_match_button_missing")
        raise RuntimeError(f"未识别到华山论剑匹配状态按钮，已保存截图：{debug_path}")

    def run_match_battle(self, mode: str, match_index: int) -> None:
        """Run one matched Huashan Lunjian battle and return to the panel."""
        ready_state = self.click_ready_button(mode, match_index)
        if ready_state == self.MATCH_READY_STATE_READY:
            self.walk_forward_for_battle(self.BATTLE_FORWARD_MS)
            finish_state = self.wait_until_battle_complete(mode, match_index)
        else:
            finish_state = ready_state

        if finish_state == self.BATTLE_FINISH_RESULT_PANEL:
            self.click_result_panel_exit()
        else:
            self._log(f"华山论剑 {mode} 第 {match_index} 场已回到面板，跳过结果面板退出点击")

        if not self.ensure_hslj_panel_visible(timeout_ms=30000):
            raise RuntimeError("战斗退出后未回到华山论剑面板")

    def click_ready_button(self, mode: str, match_index: int) -> str:
        """Wait for ready, matching completion, or a returned panel."""
        deadline = self._make_deadline(300000)
        last_heartbeat_at = 0.0

        while not self._is_deadline_expired(deadline):
            if self.confirm_match_leave_team_dialog_if_needed("华山论剑"):
                last_heartbeat_at = 0.0
                continue

            if self.is_ready_button_visible():
                self._log("点击华山论剑准备按钮")
                self.click(offset=0)
                self.wait(1000)
                return self.MATCH_READY_STATE_READY

            if self.is_result_panel_visible_quiet():
                self._log(f"华山论剑 {mode} 第 {match_index} 场在等待准备时已出现结果面板")
                return self.BATTLE_FINISH_RESULT_PANEL

            if self.is_match_success_visible_quiet():
                self._log(f"华山论剑 {mode} 第 {match_index} 场匹配成功，等待准备/入场")
                self.wait(self.MATCH_WAIT_POLL_INTERVAL_MS)
                continue

            if self.is_hslj_panel_visible_quiet():
                if not self.is_hslj_mode_selected_quiet(mode):
                    self._log(f"华山论剑 {mode} 第 {match_index} 场回到面板但当前页签不一致，继续等待")
                    self.wait(self.MATCH_WAIT_POLL_INTERVAL_MS)
                    continue
                if self.is_match_button_visible_quiet():
                    self._log(f"华山论剑 {mode} 第 {match_index} 场已回到可匹配面板")
                    return self.BATTLE_FINISH_RETURNED_PANEL

            now = time.perf_counter()
            if last_heartbeat_at <= 0 or (now - last_heartbeat_at) * 1000 >= self.MATCH_WAIT_HEARTBEAT_MS:
                self._debug(f"华山论剑 {mode} 第 {match_index} 场匹配/准备等待中...")
                last_heartbeat_at = now
            self.wait(self.MATCH_WAIT_POLL_INTERVAL_MS)

        debug_path = self.save_debug_screenshot(f"hslj_{mode}_{match_index}_match_ready_timeout")
        self._log(f"华山论剑 {mode} 第 {match_index} 场匹配/准备等待超时，已保存截图：{debug_path}")
        if self.cancel_current_match(mode, match_index):
            return self.BATTLE_FINISH_RETURNED_PANEL
        raise RuntimeError(f"华山论剑 {mode} 第 {match_index} 场匹配/准备等待超时，且取消匹配失败，已保存截图：{debug_path}")

    def cancel_current_match(self, mode: str, match_index: int) -> bool:
        """Cancel a long-running Huashan match queue and stay on the panel."""
        if not self.wait_find_image_in_roi(
            self.BTN_HSLJ_MATCH_EXIT_TEMPLATES,
            self.ROI_MATCH_BUTTON,
            timeout_ms=3000,
            description="华山论剑取消匹配按钮",
            threshold=0.85,
            interval_ms=300,
        ):
            self._log(f"华山论剑 {mode} 第 {match_index} 场超时后未找到取消匹配按钮")
            return False

        self._log(f"华山论剑 {mode} 第 {match_index} 场超时，点击取消匹配")
        self.click(offset=0)
        self.wait(self.MATCH_SETTLE_WAIT_MS)
        self.confirm_match_leave_team_dialog_if_needed("华山论剑")

        if self.ensure_hslj_panel_visible(timeout_ms=5000):
            self._log(f"华山论剑 {mode} 第 {match_index} 场已取消匹配并回到面板")
            return True

        self._log(f"华山论剑 {mode} 第 {match_index} 场取消匹配后未确认回到面板")
        return False

    def is_ready_button_visible(self) -> bool:
        """Return whether the battle ready button is visible without noisy miss logs."""
        return self.find_image_once(
            self.BTN_HSLJ_READY_TEMPLATES,
            threshold=0.85,
            roi=self.scale_roi((520, 35, 240, 120)),
        )

    def is_match_button_visible_quiet(self) -> bool:
        """Return whether the panel has returned to a clickable match state."""
        return self.find_image_once(
            self.BTN_HSLJ_MATCH_TEMPLATES,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_MATCH_BUTTON),
        )

    def is_match_cancel_button_visible_quiet(self) -> bool:
        """Return whether the panel is currently in matching state."""
        return self.find_image_once(
            self.BTN_HSLJ_MATCH_EXIT_TEMPLATES,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_MATCH_BUTTON),
        )

    def is_match_success_visible_quiet(self) -> bool:
        """Return whether the match-success transition overlay is visible."""
        return self.find_image_once(
            self.TEXT_HSLJ_MATCH_SUCCESS,
            threshold=0.85,
            roi=self.scale_roi((500, 360, 300, 120)),
        )

    def is_hslj_panel_visible_quiet(self) -> bool:
        """Return whether the Huashan panel is visible without noisy miss logs."""
        return self.find_image_once(
            self.TITLE_HSLJ,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_PANEL_TITLE),
        )

    def is_result_panel_visible_quiet(self) -> bool:
        """Return whether the result panel is visible without noisy miss logs."""
        if not Path(self.TEXT_HSLJ_EXIT).exists():
            return False
        return self.find_image_once(
            self.TEXT_HSLJ_EXIT,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_RESULT_EXIT_TEXT),
        )

    def walk_forward_for_battle(self, duration_ms: int) -> None:
        """Walk forward in battle without requiring the clean main-scene guard."""
        start = self.POINT_DIRECTION_JOYSTICK_CENTER
        end = (start[0], start[1] - self.DIRECTION_JOYSTICK_RADIUS)
        self._log(f"华山论剑战斗中向前走 {duration_ms}ms")
        self.swipe(start[0], start[1], end[0], end[1], duration_ms=duration_ms)

    def wait_until_battle_complete(self, mode: str, match_index: int) -> str:
        """Auto-battle until the result panel appears or the Huashan panel returns."""
        deadline = self._make_deadline(420000)
        while not self._is_deadline_expired(deadline):
            if self.is_result_panel_visible():
                self._log(f"华山论剑 {mode} 第 {match_index} 场结果面板已出现")
                return self.BATTLE_FINISH_RESULT_PANEL

            if self.is_hslj_panel_visible():
                self._log(f"华山论剑 {mode} 第 {match_index} 场已返回面板")
                return self.BATTLE_FINISH_RETURNED_PANEL

            self.auto_battle(interval_ms=self.AUTO_BATTLE_INTERVAL_MS)

            if self.is_result_panel_visible():
                self._log(f"华山论剑 {mode} 第 {match_index} 场结果面板已出现")
                return self.BATTLE_FINISH_RESULT_PANEL

            if self.is_hslj_panel_visible():
                self._log(f"华山论剑 {mode} 第 {match_index} 场已返回面板")
                return self.BATTLE_FINISH_RETURNED_PANEL

        debug_path = self.save_debug_screenshot(f"hslj_{mode}_{match_index}_result_timeout")
        raise RuntimeError(f"华山论剑 {mode} 第 {match_index} 场战斗结果等待超时，已保存截图：{debug_path}")

    def is_result_panel_visible(self) -> bool:
        """Return whether the post-battle result panel is visible."""
        if not Path(self.TEXT_HSLJ_EXIT).exists():
            return False
        return self.find_image(
            self.TEXT_HSLJ_EXIT,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_RESULT_EXIT_TEXT),
        )

    def click_result_panel_exit(self) -> None:
        """Click the exit button inside the post-battle result panel."""
        if not self.wait_find_image_in_roi(
            self.TEXT_HSLJ_EXIT,
            self.ROI_RESULT_EXIT_TEXT,
            timeout_ms=10000,
            description="华山论剑结果面板离开按钮",
            threshold=0.85,
        ):
            raise RuntimeError("未找到华山论剑结果面板离开按钮")

        self._log("点击华山论剑结果面板离开按钮")
        self.click(offset=0)
        self.wait(3000)

    def close_purchase_dialog_if_needed(self) -> bool:
        """Close an extra-challenge purchase dialog without hitting the panel close button behind it."""
        if not self.find_image(
            [self.BTN_CLOSE, self.BTN_PANE_CLOSE],
            threshold=0.85,
            roi=self.scale_roi((850, 130, 140, 100)),
        ):
            return False

        self._log("关闭华山论剑购买挑战次数弹窗")
        self.click(offset=0)
        self.wait(1000)
        return True

    def is_hslj_reward_confirmation_visible_quiet(self) -> bool:
        """Return whether a centered reward confirmation button is visible."""
        return self.find_image_once(
            [self.BTN_MODAL_OK, self.BTN_OK],
            threshold=0.85,
            roi=self.scale_roi(self.ROI_CENTER_MODAL_OK),
        )

    def is_hslj_temp_dialog_visible_quiet(self) -> bool:
        """Return whether the right-side Huashan reward dialog is still visible."""
        return self.find_image_once(
            [self.BTN_CLOSE, self.BTN_PANE_CLOSE],
            threshold=self.HSLJ_TEMP_DIALOG_CLOSE_THRESHOLD,
            roi=self.scale_roi(self.ROI_HSLJ_TEMP_DIALOG_CLOSE),
        )

    def settle_hslj_reward_dialogs(self) -> None:
        """Dismiss known reward dialogs before interacting with Huashan controls."""
        if not (
            self.is_hslj_reward_confirmation_visible_quiet()
            or self.is_hslj_temp_dialog_visible_quiet()
        ):
            return

        self.close_reward_dialogs(
            max_attempts=self.HSLJ_REWARD_DIALOG_MAX_ATTEMPTS,
            include_close_buttons=True,
        )
        if not self.is_hslj_temp_dialog_visible_quiet():
            return

        debug_path = self.save_debug_screenshot("hslj_reward_dialog_blocking_panel")
        raise RuntimeError(f"华山论剑奖励/临时弹窗未关闭，已保存截图：{debug_path}")

    def close_reward_dialogs(self, max_attempts: int = 4, *, include_close_buttons: bool = True) -> bool:
        """Close reward and confirmation dialogs if they appear."""
        closed = False
        for _ in range(max_attempts):
            if self.wait_find_image_in_roi(
                [self.BTN_MODAL_OK, self.BTN_OK],
                self.ROI_CENTER_MODAL_OK,
                timeout_ms=800,
                description="奖励/确认弹窗按钮",
                threshold=0.85,
            ):
                self._log("点击奖励/确认弹窗按钮")
                self.click(offset=0)
                self.wait(1000)
                closed = True
                continue

            if not include_close_buttons:
                break

            if self.wait_find_image_in_roi(
                [self.BTN_CLOSE, self.BTN_PANE_CLOSE],
                self.ROI_HSLJ_TEMP_DIALOG_CLOSE,
                timeout_ms=800,
                description="华山论剑奖励/临时弹窗关闭按钮",
                threshold=self.HSLJ_TEMP_DIALOG_CLOSE_THRESHOLD,
            ):
                self._log("关闭华山论剑奖励/临时弹窗")
                self.click(offset=0)
                self.wait(1000)
                closed = True
                continue

            break

        return closed

    def _tab_mode_target(self, mode: str) -> tuple[str, tuple[int, int], str]:
        targets = {
            "1v1": (self.TAB_HSLJ_1V1_ACTIVE, self.POINT_TAB_1V1, "1v1"),
            "3v3": (self.TAB_HSLJ_3V3_ACTIVE, self.POINT_TAB_3V3, "3v3"),
        }
        if mode not in targets:
            raise ValueError(f"Unsupported Huashan Lunjian mode: {mode}")
        return targets[mode]

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"华山论剑任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
