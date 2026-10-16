"""日常购买：按勾选选项购买商城及商会商品。"""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from botCore import StepStopException, step
from ymjh_bot.ui.task_queue_state import RCGM_ITEM_LABELS, normalize_rcgm_settings
from ymjh_bot.ym_game_task import YmGameTask


class RCGMTask(YmGameTask):
    """购买指定日常商品，购买结果不明时禁止再次扣款。"""

    task_key = "RCGM"  # 队列与参数持久化的唯一任务键。
    task_name = "日常购买"  # GUI 中显示的任务名称。
    task_description = "按勾选商品输入99购买，实际数量由游戏限购规则决定"  # 用户可见用途。
    ASSET_DIR = YmGameTask.TEMPLATES_DIR / "daily_purchase"  # 本任务真实模板目录。
    ROI_PANEL_TITLE = (20, 0, 190, 65)  # 珍宝阁标题区域，1280×720 像素坐标。
    ROI_ENTRY = (700, 0, 440, 100)  # 主场景右上角珍宝阁入口区域。
    ROI_MALL_TAB = (1158, 370, 122, 110)  # 右侧商城页签激活名称的像素区域。
    ROI_COMMERCE_TAB = (1158, 575, 122, 110)  # 右侧商会页签激活名称的像素区域。
    ROI_SIDEBAR = (45, 160, 265, 505)  # 商会左侧商品分类列表，排除顶部购买/出售页签。
    ROI_GOODS = (345, 170, 360, 470)  # 商会商品名称区域，避开底部截断条目。
    ROI_MALL_GOODS = (40, 212, 710, 430)  # 商城双列商品区域。
    ROI_DETAIL = (840, 160, 260, 58)  # 所选商品详情标题区域。
    ROI_KEYPAD = (730, 260, 400, 285)  # 游戏数字键盘确认键可能出现的区域。
    ROI_TOAST = (420, 308, 460, 55)  # 购买成功提示出现的屏幕中央区域。
    ROI_RESULT_CLOSE = (1070, 222, 48, 45)  # 银票礼盒购买后使用提示的关闭叉区域。
    POINT_MALL = (1222, 430)  # 珍宝阁右侧商城页签中心，单位为像素。
    POINT_MALL_CATEGORY = (110, 116)  # 商城奇珍异宝分类中心，单位为像素。
    POINT_COMMERCE = (1222, 622)  # 珍宝阁右侧商会页签中心，单位为像素。
    POINT_COMMERCE_PURCHASE = (120, 110)  # 商会顶部购买页签中心，单位为像素。
    POINT_MALL_QUANTITY = (946, 584)  # 商城右下角数量框中心，单位为像素。
    POINT_COMMERCE_QUANTITY = (922, 573)  # 商会右下角数量框中心，单位为像素。
    POINT_MALL_BUY = (947, 662)  # 商城数量框下方购买按钮中心，单位为像素。
    POINT_COMMERCE_BUY = (922, 651)  # 商会数量框下方购买按钮中心，单位为像素。
    KEYPAD_COLUMN_PX = 84  # 数字9与确认键的横向间距，单位为像素。
    KEYPAD_DELETE_OFFSET_PX = 166  # 删除键相对确认键的向上距离，单位为像素。
    SCROLL_DURATION_MS = 1200  # 慢速拖动持续毫秒数，避免惯性跳过目标。
    SCROLL_ATTEMPTS = 12  # 商品或分类搜索最多向后翻动次数。
    MATCH_THRESHOLD = 0.84  # 名称及界面标记的最低模板匹配分数。

    def __init__(self, rcgm_settings: dict[str, Any] | None = None):
        """self 为任务实例，rcgm_settings 为四项商品开关，None 表示全部关闭。"""
        super().__init__()
        self.rcgm_settings = normalize_rcgm_settings(rcgm_settings)  # 当前角色的独立商品购买配置。
        self._completed_items: set[str] = set()  # 本实例已购买或已达限购的商品；完整任务重试时保留。
        self._pending_item: str | None = None  # 已点击购买但尚未确认结果的商品；None 表示没有未决扣款。

    @step(retry=0, timeout_ms=180_000)
    def purchase_selected_goods(self) -> bool:
        """按商城、杂货、古董材料顺序购买；self 为当前任务实例。"""
        self._check_stop()
        if self._pending_item is not None:
            self._fail(f"{RCGM_ITEM_LABELS[self._pending_item]}上次购买结果不明，禁止重复购买")
        if not any(self.rcgm_settings.values()):
            self._log("未勾选日常购买商品，跳过购买")
            return True
        if not self._find("panel_title", self.ROI_PANEL_TITLE):
            if not self.ensure_top_shortcuts_expanded():
                self._fail("无法展开主场景顶部快捷入口")
            self._click_marker("entry", self.ROI_ENTRY, "珍宝阁入口")
        self._require_marker("panel_title", self.ROI_PANEL_TITLE, "珍宝阁面板")

        if self._needs_purchase("silver_box"):
            self.click_point(*self.POINT_MALL, offset=0)
            self._require_marker("mall_tab", self.ROI_MALL_TAB, "商城页签已激活")
            self.click_point(*self.POINT_MALL_CATEGORY, offset=0)
            self._require_marker("mall_page", (40, 86, 170, 58), "商城奇珍异宝页")
            self._click_scroll_target("silver_box_list", self.ROI_MALL_GOODS, "银票礼盒")
            self._purchase_item("silver_box", mall=True)

        if any(self._needs_purchase(key) for key in ("eggs", "tenon", "bronze_horse")):  # key 为商会商品键。
            self.click_point(*self.POINT_COMMERCE, offset=0)
            self._require_marker("commerce_tab", self.ROI_COMMERCE_TAB, "商会页签已激活")
            self.click_point(*self.POINT_COMMERCE_PURCHASE, offset=0)
            self._require_marker("commerce_page", (45, 85, 160, 55), "商会购买页")
        if self._needs_purchase("eggs") or self._needs_purchase("tenon"):
            self._reset_scroll(self.ROI_SIDEBAR)
            if not self._find("misc_sale", self.ROI_SIDEBAR):
                self._click_scroll_target(
                    ["misc_category", "misc_category_active"], self.ROI_SIDEBAR, "江湖杂货"
                )
            self._click_scroll_target("misc_sale", self.ROI_SIDEBAR, "杂货出售")
            for key in ("eggs", "tenon"):  # 依照用户要求先鸡蛋、再榫头卯眼。
                if self._needs_purchase(key):
                    self._click_scroll_target(f"{key}_list", self.ROI_GOODS, RCGM_ITEM_LABELS[key])
                    self._purchase_item(key, mall=False)
        if self._needs_purchase("bronze_horse"):
            self._click_scroll_target(
                ["antique_category", "antique_category_active"], self.ROI_SIDEBAR, "古董材料"
            )
            self._click_scroll_target("bronze_horse_list", self.ROI_GOODS, "碧铜马坯")
            self._purchase_item("bronze_horse", mall=False)
        return True

    @step(retry=1, timeout_ms=15_000)
    def close_purchase_panel(self) -> bool:
        """关闭购买面板；self 为当前任务实例。"""
        self.close_all_panels(timeout_ms=6000)
        return not self._find("panel_title", self.ROI_PANEL_TITLE)

    def cleanup_after_failure(self, failure: Exception | str | None = None) -> None:
        """清理购买界面；self 为任务实例，failure 为队列传入的失败原因。"""
        self.close_all_panels(timeout_ms=6000)
        if self._find("panel_title", self.ROI_PANEL_TITLE):
            self._fail("日常购买失败后珍宝阁面板仍未关闭")

    def _needs_purchase(self, key: str) -> bool:
        """self 为任务实例，key 为商品键；已完成商品在完整任务重试中跳过。"""
        return self.rcgm_settings[key] and key not in self._completed_items

    def _paths(self, names: str | list[str]) -> list[str]:
        """self 为任务实例，names 为本任务模板名或名称列表。"""
        # name 为单个模板文件的无扩展名名称。
        return [
            str(self.ASSET_DIR / f"{name}.png")
            for name in ([names] if isinstance(names, str) else names)
        ]

    def _find(
        self, names: str | list[str], roi: tuple[int, int, int, int],
        *, screenshot: np.ndarray | None = None,
    ) -> bool:
        """self 为任务实例，names 为模板名，roi 为像素搜索区域，screenshot 为复用帧，None 时重新截图。"""
        self._check_stop()
        return self.find_image(
            self._paths(names), threshold=self.MATCH_THRESHOLD, roi=roi, screenshot=screenshot,
        )

    def _require_marker(self, names: str | list[str], roi: tuple[int, int, int, int], label: str) -> None:
        """self 为任务实例，names 为模板名，roi 为像素搜索区域，label 为日志描述。"""
        if not self.wait_find_image_in_roi(
            self._paths(names), roi, timeout_ms=4000, description=label,
            threshold=self.MATCH_THRESHOLD, interval_ms=200,
        ):
            self._fail(f"未确认{label}")

    def _click_marker(self, names: str | list[str], roi: tuple[int, int, int, int], label: str) -> None:
        """self 为任务实例，names 为模板名，roi 为像素区域，label 为待点击目标描述。"""
        self._require_marker(names, roi, label)
        self.click(offset=0)
        self.wait(400)

    def _reset_scroll(self, roi: tuple[int, int, int, int]) -> None:
        """回到列表起始处；self 为任务实例，roi 为商品或分类列表像素区域。"""
        x = roi[0] + roi[2] // 2  # 拖动横坐标，位于列表中央。
        for _attempt in range(3):  # 最多三次向下拖动，覆盖这些商店列表的总长度。
            self._check_stop()
            self.swipe(x, roi[1] + 50, x, roi[1] + roi[3] - 30, self.SCROLL_DURATION_MS)
            self.wait(250)

    def _click_scroll_target(self, names: str | list[str], roi: tuple[int, int, int, int], label: str) -> None:
        """有限慢速拖动寻找目标；self 为任务实例，names 为模板，roi 为像素列表区域，label 为中文名称。"""
        if self._find(names, roi):
            self.click(offset=0)
            self.wait(400)
            return
        self._reset_scroll(roi)
        x = roi[0] + roi[2] // 2  # 在列表内部拖动的横坐标，单位为像素。
        for attempt in range(self.SCROLL_ATTEMPTS + 1):  # 零起始搜索轮次，最后一轮只识别不拖动。
            if self._find(names, roi):
                self.click(offset=0)
                self.wait(400)
                return
            if attempt < self.SCROLL_ATTEMPTS:
                self._debug(f"寻找{label}，慢速拖动 {attempt + 1}/{self.SCROLL_ATTEMPTS}")
                self.swipe(x, roi[1] + roi[3] - 40, x, roi[1] + roi[3] - 280, self.SCROLL_DURATION_MS)
                self.wait(300)
        self._fail(f"列表中未找到{label}")

    def _quota_exhausted(self, image: np.ndarray, *, mall: bool) -> bool:
        """比较限购分子的字形与分母；self 为实例，image 为真实帧，mall 表示商城布局。"""
        roi = (978, 226, 100, 26) if mall else (950, 215, 115, 35)  # 仅含今日购买数字和斜线的区域。
        match = self._vision.match_template(image, self._paths("quota_slash"), threshold=0.9, roi=roi)  # 今日购买分隔斜线的匹配。
        if not match.found or match.bbox is None:
            self._fail("无法识别商品今日购买限额")
        x, y, width, height = roi  # 数字区域左上角及宽高，单位为像素。
        slash_left, _top, slash_right, _bottom = match.bbox  # 斜线屏幕边界；_top、_bottom 为未使用纵坐标。
        mask = cv2.inRange(image[y:y+height, x:x+width], (140, 140, 140), (255, 255, 255))  # 限购数字浅色笔画。
        current = self._trim_digits(mask[:, :slash_left-x])  # 已购数量的紧致字形掩码。
        maximum = self._trim_digits(mask[:, slash_right-x:])  # 当日限购总数的紧致字形掩码。
        if current is None or maximum is None:
            self._fail("商品今日购买限额缺少数字")
        if any(abs(current.shape[index] - maximum.shape[index]) > 2 for index in (0, 1)):  # index 为字形高、宽维度。
            return False
        padded = cv2.copyMakeBorder(maximum, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=0)  # 留出字体抗锯齿导致的像素平移空间。
        _minimum, score, _min_location, location = cv2.minMaxLoc(
            cv2.matchTemplate(padded, current, cv2.TM_CCOEFF_NORMED)
        )  # score 为字形相关度，location 为最佳位置，其余两个值未使用。
        placed = np.zeros_like(padded)  # 对齐后的已购数字掩码。
        placed[location[1]:location[1]+current.shape[0], location[0]:location[0]+current.shape[1]] = current
        kernel = np.ones((3, 3), np.uint8)  # 一像素笔画容差，避免同一数字因抗锯齿误判。
        coverage = min(
            float(np.mean(cv2.dilate(padded, kernel)[placed > 0] > 0)),
            float(np.mean(cv2.dilate(placed, kernel)[padded > 0] > 0)),
        )  # 两侧数字笔画的最小相互覆盖率。
        return score >= 0.75 and coverage >= 0.98

    @staticmethod
    def _trim_digits(mask: np.ndarray) -> np.ndarray | None:
        """裁去字形外围空白；mask 为限购数字的二值掩码，无字形时返回 None。"""
        points = cv2.findNonZero(mask)  # 数字笔画像素坐标；None 表示空白。
        if points is None:
            return None
        x, y, width, height = cv2.boundingRect(points)  # 紧致字形区域左上角及宽高，单位为像素。
        return mask[y:y+height, x:x+width]

    def _enter_quantity_99(self, *, mall: bool) -> None:
        """使用游戏数字键盘输入 99；self 为实例，mall 决定商城或商会数量框位置。"""
        quantity_point = self.POINT_MALL_QUANTITY if mall else self.POINT_COMMERCE_QUANTITY  # 当前布局的数量框像素中心。
        self.click_point(*quantity_point, offset=0)
        self._require_marker("keypad_confirm", self.ROI_KEYPAD, "商品数量数字键盘")
        center = self._last_match_center  # 当前确认键的屏幕中心坐标，用于推导同一键盘的按键。
        if center is None:
            self._fail("数字键盘缺少确认键坐标")
        x, y = center  # 确认键的横纵屏幕像素坐标。
        for _clear_index in range(3):  # 清除数量框原有的最多三位数字。
            self.click_point(x, y - self.KEYPAD_DELETE_OFFSET_PX, offset=0)
            self.wait(80)
        for _digit_index in range(2):  # 连续输入两个数字 9。
            self.click_point(x - self.KEYPAD_COLUMN_PX, y, offset=0)
            self.wait(100)
        self.click_point(x, y, offset=0)
        if not self.wait_image_missing(self._paths("keypad_confirm"), timeout_ms=2500, interval_ms=150):
            self._fail("输入99后数字键盘未关闭")

    def _purchase_item(self, key: str, *, mall: bool) -> None:
        """确认选中商品后购买一次；self 为实例，key 为商品键，mall 为商城布局开关。"""
        label = RCGM_ITEM_LABELS[key]  # 日志中显示的商品中文名称。
        self._require_marker(f"{key}_detail", self.ROI_DETAIL, f"{label}详情")
        if self._quota_exhausted(self.screenshot(), mall=mall):
            self._completed_items.add(key)
            self._log(f"{label}今日已达限购，跳过购买")
            return
        self._enter_quantity_99(mall=mall)
        self._require_marker(f"{key}_detail", self.ROI_DETAIL, f"{label}详情")
        self._check_stop()
        self._pending_item = key
        self._log(f"购买{label}，输入数量99，实际数量由游戏限制")
        buy_point = self.POINT_MALL_BUY if mall else self.POINT_COMMERCE_BUY  # 当前布局的购买按钮像素中心。
        self.click_point(*buy_point, offset=0)
        deadline = time.monotonic() + 5  # 购买结果最多等待五秒。
        while time.monotonic() < deadline:
            self._check_stop()
            image = self.screenshot()  # 同一购买反馈帧，同时检查成功提示和明确拒绝提示。
            if self._find(["buy_success", "silver_success"], self.ROI_TOAST, screenshot=image):
                self._completed_items.add(key)
                self._pending_item = None
                self._log(f"{label}购买成功")
                self.wait(500)
                if self._find("result_close", self.ROI_RESULT_CLOSE):
                    self.click(offset=0)
                    self.wait(300)
                return
            if self._find("temporary_bag_full", self.ROI_TOAST, screenshot=image):
                self._pending_item = None
                self._fail(f"{label}购买被游戏拒绝：请先清理临时包裹")
            self.wait(150)
        self._fail(f"{label}未确认购买成功；保留未决状态，避免重复扣款")

    def _fail(self, message: str) -> None:
        """保存失败现场并抛错；self 为任务实例，message 为中文失败原因。"""
        if self._stop_requested:
            raise StepStopException("用户停止日常购买")
        path = self.save_debug_screenshot("daily_purchase_failed")  # 失败原始截图路径。
        raise RuntimeError(f"{message}，已保存截图：{path}")

    def _check_stop(self) -> None:
        """在截图与拖动边界响应停止；self 为当前任务实例。"""
        if self._stop_requested:
            raise StepStopException("用户停止日常购买")
