"""Shared helpers for banquet-style gang activity tasks."""

from __future__ import annotations

from botCore import StepStopException

from ymjh_bot.ym_game_task import YmGameTask


class StallPurchaseConfirmationError(RuntimeError):
    """Raised when a stall purchase cannot be confirmed safely."""


class StallPurchaseCancelError(RuntimeError):
    """Raised when a stuck stall-purchase prompt cannot be cancelled."""


class BanquetAcquireMixin:
    """Reusable item-acquisition flow for banquet tasks."""

    ROUTE_MENKE_WAREHOUSE_RECOMMENDED = str(YmGameTask.TEMPLATES_DIR / "route_menke_warehouse_recommended.png")
    ROUTE_MENKE_MALL = str(YmGameTask.TEMPLATES_DIR / "route_mall.png")
    ROUTE_MENKE_STALL = str(YmGameTask.TEMPLATES_DIR / "route_stall.png")
    BTN_MENKE_WAREHOUSE_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_warehouse_submit.png")
    BTN_MENKE_VIEW_ALL_SERVER = str(YmGameTask.TEMPLATES_DIR / "btn_view_all_server.png")
    BTN_MENKE_MALL_BUY_AREA = str(YmGameTask.TEMPLATES_DIR / "btn_mall_buy_area.png")
    BTN_BUY = str(YmGameTask.TEMPLATES_DIR / "btn_buy.png")
    BTN_MODAL_CANCEL = str(YmGameTask.TEMPLATES_DIR / "btn_modal_cancel.png")

    ROI_ROUTE_PANEL = (560, 70, 660, 480)
    ROI_TRADE_ACTION = (520, 440, 330, 120)

    STALL_PURCHASE_DIALOG_THRESHOLD = 0.85
    STALL_PURCHASE_FINAL_RECHECK_MS = 100
    PURCHASE_RETRY_LIMIT = 1
    BANQUET_INVITE_TIMEOUT_MS = 60000
    BANQUET_CONFIRM_TIMEOUT_MS = 10000
    BANQUET_PANEL_TIMEOUT_MS = 30000

    START_BANQUET_BRIGHTNESS_THRESHOLD = 150.0
    BANQUET_NAME = "设宴"

    def _raise_banquet_invite_failure(self, reason: str, stage: str) -> None:
        """Preserve invite failure context for the next complete task retry."""
        task_key = str(getattr(self, "task_key", "banquet")).lower()
        try:
            self.save_debug_screenshot(f"{task_key}_{stage}")
        except StepStopException:
            raise
        except Exception as exc:
            self._log(f"设宴邀约失败截图保存失败，保留原异常：{exc}")
        raise RuntimeError(reason)

    def process_banquet_items(self) -> None:
        """Process every configured banquet item slot once."""
        for index, (x, y) in enumerate(self.POINT_BANQUET_ITEM_SLOTS, start=1):
            self._log(f"处理第 {index} 个设宴物品")
            self.click_point(x, y, offset=0)
            self.wait(700)
            self.process_selected_item(index)

    def start_banquet_if_ready(self) -> None:
        """Start the banquet when the start button is enabled."""
        if self.try_start_banquet_once():
            return

        self._log("物品不足，跳过开始设宴")

    def try_start_banquet_once(self) -> bool:
        """Click the start button and confirm the prompt when it is enabled."""
        if not self.is_start_banquet_enabled():
            return False

        self._log("开始设宴按钮已可用，提交任务")
        self.click_point(self.POINT_START_BANQUET[0], self.POINT_START_BANQUET[1], offset=0)
        self.wait(1500)
        self.confirm_start_banquet_if_needed()
        return True

    def process_selected_item(self, slot_index: int) -> None:
        """Submit or acquire the currently selected banquet item once."""
        one_key_template = getattr(self, "BTN_BANQUET_ONE_KEY_SUBMIT", None)
        if one_key_template and self.click_template_if_available(
            one_key_template,
            timeout_ms=800,
            description="一键提交按钮",
            roi=self.ROI_BANQUET_ACTION,
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            self._log(f"第 {slot_index} 个物品已尝试一键提交")
            return

        if self.click_template_if_available(
            self.BTN_BANQUET_GET_ITEM,
            timeout_ms=800,
            description="获取按钮",
            roi=self.ROI_BANQUET_ACTION,
            threshold=0.85,
            wait_after_click_ms=800,
        ):
            self.acquire_selected_item(slot_index)
            self.submit_selected_item_if_available(slot_index)
            return

        self._log(f"第 {slot_index} 个物品未找到可执行按钮，跳过")

    def submit_selected_item_if_available(self, slot_index: int) -> bool:
        """Submit the selected item after acquisition if the task exposes a submit button."""
        one_key_template = getattr(self, "BTN_BANQUET_ONE_KEY_SUBMIT", None)
        if not one_key_template:
            return False

        if not self.click_template_if_available(
            one_key_template,
            timeout_ms=1500,
            description="获取后一键提交按钮",
            roi=self.ROI_BANQUET_ACTION,
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            return False

        self._log(f"第 {slot_index} 个物品获取后已尝试一键提交")
        return True

    def acquire_selected_item(self, slot_index: int) -> None:
        """Acquire one item, retrying once when a purchase leaves the get button visible."""
        self._log(f"开始获取第 {slot_index} 个物品")

        for purchase_attempt in range(self.PURCHASE_RETRY_LIMIT + 1):
            if self.try_recommended_warehouse_route():
                return

            purchased = self.try_mall_route()
            if not purchased:
                purchased = self.try_stall_route()

            if not purchased:
                self._log(f"第 {slot_index} 个物品未能通过支持的路径获取，跳过")
                self.return_to_banquet_panel()
                return

            if not self.wait_find_image_in_roi(
                self.BTN_BANQUET_GET_ITEM,
                self.ROI_BANQUET_ACTION,
                timeout_ms=1500,
                description="购买后仍存在的获取按钮",
                threshold=0.85,
            ):
                return

            if purchase_attempt >= self.PURCHASE_RETRY_LIMIT:
                self._log(f"第 {slot_index} 个物品再次获取后仍显示获取按钮，停止重试并继续后续槽位")
                return

            self._log(f"第 {slot_index} 个物品购买后仍显示获取按钮，判定购买异常，再次获取 1/1")
            self.click()
            self.wait(800)

    def try_recommended_warehouse_route(self) -> bool:
        """Use recommended gang warehouse if available."""
        if not self.ensure_route_panel_open():
            return False
        if not self.click_template_if_available(
            self.ROUTE_MENKE_WAREHOUSE_RECOMMENDED,
            timeout_ms=800,
            description="推荐帮派仓库",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.8,
            wait_after_click_ms=1500,
        ):
            return False

        if self.click_template_if_available(
            self.BTN_MENKE_WAREHOUSE_SUBMIT,
            timeout_ms=2500,
            description="帮派仓库提交按钮",
            roi=(760, 530, 230, 115),
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            self.return_to_banquet_panel()
            return True

        self._log("帮派仓库无可提交物品，继续其他获取路径")
        self.return_to_banquet_panel()
        return False

    def try_mall_route(self) -> bool:
        """Buy the selected item from mall when the route is available."""
        if not self.ensure_route_panel_open():
            return False
        if not self.click_template_if_available(
            self.ROUTE_MENKE_MALL,
            timeout_ms=800,
            description="商城购买路径",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.8,
            wait_after_click_ms=2000,
        ):
            return False

        if not self.click_template_if_available(
            self.BTN_MENKE_MALL_BUY_AREA,
            timeout_ms=5000,
            description="商城购买按钮",
            roi=(800, 610, 290, 100),
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            self._log("商城未找到购买按钮")
            self.return_to_banquet_panel()
            return False

        self.click_template_if_available(
            self.BTN_BUY,
            timeout_ms=1200,
            description="商城购买确认按钮",
            roi=self.ROI_TRADE_ACTION,
            threshold=0.85,
            wait_after_click_ms=1500,
        )
        self.confirm_purchase_if_needed()
        self.return_to_banquet_panel()
        return True

    def try_stall_route(self) -> bool:
        """Buy the selected item from stall or all-server stall."""
        if not self.ensure_route_panel_open():
            return False
        if not self.click_template_if_available(
            self.ROUTE_MENKE_STALL,
            timeout_ms=800,
            description="摆摊购买路径",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.8,
            wait_after_click_ms=2500,
        ):
            return False

        if self.click_template_if_available(
            self.BTN_BUY,
            timeout_ms=4000,
            description="摆摊购买按钮",
            roi=self.ROI_TRADE_ACTION,
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            self.confirm_stall_purchase()
            self.return_to_banquet_panel()
            return True

        if not self.click_template_if_available(
            self.BTN_MENKE_VIEW_ALL_SERVER,
            timeout_ms=2500,
            description="查看全服按钮",
            roi=self.ROI_TRADE_ACTION,
            threshold=0.85,
            wait_after_click_ms=2500,
        ):
            self._log("摆摊未找到商品，且未出现查看全服按钮")
            self.return_to_banquet_panel()
            return False

        if self.click_template_if_available(
            self.BTN_BUY,
            timeout_ms=5000,
            description="全服摆摊购买按钮",
            roi=self.ROI_TRADE_ACTION,
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            self.confirm_stall_purchase()
            self.return_to_banquet_panel()
            return True

        self._log("全服摆摊仍未找到可购买商品")
        self.return_to_banquet_panel()
        return False

    def confirm_stall_purchase(
        self,
        max_attempts: int = 3,
        retry_interval_ms: int = 3000,
    ) -> bool:
        """Confirm one stall purchase and require its prompt to disappear."""
        if max_attempts <= 0:
            raise ValueError("max_attempts 必须大于 0")
        if retry_interval_ms <= 0:
            raise ValueError("retry_interval_ms 必须大于 0")

        if not self.wait_image_appear(
            self.BTN_MODAL_OK,
            timeout_ms=3000,
            threshold=self.STALL_PURCHASE_DIALOG_THRESHOLD,
        ):
            debug_path = self.save_debug_screenshot("stall_purchase_unconfirmed")
            raise StallPurchaseConfirmationError(
                f"点击摆摊购买后未确认购买弹窗，已保存截图：{debug_path}"
            )

        attempts = 0

        def click_confirm_if_visible(found: bool, _missing_count: int) -> None:
            nonlocal attempts
            if not found or attempts >= max_attempts:
                return
            attempts += 1
            self._log(f"点击摆摊购买确认按钮 {attempts}/{max_attempts}")
            self.click(offset=0)

        if self.wait_image_missing(
            self.BTN_MODAL_OK,
            timeout_ms=(max_attempts * retry_interval_ms) + self.STALL_PURCHASE_FINAL_RECHECK_MS,
            threshold=self.STALL_PURCHASE_DIALOG_THRESHOLD,
            missing_threshold=1,
            callback=click_confirm_if_visible,
            interval_ms=retry_interval_ms,
        ):
            self._log(f"第 {attempts} 次确认后购买弹窗已消失")
            return True

        stuck_path = self.save_debug_screenshot("stall_purchase_confirm_stuck")
        if not self.find_image(
            self.BTN_MODAL_CANCEL,
            threshold=self.STALL_PURCHASE_DIALOG_THRESHOLD,
            roi=self.scale_roi((300, 440, 250, 120)),
        ):
            cancel_path = self.save_debug_screenshot("stall_purchase_cancel_failed")
            raise StallPurchaseCancelError(
                f"摆摊购买确认连续 {max_attempts} 次未生效，且未找到取消按钮；"
                f"确认截图：{stuck_path}，取消截图：{cancel_path}"
            )

        self._log(f"摆摊购买确认连续 {max_attempts} 次未生效，点击取消")
        self.click(offset=0)

        if self.wait_image_missing(
            self.BTN_MODAL_OK,
            timeout_ms=retry_interval_ms,
            threshold=self.STALL_PURCHASE_DIALOG_THRESHOLD,
            missing_threshold=1,
            interval_ms=300,
        ):
            raise StallPurchaseConfirmationError(
                f"摆摊购买确认连续 {max_attempts} 次未生效，已取消本次购买；"
                f"已保存截图：{stuck_path}"
            )

        cancel_path = self.save_debug_screenshot("stall_purchase_cancel_failed")
        raise StallPurchaseCancelError(
            f"摆摊购买确认连续 {max_attempts} 次未生效，取消购买也未生效；"
            f"确认截图：{stuck_path}，取消截图：{cancel_path}"
        )

    def confirm_purchase_if_needed(self) -> bool:
        """Confirm the secondary purchase prompt if the game shows one."""
        return self.click_template_if_available(
            self.BTN_MODAL_OK,
            timeout_ms=2000,
            description="购买二次确认按钮",
            threshold=0.85,
            wait_after_click_ms=2000,
        )

    def confirm_start_banquet_if_needed(self) -> bool:
        """Confirm the final banquet-start prompt if the game shows one."""
        return self.click_template_if_available(
            self.BTN_MODAL_OK,
            timeout_ms=3000,
            description="开始设宴确认按钮",
            threshold=0.85,
            wait_after_click_ms=2000,
        )

    def ensure_route_panel_open(self) -> bool:
        """Ensure the acquire-route panel is visible for the selected item."""
        if self.is_route_panel_visible():
            return True

        if not self.click_template_if_available(
            self.BTN_BANQUET_GET_ITEM,
            timeout_ms=1000,
            description="获取按钮",
            roi=self.ROI_BANQUET_ACTION,
            threshold=0.85,
            wait_after_click_ms=800,
        ):
            return False

        return self.wait_route_panel_visible(timeout_ms=3000)

    def wait_route_panel_visible(self, timeout_ms: int = 3000) -> bool:
        """Wait for any supported acquire-route option to appear."""
        return self.wait_find_image_in_roi(
            [self.ROUTE_MENKE_WAREHOUSE_RECOMMENDED, self.ROUTE_MENKE_MALL, self.ROUTE_MENKE_STALL],
            self.ROI_ROUTE_PANEL,
            timeout_ms=timeout_ms,
            description="获取途径面板",
            threshold=0.8,
        )

    def is_route_panel_visible(self) -> bool:
        """Return whether any supported acquire route is currently visible."""
        return self.find_image(
            [self.ROUTE_MENKE_WAREHOUSE_RECOMMENDED, self.ROUTE_MENKE_MALL, self.ROUTE_MENKE_STALL],
            threshold=0.8,
            roi=self.scale_roi(self.ROI_ROUTE_PANEL),
        )

    def return_to_banquet_panel(self, max_attempts: int = 4) -> bool:
        """Close transient panels until the banquet item panel is visible."""
        for _ in range(max_attempts):
            if self.is_banquet_panel_visible():
                return True
            if self.wait_image_appear([self.BTN_CLOSE, self.BTN_PANE_CLOSE], timeout_ms=800, threshold=0.8):
                self.click()
                self.wait(1000)
                continue
            self.wait(500)

        self._log(f"未确认返回{self.BANQUET_NAME}面板")
        return False

    def is_banquet_panel_visible(self) -> bool:
        """Return whether the main banquet item panel is visible."""
        action_roi = self.scale_roi(self.ROI_BANQUET_ACTION)
        start_roi = self.scale_roi(self.ROI_START_BANQUET_BUTTON)
        action_templates = self._banquet_action_templates()
        start_template = getattr(self, "BTN_BANQUET_START_ACTIVE", None)
        return (
            bool(action_templates and self.find_image(action_templates, threshold=0.8, roi=action_roi))
            or bool(start_template and self.find_image(start_template, threshold=0.8, roi=start_roi))
        )

    def is_start_banquet_enabled(self) -> bool:
        """Detect the enabled start button by brightness; template alone can match disabled states."""
        x, y, width, height = self.scale_roi(self.ROI_START_BANQUET_BUTTON)
        screenshot = self.screenshot()
        region = screenshot[y : y + height, x : x + width]
        if region.size == 0:
            return False

        brightness = float(region.mean())
        self._log(f"开始设宴按钮亮度：{brightness:.1f}")
        return brightness >= self.START_BANQUET_BRIGHTNESS_THRESHOLD

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
        self.click()
        self.wait(wait_after_click_ms)
        return True

    def _banquet_action_templates(self) -> list[str]:
        templates = [self.BTN_BANQUET_GET_ITEM]
        one_key_template = getattr(self, "BTN_BANQUET_ONE_KEY_SUBMIT", None)
        if one_key_template:
            templates.append(one_key_template)
        return templates
