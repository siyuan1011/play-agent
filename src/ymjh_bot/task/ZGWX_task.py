"""坐观万象任务 - Python DSL 实现。"""

from __future__ import annotations

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class ZGWXTask(YmGameTask):
    """一梦江湖坐观万象任务。"""

    task_key = "ZGWX"
    task_name = "坐观万象"
    task_description = "坐观万象自动前往并等待修炼完成"
    auto_recover_health = False

    BTN_ACTIVITY_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_bangpai_task_forward.png")
    TEXT_MEDITATING = str(YmGameTask.TEMPLATES_DIR / "text_zgwx_meditating.png")

    ROI_ZGWX_FORWARD = (120, 250, 220, 120)

    FORWARD_THRESHOLD = 0.85
    MEDITATING_THRESHOLD = 0.9

    MEDITATION_START_TIMEOUT_MS = 600000
    MEDITATION_COMPLETE_TIMEOUT_MS = 900000
    MEDITATION_MISSING_THRESHOLD = 20
    MEDITATION_MISSING_INTERVAL_MS = 5000

    def on_start(self) -> None:
        """任务开始前准备。"""
        self._log("=" * 40)
        self._log("坐观万象任务开始")
        self._log("=" * 40)

    @step(retry=1, timeout_ms=30000)
    def close_all(self) -> None:
        """关闭所有弹窗，回到游戏主界面。"""
        self.close_all_panels()
        if self.wake_from_power_saving_if_needed():
            self.close_all_panels()
        self.wait(1000)

    @step(retry=3, timeout_ms=30000)
    def open_youli_activity(self) -> None:
        """打开活动-游历并点击坐观万象前往。"""
        self.open_activity_panel(
            "游历",
            wait_after_category_ms=2000,
        )

        if not self.wait_find_image_in_roi(
            self.BTN_ACTIVITY_FORWARD,
            self.ROI_ZGWX_FORWARD,
            timeout_ms=3000,
            description="活动页坐观万象前往按钮",
            threshold=self.FORWARD_THRESHOLD,
        ):
            self._log("未找到坐观万象前往按钮，默认当前不可接取或已完成")
            self.jump_to("verify_completion")

        self._log("点击坐观万象前往按钮")
        self.click(offset=0)
        self.wait(1500)

    @step(retry=1, timeout_ms=None)
    def wait_meditation_start(self) -> None:
        """等待自动寻路结束并进入坐观万象修炼倒计时。"""
        if not self.wait_image_appear(
            self.TEXT_MEDITATING,
            timeout_ms=self.MEDITATION_START_TIMEOUT_MS,
            threshold=self.MEDITATING_THRESHOLD,
            interval_ms=1500
        ):
            raise RuntimeError("坐观万象修炼开始等待超时")
        self._log("检测到修炼中倒计时，坐观万象开始修炼")

    @step(retry=1, timeout_ms=None)
    def wait_meditation_complete(self) -> None:
        """等待修炼中倒计时消失。"""
        if not self.wait_image_missing(
            self.TEXT_MEDITATING,
            timeout_ms=self.MEDITATION_COMPLETE_TIMEOUT_MS,
            threshold=self.MEDITATING_THRESHOLD,
            missing_threshold=self.MEDITATION_MISSING_THRESHOLD,
            interval_ms=self.MEDITATION_MISSING_INTERVAL_MS,
        ):
            raise RuntimeError("坐观万象修炼完成等待超时")
        self._log("检测到修炼中倒计时消失，坐观万象修炼结束")

    @step(retry=1, timeout_ms=30000)
    def verify_completion(self) -> None:
        """验证活动-游历页已无坐观万象前往按钮。"""
        self.close_all_panels()
        self.open_activity_panel(
            "游历",
            wait_after_category_ms=2000,
        )

        if not self.wait_find_image_in_roi(
            self.BTN_ACTIVITY_FORWARD,
            self.ROI_ZGWX_FORWARD,
            timeout_ms=3000,
            description="活动页坐观万象前往按钮",
            threshold=self.FORWARD_THRESHOLD,
        ):
            self._log("完成验证：活动页已无坐观万象前往按钮")
            return

        raise RuntimeError("坐观万象完成验证失败：活动页仍存在前往按钮")

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"坐观万象任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
