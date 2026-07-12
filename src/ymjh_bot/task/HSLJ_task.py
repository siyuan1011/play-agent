"""华山论剑任务 - Python DSL 实现。"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class HSLJTask(YmGameTask):
    """一梦江湖华山论剑任务。"""

    task_key = "HSLJ"
    task_name = "华山论剑"
    task_description = "按配置完成华山论剑 1v1/3v3"
    auto_recover_health = False

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
    BTN_HSLJ_READY = str(YmGameTask.TEMPLATES_DIR / "btn_hslj_ready.png")
    ICON_HSLJ_FIRST_WIN = str(YmGameTask.TEMPLATES_DIR / "icon_hslj_first_win.png")
    ICON_HSLJ_FIRST_WIN_READY = str(YmGameTask.TEMPLATES_DIR / "icon_hslj_first_win_ready.png")
    ICON_HSLJ_FIRST_WIN_CHEST = str(YmGameTask.TEMPLATES_DIR / "icon_hslj_first_win_chest.png")
    TEXT_HSLJ_1V1_COMPLETE = str(YmGameTask.TEMPLATES_DIR / "text_HSLJ_complete.png")
    TEXT_HSLJ_3V3_COMPLETE = str(YmGameTask.TEMPLATES_DIR / "text_HSLJ_complete.png")
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

    ROI_ACTIVITY_HSLJ_CARD = (105, 170, 250, 190)
    ROI_ACTIVITY_HSLJ_OPEN = (730, 410, 210, 105)
    ROI_PANEL_TITLE = (170, 45, 330, 80)
    ROI_SIDE_TABS = (1035, 115, 165, 285)
    ROI_MATCH_BUTTON = (850, 535, 220, 115)
    ROI_MATCH_SUCCESS = (500, 360, 300, 120)
    ROI_FIRST_WIN_CHEST = (900, 450, 130, 100)
    ROI_1V1_COMPLETE = (730, 455, 230, 85)
    ROI_3V3_COMPLETE = (730, 455, 230, 85)
    ROI_READY_BUTTON = (520, 35, 240, 120)
    ROI_RESULT_EXIT_BUTTON = (380, 420, 520, 240)
    ROI_RESULT_EXIT_TEXT = (540, 630, 180, 80)
    ROI_PURCHASE_DIALOG_CLOSE = (850, 130, 140, 100)

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
    SINGLE_MATCH_TIMEOUT_MS = 480000
    READY_TIMEOUT_MS = 120000
    RESULT_TIMEOUT_MS = 420000
    MATCH_SETTLE_WAIT_MS = 2500
    MATCH_READY_TIMEOUT_MS = READY_TIMEOUT_MS
    MATCH_WAIT_POLL_INTERVAL_MS = 1000
    MATCH_WAIT_HEARTBEAT_MS = 10000
    BATTLE_FORWARD_MS = 5000
    AUTO_BATTLE_INTERVAL_MS = 250
    MATCH_READY_STATE_READY = "ready"
    BATTLE_FINISH_RESULT_PANEL = "result_panel"
    BATTLE_FINISH_RETURNED_PANEL = "hslj_panel"

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

    def before_start(self) -> None:
        """Let close_all wake foreground power-saving mode before normal task steps."""
        if not self.auto_ensure_game_started:
            return
        if self.is_game_foreground():
            self._log("检测到游戏已在前台，省电唤醒交给 close_all")
            return
        self.ensure_game_started()

    def on_start(self) -> None:
        """任务开始前准备。"""
        self._log("=" * 40)
        self._log("华山论剑任务开始")
        self._log("=" * 40)

    @step(retry=1, timeout_ms=120000)
    def close_all(self) -> None:
        """关闭所有弹窗，回到游戏主界面。"""
        self.close_all_panels_for_hslj()
        if self.wake_from_power_saving_if_needed():
            self.close_all_panels_for_hslj()
        self.wait(1000)
        try:
            self.return_to_safe_zone()
        except RuntimeError as exc:
            self._log(f"返回鸡鸣寺安全区未完成，继续从当前界面打开华山论剑：{exc}")

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
        self.ensure_hslj_panel_ready(mode="1v1", timeout_ms=10000)
        self.select_hslj_mode("1v1")

        strategy = self.mode_strategy(self.MODE_1V1)
        if strategy == self.STRATEGY_FIRST_WIN:
            self.complete_mode_until_first_win(self.MODE_1V1)
            return

        if strategy == self.STRATEGY_INFINITE:
            self.complete_mode_infinite(self.MODE_1V1)
            return

        self.complete_mode_fixed_count(self.MODE_1V1)

    def complete_mode_until_first_win(self, mode: str) -> None:
        """Run a mode until its visible first-win/complete marker appears."""
        if self.claim_first_win_reward(mode):
            self._log(f"检测到华山论剑 {mode} 首胜奖励已领取，跳过匹配")
            return

        max_attempts = self.mode_count(mode)
        match_index = 1
        while not self.is_stopped() and match_index <= max_attempts:
            self._log(f"开始第 {match_index}/首胜 场华山论剑 {mode} 匹配")
            self.click_match_button()
            self.run_match_battle(mode, match_index)
            if self.claim_first_win_reward(mode):
                self._log(f"检测到华山论剑 {mode} 首胜奖励已领取")
                return
            match_index += 1

        if match_index > max_attempts:
            self._log(f"华山论剑 {mode} 首胜尝试达到上限 {max_attempts} 场，继续后续流程")
            return

        self._log(f"华山论剑 {mode} 首胜匹配已停止")

    def complete_mode_infinite(self, mode: str) -> None:
        """Run a mode until the task is stopped."""
        index = 1
        self._log(f"华山论剑 {mode} 无限匹配模式已启用")
        while not self.is_stopped():
            self._log(f"开始第 {index}/无限 场华山论剑 {mode} 匹配")
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
            self.click_match_button()
            self.run_match_battle(mode, index)
            self.claim_first_win_reward(mode)

        self._log(f"已执行 {count} 场华山论剑 {mode}，按配置结束")

    @step(retry=1, timeout_ms=60000)
    def claim_first_win(self) -> None:
        """领取当前华山论剑模式首胜奖励。"""
        self.ensure_hslj_panel_ready(mode="1v1", timeout_ms=10000)
        if not self.claim_first_win_reward("当前模式"):
            self._log("当前华山论剑模式首胜奖励未确认领取")

    @step(retry=3, timeout_ms=30000)
    def switch_to_3v3(self) -> None:
        """切换到 3v3 页签。"""
        self.ensure_hslj_panel_ready(mode="3v3", timeout_ms=10000)
        self.select_hslj_mode("3v3")

    @step(retry=0, timeout_ms=None)
    def complete_3v3_matches(self) -> None:
        """Complete configured 3v3 matches."""
        self.ensure_hslj_panel_ready(mode="3v3", timeout_ms=10000)
        self.select_hslj_mode("3v3")

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
            self.ROI_ACTIVITY_HSLJ_CARD,
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
            self.ROI_ACTIVITY_HSLJ_OPEN,
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

        self._log("华山论剑面板不可见，尝试从主界面重新打开")
        self.close_all_panels_for_hslj(timeout_ms=1500, max_attempts=6)
        self.open_fenzheng_activity_panel()
        self.open_hslj_from_activity(mode)

    def select_hslj_mode(self, mode: str) -> None:
        """Select the requested Huashan Lunjian right-side tab."""
        active_template, point, description = self._tab_mode_target(mode)
        self._log(f"切换华山论剑到 {description} 页签")
        self.click_point(point[0], point[1], offset=0)
        self.wait(1500)

        if self.wait_find_image_in_roi(
            active_template,
            self.ROI_SIDE_TABS,
            timeout_ms=800,
            description=f"{description}已选中页签",
            threshold=0.85,
            interval_ms=300,
        ):
            self._log(f"华山论剑已在 {description} 页签")
        else:
            self._log(f"未确认华山论剑 {description} 页签激活态，继续通过面板标题校验")

        if not self.ensure_hslj_panel_visible(timeout_ms=5000):
            raise RuntimeError(f"切换华山论剑 {description} 后未识别到面板")

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

    def is_hslj_panel_visible(self) -> bool:
        """Return whether the Huashan Lunjian panel is currently visible."""
        return self.find_image(
            self.TITLE_HSLJ,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_PANEL_TITLE),
        )

    def is_1v1_complete(self) -> bool:
        """Return whether the 1v1 challenge count is visibly complete."""
        return self.find_image(
            self.TEXT_HSLJ_1V1_COMPLETE,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_1V1_COMPLETE),
        )

    def is_3v3_complete(self) -> bool:
        """Return whether the 3v3 challenge count is visibly complete."""
        return self.find_image(
            self.TEXT_HSLJ_3V3_COMPLETE,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_3V3_COMPLETE),
        )

    def claim_first_win_reward(self, mode: str) -> bool:
        """Try once to claim the first-win reward for the current Huashan mode."""
        if self.is_first_win_reward_claimed():
            self._log(f"华山论剑 {mode} 首胜奖励已领取")
            return True

        if self.is_first_win_reward_ready():
            self._log(f"点击华山论剑 {mode} 可领取首胜奖励")
            self.click(offset=0)
            return self.confirm_first_win_reward_claimed(mode)

        if self.is_first_win_reward_initial():
            self._log(f"华山论剑 {mode} 首胜宝箱尚未可领取")
            return False

        self._log("未识别到华山论剑首胜宝箱状态，使用保底坐标尝试领取")
        self.click_point(self.POINT_FIRST_WIN_CHEST[0], self.POINT_FIRST_WIN_CHEST[1], offset=0)
        return self.confirm_first_win_reward_claimed(mode)

    def confirm_first_win_reward_claimed(self, mode: str) -> bool:
        """Close reward dialogs and verify whether the first-win chest is claimed."""
        self.wait(1500)
        self.close_reward_dialogs(max_attempts=2, include_close_buttons=False)
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

    def is_mode_complete(self, mode: str) -> bool:
        """Return whether the requested Huashan mode is visibly complete."""
        if mode == self.MODE_1V1:
            return self.is_1v1_complete()
        if mode == self.MODE_3V3:
            return self.is_3v3_complete()
        raise ValueError(f"Unsupported Huashan Lunjian mode: {mode}")

    def click_match_button(self) -> None:
        """Click the Huashan Lunjian match button."""
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
        deadline = self._make_deadline(self.MATCH_READY_TIMEOUT_MS)
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
                if mode == "1v1" and self.is_1v1_complete_quiet():
                    self._log(f"华山论剑 {mode} 第 {match_index} 场已完成并返回面板")
                    return self.BATTLE_FINISH_RETURNED_PANEL
                if mode == "3v3" and self.is_3v3_complete_quiet():
                    self._log(f"华山论剑 {mode} 第 {match_index} 场检测到次数已完成")
                    return self.BATTLE_FINISH_RETURNED_PANEL
                if self.is_match_button_visible_quiet():
                    self._log(f"华山论剑 {mode} 第 {match_index} 场已回到可匹配面板")
                    return self.BATTLE_FINISH_RETURNED_PANEL

            now = time.perf_counter()
            if last_heartbeat_at <= 0 or (now - last_heartbeat_at) * 1000 >= self.MATCH_WAIT_HEARTBEAT_MS:
                self._log(f"华山论剑 {mode} 第 {match_index} 场匹配/准备等待中...")
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
            self.BTN_HSLJ_READY,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_READY_BUTTON),
        )

    def is_match_button_visible_quiet(self) -> bool:
        """Return whether the panel has returned to a clickable match state."""
        return self.find_image_once(
            self.BTN_HSLJ_MATCH_TEMPLATES,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_MATCH_BUTTON),
        )

    def is_match_success_visible_quiet(self) -> bool:
        """Return whether the match-success transition overlay is visible."""
        return self.find_image_once(
            self.TEXT_HSLJ_MATCH_SUCCESS,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_MATCH_SUCCESS),
        )

    def is_hslj_panel_visible_quiet(self) -> bool:
        """Return whether the Huashan panel is visible without noisy miss logs."""
        return self.find_image_once(
            self.TITLE_HSLJ,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_PANEL_TITLE),
        )

    def is_1v1_complete_quiet(self) -> bool:
        """Return whether the 1v1 count is complete without noisy miss logs."""
        return self.find_image_once(
            self.TEXT_HSLJ_1V1_COMPLETE,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_1V1_COMPLETE),
        )

    def is_3v3_complete_quiet(self) -> bool:
        """Return whether the 3v3 count is complete without noisy miss logs."""
        return self.find_image_once(
            self.TEXT_HSLJ_3V3_COMPLETE,
            threshold=0.85,
            roi=self.scale_roi(self.ROI_3V3_COMPLETE),
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
        deadline = self._make_deadline(self.RESULT_TIMEOUT_MS)
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

    def close_all_panels_for_hslj(
        self,
        *,
        timeout_ms: int = 5000,
        wait_after_click_ms: int = 500,
        max_attempts: int | None = None,
    ) -> None:
        """Close overlays with a guard for challenge purchase dialogs."""
        attempts = max_attempts or self.CLOSE_ALL_MAX_ATTEMPTS
        targets = [self.BTN_CLOSE, self.BTN_PANE_CLOSE, self.BTN_WELCOME_CLOSE]

        self.collapse_chat_if_open()
        for _ in range(attempts):
            if self.close_purchase_dialog_if_needed():
                continue

            if not self.wait_image_appear(targets, timeout_ms=timeout_ms):
                self.collapse_chat_if_open()
                self._log("已关闭所有弹窗")
                return

            self.click()
            self.wait(wait_after_click_ms)

        self.collapse_chat_if_open()
        self._log(f"关闭弹窗达到上限 {attempts} 次，继续后续流程")

    def close_purchase_dialog_if_needed(self) -> bool:
        """Close an extra-challenge purchase dialog without hitting the panel close button behind it."""
        if not self.find_image(
            [self.BTN_CLOSE, self.BTN_PANE_CLOSE],
            threshold=0.85,
            roi=self.scale_roi(self.ROI_PURCHASE_DIALOG_CLOSE),
        ):
            return False

        self._log("关闭华山论剑购买挑战次数弹窗")
        self.click(offset=0)
        self.wait(1000)
        return True

    def close_reward_dialogs(self, max_attempts: int = 4, *, include_close_buttons: bool = True) -> bool:
        """Close reward and confirmation dialogs if they appear."""
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

    def save_debug_screenshot(self, prefix: str) -> str:
        """Save the current screen for post-run debugging."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = self.TEMPLATES_DIR.parents[2] / "screenshots" / f"{prefix}_{timestamp}.png"
        cv2.imwrite(str(path), self.screenshot())
        self._log(f"已保存调试截图：{path}")
        return str(path)

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
