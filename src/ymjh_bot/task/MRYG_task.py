"""
每日一卦 - Python DSL 实现
"""

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class MRYGTask(YmGameTask):
    """每日一卦。"""

    task_key = "MRYG"
    task_name = "每日一卦"
    task_description = "每日一卦任务"

    BTN_SMZB = str(YmGameTask.TEMPLATES_DIR / "btn_MRYG_SMZB.png")
    BTN_TTYM = str(YmGameTask.TEMPLATES_DIR / "btn_MRYG_TTYM.png")
    BTN_JSGX = str(YmGameTask.TEMPLATES_DIR / "btn_MRYG_JSGX.png")

    ICON_CGSS_COMPLETE = str(YmGameTask.TEMPLATES_DIR / "icon_cgss_complete.png")

    TTYM_CLICK_INTERVAL_MS = 1500

    # 固定坐标点 (设计分辨率 1280x720 下)
    POINT_QIANWANG = (434, 416)
    POINT_ANSWER = (1232, 540)

    @step(retry=3, timeout_ms=30000)
    def open_huodong(self) -> None:
        """打开活动界面。"""
        self.open_activity_panel("游历", wait_after_category_ms=2000)
        # 条件检查：如果已经检测到 CGSS_COMPLETE 图标，说明已茶馆说书已完成
        if self.wait_image_appear(self.ICON_CGSS_COMPLETE, timeout_ms=2000):
            self._log("检测到每日一卦已完成，直接结束任务")
            self.jump_to_end()
        self.click_point(self.POINT_QIANWANG[0], self.POINT_QIANWANG[1])
        self.wait(1500)

    @step(retry=1, timeout_ms=None)
    def auto_pathfinding(self) -> None:
        """等待自动寻路开始（检测到"自动寻路"文字消失）。"""
        self.wait_auto_pathfinding()

    @step(retry=0, timeout_ms=240000)
    def enter_panel(self) -> None:
        """点击进入茶馆（循环点击直到消失）。"""
        fortune_targets = [self.BTN_SMZB, self.BTN_OK]
        if not self.wait_image_appear(fortune_targets, timeout_ms=180000):
            raise RuntimeError("未找到算命占卜按钮")
        self._click_current_match_and_wait()

        if not self.wait_image_missing(
            fortune_targets,
            callback=lambda found, count: self._click_current_match_and_wait() if found else None,
        ):
            raise RuntimeError("算命占卜按钮点击后未消失")

        if not self.wait_image_appear(self.BTN_TTYM):
            raise RuntimeError("未找到听天由命按钮")
        self._click_current_match_and_wait()

        if not self.wait_image_appear(
            self.BTN_JSGX,
            timeout_ms=180000,
            interval_ms=self.TTYM_CLICK_INTERVAL_MS,
            callback=lambda found: self.click_point(1024, 580) if not found else None,
        ):
            raise RuntimeError("听天由命后未出现接受卦象按钮")
        self._click_current_match_and_wait()

        if not self.wait_image_appear(self.BTN_MODAL_OK):
            raise RuntimeError("未找到每日一卦确认按钮")
        self._click_current_match_and_wait()
        if not self.wait_image_missing(
            self.BTN_MODAL_OK,
            callback=lambda found, count: self._click_current_match_and_wait() if found else None,
        ):
            raise RuntimeError("每日一卦确认按钮点击后未消失")

    def _click_current_match_and_wait(self, wait_ms: int = 1500) -> None:
        self.click()
        self.wait(wait_ms)

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self.close_all_panels()
        self._log("=" * 40)
        self._log(f"每日一卦任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
