"""江湖行商任务 - 通过悬赏面板发布江湖行商。"""

from __future__ import annotations

from typing import Literal

import numpy as np

from botCore import ImageMatchResult, step
from ymjh_bot.ym_game_task import YmGameTask

BinaryMode = Literal["otsu_dark", "light_foreground"]


class JHXSTask(YmGameTask):
    """一梦江湖江湖行商发布悬赏任务。"""

    task_key = "JHXS"
    task_name = "江湖行商"
    task_description = "打开悬赏面板并发布江湖行商悬赏"
    auto_recover_health = False
    DEFER_FOREGROUND_WAKE_TO_ON_START = True
    STARTUP_CLOSE_SETTLE_WAIT_MS = 800

    ICON_BOUNTY = str(YmGameTask.TEMPLATES_DIR / "icon_xsrw_bounty.png")
    TEXT_BOUNTY_PANEL_TITLE = str(
        YmGameTask.TEMPLATES_DIR / "text_xsrw_panel_title.png"
    )
    BTN_PUBLISH_ENTRY = str(
        YmGameTask.TEMPLATES_DIR / "btn_bounty_publish_entry.png"
    )
    TEXT_PUBLISH_PANEL_TITLE = str(
        YmGameTask.TEMPLATES_DIR / "text_bounty_publish_title.png"
    )
    BTN_PUBLISH_CONFIRM = str(
        YmGameTask.TEMPLATES_DIR / "btn_bounty_publish_confirm.png"
    )
    BTN_PUBLISH_MODAL_CONFIRM = YmGameTask.BTN_MODAL_OK
    TEXT_TARGET_OPTION_JIANGHU_XINGSHANG = str(
        YmGameTask.TEMPLATES_DIR / "text_bounty_target_option_jianghu_xingshang.png"
    )
    TEXT_TARGET_SELECTED_JIANGHU_XINGSHANG = str(
        YmGameTask.TEMPLATES_DIR
        / "text_bounty_target_selected_jianghu_xingshang.png"
    )

    ROI_BOUNTY_ENTRY = (940, 0, 240, 110)
    ROI_BOUNTY_PANEL_TITLE = (250, 105, 250, 70)
    ROI_PUBLISH_ENTRY = (990, 540, 140, 90)
    ROI_PUBLISH_PANEL_TITLE = (540, 140, 210, 80)
    ROI_TARGET_OPTIONS = (510, 250, 260, 150)
    ROI_TARGET_SELECTED = (510, 200, 370, 60)
    ROI_PUBLISH_CONFIRM = (770, 500, 210, 100)
    ROI_PUBLISH_MODAL_CONFIRM = (730, 440, 250, 120)

    POINT_TARGET_DROPDOWN = (700, 228)

    BOUNTY_ENTRY_THRESHOLD = 0.90
    BOUNTY_PANEL_THRESHOLD = 0.80
    PUBLISH_ENTRY_THRESHOLD = 0.90
    PUBLISH_PANEL_THRESHOLD = 0.90
    TARGET_OPTION_THRESHOLD = 0.90
    TARGET_SELECTED_THRESHOLD = 0.90
    PUBLISH_CONFIRM_THRESHOLD = 0.90
    PUBLISH_MODAL_CONFIRM_THRESHOLD = 0.95

    PANEL_TIMEOUT_MS = 15000
    PANEL_POLL_INTERVAL_MS = 300
    ACTIVITY_SETTLE_MS = 1500
    BOUNTY_PANEL_SETTLE_MS = 1200
    PUBLISH_PANEL_SETTLE_MS = 800
    DROPDOWN_SETTLE_MS = 500
    TARGET_SELECT_SETTLE_MS = 500
    PUBLISH_SETTLE_MS = 1200

    STEP_ORDER = (
        "open_any_activity_panel",
        "open_bounty_panel",
        "open_bounty_publish_panel",
        "open_bounty_target_dropdown",
        "select_bounty_target",
        "publish_bounty",
    )

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._publish_submitted = False

    @classmethod
    def get_steps(cls) -> list[tuple[str, object, dict]]:
        """Return the Jianghu Xingshang publisher steps in a stable order."""
        steps: list[tuple[str, object, dict]] = []
        for name in cls.STEP_ORDER:
            func = getattr(cls, name)
            steps.append((name, func, func._step_meta))
        return steps

    def reset_startup_state(self) -> None:
        self._publish_submitted = False

    def before_retry(
        self,
        retry_scope: str,
        failure: Exception | str | None = None,
    ) -> None:
        """Finish a pending Jianghu Xingshang confirmation before recovery."""
        if self.confirm_publish_modal_if_visible(timeout_ms=1000):
            self._log("重试前已处理待确认的江湖行商悬赏发布弹框")
            return
        super().before_retry(retry_scope, failure)

    @step(retry=3, timeout_ms=30000)
    def open_any_activity_panel(self) -> None:
        """1. Open Activity; its current category may be arbitrary."""
        self.open_activity_panel(wait_after_open_ms=self.ACTIVITY_SETTLE_MS)

    @step(retry=3, timeout_ms=30000)
    def open_bounty_panel(self) -> None:
        """2. Click the Bounty entry and verify its receive panel."""
        self.ensure_bounty_panel_open()

    @step(retry=3, timeout_ms=30000)
    def open_bounty_publish_panel(self) -> None:
        """3. Click the lower-right Publish entry."""
        self.ensure_bounty_publish_panel_open()

    @step(retry=3, timeout_ms=30000)
    def open_bounty_target_dropdown(self) -> None:
        """4. Open the target selector on the Publish Bounty panel."""
        if self.is_bounty_target_dropdown_open():
            return

        self.ensure_bounty_publish_panel_open()
        self._log("点击江湖行商悬赏目标下拉框")
        self.click_point(*self.POINT_TARGET_DROPDOWN, offset=0)
        self.wait(self.DROPDOWN_SETTLE_MS)
        if not self.is_bounty_target_dropdown_open(timeout_ms=self.PANEL_TIMEOUT_MS):
            self._raise_publish_error("dropdown_missing", "悬赏目标下拉框未打开")

    @step(retry=3, timeout_ms=30000)
    def select_bounty_target(self) -> None:
        """5. Select Jianghu Xingshang as the bounty target."""
        if (
            not self.is_bounty_target_dropdown_open()
            and self.is_bounty_target_selected()
        ):
            self._log("悬赏目标已选中：江湖行商")
            return

        if not self.is_bounty_target_dropdown_open():
            self.open_bounty_target_dropdown()

        target = self._wait_bounty_match(
            self.TEXT_TARGET_OPTION_JIANGHU_XINGSHANG,
            mode="light_foreground",
            threshold=self.TARGET_OPTION_THRESHOLD,
            roi=self.ROI_TARGET_OPTIONS,
            timeout_ms=self.PANEL_TIMEOUT_MS,
        )
        if not target.found or target.center is None:
            self._raise_publish_error(
                "target_option_missing",
                "悬赏目标下拉框未找到江湖行商",
            )

        self._log("选择悬赏目标：江湖行商")
        self.tap(*target.center)
        self.wait(self.TARGET_SELECT_SETTLE_MS)
        if not self.is_bounty_target_selected(timeout_ms=self.PANEL_TIMEOUT_MS):
            self._raise_publish_error(
                "target_select_failed",
                "未能确认悬赏目标：江湖行商",
            )

    @step(retry=3, timeout_ms=30000)
    def publish_bounty(self) -> None:
        """6. Publish Jianghu Xingshang and verify the modal is dismissed."""
        if self._publish_submitted and self.is_bounty_panel_visible(timeout_ms=1000):
            return

        if self.confirm_publish_modal_if_visible(timeout_ms=0):
            self._verify_publish_success()
            return

        if not self.is_bounty_publish_panel_visible():
            self.ensure_bounty_publish_panel_open()
        if not self.is_bounty_target_selected():
            self.select_bounty_target()

        publish = self._wait_bounty_match(
            self.BTN_PUBLISH_CONFIRM,
            mode="otsu_dark",
            threshold=self.PUBLISH_CONFIRM_THRESHOLD,
            roi=self.ROI_PUBLISH_CONFIRM,
            timeout_ms=self.PANEL_TIMEOUT_MS,
        )
        if not publish.found or publish.center is None:
            self._raise_publish_error("confirm_missing", "发布悬赏按钮未找到")

        self._log("点击发布悬赏：江湖行商")
        self.tap(*publish.center)
        self.wait(self.PUBLISH_PANEL_SETTLE_MS)
        if not self.confirm_publish_modal_if_visible(timeout_ms=self.PANEL_TIMEOUT_MS):
            self._raise_publish_error(
                "modal_confirm_missing",
                "发布江湖行商悬赏后未找到二次确认按钮",
            )

        self._verify_publish_success()

    def confirm_publish_modal_if_visible(self, *, timeout_ms: int = 0) -> bool:
        """Confirm a pending Jianghu Xingshang publish summary modal."""
        modal_confirm = self._wait_bounty_match(
            self.BTN_PUBLISH_MODAL_CONFIRM,
            mode="otsu_dark",
            threshold=self.PUBLISH_MODAL_CONFIRM_THRESHOLD,
            roi=self.ROI_PUBLISH_MODAL_CONFIRM,
            timeout_ms=timeout_ms,
        )
        if not modal_confirm.found or modal_confirm.center is None:
            return False

        self._log("确认发布悬赏：江湖行商")
        self.tap(*modal_confirm.center)
        self._publish_submitted = True
        self.wait(self.PUBLISH_SETTLE_MS)
        return True

    def _verify_publish_success(self) -> None:
        if not self._wait_publish_success(timeout_ms=self.PANEL_TIMEOUT_MS):
            self._raise_publish_error(
                "submit_failed",
                "江湖行商悬赏发布后面板未关闭",
            )
        self._log("江湖行商悬赏发布成功")

    def ensure_bounty_panel_open(self) -> None:
        """Recover Activity/Bounty prerequisites for Jianghu Xingshang."""
        if self.is_bounty_publish_panel_visible() or self.is_bounty_panel_visible():
            return

        self.open_activity_panel(wait_after_open_ms=self.ACTIVITY_SETTLE_MS)
        bounty = self._wait_bounty_match(
            self.ICON_BOUNTY,
            mode="light_foreground",
            threshold=self.BOUNTY_ENTRY_THRESHOLD,
            roi=self.ROI_BOUNTY_ENTRY,
            timeout_ms=self.PANEL_TIMEOUT_MS,
        )
        if not bounty.found or bounty.center is None:
            self._raise_publish_error("entry_missing", "活动面板未找到悬赏入口")

        self._log("点击活动面板悬赏入口")
        self.tap(*bounty.center)
        self.wait(self.BOUNTY_PANEL_SETTLE_MS)
        if not self.is_bounty_panel_visible(timeout_ms=self.PANEL_TIMEOUT_MS):
            self._raise_publish_error("panel_missing", "未能确认悬赏面板")

    def ensure_bounty_publish_panel_open(self) -> None:
        """Recover the Bounty panel and open the Jianghu Xingshang publisher."""
        if self.is_bounty_publish_panel_visible():
            return

        self.ensure_bounty_panel_open()
        publish_entry = self._wait_bounty_match(
            self.BTN_PUBLISH_ENTRY,
            mode="otsu_dark",
            threshold=self.PUBLISH_ENTRY_THRESHOLD,
            roi=self.ROI_PUBLISH_ENTRY,
            timeout_ms=self.PANEL_TIMEOUT_MS,
        )
        if not publish_entry.found or publish_entry.center is None:
            self._raise_publish_error("publish_entry_missing", "悬赏面板未找到发布入口")

        self._log("点击悬赏面板右下角发布")
        self.tap(*publish_entry.center)
        self.wait(self.PUBLISH_PANEL_SETTLE_MS)
        if not self.is_bounty_publish_panel_visible(timeout_ms=self.PANEL_TIMEOUT_MS):
            self._raise_publish_error("publish_panel_missing", "未能确认发布悬赏面板")

    def is_bounty_panel_visible(
        self,
        screenshot: np.ndarray | None = None,
        *,
        timeout_ms: int = 0,
    ) -> bool:
        return self._find_or_wait_bounty_match(
            self.TEXT_BOUNTY_PANEL_TITLE,
            screenshot=screenshot,
            mode="otsu_dark",
            threshold=self.BOUNTY_PANEL_THRESHOLD,
            roi=self.ROI_BOUNTY_PANEL_TITLE,
            timeout_ms=timeout_ms,
        ).found

    def is_bounty_publish_panel_visible(
        self,
        screenshot: np.ndarray | None = None,
        *,
        timeout_ms: int = 0,
    ) -> bool:
        return self._find_or_wait_bounty_match(
            self.TEXT_PUBLISH_PANEL_TITLE,
            screenshot=screenshot,
            mode="light_foreground",
            threshold=self.PUBLISH_PANEL_THRESHOLD,
            roi=self.ROI_PUBLISH_PANEL_TITLE,
            timeout_ms=timeout_ms,
        ).found

    def is_bounty_target_dropdown_open(
        self,
        screenshot: np.ndarray | None = None,
        *,
        timeout_ms: int = 0,
    ) -> bool:
        return self._find_or_wait_bounty_match(
            self.TEXT_TARGET_OPTION_JIANGHU_XINGSHANG,
            screenshot=screenshot,
            mode="light_foreground",
            threshold=self.TARGET_OPTION_THRESHOLD,
            roi=self.ROI_TARGET_OPTIONS,
            timeout_ms=timeout_ms,
        ).found

    def is_bounty_target_selected(
        self,
        screenshot: np.ndarray | None = None,
        *,
        timeout_ms: int = 0,
    ) -> bool:
        return self._find_or_wait_bounty_match(
            self.TEXT_TARGET_SELECTED_JIANGHU_XINGSHANG,
            screenshot=screenshot,
            mode="light_foreground",
            threshold=self.TARGET_SELECTED_THRESHOLD,
            roi=self.ROI_TARGET_SELECTED,
            timeout_ms=timeout_ms,
        ).found

    def _wait_publish_success(self, *, timeout_ms: int) -> bool:
        deadline = self._make_deadline(timeout_ms)
        while True:
            screenshot = self.screenshot()
            if (
                not self.is_bounty_publish_panel_visible(screenshot)
                and self.is_bounty_panel_visible(screenshot)
            ):
                return True
            if self._is_deadline_expired(deadline):
                return False
            self.wait(min(self.PANEL_POLL_INTERVAL_MS, self._remaining_ms(deadline)))

    def _find_or_wait_bounty_match(
        self,
        template: str | tuple[str, ...],
        *,
        screenshot: np.ndarray | None,
        mode: BinaryMode,
        threshold: float,
        roi: tuple[int, int, int, int],
        timeout_ms: int,
    ) -> ImageMatchResult:
        if screenshot is not None:
            return self._match_bounty_template(
                screenshot,
                template,
                mode=mode,
                threshold=threshold,
                roi=roi,
            )
        return self._wait_bounty_match(
            template,
            mode=mode,
            threshold=threshold,
            roi=roi,
            timeout_ms=timeout_ms,
        )

    def _wait_bounty_match(
        self,
        template: str | tuple[str, ...],
        *,
        mode: BinaryMode,
        threshold: float,
        roi: tuple[int, int, int, int],
        timeout_ms: int,
    ) -> ImageMatchResult:
        deadline = self._make_deadline(timeout_ms)
        last = ImageMatchResult(False, 0.0, None, None)
        while True:
            last = self._match_bounty_template(
                self.screenshot(),
                template,
                mode=mode,
                threshold=threshold,
                roi=roi,
            )
            if last.found or self._is_deadline_expired(deadline):
                return last
            self.wait(min(self.PANEL_POLL_INTERVAL_MS, self._remaining_ms(deadline)))

    def _match_bounty_template(
        self,
        screenshot: np.ndarray,
        template: str | tuple[str, ...],
        *,
        mode: BinaryMode,
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

    def _raise_publish_error(self, suffix: str, message: str) -> None:
        debug_path = self.save_debug_screenshot(f"jhxs_bounty_publish_{suffix}")
        raise RuntimeError(f"{message}，已保存截图：{debug_path}")

    def on_finish(self, results: list) -> None:
        success_count = sum(1 for result in results if result.success)
        self._log("=" * 40)
        self._log(f"江湖行商悬赏发布任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
