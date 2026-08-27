"""Account-role navigation used between complete YMJH task queues."""

from __future__ import annotations

import time

import numpy as np

from ymjh_bot.ui.task_queue_state import MAX_ROLE_COUNT
from ymjh_bot.ym_game_task import YmGameTask


class AccountRoleSwitcher(YmGameTask):
    """Navigate from the main scene to a numbered account role and enter it."""

    __abstract_task__ = True
    auto_recover_health = False

    POINT_SYSTEM_MENU_MORE = (1225, 195)
    POINT_SETTINGS = (1215, 665)
    POINT_SWITCH_ROLE = (368, 307)
    ROLE_POINTS = (
        (1125, 61),
        (1125, 159),
        (1125, 258),
        (1125, 356),
        (1125, 455),
    )
    ROI_ENTER_GAME = (970, 610, 310, 110)
    ROI_SETTINGS_PAGE_CLOSE = (1050, 0, 140, 130)

    SETTINGS_OPEN_WAIT_MS = 1000
    SETTINGS_PAGE_TIMEOUT_MS = 3000
    SETTINGS_NAV_MAX_ATTEMPTS = 2
    SWITCH_CONFIRM_TIMEOUT_MS = 5000
    SWITCH_CONFIRM_SETTLE_WAIT_MS = 1000
    ROLE_PAGE_TIMEOUT_MS = 45000
    ROLE_SELECTED_STRIP_X = 1270
    ROLE_SELECTED_STRIP_WIDTH = 10
    ROLE_SELECTED_STRIP_HALF_HEIGHT = 25
    ROLE_SELECTED_WHITE_MIN_CHANNEL = 240
    ROLE_SELECTED_WHITE_MAX_SPREAD = 10
    ROLE_SELECTED_WHITE_RATIO = 0.85
    ROLE_SELECT_MAX_ATTEMPTS = 3
    ROLE_SELECT_TIMEOUT_MS = 2000
    ROLE_SELECT_POLL_INTERVAL_MS = 200

    def reset_stop(self) -> None:
        """Allow a paused role switch to be attempted again."""
        self._stop_requested = False

    def switch_to_role(self, role_index: int) -> None:
        """Select a zero-based role row, then wait for its clean main scene."""
        if not 0 <= role_index < MAX_ROLE_COUNT:
            raise ValueError(f"角色序号超出支持范围：{role_index + 1}")

        display_index = role_index + 1
        self._log(f"准备切换到第 {display_index} 个角色")

        if self._is_role_page_visible():
            self._log("当前已在角色页，跳过登录旧角色和主界面导航")
        else:
            self.ensure_game_started()
            self.close_all_panels()
            if self.wake_from_power_saving_if_needed():
                self.close_all_panels()
            self._navigate_from_main_to_role_page()

        self._select_role_and_enter(role_index)
        self._log(f"第 {display_index} 个角色已进入主界面")

    def _navigate_from_main_to_role_page(self) -> None:
        """Open Settings, confirm switching, and wait for the role page."""
        self._open_settings_page()
        self._request_role_page_from_settings()

    def _open_settings_page(self) -> None:
        """Open Settings whether the secondary system menu is collapsed or expanded."""
        if self._is_settings_page_visible():
            self._log("设置页已打开，跳过重复导航")
            return

        for attempt in range(1, self.SETTINGS_NAV_MAX_ATTEMPTS + 1):
            self._log(
                f"打开设置，第 {attempt}/{self.SETTINGS_NAV_MAX_ATTEMPTS} 次导航"
            )

            # When the secondary system menu is already expanded, Settings is
            # directly available at this point.
            self.click_point(*self.POINT_SETTINGS, offset=0)
            if self._wait_for_settings_page(self.SETTINGS_PAGE_TIMEOUT_MS):
                self._log("设置页复核通过")
                return

            # Otherwise the same coordinate belongs to the normal action bar.
            # Expand the secondary system menu, then click Settings again.
            self._log("设置页未出现，展开右侧二级系统菜单后重试")
            self.click_point(*self.POINT_SYSTEM_MENU_MORE, offset=0)
            self.wait(self.SETTINGS_OPEN_WAIT_MS)
            self.click_point(*self.POINT_SETTINGS, offset=0)
            if self._wait_for_settings_page(self.SETTINGS_PAGE_TIMEOUT_MS):
                self._log("二级系统菜单已展开，设置页复核通过")
                return

        debug_path = self.save_debug_screenshot("settings_page_not_found")
        raise RuntimeError(f"未能打开设置页，已保存截图：{debug_path}")

    def _request_role_page_from_settings(self) -> None:
        """Click Switch Role, confirm the warning, and wait through loading."""
        if not self._is_settings_page_visible():
            debug_path = self.save_debug_screenshot("settings_page_state_lost")
            raise RuntimeError(f"设置页状态已丢失，已保存截图：{debug_path}")

        self._log("点击切换角色")
        self.click_point(*self.POINT_SWITCH_ROLE, offset=0)

        if not self.wait_image_appear(
            self.BTN_MODAL_OK,
            timeout_ms=self.SWITCH_CONFIRM_TIMEOUT_MS,
            threshold=0.85,
            interval_ms=200,
            roi=self.scale_roi(self.ROI_CENTER_MODAL_OK),
        ):
            debug_path = self.save_debug_screenshot(
                "switch_role_confirm_not_found"
            )
            raise RuntimeError(
                f"点击切换角色后未出现确认弹窗，已保存截图：{debug_path}"
            )

        self._log("切换角色确认弹窗复核通过，点击确定")
        self.click(offset=0)
        self.wait(self.SWITCH_CONFIRM_SETTLE_WAIT_MS)

        if not self.wait_image_appear(
            self.BTN_JRYX,
            timeout_ms=self.ROLE_PAGE_TIMEOUT_MS,
            threshold=0.8,
            interval_ms=500,
            roi=self.scale_roi(self.ROI_ENTER_GAME),
        ):
            debug_path = self.save_debug_screenshot("role_page_not_found")
            raise RuntimeError(f"确认切换角色后未进入角色页，已保存截图：{debug_path}")
        self._log("角色页复核通过")

    def _select_role_and_enter(self, role_index: int) -> None:
        """Verify one target row on the role page and enter its main scene."""
        display_index = role_index + 1

        screenshot = self.screenshot()
        selected_role, scores = self.detect_selected_role(screenshot)
        score_text = ", ".join(f"角色{i + 1}={score:.2f}" for i, score in enumerate(scores))
        self._debug(f"角色选中白条占比：{score_text}")
        if selected_role is None:
            self._log("角色页未识别到默认选中角色，将点击并严格复核目标角色")
        else:
            self._log(f"角色页默认选中角色 {selected_role + 1}（上次登录角色）")

        if selected_role != role_index:
            if not self._select_and_verify_role(role_index):
                debug_path = self.save_debug_screenshot(
                    f"role_{display_index}_selection_failed"
                )
                raise RuntimeError(
                    f"点击角色 {display_index} 后未检测到右侧纯白选中区域，"
                    f"已保存截图：{debug_path}"
                )
        else:
            self._log(f"角色 {display_index} 已处于选中状态，跳过重复点击")

        # enter_game already verifies the role-page button and waits through
        # loading/startup popups until the clean main scene is stable.
        self.enter_game()

    def _is_role_page_visible(self) -> bool:
        """Return whether the role-page Enter Game button is visible now."""
        return self.find_image(
            self.BTN_JRYX,
            threshold=0.8,
            roi=self.scale_roi(self.ROI_ENTER_GAME),
        )

    def _is_settings_page_visible(self) -> bool:
        """Return whether the Settings panel's top-right close button is visible."""
        return self.find_image(
            self.BTN_PANE_CLOSE,
            threshold=0.9,
            roi=self.scale_roi(self.ROI_SETTINGS_PAGE_CLOSE),
        )

    def _wait_for_settings_page(self, timeout_ms: int) -> bool:
        """Wait for the Settings panel signature in its fixed close-button ROI."""
        return self.wait_image_appear(
            self.BTN_PANE_CLOSE,
            timeout_ms=timeout_ms,
            threshold=0.9,
            interval_ms=200,
            roi=self.scale_roi(self.ROI_SETTINGS_PAGE_CLOSE),
        )

    def _select_and_verify_role(self, role_index: int) -> bool:
        """Click one explicit role point and require its right-edge white strip."""
        display_index = role_index + 1
        role_x, role_y = self.ROLE_POINTS[role_index]
        for attempt in range(1, self.ROLE_SELECT_MAX_ATTEMPTS + 1):
            self._log(
                f"选择角色 {display_index}，第 {attempt}/{self.ROLE_SELECT_MAX_ATTEMPTS} 次"
            )
            self.click_point(role_x, role_y, offset=0)
            if self._wait_until_role_selected(role_index):
                self._log(f"角色 {display_index} 右侧纯白区域复核通过")
                return True
        return False

    def _wait_until_role_selected(self, role_index: int) -> bool:
        deadline = time.perf_counter() + self.ROLE_SELECT_TIMEOUT_MS / 1000.0
        while time.perf_counter() < deadline:
            selected_role, scores = self.detect_selected_role(self.screenshot())
            if selected_role == role_index:
                return True
            self._debug(
                f"等待角色 {role_index + 1} 选中："
                + ", ".join(
                    f"角色{i + 1}={score:.2f}" for i, score in enumerate(scores)
                )
            )
            remaining_ms = max(0, int((deadline - time.perf_counter()) * 1000))
            if remaining_ms:
                self.wait(min(self.ROLE_SELECT_POLL_INTERVAL_MS, remaining_ms))
        return False

    @classmethod
    def detect_selected_role(
        cls,
        screenshot: np.ndarray,
    ) -> tuple[int | None, tuple[float, ...]]:
        """Detect the uniquely selected role from the pure-white right-edge strip."""
        scores = tuple(
            cls.role_selected_white_ratio(screenshot, role_index)
            for role_index in range(len(cls.ROLE_POINTS))
        )
        selected = [
            role_index
            for role_index, score in enumerate(scores)
            if score >= cls.ROLE_SELECTED_WHITE_RATIO
        ]
        if len(selected) != 1:
            return None, scores
        return selected[0], scores

    @classmethod
    def role_selected_white_ratio(
        cls,
        screenshot: np.ndarray,
        role_index: int,
    ) -> float:
        """Return the pure-white pixel ratio in one role row's right-edge strip."""
        if not 0 <= role_index < len(cls.ROLE_POINTS):
            raise ValueError(f"角色序号超出支持范围：{role_index + 1}")
        if screenshot.ndim != 3 or screenshot.shape[2] < 3:
            return 0.0

        height, width = screenshot.shape[:2]
        design_width, design_height = cls.FIXED_RESOLUTION
        center_y = cls.ROLE_POINTS[role_index][1]
        x1 = round(cls.ROLE_SELECTED_STRIP_X * width / design_width)
        strip_width = max(
            1,
            round(cls.ROLE_SELECTED_STRIP_WIDTH * width / design_width),
        )
        x2 = min(width, x1 + strip_width)
        scaled_center_y = round(center_y * height / design_height)
        half_height = max(
            1,
            round(cls.ROLE_SELECTED_STRIP_HALF_HEIGHT * height / design_height),
        )
        y1 = max(0, scaled_center_y - half_height)
        y2 = min(height, scaled_center_y + half_height)
        if x1 >= x2 or y1 >= y2:
            return 0.0

        pixels = screenshot[y1:y2, x1:x2, :3].astype(np.int16)
        minimum = pixels.min(axis=2)
        spread = pixels.max(axis=2) - minimum
        white = (minimum >= cls.ROLE_SELECTED_WHITE_MIN_CHANNEL) & (
            spread <= cls.ROLE_SELECTED_WHITE_MAX_SPREAD
        )
        return float(white.mean())
