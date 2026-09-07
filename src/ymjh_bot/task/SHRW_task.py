"""生活任务：通过地图生活筛选定位资源并循环采集。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal

import cv2
import numpy as np

from botCore import StepStopException, step
from ymjh_bot.ui.task_queue_state import (
    SHRW_MATERIAL_OPTIONS,
    SHRW_TASK_TYPE_LABELS,
    normalize_shrw_settings,
)
from ymjh_bot.ym_game_task import TEMPLATES_DIR, YmGameTask


@dataclass(frozen=True, slots=True)
class LifeMaterialSpec:
    """一个生活材料在地图生活面板中的位置及其目标地图。"""

    key: str
    label: str
    task_type: str
    item_index: int
    map_key: str
    gather_slot: int


class LifeTaskUnavailable(RuntimeError):
    """体力或采集工具不足时用于正常结束生活任务循环。"""


TARGET_MAP_LABELS = {
    "zhongyuan": "中原",
    "jiangnan": "江南",
    "saibei": "塞北",
    "buwenchun": "不闻春",
}


def _target_map_for_material(task_type: str, material_key: str) -> str:
    """Return the map requested by the product rule for one material."""
    if task_type == "mining":
        return "zhongyuan"
    if task_type == "logging":
        return "jiangnan"
    if task_type == "wool":
        return "buwenchun"
    if material_key == "wild_ginseng":
        return "jiangnan"
    if material_key == "lingzhi":
        return "saibei"
    return "zhongyuan"


def _map_filter_item_index(
    task_type: str,
    material_key: str,
    option_index: int,
) -> int:
    """Return the index shown by the actual map filter for a configured item.

    采毛地图不按四种产物列筛选，只显示两种来源动物：山羊和驯鹿。
    因此羊毛/羊绒共享山羊资源点，驯鹿毛/驯鹿绒共享驯鹿资源点。
    """
    if task_type == "wool":
        return 0 if material_key in {"wool", "cashmere"} else 1
    return option_index


def _gather_slot_for_material(material_key: str) -> int:
    """采毛同一动物会展示两种产物，绒类使用第二个交互按钮。"""
    return 1 if material_key in {"cashmere", "reindeer_down"} else 0


def _material_specs() -> dict[str, LifeMaterialSpec]:
    specs: dict[str, LifeMaterialSpec] = {}
    for task_type, options in SHRW_MATERIAL_OPTIONS.items():
        for item_index, (key, label) in enumerate(options):
            specs[key] = LifeMaterialSpec(
                key=key,
                label=label,
                task_type=task_type,
                item_index=_map_filter_item_index(task_type, key, item_index),
                map_key=_target_map_for_material(task_type, key),
                gather_slot=_gather_slot_for_material(key),
            )
    return specs


class SHRWTask(YmGameTask):
    """一梦江湖生活资源采集。

    真机地图流程：打开地图 -> 打开左侧筛选 -> 生活 -> 技能下拉 ->
    材料 -> 地图资源标志 -> 自动寻路 -> 场景采集。
    """

    task_key = "SHRW"
    task_name = "生活任务"
    task_description = "按配置地图定位资源，并持续执行自动寻路和采集"
    MATERIAL_SPECS = _material_specs()

    # 坐标均由 1280x720 真机截图校准。
    POINT_MAP = (1260, 90)
    POINT_MAP_FILTER = (20, 345)
    POINT_MAP_LIFE_TAB = (66, 117)
    POINT_MAP_WORLD = (1235, 675)
    POINT_MAP_CLOSE = (1235, 42)
    POINT_CLEAR_MAP_FILTERS = (1125, 42)
    POINT_LIFE_PANEL_COLLAPSE = (500, 342)
    POINT_LIFE_PANEL_X = 300
    # 场景交互菱形的中心；采毛的绒类产物位于同一动物的第二行。
    POINT_GATHER_ACTIONS = ((935, 466), (918, 562))
    POINT_GATHER_ACTION = POINT_GATHER_ACTIONS[0]
    POINT_TARGET_MAPS: ClassVar[dict[str, tuple[int, int]]] = {
        "zhongyuan": (672, 366),
        "jiangnan": (966, 275),
        "saibei": (599, 105),
        "buwenchun": (841, 90),
    }

    POINT_LIFE_SCROLL_DOWN_START = (300, 160)
    POINT_LIFE_SCROLL_DOWN_END = (300, 650)
    POINT_LIFE_SCROLL_UP_START = (300, 620)
    POINT_LIFE_SCROLL_UP_END = (300, 160)

    # 将生活列表回到顶部后，各生活技能下拉行的中心。采毛在下一屏。
    LIFE_SKILL_TOP_Y: ClassVar[dict[str, int]] = {
        "herb": 401,
        "logging": 490,
        "mining": 580,
    }
    LIFE_WOOL_Y_AFTER_SCROLL = 514
    LIFE_HEADER_TO_FIRST_ITEM_Y = 87
    LIFE_MATERIAL_ROW_HEIGHT = 82

    ROI_MAP_CLOSE = (1185, 0, 95, 90)
    ROI_LIFE_ITEM_ICONS = (155, 0, 105, 720)
    ROI_RESOURCE_MAP = (500, 60, 600, 500)
    ROI_GATHER_ACTIONS = (
        ((975, 425, 115, 80), (875, 420, 105, 100)),
        ((960, 520, 150, 80), (870, 515, 105, 95)),
    )
    ROI_GATHER_TEMPLATE_SEARCH = (
        (885, 425, 95, 75),
        (870, 520, 100, 75),
    )
    ROI_GATHER_TEXT = ROI_GATHER_ACTIONS[0][0]
    ROI_GATHER_DIAMOND = ROI_GATHER_ACTIONS[0][1]
    ROI_MAIN_HEALTH = (74, 27, 260, 20)
    # 跨图加载页底部的进度条。仅在未识别到主场景时使用，避免将普通
    # 场景中的明亮 UI 误判为过图。
    ROI_SCENE_LOADING_PROGRESS = (250, 592, 800, 24)

    # 每张地图上的资源图标聚集区。地图差分不可用时才作为保守兜底。
    MAP_RESOURCE_ANCHORS: ClassVar[
        dict[str, tuple[tuple[int, int], ...]]
    ] = {
        "zhongyuan": ((613, 445), (671, 519), (718, 494), (615, 527)),
        "jiangnan": ((565, 456), (592, 428), (715, 310), (540, 488)),
        "saibei": ((586, 129), (623, 171), (747, 222), (546, 345)),
        "buwenchun": ((901, 423), (984, 402)),
    }

    MAP_WAIT_MS = 900
    PANEL_WAIT_MS = 550
    AUTO_PATH_TIMEOUT_MS = 360_000
    GATHER_ACTION_WAIT_MS = 20_000
    GATHER_COMPLETE_TIMEOUT_MS = 120_000
    SCENE_TRANSITION_TIMEOUT_MS = 45_000
    MAX_COLLECTIONS_PER_RUN = 200
    MAX_EMPTY_MARKER_RESELECTS = 2
    MAX_LIFE_PANEL_REWIND_SWIPES = 3
    MAP_RESOURCE_CHANGE_MIN_PIXELS = 500
    MAP_RESOURCE_CHANGE_RADIUS = 44
    GATHER_TEMPLATE_THRESHOLD = 0.76

    # 采集工具会随技能和资源等级改变。模板来自 1280x720 真机截图，
    # 每类技能匹配全部已知等级，避免把高阶工具误判为“未到达”。
    GATHER_TOOL_TEMPLATES: ClassVar[dict[str, tuple[str, ...]]] = {
        "mining": tuple(
            str(TEMPLATES_DIR / f"icon_shrw_mining_tool_{level}.png")
            for level in range(6)
        ),
        "logging": tuple(
            str(TEMPLATES_DIR / f"icon_shrw_logging_tool_{level}.png")
            for level in range(6)
        ),
        "herb": (str(TEMPLATES_DIR / "icon_shrw_herb_action.png"),),
        "wool": (str(TEMPLATES_DIR / "icon_shrw_wool_action.png"),),
    }

    def __init__(self, shrw_settings: dict[str, Any] | None = None):
        super().__init__()
        self.shrw_settings = normalize_shrw_settings(shrw_settings)
        self.task_type = str(self.shrw_settings["task_type"])
        self.material_key = str(self.shrw_settings["material"])
        self.material = self.MATERIAL_SPECS[self.material_key]
        # 兼容既有持久化字段；新版语义是是否持续执行采集循环。
        self.loop_lines = bool(self.shrw_settings["loop_lines"])
        self._successful_gathers = 0
        self._known_unavailable_reason: str | None = None
        self._resource_filter_selected = False
        self._map_filter_baseline: np.ndarray | None = None

    @step(retry=0, timeout_ms=None)
    def collect_life_material(self) -> None:
        """选择配置材料后，按“标志→寻路→采集→重开地图”循环。"""
        try:
            self.select_configured_resource_on_map()
            visited_markers: set[tuple[int, int]] = set()
            empty_reselects = 0

            for collection_index in range(1, self.MAX_COLLECTIONS_PER_RUN + 1):
                marker = self.choose_resource_marker(visited_markers)
                if marker is None:
                    if empty_reselects >= self.MAX_EMPTY_MARKER_RESELECTS:
                        raise RuntimeError(
                            f"{TARGET_MAP_LABELS[self.material.map_key]}地图未识别到可用"
                            f"{self.material.label}资源标志"
                        )
                    empty_reselects += 1
                    self._log("当前地图资源标志已耗尽，重新选择生活材料刷新标志")
                    self.select_configured_resource_on_map()
                    visited_markers.clear()
                    continue

                empty_reselects = 0
                visited_markers.add(self._marker_key(marker))
                self.click_point(*marker, offset=0)
                self.wait(500)
                self.close_map_after_marker_click()

                if not self.wait_resource_auto_path_started(timeout_ms=15_000):
                    raise RuntimeError("点击生活资源标志后未检测到自动寻路开始")
                if not self.wait_auto_pathfinding(
                    timeout_ms=self.AUTO_PATH_TIMEOUT_MS,
                    missing_threshold=3,
                ):
                    raise RuntimeError("前往生活资源点的自动寻路超时")

                self.wake_from_power_saving_if_needed()
                if not self.gather_arrived_resource():
                    self._log(
                        f"到达后未出现{self.material.label}对应的"
                        f"{SHRW_TASK_TYPE_LABELS[self.task_type]}图标，"
                        "保留当前筛选并尝试下一资源标志"
                    )
                    self.open_existing_resource_map()
                    continue

                self._successful_gathers += 1
                self._log(
                    f"第 {self._successful_gathers} 次采集完成：{self.material.label}，"
                    f"累计 {self._successful_gathers} 次"
                )
                if not self.loop_lines:
                    return

                # 地图标志可能代表一整片资源区；一次采集后仍可再次点击同一
                # 标志前往下一个刷新点，不能把上一轮坐标永久排除。
                visited_markers.clear()
                self.open_existing_resource_map()

            raise RuntimeError(f"连续采集超过 {self.MAX_COLLECTIONS_PER_RUN} 次，已安全停止")
        except StepStopException:
            raise
        except LifeTaskUnavailable as exc:
            self._known_unavailable_reason = str(exc)
            self._log(f"生活任务停止采集：{exc}")
            return
        except Exception as exc:
            debug_path = self.save_debug_screenshot("shrw_flow_failed")
            raise RuntimeError(f"生活任务流程失败：{exc}，已保存截图：{debug_path}") from exc

    def before_retry(
        self,
        retry_scope: str,
        failure: Exception | str | None = None,
    ) -> None:
        """地图选择错误不触发通用“脱离卡死”，避免无关传送。"""
        self._log(f"生活任务{retry_scope}重试前仅关闭地图/弹窗：{failure}")
        self.close_all_panels(timeout_ms=3000)

    def select_configured_resource_on_map(self) -> None:
        """在地图生活面板中选择配置的技能与材料，令游戏打开目标地图。"""
        self.wake_from_power_saving_if_needed()
        self.close_all_panels(timeout_ms=3000)
        self.open_map()
        self.select_target_map()
        self.collapse_life_filter_panel_if_visible()
        self.clear_existing_map_filters()
        self.open_life_filter_panel()
        self.collapse_expanded_life_skill_if_needed()
        header_y = self.open_configured_life_skill()
        self.click_configured_material(header_y)
        self.collapse_life_filter_panel()
        self.wait(self.MAP_WAIT_MS)
        self._resource_filter_selected = True
        self._log(
            f"已选择 {SHRW_TASK_TYPE_LABELS[self.task_type]}-{self.material.label}，"
            f"目标地图：{TARGET_MAP_LABELS[self.material.map_key]}"
        )

    def clear_existing_map_filters(self) -> None:
        """清理残留的多项筛选，确保资源标志只属于当前配置材料。"""
        self.click_point(*self.POINT_CLEAR_MAP_FILTERS, offset=0)
        self.wait(self.PANEL_WAIT_MS)
        # 后续仅选择“清空后新增”的图标，固定城镇/车夫/传送点不会被误点。
        self._map_filter_baseline = self.screenshot()

    def open_existing_resource_map(self) -> None:
        """采集结束后重开保留筛选条件的地图，进入下一轮资源标志选择。"""
        if not self._resource_filter_selected:
            self.select_configured_resource_on_map()
            return
        self.open_map()

    def select_target_map(self) -> None:
        """根据材料规则经世界地图进入中原、江南、塞北或不闻春。"""
        if not self.is_world_map_visible_quiet():
            self.click_point(*self.POINT_MAP_WORLD, offset=0)
            self.wait(self.MAP_WAIT_MS)
        if not self.is_world_map_visible_quiet():
            raise RuntimeError("未能从区域地图切换到世界地图")

        target = self.POINT_TARGET_MAPS[self.material.map_key]
        self.click_point(*target, offset=0)
        self.wait(self.MAP_WAIT_MS)
        if self.is_world_map_visible_quiet():
            raise RuntimeError(
                f"点击{TARGET_MAP_LABELS[self.material.map_key]}后仍停留在世界地图"
            )
        self._log(f"已进入{TARGET_MAP_LABELS[self.material.map_key]}地图")

    def open_map(self) -> None:
        """打开右上角地图，并以右上角关闭圆钮确认地图已经出现。"""
        if self.is_map_visible(self.screenshot()):
            return
        self.click_point(*self.POINT_MAP, offset=0)
        self.wait(self.MAP_WAIT_MS)
        if not self.is_map_visible(self.screenshot()):
            raise RuntimeError("点击右上角地图后未打开地图")

    def open_life_filter_panel(self) -> None:
        """点击地图左侧放大镜，再选择生活 Tab。"""
        if not self.is_life_filter_panel_visible(self.screenshot()):
            self.click_point(*self.POINT_MAP_FILTER, offset=0)
            self.wait(self.PANEL_WAIT_MS)
        self.click_point(*self.POINT_MAP_LIFE_TAB, offset=0)
        self.wait(self.PANEL_WAIT_MS)
        if not self.is_life_filter_panel_visible(self.screenshot()):
            raise RuntimeError("地图左侧生活筛选面板未打开")

    def collapse_life_filter_panel_if_visible(self) -> None:
        """建立无侧栏地图基线；首次运行时兼容游戏保留的展开状态。"""
        if self.is_life_filter_panel_visible(self.screenshot()):
            self.collapse_life_filter_panel()

    def collapse_life_filter_panel(self) -> None:
        """收起生活筛选侧栏，令资源标志在完整地图上可被搜索和点击。"""
        if not self.is_life_filter_panel_visible(self.screenshot()):
            return
        self.click_point(*self.POINT_LIFE_PANEL_COLLAPSE, offset=0)
        self.wait(self.PANEL_WAIT_MS)
        if self.is_life_filter_panel_visible(self.screenshot()):
            raise RuntimeError("选择生活采集物后地图侧栏未能收起")

    def collapse_expanded_life_skill_if_needed(self) -> None:
        """回到列表顶部并收起残留的技能下拉，建立可重复的选择基线。"""
        self.rewind_life_panel()
        image = self.screenshot()
        centers = self.find_life_material_icon_centers(image)
        if not centers:
            # 采毛在列表底部；其展开项须向上滚动一屏后才可见。
            self.scroll_life_panel_up(510)
            image = self.screenshot()
            centers = self.find_life_material_icon_centers(image)
        if not centers:
            return

        first_center = min(centers, key=lambda point: point[1])
        header_y = first_center[1] - self.LIFE_HEADER_TO_FIRST_ITEM_Y
        if header_y < 28:
            self.rewind_life_panel()
            image = self.screenshot()
            centers = self.find_life_material_icon_centers(image)
            if not centers:
                return
            first_center = min(centers, key=lambda point: point[1])
            header_y = first_center[1] - self.LIFE_HEADER_TO_FIRST_ITEM_Y
        if 28 <= header_y <= 690:
            self.click_point(self.POINT_LIFE_PANEL_X, header_y, offset=0)
            self.wait(self.PANEL_WAIT_MS)

    def rewind_life_panel(self) -> None:
        """将左侧生活技能列表滚动到顶部。"""
        for _ in range(self.MAX_LIFE_PANEL_REWIND_SWIPES):
            self.swipe(
                *self.POINT_LIFE_SCROLL_DOWN_START,
                *self.POINT_LIFE_SCROLL_DOWN_END,
                duration_ms=350,
            )
            self.wait(250)

    def scroll_life_panel_up(self, distance: int) -> None:
        """向下浏览生活列表。

        真机列表的惯性滚动约为手指位移的两倍；调用方传入内容需要移动的
        近似距离，此处换算为实际滑动手势，避免高阶材料越过目标行。
        """
        finger_distance = max(80, round(distance / 2))
        end_y = max(140, self.POINT_LIFE_SCROLL_UP_START[1] - finger_distance)
        self.swipe(
            *self.POINT_LIFE_SCROLL_UP_START,
            self.POINT_LIFE_SCROLL_UP_END[0],
            end_y,
            duration_ms=350,
        )
        self.wait(700)

    def open_configured_life_skill(self) -> int:
        """打开采草、伐木、挖矿或采毛的下拉，并返回其当前标题行中心。"""
        self.rewind_life_panel()
        if self.task_type == "wool":
            self.scroll_life_panel_up(510)
            header_y = self.LIFE_WOOL_Y_AFTER_SCROLL
        else:
            header_y = self.LIFE_SKILL_TOP_Y[self.task_type]

        self.click_point(self.POINT_LIFE_PANEL_X, header_y, offset=0)
        self.wait(self.PANEL_WAIT_MS)
        return header_y

    def click_configured_material(self, header_y: int) -> None:
        """将目标材料行滚入可见区域，通过图标圆心点击而非文本 OCR。"""
        if self.task_type != "wool":
            # 下拉后重置到顶部，使标题和各材料行位置稳定。
            self.rewind_life_panel()
            header_y = self.LIFE_SKILL_TOP_Y[self.task_type]

        expected_y = (
            header_y
            + self.LIFE_HEADER_TO_FIRST_ITEM_Y
            + self.material.item_index * self.LIFE_MATERIAL_ROW_HEIGHT
        )
        if expected_y > 680 and self.task_type != "wool":
            # 采毛只有“山羊/驯鹿”两种地图来源，两个条目本就位于屏内；
            # 其他技能按目标行仅做最小滚动，保留首行可用于索引定位。
            shift = min(420, expected_y - 600)
            self.scroll_life_panel_up(shift)
            expected_y -= shift

        image = self.screenshot()
        centers = self.find_life_material_icon_centers(image)
        if not centers:
            raise RuntimeError(f"未找到{self.material.label}的材料图标")
        material_count = len(SHRW_MATERIAL_OPTIONS[self.task_type])
        if len(centers) >= material_count:
            # 下拉已完整滚入屏幕时，图标的纵向顺序就是材料配置顺序。
            center = centers[self.material.item_index]
        elif (
            centers
            and centers[0][1] >= 220
            and self.material.item_index < len(centers)
        ):
            # 目标行尚未触底时，首个可见图标仍是材料列表第 0 项。
            # 这覆盖伐木/采草中“前五项可见、第六项在屏外”的布局，避免
            # 使用距离猜测将松树误点成上一行的枫树。
            center = centers[self.material.item_index]
        else:
            center = min(centers, key=lambda point: abs(point[1] - expected_y))
        if abs(center[1] - expected_y) > 110 and len(centers) < material_count:
            raise RuntimeError(
                f"{self.material.label}材料图标未处于预期位置，"
                f"期望 y={expected_y}，识别 y={center[1]}"
            )
        self.click_point(*center, offset=0)
        self.wait(self.MAP_WAIT_MS)

    def choose_resource_marker(
        self,
        visited_markers: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        """从已筛选目标地图中选择一个未访问的资源标志。"""
        image = self.screenshot()
        if not self.is_map_visible(image):
            raise RuntimeError("选择资源标志时地图不可见")
        candidates = self.find_resource_map_marker_centers(image)
        anchors = self.MAP_RESOURCE_ANCHORS[self.material.map_key]

        changed_marker = self.choose_changed_resource_marker(
            image,
            candidates,
            anchors,
            visited_markers,
        )
        if changed_marker is not None:
            return changed_marker
        if self._map_filter_baseline is not None:
            # 已有清空前基线却找不到新增图标时，不能退回固定地点圆形图标。
            return None

        ranked: list[tuple[float, tuple[int, int]]] = []
        for center in candidates:
            key = self._marker_key(center)
            if key in visited_markers:
                continue
            distance = min(
                float(np.hypot(center[0] - anchor[0], center[1] - anchor[1]))
                for anchor in anchors
            )
            ranked.append((distance, center))
        if ranked:
            distance, center = min(ranked, key=lambda item: item[0])
            if distance <= 100:
                self._log(f"识别到{self.material.label}资源标志：{center}")
                return center

        # 采毛图标为深色剪刀，圆形检测不稳定；已知不闻春资源区使用锚点兜底。
        if self.material.map_key == "buwenchun":
            for anchor in anchors:
                if self._marker_key(anchor) not in visited_markers:
                    self._log(f"使用不闻春采毛资源标志锚点：{anchor}")
                    return anchor
        return None

    def choose_changed_resource_marker(
        self,
        image: np.ndarray,
        candidates: list[tuple[int, int]],
        anchors: tuple[tuple[int, int], ...],
        visited_markers: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        """从应用唯一筛选后新增的地图图标中选择未访问资源点。"""
        baseline = self._map_filter_baseline
        if baseline is None or baseline.shape != image.shape:
            return None

        # 采毛剪刀图标未必能被圆检测到，已知资源区锚点同样纳入差分候选。
        candidates = self.merge_nearby(
            [*candidates, *anchors],
            radius=24,
        )
        ranked: list[tuple[int, float, tuple[int, int]]] = []
        for center in candidates:
            key = self._marker_key(center)
            if key in visited_markers:
                continue
            changed_pixels = self.map_marker_change_pixels(baseline, image, center)
            if changed_pixels < self.MAP_RESOURCE_CHANGE_MIN_PIXELS:
                continue
            distance = min(
                float(np.hypot(center[0] - anchor[0], center[1] - anchor[1]))
                for anchor in anchors
            )
            ranked.append((changed_pixels, distance, center))
        if not ranked:
            return None

        changed_pixels, _distance, center = max(
            ranked,
            key=lambda item: (item[0], -item[1]),
        )
        self._log(
            f"识别到{self.material.label}新增资源标志：{center}，"
            f"地图差分={changed_pixels} 像素"
        )
        return center

    def map_marker_change_pixels(
        self,
        baseline: np.ndarray,
        image: np.ndarray,
        center: tuple[int, int],
    ) -> int:
        """计算候选标志附近相较“全部清除”地图的显著变化像素数。"""
        radius = self.MAP_RESOURCE_CHANGE_RADIUS
        x1 = max(0, center[0] - radius)
        y1 = max(0, center[1] - radius)
        x2 = min(image.shape[1], center[0] + radius)
        y2 = min(image.shape[0], center[1] + radius)
        before = baseline[y1:y2, x1:x2]
        after = image[y1:y2, x1:x2]
        if before.size == 0 or after.size == 0:
            return 0
        diff = cv2.absdiff(before, after)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        return int(np.count_nonzero(gray >= 35))

    def close_map_after_marker_click(self) -> None:
        """资源标志触发寻路后关闭小地图。"""
        if self.is_map_visible(self.screenshot()):
            self.click_point(*self.POINT_MAP_CLOSE, offset=0)
            self.wait(500)

    def wait_resource_auto_path_started(self, *, timeout_ms: int) -> bool:
        """确认新资源标志确实触发自动寻路，再允许检测采集图标。

        角色身边可能仍显示上一个资源的交互按钮；若先监听采集图标会把旧
        按钮当成新标志的终点。这里刻意不提供“直接抵达”捷径。
        """
        deadline = self._make_deadline(timeout_ms)
        while not self._is_deadline_expired(deadline):
            screenshot = self.screenshot()
            auto_path = self._vision.match_template(
                screenshot,
                self.TEXT_AUTO_PATH,
                threshold=0.8,
            )
            if auto_path.found:
                self._log("检测到生活资源自动寻路开始")
                return True
            self.wait(500)
        return False

    def gather_arrived_resource(self) -> bool:
        """自动寻路结束后等待对应工具图标，点击并等待其消失。"""
        deadline = self._make_deadline(self.GATHER_ACTION_WAIT_MS)
        center: tuple[int, int] | None = None
        while not self._is_deadline_expired(deadline):
            center = self.find_configured_gather_action(self.screenshot())
            if center is not None:
                break
            self.wait(500)
        else:
            return False

        self.click_point(*center, offset=0)
        self.wait(900)
        after_click = self.screenshot()
        if not self.is_main_scene(after_click):
            if self.is_scene_transition_loading(after_click):
                self._log("点击采集后检测到跨图加载，等待主场景恢复")
                if not self.wait_for_main_scene_after_loading():
                    raise RuntimeError("跨图加载后主场景未在时限内恢复")
                self._log("跨图完成，当前资源点状态未知，重新定位资源")
                return False
            self.close_all_panels(timeout_ms=3000)
            raise LifeTaskUnavailable(
                "点击采集后打开了工具获取面板，可能缺少或未装备"
                "当前等级的生活工具；已关闭面板且不会自动购买"
            )

        completion = self.wait_gather_action_complete()
        if completion == "completed":
            return True
        if completion == "transitioned":
            return False
        raise LifeTaskUnavailable("采集标志长时间未消失，可能体力不足或工具已耗尽")

    def wait_gather_action_complete(
        self,
    ) -> Literal["completed", "transitioned", "timed_out"]:
        """连续两帧未发现采集按钮时视为该次采集完成。"""
        deadline = self._make_deadline(self.GATHER_COMPLETE_TIMEOUT_MS)
        consecutive_missing = 0
        while not self._is_deadline_expired(deadline):
            self.wait(700)
            screenshot = self.screenshot()
            if not self.is_main_scene(screenshot):
                if self.is_scene_transition_loading(screenshot):
                    self._log("采集过程中检测到跨图加载，等待主场景恢复")
                    if not self.wait_for_main_scene_after_loading():
                        raise RuntimeError("跨图加载后主场景未在时限内恢复")
                    self._log("跨图完成，当前资源点状态未知，重新定位资源")
                    return "transitioned"
                self.close_all_panels(timeout_ms=3000)
                raise LifeTaskUnavailable(
                    "采集过程中打开了工具获取面板，可能缺少或未装备"
                    "当前等级的生活工具；已关闭面板且不会自动购买"
                )
            if self.find_configured_gather_action(screenshot) is None:
                consecutive_missing += 1
                if consecutive_missing >= 2:
                    return "completed"
            else:
                consecutive_missing = 0
        return "timed_out"

    def configured_gather_templates(self) -> tuple[str, ...]:
        """返回当前技能可接受的全部等级工具模板，并忽略缺失文件。"""
        return tuple(
            template
            for template in self.GATHER_TOOL_TEMPLATES[self.task_type]
            if Path(template).is_file()
        )

    def find_configured_gather_action(
        self,
        image: np.ndarray,
    ) -> tuple[int, int] | None:
        """仅在当前产物对应的交互行中识别该技能的采集工具。"""
        slot = self.material.gather_slot
        point = self.POINT_GATHER_ACTIONS[slot]
        if self.is_map_visible(image) or not self.is_main_scene(image):
            return None

        templates = self.configured_gather_templates()
        if templates:
            label_visible = self.is_gather_action_label_visible(image, slot)
            match = self._vision.match_template(
                image,
                list(templates),
                threshold=self.GATHER_TEMPLATE_THRESHOLD,
                roi=self.ROI_GATHER_TEMPLATE_SEARCH[slot],
            )
            if match.found and label_visible:
                return point

        # 采草/采毛的工具素材仍可能因装备状态变化；保留严格限定在对应行的
        # 结构判定作为兜底，但挖矿/伐木的高阶图标优先由模板覆盖。
        if self.find_scene_gather_actions(image, action_slot=slot):
            return point
        return None

    @classmethod
    def is_gather_action_label_visible(cls, image: np.ndarray, action_slot: int) -> bool:
        """要求工具图标右侧同时存在亮色操作文字，排除场景纹理误匹配。"""
        text_roi, _diamond_roi = cls.ROI_GATHER_ACTIONS[action_slot]
        text = cls.crop(image, text_roi)
        if text.size == 0:
            return False
        text_gray = cv2.cvtColor(text, cv2.COLOR_BGR2GRAY)
        text_hsv = cv2.cvtColor(text, cv2.COLOR_BGR2HSV)
        text_white = int(
            np.count_nonzero((text_gray >= 145) & (text_hsv[:, :, 1] <= 110))
        )
        return text_white >= 180

    def wait_for_main_scene_after_loading(self) -> bool:
        """在已确认的跨图加载页后，等待角色血条重新出现。

        加载页的进度条可能会在完成前短暂消失，因此一旦确认进入加载，
        后续不再逐帧要求仍能识别该进度条；期间不会执行任何点击。
        """
        deadline = self._make_deadline(self.SCENE_TRANSITION_TIMEOUT_MS)
        while not self._is_deadline_expired(deadline):
            self.wait(500)
            if self.is_main_scene(self.screenshot()):
                return True
        return False

    @classmethod
    def is_map_visible(cls, image: np.ndarray) -> bool:
        """地图右上角始终存在大型圆形关闭按钮。"""
        return bool(cls.find_circles(image, cls.ROI_MAP_CLOSE, min_radius=24, max_radius=44))

    @staticmethod
    def is_life_filter_panel_visible(image: np.ndarray) -> bool:
        """根据左侧“任务(深色) / 生活(浅色)”组合识别筛选面板。

        塞北地图左上角是大面积雪地，单独以浅色区域识别生活页签会将
        雪地误判为已打开面板，继而误触地图坐标输入。必须同时确认其上方
        的“任务”标签仍是深色底，才认为左侧筛选面板实际存在。
        """
        life_tab = image[84:150, 4:128]
        task_tab = image[4:70, 4:128]
        if life_tab.size == 0 or task_tab.size == 0:
            return False
        life_gray = cv2.cvtColor(life_tab, cv2.COLOR_BGR2GRAY)
        task_gray = cv2.cvtColor(task_tab, cv2.COLOR_BGR2GRAY)
        return (
            float(np.mean(life_gray >= 145)) >= 0.45
            and float(np.mean(task_gray <= 100)) >= 0.65
        )

    @classmethod
    def find_life_material_icon_centers(cls, image: np.ndarray) -> list[tuple[int, int]]:
        """识别展开下拉中左侧的圆形材料图标。"""
        return sorted(
            cls.find_circles(
                image,
                cls.ROI_LIFE_ITEM_ICONS,
                min_radius=25,
                max_radius=40,
                min_distance=50,
                param2=24,
            ),
            key=lambda point: point[1],
        )

    @classmethod
    def find_resource_map_marker_centers(cls, image: np.ndarray) -> list[tuple[int, int]]:
        """识别筛选后世界地图中大号生活资源标志的圆形边缘。"""
        return cls.find_circles(
            image,
            cls.ROI_RESOURCE_MAP,
            min_radius=20,
            max_radius=42,
            min_distance=40,
            param2=26,
        )

    @classmethod
    def find_scene_gather_actions(
        cls,
        image: np.ndarray,
        *,
        action_slot: int = 0,
    ) -> list[tuple[int, int]]:
        """识别右侧固定交互位的绿色菱形和“采集”文字组合。"""
        if cls.is_map_visible(image) or not cls.is_main_scene(image):
            return []

        text_roi, diamond_roi = cls.ROI_GATHER_ACTIONS[action_slot]
        text = cls.crop(image, text_roi)
        diamond = cls.crop(image, diamond_roi)
        if text.size == 0 or diamond.size == 0:
            return []
        diamond_gray = cv2.cvtColor(diamond, cv2.COLOR_BGR2GRAY)
        diamond_hsv = cv2.cvtColor(diamond, cv2.COLOR_BGR2HSV)
        green_border = int(
            np.count_nonzero(
                (diamond_hsv[:, :, 0] >= 35)
                & (diamond_hsv[:, :, 0] <= 95)
                & (diamond_hsv[:, :, 1] >= 60)
                & (diamond_hsv[:, :, 2] >= 70)
            )
        )
        # 采草的菱形是绿色，挖矿等技能在真机上会切换为亮白高亮；
        # 动作文本也会从“采集”变为“挖矿/伐木/采毛”，因此不匹配具体文字。
        diamond_white = int(
            np.count_nonzero((diamond_gray >= 145) & (diamond_hsv[:, :, 1] <= 110))
        )
        if cls.is_gather_action_label_visible(image, action_slot) and (
            green_border >= 250 or diamond_white >= 300
        ):
            return [cls.POINT_GATHER_ACTIONS[action_slot]]
        return []

    @classmethod
    def is_main_scene(cls, image: np.ndarray) -> bool:
        """确认处于包含角色血条的主场景，避免把交易/菜单控件误当采集。"""
        x, y, width, height = cls.ROI_MAIN_HEALTH
        region = image[y : y + height, x : x + width]
        if region.size == 0:
            return False
        channels = region.astype(np.int16)
        blue = channels[:, :, 0]
        green = channels[:, :, 1]
        red = channels[:, :, 2]
        red_health = (
            (red >= cls.HEALTH_RED_MIN_VALUE)
            & (red >= green + cls.HEALTH_RED_MIN_DELTA)
            & (red >= blue + cls.HEALTH_RED_MIN_DELTA)
        )
        return int(np.count_nonzero(red_health)) >= 300

    @classmethod
    def is_scene_transition_loading(cls, image: np.ndarray) -> bool:
        """识别跨图时覆盖屏幕底部的大型中性进度条。

        真机加载页没有角色血条，底部进度条会连续多行呈现 150px 以上的
        灰白横线。与普通对话、背包等面板不同，该特征横跨屏幕中央并且
        只在主场景缺失时参与判断。
        """
        if cls.is_main_scene(image):
            return False
        progress = cls.crop(image, cls.ROI_SCENE_LOADING_PROGRESS)
        if progress.size == 0:
            return False
        hsv = cv2.cvtColor(progress, cv2.COLOR_BGR2HSV)
        neutral_bright = (hsv[:, :, 1] <= 100) & (hsv[:, :, 2] >= 100)
        wide_rows = 0
        for row in neutral_bright:
            padded = np.concatenate(([False], row, [False]))
            edges = np.flatnonzero(padded[1:] != padded[:-1])
            run_lengths = edges[1::2] - edges[::2]
            if np.any(run_lengths >= 150):
                wide_rows += 1
        return wide_rows >= 5

    @staticmethod
    def _marker_key(center: tuple[int, int]) -> tuple[int, int]:
        """Normalize Hough-circle jitter for the same map resource marker."""
        return center[0] // 64, center[1] // 64

    @staticmethod
    def crop(image: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
        x, y, width, height = roi
        return image[y : y + height, x : x + width]

    @classmethod
    def find_circles(
        cls,
        image: np.ndarray,
        roi: tuple[int, int, int, int],
        *,
        min_radius: int,
        max_radius: int,
        min_distance: int = 30,
        param2: int = 30,
    ) -> list[tuple[int, int]]:
        x, y, _width, _height = roi
        region = cls.crop(image, roi)
        if region.size == 0:
            return []
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 2)
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=min_distance,
            param1=100,
            param2=param2,
            minRadius=min_radius,
            maxRadius=max_radius,
        )
        if circles is None:
            return []
        return cls.merge_nearby(
            [(x + round(cx), y + round(cy)) for cx, cy, _r in circles[0]],
            radius=max(10, min_distance // 2),
        )

    @staticmethod
    def merge_nearby(
        centers: list[tuple[int, int]],
        *,
        radius: int,
    ) -> list[tuple[int, int]]:
        merged: list[tuple[int, int]] = []
        for center in centers:
            if any(
                abs(center[0] - existing[0]) <= radius
                and abs(center[1] - existing[1]) <= radius
                for existing in merged
            ):
                continue
            merged.append(center)
        return merged

    def on_finish(self, results: list) -> None:
        if self._known_unavailable_reason:
            detail = f"停止原因：{self._known_unavailable_reason}"
        else:
            detail = f"共采集 {self._successful_gathers} 次 {self.material.label}"
        self._log(f"生活任务完成，{detail}")
