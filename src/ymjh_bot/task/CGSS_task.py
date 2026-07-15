"""
茶馆说书任务 - Python DSL 实现
"""

from __future__ import annotations

from botCore import step

from ymjh_bot.ym_game_task import YmGameTask


class CGSSTask(YmGameTask):
    """一梦江湖茶馆说书任务。"""

    task_key = "CGSS"
    task_name = "茶馆说书"
    task_description = "茶馆说书任务"
    auto_recover_health = False

    BTN_JRCG = str(YmGameTask.TEMPLATES_DIR / "btn_CGSS_JRCG.png")
    BTN_CHAGUANSHUOSHU_ENTRY = str(YmGameTask.TEMPLATES_DIR / "btn_CGSS_entry.png")
    BTN_TCCG = str(YmGameTask.TEMPLATES_DIR / "btn_CGSS_TCCG.png")

    # 固定坐标点 (设计分辨率 1280x720 下)
    POINT_SEAT = (797, 459)
    POINT_ANSWER = (1232, 540)
    ROI_CHAGUANSHUOSHU_ENTRY = (170, 430, 230, 210)

    ANSWER_CLICK_INTERVAL_MS = 3000

    @step(retry=3, timeout_ms=30000)
    def open_huodong(self) -> None:
        """打开活动界面。"""
        self.open_activity_panel(
            "江湖",
            wait_after_category_ms=2000,
        )

        if not self.wait_find_image_in_roi(
            self.BTN_CHAGUANSHUOSHU_ENTRY,
            self.ROI_CHAGUANSHUOSHU_ENTRY,
            timeout_ms=3000,
            description="活动页茶馆说书入口",
        ):
            self._log("未找到茶馆说书入口，默认茶馆说书当前不可接取或已完成")
            self.jump_to_end()

        self.click()
        self.wait(1500)

    @step(retry=1, timeout_ms=None)
    def auto_pathfinding(self) -> None:
        """等待自动寻路开始（检测到"自动寻路"文字消失）。"""
        self.wait_auto_pathfinding()

    @step(retry=3, timeout_ms=60000)
    def enter_chaguan(self) -> None:
        """点击进入茶馆（循环点击直到消失）。"""
        if not self.wait_image_appear(self.BTN_JRCG, timeout_ms=30000):
            raise RuntimeError("未找到进入茶馆按钮")

        if not self.wait_image_missing(
            self.BTN_JRCG,
            timeout_ms=30000,
            callback=lambda found, count: self.click() if found else None,
        ):
            raise RuntimeError("进入茶馆按钮未消失")
        self.wait(1000)
        self.click_point(self.POINT_SEAT[0], self.POINT_SEAT[1])
        self._log("已尝试点击茶馆入座")
        self.wait(1000)

    @step(retry=0, timeout_ms=None)
    def click_answer(self) -> None:
        """轮询点击答案选项，直到出现退出茶馆按钮。"""
        click_count = 0

        while True:
            if self.find_image(self.BTN_TCCG):
                self._log("检测到退出茶馆按钮，停止答题")
                return

            if click_count % 10 == 0:
                self._log(f"茶馆答题轮询中，已尝试 {click_count} 次")
            self.click_point(self.POINT_ANSWER[0], self.POINT_ANSWER[1])
            click_count += 1
            self.wait(self.ANSWER_CLICK_INTERVAL_MS)

    @step(retry=1, timeout_ms=10000)
    def exit_chaguan(self) -> None:
        """退出茶馆答题界面。"""
        if not self.wait_image_appear(self.BTN_TCCG, timeout_ms=None):
            raise RuntimeError("未找到退出茶馆按钮")
        self.click()
        self.wait(2000)

    @step(retry=1, timeout_ms=30000)
    def verify_completion(self) -> None:
        """验证茶馆说书已完成。"""
        self.close_all_panels()
        self.open_activity_panel(
            "江湖",
            wait_after_category_ms=2000,
        )

        if not self.wait_find_image_in_roi(
            self.BTN_CHAGUANSHUOSHU_ENTRY,
            self.ROI_CHAGUANSHUOSHU_ENTRY,
            timeout_ms=3000,
            description="活动页茶馆说书入口",
        ):
            self._log("完成验证：活动页已无茶馆说书入口")
            return

        raise RuntimeError("茶馆说书完成验证失败：活动页仍存在茶馆说书入口")

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"茶馆说书任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
