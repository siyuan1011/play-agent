"""生活任务：自动采集并按配置遍历游戏分线。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from botCore import StepStopException, step

from ymjh_bot.ui.task_queue_state import (
    SHRW_LINE_SCOPE_LABELS,
    SHRW_MATERIAL_OPTIONS,
    SHRW_TASK_TYPE_LABELS,
    normalize_shrw_settings,
)
from ymjh_bot.ym_game_task import YmGameTask


@dataclass(frozen=True, slots=True)
class LifeMaterialSpec:
    key: str
    label: str
    task_type: str
    page_index: int
    slot_index: int


@dataclass(frozen=True, slots=True)
class LineEntry:
    scope: str
    index: int
    center: tuple[int, int]
    page_index: int = 0
    row_index: int = 0
    selected: bool = False

    @property
    def key(self) -> str:
        return f"{self.scope}:{self.index}"

    @property
    def label(self) -> str:
        prefix = "互联 " if self.scope == "interconnected" else ""
        return f"{prefix}{self.index}线"


class LifeTaskUnavailable(RuntimeError):
    """遇到已知且应视为任务成功完成的情况时抛出。"""


def _material_specs() -> dict[str, LifeMaterialSpec]:
    specs: dict[str, LifeMaterialSpec] = {}
    for task_type, options in SHRW_MATERIAL_OPTIONS.items():
        for option_index, (key, label) in enumerate(options):
            if option_index < 2:
                page_index, slot_index = 0, option_index
            else:
                page_index, slot_index = option_index - 1, 0
            specs[key] = LifeMaterialSpec(key, label, task_type, page_index, slot_index)
    return specs


class SHRWTask(YmGameTask):
    """一梦江湖生活任务自动采集。"""

    task_key = "SHRW"
    task_name = "生活任务"
    task_description = "自动执行挖矿、采草、伐木、采毛并按分线采集"
    auto_recover_health = False

    MATERIAL_SPECS = _material_specs()

    # 所有固定坐标均基于实机截图 1280x720。
    POINT_QUICK_MENU = (1225, 190)
    POINT_LIFE_SKILL_MENU = (1068, 518)
    POINT_LIFE_CATEGORIES = {
        "wool": (250, 288),
        "herb": (250, 370),
        "logging": (250, 451),
        "mining": (250, 532),
    }
    POINT_PAGE_PREVIOUS = (476, 386)
    POINT_PAGE_NEXT = (1130, 386)
    POINT_MATERIAL_LOCATORS = ((753, 258), (1076, 258))
    POINT_MAP_CLOSE = (1235, 42)
    POINT_MAP_WORLD_FALLBACK = (1235, 675)
    POINT_LINE_DROPDOWN = (1118, 74)
    POINT_LINE_SCOPE_SWITCH = (1058, 646)
    POINT_LINE_LIST_SWIPE_START = (975, 560)
    POINT_LINE_LIST_SWIPE_END = (975, 160)

    ROI_LIFE_TITLE = (35, 5, 245, 65)
    ROI_LIFE_SELECTED_CATEGORY = (110, 245, 305, 340)
    ROI_LIFE_MATERIAL_CARD = (480, 210, 650, 110)
    ROI_LIFE_STAMINA = (100, 80, 320, 80)
    ROI_WORLD_RESOURCE_REGIONS = (155, 85, 980, 450)
    ROI_LOCAL_RESOURCE_NODES = (375, 220, 470, 380)
    ROI_LINE_PANEL = (850, 20, 250, 670)
    ROI_LINE_ENTRIES = (860, 30, 230, 570)
    ROI_GATHER_ACTIONS = (
        (875, 245, 110, 115),  # circular interaction button
        (880, 425, 125, 90),   # diamond interaction button
    )

    LIFE_PANEL_WAIT_MS = 800
    MAP_WAIT_MS = 800
    AUTO_PATH_TIMEOUT_MS = 360_000
    GATHER_TIMEOUT_MS = 20_000
    GATHER_START_RECHECKS = 3
    MAX_GATHER_START_CLICKS = 2
    LINE_SWITCH_TIMEOUT_MS = 20_000
    EMPTY_ROUND_WAIT_MS = 20_000
    MAX_LINE_SCROLL_PAGES = 8
    MAX_NODES_PER_LINE = 40
    MAX_REGION_ATTEMPTS = 30
    MAX_PAGE_REWIND_ATTEMPTS = 6

    def __init__(self, shrw_settings: dict[str, Any] | None = None):
        super().__init__()
        self.shrw_settings = normalize_shrw_settings(shrw_settings)
        self.task_type = str(self.shrw_settings["task_type"])
        self.material_key = str(self.shrw_settings["material"])
        self.material = self.MATERIAL_SPECS[self.material_key]
        self.loop_lines = bool(self.shrw_settings["loop_lines"])
        self.line_scope = str(self.shrw_settings["line_scope"])
        self._successful_gathers = 0
        self._round_index = 0
        self._known_unavailable_reason: str | None = None

    @step(retry=0, timeout_ms=None)
    def collect_life_material(self) -> None:
        """执行一轮线路循环，并可选择无限重复。"""
        while True:
            self._round_index += 1
            round_gathers = self.run_collection_round()
            self._log(
                f"第 {self._round_index} 轮完成：采集 {round_gathers} 个资源点，"
                f"累计 {self._successful_gathers} 个"
            )
            if not self.loop_lines:
                return
            if round_gathers == 0:
                self._log("完整一轮未采集到资源，等待 20 秒后重新枚举线路")
                self.wait(self.EMPTY_ROUND_WAIT_MS)

    def run_collection_round(self) -> int:
        """枚举已配置范围，并逐一访问每条线路。"""
        try:
            entries = self.enumerate_lines(self.line_scope)
            if not entries:
                raise RuntimeError(
                    f"{SHRW_LINE_SCOPE_LABELS[self.line_scope]}未枚举到任何线路"
                )

            round_gathers = 0
            visited: set[str] = set()
            for entry in entries:
                if entry.key in visited:
                    continue
                visited.add(entry.key)
                self.switch_to_line(entry)
                line_gathers = self.collect_current_line()
                round_gathers += line_gathers
                self._successful_gathers += line_gathers
            return round_gathers
        except LifeTaskUnavailable as exc:
            self._known_unavailable_reason = str(exc)
            self._log(f"生活任务跳过并成功结束：{exc}")
            self.jump_to_end()
            return 0
        except StepStopException:
            raise
        except Exception as exc:
            debug_path = self.save_debug_screenshot("shrw_flow_failed")
            raise RuntimeError(f"生活任务流程失败：{exc}，已保存截图：{debug_path}") from exc

    def collect_current_line(self) -> int:
        """持续选择未访问的地图节点，直到当前线路没有候选项。"""
        visited_nodes: set[tuple[int, int, int]] = set()
        gathers = 0
        for _attempt in range(self.MAX_NODES_PER_LINE):
            route = self.open_material_map_and_choose_node(visited_nodes)
            if route is None:
                return gathers
            visited_nodes.add(route)

            self.close_map_if_visible()
            transition = self.wait_resource_route_started(timeout_ms=15_000)
            if transition == "auto_path":
                if not self.wait_auto_pathfinding(
                    timeout_ms=self.AUTO_PATH_TIMEOUT_MS,
                    missing_threshold=3,
                ):
                    raise RuntimeError("前往生活资源点的自动寻路超时")
            elif transition != "arrived":
                raise RuntimeError("点击生活资源点后未开始自动寻路，也未到达资源旁")
            self.wake_from_power_saving_if_needed()
            if not self.gather_arrived_resource():
                self._log("到达后未发现可采集交互，跳过当前地图点")
                continue
            gathers += 1
        raise RuntimeError(f"单条线路连续采集超过 {self.MAX_NODES_PER_LINE} 个资源点")

    def open_material_map_and_choose_node(
        self,
        visited_nodes: set[tuple[int, int, int, int]],
    ) -> tuple[int, int, int] | None:
        """打开筛选后的资源地图，并选择一个未访问节点。"""
        self.open_life_skill_material()
        self.click_point(*self.POINT_MATERIAL_LOCATORS[self.material.slot_index], offset=0)
        self.wait(self.MAP_WAIT_MS)

        if not self.is_filtered_map_visible(self.screenshot()):
            raise LifeTaskUnavailable(
                f"{self.material.label}未解锁、缺少工具或当前不可采集"
            )

        screenshot = self.screenshot()
        if self.is_local_resource_map(screenshot):
            node = self.choose_local_resource_node(visited_nodes)
            if node is not None:
                return node
            self.close_map_if_visible()
            return None

        regions = self.find_world_resource_regions(screenshot)
        if not regions:
            return None

        for region_index, center in enumerate(regions[: self.MAX_REGION_ATTEMPTS]):
            self.click_point(*center, offset=0)
            self.wait(self.MAP_WAIT_MS)
            node = self.choose_local_resource_node(visited_nodes, region_index=region_index)
            if node is not None:
                return node
            if not self.return_to_world_resource_map():
                break

        self.close_map_if_visible()
        return None

    def open_life_skill_material(self) -> None:
        """打开生活技能，选择已配置的分类和材料页。"""
        self.close_all_panels(timeout_ms=3000)
        self.click_point(*self.POINT_QUICK_MENU, offset=0)
        self.wait(500)
        self.click_point(*self.POINT_LIFE_SKILL_MENU, offset=0)
        self.wait(self.LIFE_PANEL_WAIT_MS)
        screenshot = self.screenshot()
        if not self.is_life_panel_visible(screenshot):
            raise RuntimeError("未进入生活技能面板")

        self.click_point(*self.POINT_LIFE_CATEGORIES[self.task_type], offset=0)
        self.wait(500)
        self.rewind_material_pages()
        for _ in range(self.material.page_index):
            self.click_point(*self.POINT_PAGE_NEXT, offset=0)
            self.wait(350)

        screenshot = self.screenshot()
        if not self.is_material_page_ready(screenshot):
            raise LifeTaskUnavailable(
                f"{SHRW_TASK_TYPE_LABELS[self.task_type]}-{self.material.label}未解锁或不可用"
            )

    def rewind_material_pages(self) -> None:
        """将材料轮播区返回至第一页。"""
        for _ in range(self.MAX_PAGE_REWIND_ATTEMPTS):
            before = self.screenshot()
            self.click_point(*self.POINT_PAGE_PREVIOUS, offset=0)
            self.wait(250)
            after = self.screenshot()
            if self.images_similar(before, after, self.ROI_LIFE_MATERIAL_CARD, threshold=0.985):
                return

    def choose_local_resource_node(
        self,
        visited_nodes: set[tuple[int, int, int]],
        *,
        region_index: int = 0,
    ) -> tuple[int, int, int] | None:
        screenshot = self.screenshot()
        nodes = self.find_local_resource_nodes(screenshot)
        for center in nodes:
            identity = (region_index, center[0] // 12, center[1] // 12)
            if identity in visited_nodes:
                continue
            self.click_point(*center, offset=0)
            self.wait(500)
            return identity
        return None

    def return_to_world_resource_map(self) -> bool:
        """从区域地图返回筛选后的世界地图。"""
        self.click_point(*self.POINT_MAP_WORLD_FALLBACK, offset=0)
        self.wait(self.MAP_WAIT_MS)
        return bool(self.find_world_resource_regions(self.screenshot()))

    def is_local_resource_map(self, image: np.ndarray) -> bool:
        return self._vision.match_template(
            image,
            self.MAP_BTN_WORLD,
            threshold=0.8,
        ).found

    def gather_arrived_resource(self) -> bool:
        """点击场景采集操作，并等待操作完成。"""
        deadline = self._make_deadline(10_000)
        center: tuple[int, int] | None = None
        while not self._is_deadline_expired(deadline):
            screenshot = self.screenshot()
            centers = self.find_scene_gather_actions(screenshot)
            if centers:
                center = centers[0]
                break
            self.wait(500)
        if center is None:
            return False

        before = self.screenshot()
        for click_attempt in range(1, self.MAX_GATHER_START_CLICKS + 1):
            self.click_point(*center, offset=0)
            consecutive_missing = 0
            for _ in range(self.GATHER_START_RECHECKS):
                self.wait(700)
                after = self.screenshot()
                actions = self.find_scene_gather_actions(after)
                if not actions:
                    consecutive_missing += 1
                    if consecutive_missing >= 2:
                        return True
                    continue
                consecutive_missing = 0
                center = actions[0]
                if self.is_gathering_in_progress(after):
                    return self.wait_gather_action_complete()

            if click_attempt < self.MAX_GATHER_START_CLICKS:
                self._log("采集按钮仍在，角色可能刚下马，重新识别后再次点击")

        if self.wait_gather_action_complete():
            return True

        if all(
            self.images_similar(before, after, roi, threshold=0.995)
            for roi in self.ROI_GATHER_ACTIONS
        ):
            raise LifeTaskUnavailable("采集未启动，可能体力耗尽或工具不可用")
        raise RuntimeError("生活资源采集动作超时")

    def wait_gather_action_complete(self) -> bool:
        """等待进行中的采集交互连续两次消失。"""
        deadline = self._make_deadline(self.GATHER_TIMEOUT_MS)
        consecutive_missing = 0
        while not self._is_deadline_expired(deadline):
            self.wait(700)
            after = self.screenshot()
            if not self.find_scene_gather_actions(after):
                consecutive_missing += 1
                if consecutive_missing >= 2:
                    return True
            else:
                consecutive_missing = 0
        return False

    @classmethod
    def is_gathering_in_progress(cls, image: np.ndarray) -> bool:
        """识别采集开始后显示的明亮菱形边框。"""
        x, y, _width, _height = cls.ROI_GATHER_ACTIONS[1]
        roi = image[y : y + 90, x : x + 85]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        bright_neutral = (gray >= 180) & (hsv[:, :, 1] <= 80)
        return int(np.count_nonzero(bright_neutral)) >= 900

    def wait_resource_route_started(self, *, timeout_ms: int) -> str | None:
        """等待长路径界面出现，或直接通过短路径抵达。"""
        deadline = self._make_deadline(timeout_ms)
        while not self._is_deadline_expired(deadline):
            screenshot = self.screenshot()
            if self.find_scene_gather_actions(screenshot):
                self._log("短距离寻路已直接到达生活资源旁")
                return "arrived"
            auto_path = self._vision.match_template(
                screenshot,
                self.TEXT_AUTO_PATH,
                threshold=0.8,
            )
            if auto_path.found:
                self._log("检测到生活资源自动寻路开始")
                return "auto_path"
            self.wait(500)
        return None

    def enumerate_lines(self, scope: str) -> list[LineEntry]:
        """枚举一个服务器范围内可见及可滚动的线路。"""
        self.close_all_panels(timeout_ms=3000)
        self.click_point(*self.POINT_LINE_DROPDOWN, offset=0)
        self.wait(500)
        screenshot = self.screenshot()
        if not self.is_line_panel_visible(screenshot):
            raise RuntimeError("未打开线路面板")

        current_scope = self.detect_line_panel_scope(screenshot)
        if current_scope != scope:
            self.click_point(*self.POINT_LINE_SCOPE_SWITCH, offset=0)
            self.wait(500)
            screenshot = self.screenshot()
            if self.detect_line_panel_scope(screenshot) != scope:
                raise RuntimeError(f"无法切换到{SHRW_LINE_SCOPE_LABELS[scope]}")
        self.rewind_line_list()

        entries: list[LineEntry] = []
        fingerprints: set[bytes] = set()
        stagnant_pages = 0
        previous_signature: tuple[tuple[int, int], ...] | None = None
        for page_index in range(self.MAX_LINE_SCROLL_PAGES):
            screenshot = self.screenshot()
            centers = self.find_line_entry_centers(screenshot)
            signature = tuple((x, y) for x, y in centers)
            for row_index, center in enumerate(centers):
                fingerprint = self.line_row_fingerprint(screenshot, center)
                if fingerprint in fingerprints:
                    continue
                fingerprints.add(fingerprint)
                inferred_index = len(entries) + 1
                entries.append(
                    LineEntry(
                        scope=scope,
                        index=inferred_index,
                        center=center,
                        page_index=page_index,
                        row_index=row_index,
                        selected=self.is_line_row_selected(screenshot, center),
                    )
                )

            if signature == previous_signature:
                stagnant_pages += 1
            else:
                stagnant_pages = 0
            if stagnant_pages >= 1 or not centers:
                break
            previous_signature = signature
            self.swipe(
                *self.POINT_LINE_LIST_SWIPE_START,
                *self.POINT_LINE_LIST_SWIPE_END,
                duration_ms=400,
            )
            self.wait(500)

        self.click_point(820, 400, offset=0)
        return entries

    def switch_to_line(self, entry: LineEntry) -> None:
        """切换到一条已枚举线路，并验证场景切换已稳定。"""
        self.close_all_panels(timeout_ms=3000)
        self.click_point(*self.POINT_LINE_DROPDOWN, offset=0)
        self.wait(400)
        screenshot = self.screenshot()
        if self.detect_line_panel_scope(screenshot) != entry.scope:
            self.click_point(*self.POINT_LINE_SCOPE_SWITCH, offset=0)
            self.wait(400)
        self.rewind_line_list()

        # 从顶部重新打开，再滚动到包含该条目的页面。
        entries = self.find_line_entry_centers(self.screenshot())
        page_index = entry.page_index
        row_index = entry.row_index
        for _ in range(page_index):
            self.swipe(
                *self.POINT_LINE_LIST_SWIPE_START,
                *self.POINT_LINE_LIST_SWIPE_END,
                duration_ms=400,
            )
            self.wait(350)
        centers = self.find_line_entry_centers(self.screenshot())
        if row_index >= len(centers):
            raise RuntimeError(f"无法定位线路 {entry.label}")
        self.click_point(*centers[row_index], offset=0)

        deadline = self._make_deadline(self.LINE_SWITCH_TIMEOUT_MS)
        while not self._is_deadline_expired(deadline):
            self.wait(700)
            self.wake_from_power_saving_if_needed()
            if self.is_game_main_ready() and not self.is_line_panel_visible(self.screenshot()):
                if self.verify_line_selected(entry):
                    self._log(f"已切换线路：{entry.label}")
                    return
                raise RuntimeError(f"切换线路 {entry.label} 后选中状态校验失败")
        raise RuntimeError(f"切换线路 {entry.label} 后主界面未恢复")

    def verify_line_selected(self, entry: LineEntry) -> bool:
        """重新打开线路面板，并验证目标行已高亮。"""
        self.click_point(*self.POINT_LINE_DROPDOWN, offset=0)
        self.wait(400)
        screenshot = self.screenshot()
        if not self.is_line_panel_visible(screenshot):
            return False
        if self.detect_line_panel_scope(screenshot) != entry.scope:
            self.click_point(*self.POINT_LINE_SCOPE_SWITCH, offset=0)
            self.wait(400)
        self.rewind_line_list()
        for _ in range(entry.page_index):
            self.swipe(
                *self.POINT_LINE_LIST_SWIPE_START,
                *self.POINT_LINE_LIST_SWIPE_END,
                duration_ms=400,
            )
            self.wait(350)
        screenshot = self.screenshot()
        centers = self.find_line_entry_centers(screenshot)
        row_index = entry.row_index
        verified = row_index < len(centers) and self.is_line_row_selected(
            screenshot,
            centers[row_index],
        )
        self.click_point(820, 400, offset=0)
        return verified

    def rewind_line_list(self) -> None:
        """按索引访问前，将线路列表滚回第一页。"""
        for _ in range(self.MAX_LINE_SCROLL_PAGES):
            before = self.screenshot()
            self.swipe(
                *self.POINT_LINE_LIST_SWIPE_END,
                *self.POINT_LINE_LIST_SWIPE_START,
                duration_ms=400,
            )
            self.wait(300)
            after = self.screenshot()
            if self.images_similar(before, after, self.ROI_LINE_ENTRIES, threshold=0.985):
                return

    def close_map_if_visible(self) -> None:
        screenshot = self.screenshot()
        if self.is_filtered_map_visible(screenshot):
            self.click_point(*self.POINT_MAP_CLOSE, offset=0)
            self.wait(400)
        screenshot = self.screenshot()
        if self.is_life_panel_visible(screenshot):
            self.click_point(*self.POINT_MAP_CLOSE, offset=0)
            self.wait(400)

    @classmethod
    def is_life_panel_visible(cls, image: np.ndarray) -> bool:
        # 左侧分类选择器是生活面板中的大型半透明浅色卡片，
        # 在各分类和材料页之间保持稳定。
        gray = cv2.cvtColor(image[165:250, 100:415], cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray >= 150)) >= 0.80

    def is_material_page_ready(self, image: np.ndarray) -> bool:
        roi = self.crop(image, self.ROI_LIFE_MATERIAL_CARD)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # 材料卡片包含明亮的物品图像和定位手势。
        bright_components = self.component_centers(gray >= 170, min_area=50, max_area=6000)
        locator_x = self.POINT_MATERIAL_LOCATORS[self.material.slot_index][0]
        return any(abs((self.ROI_LIFE_MATERIAL_CARD[0] + x) - locator_x) < 65 for x, _y in bright_components)

    @classmethod
    def is_filtered_map_visible(cls, image: np.ndarray) -> bool:
        # 两个筛选地图层级的右上角都有大型圆形关闭按钮。
        circles = cls.find_circles(image, (1185, 0, 95, 90), min_radius=24, max_radius=44)
        return bool(circles)

    @classmethod
    def find_world_resource_regions(cls, image: np.ndarray) -> list[tuple[int, int]]:
        circles = cls.find_circles(
            image,
            cls.ROI_WORLD_RESOURCE_REGIONS,
            min_radius=13,
            max_radius=27,
            min_distance=28,
            param2=24,
        )
        return sorted(circles, key=lambda point: (point[1], point[0]))

    @classmethod
    def find_local_resource_nodes(cls, image: np.ndarray) -> list[tuple[int, int]]:
        circles = cls.find_circles(
            image,
            cls.ROI_LOCAL_RESOURCE_NODES,
            min_radius=25,
            max_radius=42,
            min_distance=40,
            param2=25,
        )
        resource_nodes: list[tuple[int, int]] = []
        for x, y in circles:
            crop = image[max(0, y - 32) : y + 33, max(0, x - 32) : x + 33]
            if crop.size == 0:
                continue
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            white_ratio = float(np.mean((gray >= 160) & (hsv[:, :, 1] <= 80)))
            if white_ratio >= 0.18:
                resource_nodes.append((x, y))
        return sorted(resource_nodes, key=lambda point: (-point[1], point[0]))

    @classmethod
    def is_line_panel_visible(cls, image: np.ndarray) -> bool:
        roi = cls.crop(image, cls.ROI_LINE_PANEL)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        dark_ratio = float(np.mean(gray < 50))
        edge_density = float(np.mean(cv2.Canny(gray, 60, 140) > 0))
        border = cv2.Canny(gray, 60, 140)
        vertical_lines = cv2.HoughLinesP(
            border,
            1,
            np.pi / 180,
            threshold=80,
            minLineLength=300,
            maxLineGap=12,
        )
        has_panel_border = vertical_lines is not None and any(
            abs(int(line[0][0]) - int(line[0][2])) <= 4
            for line in vertical_lines
        )
        return dark_ratio >= 0.35 and edge_density >= 0.02 and has_panel_border

    @classmethod
    def detect_line_panel_scope(cls, image: np.ndarray) -> str:
        if not cls.is_line_panel_visible(image):
            raise RuntimeError("线路面板不可见")
        centers = cls.find_line_entry_centers(image)
        if not centers:
            raise RuntimeError("线路面板没有可选线路")
        # 行中心处本地标签从约 x=935 开始，而互通前缀会向左延伸到 x=930，
        # 且在 x=970 前包含更多浅色文本。
        first_y = centers[0][1]
        row = image[max(0, first_y - 22) : first_y + 22, 920:980]
        hsv = cv2.cvtColor(row, cv2.COLOR_BGR2HSV)
        light_text = (hsv[:, :, 2] >= 105) & (hsv[:, :, 1] <= 115)
        return "interconnected" if int(np.count_nonzero(light_text)) < 400 else "local"

    @classmethod
    def find_line_entry_centers(cls, image: np.ndarray) -> list[tuple[int, int]]:
        x, y, w, h = cls.ROI_LINE_ENTRIES
        roi = image[y : y + h, x : x + w]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        # 每条线路左侧的绿/黄状态圆点比文字 OCR 更稳定。
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        mask = ((saturation >= 70) & (value >= 80)).astype(np.uint8) * 255
        centers = cls.component_centers(mask > 0, min_area=90, max_area=900)
        centers = [(x + cx, y + cy) for cx, cy in centers if cx < 80]
        return sorted(cls.merge_nearby(centers, radius=24), key=lambda point: point[1])

    @staticmethod
    def is_line_row_selected(image: np.ndarray, center: tuple[int, int]) -> bool:
        """返回线路行是否具有明亮的选中背景。"""
        _x, y = center
        row = image[max(0, y - 30) : y + 31, 860:1090]
        gray = cv2.cvtColor(row, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray >= 70)) >= 0.60

    @staticmethod
    def line_row_fingerprint(image: np.ndarray, center: tuple[int, int]) -> bytes:
        """根据一条线路的文字和圆点构建与位置无关的指纹。"""
        _x, y = center
        row = image[max(0, y - 25) : y + 26, 875:1070]
        hsv = cv2.cvtColor(row, cv2.COLOR_BGR2HSV)
        foreground = (
            ((hsv[:, :, 2] >= 95) & (hsv[:, :, 1] <= 130))
            | ((hsv[:, :, 1] >= 70) & (hsv[:, :, 2] >= 80))
        ).astype(np.uint8)
        compact = cv2.resize(foreground, (48, 16), interpolation=cv2.INTER_AREA)
        return (compact >= 96).astype(np.uint8).tobytes()

    @classmethod
    def find_scene_gather_actions(cls, image: np.ndarray) -> list[tuple[int, int]]:
        if cls.is_filtered_map_visible(image):
            return []
        diamond_roi = cls.ROI_GATHER_ACTIONS[1]
        x, y, width, height = diamond_roi
        roi = image[y : y + height, x : x + width]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        white = (gray >= 145) & (hsv[:, :, 1] <= 100)
        centers = cls.component_centers(white, min_area=350, max_area=1000)
        if centers:
            # 白色部分是手势字形；实际菱形交互控件延伸至其右侧的操作标签。
            return [(x + centers[0][0] + 68, y + centers[0][1])]
        return []

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
            [(x + int(round(cx)), y + int(round(cy))) for cx, cy, _r in circles[0]],
            radius=max(10, min_distance // 2),
        )

    @staticmethod
    def component_centers(
        mask: np.ndarray,
        *,
        min_area: int,
        max_area: int,
    ) -> list[tuple[int, int]]:
        count, _labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8),
            connectivity=8,
        )
        centers: list[tuple[int, int]] = []
        for index in range(1, count):
            area = int(stats[index, cv2.CC_STAT_AREA])
            if min_area <= area <= max_area:
                centers.append(
                    (int(round(centroids[index][0])), int(round(centroids[index][1])))
                )
        return centers

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

    @classmethod
    def images_similar(
        cls,
        before: np.ndarray,
        after: np.ndarray,
        roi: tuple[int, int, int, int],
        *,
        threshold: float,
    ) -> bool:
        first = cv2.cvtColor(cls.crop(before, roi), cv2.COLOR_BGR2GRAY)
        second = cv2.cvtColor(cls.crop(after, roi), cv2.COLOR_BGR2GRAY)
        if first.shape != second.shape or first.size == 0:
            return False
        difference = cv2.absdiff(first, second)
        similarity = 1.0 - float(np.mean(difference)) / 255.0
        return similarity >= threshold

    def on_finish(self, results: list) -> None:
        """记录最终采集统计信息。"""
        if self._known_unavailable_reason:
            detail = f"跳过：{self._known_unavailable_reason}"
        else:
            detail = f"共采集 {self._successful_gathers} 个资源点"
        self._log(f"生活任务完成，{detail}")
