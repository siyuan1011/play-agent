"""生活任务：按材料内置地图、世界坐标与统一采集循环执行。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

import cv2
import numpy as np

from botCore import StepStopException, step
from botCore.vision import load_image
from ymjh_bot.ui.task_queue_state import (
    SHRW_MATERIAL_OPTIONS,
    SHRW_STRATEGY_CONTINUOUS,
    SHRW_STRATEGY_FIXED_COUNT,
    normalize_shrw_settings,
)
from ymjh_bot.ym_game_task import TEMPLATES_DIR, YmGameTask


@dataclass(frozen=True, slots=True)
class LifeMaterialSpec:
    """生活材料的目标地图与采集交互位置。"""

    key: str  # 材料的持久化标识。
    label: str  # 材料在界面和日志中的中文名称。
    map_key: str  # 材料所在的目标地图标识。
    gather_slot: int  # 场景右侧采集交互行的零起始序号。


class LifeTaskUnavailable(RuntimeError):
    """体力或采集工具不足时用于正常结束生活任务循环。"""


TARGET_MAP_LABELS = {
    "zhongyuan": "中原",
    "jiangnan": "江南",
    "saibei": "塞北",
    "buwenchun": "不闻春",
}

# 各地图的切换落点，使用游戏世界坐标 (X, Y)，不作为采集点。
TARGET_MAP_ARRIVAL_COORDINATES: dict[str, tuple[int, int]] = {
    "zhongyuan": (1156, 1698),
    "jiangnan": (1030, 1148),
    "saibei": (1278, 762),
    "buwenchun": (2274, 140),
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


def _gather_slot_for_material(material_key: str) -> int:
    """采毛同一动物会展示两种产物，绒类使用第二个交互按钮。"""
    return 1 if material_key in {"cashmere", "reindeer_down"} else 0


def _material_specs() -> dict[str, LifeMaterialSpec]:
    """从 GUI 的材料选项生成运行时材料数据。"""
    # specs：以材料标识为键的运行时材料配置。
    specs: dict[str, LifeMaterialSpec] = {}
    # task_type：生活技能标识；options：该技能可选材料的有序列表。
    for task_type, options in SHRW_MATERIAL_OPTIONS.items():
        # key：材料标识；label：对应的中文显示名称。
        for key, label in options:
            specs[key] = LifeMaterialSpec(
                key=key,
                label=label,
                map_key=_target_map_for_material(task_type, key),
                gather_slot=_gather_slot_for_material(key),
            )
    return specs


# 各材料的采集点世界坐标，(0, 0) 表示尚未配置并禁止执行。
LIFE_COORDINATES: dict[str, tuple[tuple[int, int], ...]] = {
    "stone": ((1498, 1853), (1490, 1844), (1488, 1838)),
    "brass_ore": ((1586, 1778), (1576, 1772)),
    "silver_ore": ((1212, 1582), (1200, 1585)),
    "gold_ore": ((1121, 1626), (1141, 1618)),
    "emerald_ore": ((850, 1488), (906, 1524), (964, 1494)),
    "tungsten_ore": ((846, 1696), (855, 1700)),
    **{
        key: ((0, 0),)
        for skill, options in SHRW_MATERIAL_OPTIONS.items()
        if skill != "mining"
        for key, _label in options
    },
}


class LifeConfigurationError(ValueError):
    """不允许通过游戏操作恢复的配置错误。"""


class LifeSignal(Enum):
    IDLE = "idle"
    GATHERING = "gathering"
    NO_TOOL = "no_tool"
    NO_STAMINA = "no_stamina"
    LOADING = "loading"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LifeObservation:
    signal: LifeSignal  # 当前采集界面的状态分类。
    action: tuple[int, int] | None = None  # 可点击采集位置；无入口时为 None。


@dataclass(frozen=True)
class LifeLine:
    number: int  # 互联线路编号，从一开始。
    point: tuple[int, int]  # 分线列表中的屏幕点击坐标。
    current: bool  # 当前角色是否已处于该线路。
    available: bool  # 当前是否可切入该线路。
    page: int = 0  # 分线列表页码，从零开始。


class LifeFlow:
    ACTION_WAIT_MS = 3_000  # 单个采集点等待交互入口的最长毫秒数。
    POLL_MS = 300  # 采集状态轮询间隔，单位毫秒。
    LINE_RECHECK_MS = 30_000  # 无可用线路时的重查间隔，单位毫秒。
    LINE_CHECK_ATTEMPTS = 3  # 无可用线路时的最多检查次数。

    def __init__(self, task: SHRWTask, ui):
        """task 为当前生活任务，ui 为对应界面观察与导航器。"""
        self.task = task  # 当前生活任务实例。
        self.ui = ui  # 生活采集界面操作器。
        self.round_number = 0  # 已开始的坐标巡查轮次。
        self.line_number = 0  # 当前互联线编号；零表示尚未选择。

    def check_stop(self) -> None:
        if self.task.is_stopped():
            raise StepStopException("Stop requested")

    def observe(self) -> LifeObservation:
        self.check_stop()
        observation = self.ui.observe()
        if observation.signal in (LifeSignal.NO_TOOL, LifeSignal.NO_STAMINA):
            reason = "没有可用的采集工具" if observation.signal == LifeSignal.NO_TOOL else "体力耗尽"
            raise LifeTaskUnavailable(reason)
        return observation

    def require_stable_scene(self, observation: LifeObservation) -> None:
        if observation.signal == LifeSignal.LOADING:
            if not self.task.wait_for_main_scene_after_loading():
                raise RuntimeError("生活采集场景加载超时")
            raise RuntimeError("采集期间出现非预期场景切换，未将本次操作计为成功或无资源")
        if observation.signal == LifeSignal.UNKNOWN:
            raise RuntimeError("生活采集界面状态未知，未识别到工具或体力耗尽标志")

    def wait_action(self) -> tuple[int, int] | None:
        deadline = self.task._make_deadline(self.ACTION_WAIT_MS)
        while True:
            observation = self.observe()
            self.require_stable_scene(observation)
            if observation.action is not None:
                return observation.action
            if observation.signal != LifeSignal.IDLE:
                raise RuntimeError("到点后仍有未完成的采集动作")
            if self.task._is_deadline_expired(deadline):
                return None
            self.task.wait(min(self.POLL_MS, self.task._remaining_ms(deadline)))

    def gather_once(self, action: tuple[int, int]) -> None:
        self.check_stop()
        self.task.click_point(*action, offset=0)
        self.ui.reset_acceleration()
        progress_seen = False
        unknown_deadline = None
        non_scene_seen = False

        def on_poll(_found: bool, _missing: int) -> None:
            nonlocal progress_seen, unknown_deadline, non_scene_seen
            observation = self.observe()
            if observation.signal in (LifeSignal.UNKNOWN, LifeSignal.LOADING):
                non_scene_seen = True
                if unknown_deadline is None:
                    unknown_deadline = self.task._make_deadline(3_000)
                elif self.task._is_deadline_expired(unknown_deadline):
                    raise RuntimeError("采集后出现未确认的过渡画面或面板")
                return
            unknown_deadline = None
            self.require_stable_scene(observation)
            progress_seen |= observation.signal == LifeSignal.GATHERING
            progress_seen |= self.ui.click_acceleration_if_visible()

        marker_missing = self.task.wait_image_missing(
            str(LIFE_ASSET_DIR / f"{self.ui.action_label_asset}.png"),
            timeout_ms=self.task.GATHER_COMPLETE_TIMEOUT_MS,
            threshold=0.82,
            missing_threshold=3,
            interval_ms=self.POLL_MS,
            roi=self.ui.action_label_roi,
            callback=on_poll,
        )
        if unknown_deadline is not None:
            while True:
                observation = self.observe()
                if observation.signal not in (LifeSignal.UNKNOWN, LifeSignal.LOADING):
                    self.require_stable_scene(observation)
                    break
                if self.task._is_deadline_expired(unknown_deadline):
                    raise RuntimeError("采集后出现未确认的过渡画面或面板")
                self.task.wait(self.POLL_MS)
        if non_scene_seen:
            raise RuntimeError("采集期间曾出现过渡画面或普通面板，不能计为成功")
        if not marker_missing:
            raise RuntimeError("采集标志未消失：未确认采集完成，不能推断工具或体力耗尽")
        if not progress_seen:
            raise RuntimeError("采集标志消失但未观察到采集过程，不能计为成功")

    def switch_line(self) -> None:
        scope = "interconnected"
        target_number = 1 if self.line_number == 0 else self.line_number % 7 + 1
        for attempt in range(1, self.LINE_CHECK_ATTEMPTS + 1):
            self.check_stop()
            lines = self.ui.list_lines(scope)
            order = list(range(target_number, 8)) + list(range(1, target_number))
            if self.line_number == 0:
                order = [1]
            for number in order:
                self.check_stop()
                line = next((item for item in lines if item.number == number), None)
                if line is None or not line.available or (self.line_number and line.current):
                    continue
                if line.current or self.ui.change_line(scope, line):
                    self.line_number = number
                    self.ui.close_lines()
                    self.task._log(f"生活任务已切换至互联 {number} 线")
                    return
                self.task._log(f"互联 {number} 线当前不可进入，尝试下一条")
            self.ui.close_lines()
            self.task._log(f"生活采集暂无可用线路，第 {attempt}/{self.LINE_CHECK_ATTEMPTS} 次检查")
            if attempt < self.LINE_CHECK_ATTEMPTS:
                self.task.wait(self.LINE_RECHECK_MS)
        raise RuntimeError("连续三次检查均无可用分线")

    def run(self, coordinates: tuple[tuple[int, int], ...]) -> None:
        """切换目标地图后，按线路与材料坐标执行采集。

        参数：
            self：当前生活任务流程。
            coordinates：材料采集点的世界坐标序列；不包含地图切换落点。
        """
        self.check_stop()
        self.ui.travel_to_target_map()
        self.switch_line()  # Always start from interconnected line 1.
        while self.task._should_continue_collecting():
            self.check_stop()
            self.round_number += 1
            # index：本轮采集点顺序，从一开始；coordinate：当前世界坐标。
            for index, coordinate in enumerate(coordinates, start=1):
                self.check_stop()
                self.task._log(
                    f"{self.task.material.label}：第 {self.round_number} 轮，"
                    f"互联 {self.line_number} 线，"
                    f"坐标 {index}/{len(coordinates)} {coordinate}"
                )
                self.ui.move_to(coordinate)
                # action：已识别的场景采集入口；None 表示该坐标无资源。
                action = self.wait_action()
                if action is None:
                    self.task._log(f"坐标 {coordinate} 未找到采集物，尝试本线下一坐标")
                    continue
                self.gather_once(action)
                self.task._successful_gathers += 1
                self.task._log(f"{self.task.material.label} 采集完成，累计 {self.task._successful_gathers} 次")
                if not self.task._should_continue_collecting():
                    return
            self.switch_line()


# 现有真机采样素材仍存放于 mining 目录，逻辑按生活任务共用。
LIFE_ASSET_DIR = TEMPLATES_DIR / "mining"


def glyph_runs(mask: np.ndarray) -> list[tuple[int, np.ndarray]]:
    """Split a tightly scoped numeric field by blank columns, retaining punctuation."""
    runs = []
    start = None
    for x, occupied in enumerate(np.any(mask, axis=0).tolist() + [False]):
        if occupied and start is None:
            start = x
        elif not occupied and start is not None:
            glyph = mask[:, start:x]
            rows = np.flatnonzero(np.any(glyph, axis=1))
            runs.append((start, glyph[rows[0] : rows[-1] + 1]))
            start = None
    return runs


@lru_cache(maxsize=10)
def digit_template(digit: int) -> np.ndarray:
    return cv2.cvtColor(load_image(str(LIFE_ASSET_DIR / f"digit_{digit}.png")), cv2.COLOR_BGR2GRAY)


@lru_cache(maxsize=10)
def hud_digit_templates(digit: int) -> tuple[np.ndarray, ...]:
    return tuple(cv2.cvtColor(load_image(str(p)), cv2.COLOR_BGR2GRAY)
                 for p in sorted(LIFE_ASSET_DIR.glob(f"hud_digit_{digit}_*.png")))


@lru_cache(maxsize=10)
def field_digit_templates(digit: int) -> tuple[np.ndarray, ...]:
    return (digit_template(digit),) + tuple(
        cv2.cvtColor(load_image(str(p)), cv2.COLOR_BGR2GRAY)
        for p in sorted(LIFE_ASSET_DIR.glob(f"field_digit_{digit}_*.png"))
    )


def read_number(mask: np.ndarray, *, hud: bool = False) -> int | None:
    digits = []
    for _, glyph in glyph_runs(mask):
        height, width = glyph.shape
        if height < 8 or (hud and height > 13) or width / height < 0.2:
            # HUD parentheses are taller than digits; the digit 1 is narrow.
            continue
        scores = []
        for digit in range(10):
            templates = hud_digit_templates(digit) if hud else field_digit_templates(digit)
            errors = []
            for template in templates:
                aspect_error = abs(width / height - template.shape[1] / template.shape[0])
                resized = cv2.resize(glyph, (template.shape[1], template.shape[0]), interpolation=cv2.INTER_AREA)
                error = float(np.mean(np.abs(resized.astype(float) - template))) / 255
                errors.append(error + aspect_error * 0.4)
            scores.append((min(errors, default=1.0), digit))
        scores.sort()
        if scores[0][0] > 0.26 or scores[1][0] - scores[0][0] < 0.025:
            return None
        digits.append(str(scores[0][1]))
    return int("".join(digits)) if digits else None


class LifeUI:
    # 以下地图输入和分线点击点为 1280×720 屏幕像素，来自实机截图校准。
    INPUT_POINTS = ((164, 634), (280, 634))
    INPUT_CONFIRM = (1102, 80)
    GO_POINT = (367, 634)
    LINE_POINT = (1118, 45)
    SCOPE_POINT = (978, 646)
    MAX_LINE_PAGES = 20
    # 两个采集交互行的动作文字区域，按零起始交互行索引选择。
    ROI_ACTION_LABELS = ((970, 438, 75, 55), (955, 535, 75, 55))
    ROI_ACTION_LABEL = ROI_ACTION_LABELS[0]
    # 两个采集交互行的采集中标志区域，单位为屏幕像素。
    ROI_GATHERING = ((905, 415, 55, 35), (890, 512, 55, 35))
    ROI_ACCELERATION = (560, 455, 170, 90)
    # 每种技能的动作文字模板；尚未取得实机素材的技能在启动前拦截。
    ACTION_LABEL_ASSETS: ClassVar[dict[str, str]] = {"mining": "action_label"}
    # 无工具页面模板及其屏幕区域，只登记经过实机截图验证的技能。
    NO_TOOL_ASSETS: ClassVar[dict[str, tuple[tuple[str, tuple[int, int, int, int]], ...]]] = {
        "mining": (
            ("tool_purchase", (200, 80, 900, 530)),
            ("tool_trade", (200, 80, 900, 530)),
            ("tool_trade_page", (0, 0, 160, 80)),
        ),
    }
    # 各技能共用的地图、数字、分线和采集状态识别素材名称。
    REQUIRED_ASSETS = (
        "map_coordinates", "input_confirm", "switch_to_local",
        "switch_to_interconnected", "gathering", "stamina", "acceleration",
    )

    def __init__(self, task: SHRWTask):
        """建立当前材料的界面观察器；task 是正在执行的生活任务。"""
        self.task = task  # 当前生活任务及其材料配置。
        self._acceleration_visible = False  # 上次截图是否已出现加速按钮。
        self._latest_image: np.ndarray | None = None  # 最近一次观察截图，未观察时为 None。

    @property
    def action_label_asset(self) -> str:
        """当前技能采集动作文字的模板名称。"""
        return self.ACTION_LABEL_ASSETS[self.task.task_type]

    @property
    def action_label_roi(self) -> tuple[int, int, int, int]:
        """当前材料交互行的动作文字屏幕区域。"""
        return self.ROI_ACTION_LABELS[self.task.material.gather_slot]

    def validate_assets(self) -> None:
        """采集前确认当前技能的全部实机识别素材齐备。"""
        if self.task.task_type not in self.ACTION_LABEL_ASSETS or self.task.task_type not in self.NO_TOOL_ASSETS:
            self.task._life_configuration_failed = True
            raise LifeConfigurationError(f"{self.task.material.label}尚无已验证的采集和工具耗尽识别素材")
        # required：共用素材、动作文字和当前技能耗尽页面的文件名称。
        # name：当前技能的耗尽页面模板名；_roi：该模板对应的屏幕识别区域。
        required = self.REQUIRED_ASSETS + (self.action_label_asset,) + tuple(
            name for name, _roi in self.NO_TOOL_ASSETS[self.task.task_type]
        )
        # missing：缺失的必需素材或数字字形名称。
        missing = [name for name in required if not (LIFE_ASSET_DIR / f"{name}.png").is_file()]
        missing += [f"digit_{i}" for i in range(10) if not (LIFE_ASSET_DIR / f"digit_{i}.png").is_file()]
        missing += [f"hud_digit_{i}" for i in range(10) if not list(LIFE_ASSET_DIR.glob(f"hud_digit_{i}_*.png"))]
        if missing:
            self.task._life_configuration_failed = True
            raise LifeConfigurationError("生活采集识别素材尚待实机补齐：" + "、".join(missing))

    def screenshot(self) -> np.ndarray:
        if self.task.is_stopped():
            raise StepStopException("Stop requested")
        image = self.task.screenshot()
        if image.shape[:2] != (720, 1280):
            raise RuntimeError("固定坐标生活采集仅支持 1280×720 游戏画面")
        return image

    def matches(self, image: np.ndarray, name: str, roi, threshold: float = 0.86) -> bool:
        path = LIFE_ASSET_DIR / f"{name}.png"
        if not path.is_file():
            raise LifeConfigurationError(f"生活采集识别素材缺失：{name}")
        return self.task._vision.match_template(image, str(path), roi=roi, threshold=threshold).found

    def observe(self) -> LifeObservation:
        image = self.screenshot()
        self._latest_image = image
        # Specific signs take precedence over a generic non-scene classification.
        if self.matches(image, "stamina", (250, 150, 800, 450)):
            return LifeObservation(LifeSignal.NO_STAMINA)
        # name：耗尽页面模板名；roi：对应的屏幕像素识别区域。
        if any(
            self.matches(image, name, roi)
            for name, roi in self.NO_TOOL_ASSETS[self.task.task_type]
        ):
            return LifeObservation(LifeSignal.NO_TOOL)
        if self.task.is_scene_transition_loading(image):
            return LifeObservation(LifeSignal.LOADING)
        if not self.task.is_main_scene(image) or self.task.is_map_visible(image):
            return LifeObservation(LifeSignal.UNKNOWN)
        if self.matches(image, "gathering", self.ROI_GATHERING[self.task.material.gather_slot]):
            return LifeObservation(LifeSignal.GATHERING)
        action = self.task.find_configured_gather_action(image)
        return LifeObservation(LifeSignal.IDLE, action)

    def reset_acceleration(self) -> None:
        self._acceleration_visible = False

    def click_acceleration_if_visible(self) -> bool:
        if self._latest_image is None:
            return False
        visible = self.matches(self._latest_image, "acceleration", self.ROI_ACCELERATION)
        if visible and not self._acceleration_visible:
            self.task.click_point(637, 462, offset=0)
            self.task._log("检测到采集加速，已点击")
        self._acceleration_visible = visible
        return visible

    def current_coordinate(self, image: np.ndarray) -> tuple[int, int] | None:
        """从主场景右上角读取世界坐标；image 为 1280×720 截图。"""
        region = image[0:21, 1186:1280]
        mask = cv2.inRange(region, (185, 185, 185), (255, 255, 255))
        punctuation = [(x, glyph.shape[1]) for x, glyph in glyph_runs(mask) if glyph.shape[0] <= 6]
        if len(punctuation) != 1:
            return None
        comma, width = punctuation[0]
        x, y = read_number(mask[:, :comma], hud=True), read_number(mask[:, comma + width :], hud=True)
        return (x, y) if x is not None and y is not None else None

    def at_coordinate(self, image: np.ndarray, coordinate: tuple[int, int]) -> bool:
        current = self.current_coordinate(image)
        return current is not None and max(abs(a - b) for a, b in zip(current, coordinate)) <= 2

    def input_coordinate(self, coordinate: tuple[int, int]) -> None:
        if not self.matches(self.screenshot(), "map_coordinates", (0, 605, 400, 60)):
            raise RuntimeError("未识别到地图坐标输入区域")
        for point, value in zip(self.INPUT_POINTS, coordinate):
            self.task.click_point(*point, offset=0)
            self.task.wait(300)
            if not self.matches(self.screenshot(), "input_confirm", (1050, 30, 110, 100)):
                raise RuntimeError("地图坐标输入框未打开")
            self.task.shell("input keyevent KEYCODE_MOVE_END")
            self.task.shell("input keyevent " + " ".join(["KEYCODE_DEL"] * 12))
            self.task.shell(f"input text {value:d}")
            self.task.click_point(*self.INPUT_CONFIRM, offset=0)
            self.task.wait(300)
        image = self.screenshot()
        for roi, expected in zip(((119, 619, 95, 27), (235, 619, 95, 27)), coordinate):
            x, y, w, h = roi
            mask = cv2.inRange(image[y:y+h, x:x+w], (190, 190, 190), (255, 255, 255))
            if read_number(mask) != expected:
                raise RuntimeError("地图坐标输入回读不一致，取消前往")

    def move_to(self, coordinate: tuple[int, int]) -> None:
        self.task.wake_from_power_saving_if_needed()
        image = self.screenshot()
        if self.task.is_main_scene(image) and self.at_coordinate(image, coordinate):
            self.wait_arrival(coordinate)
            return
        self.task.close_all_panels(timeout_ms=3000)
        self.task.open_map()
        # Selecting the map is cheap and avoids trusting a stale remote-map view.
        self.task.select_target_map()
        self.task.collapse_life_filter_panel_if_visible()
        self.input_coordinate(coordinate)
        self.task.click_point(*self.GO_POINT, offset=0)
        self.task.wait(300)
        self.task.close_map_after_navigation()
        deadline = self.task._make_deadline(15_000)
        while not self.task._is_deadline_expired(deadline):
            image = self.screenshot()
            moving = self.task._vision.match_template(image, self.task.TEXT_AUTO_PATH, threshold=0.8).found
            if moving or self.task.is_scene_transition_loading(image):
                if not self.task.wait_auto_pathfinding(timeout_ms=self.task.AUTO_PATH_TIMEOUT_MS, missing_threshold=3):
                    raise RuntimeError("前往生活采集坐标的自动寻路超时")
                break
            if self.at_coordinate(image, coordinate):
                break  # Short routes may finish before the first poll.
            self.task.wait(300)
        else:
            raise RuntimeError("坐标前往后未检测到移动，也未到达目标坐标")
        self.wait_arrival(coordinate)

    def travel_to_target_map(self) -> None:
        """前往目标地图落点，确认寻路开始且寻路与过图稳定结束。"""
        # arrival_coordinate：目标地图上的世界坐标落点，不属于材料采集点。
        arrival_coordinate = TARGET_MAP_ARRIVAL_COORDINATES[self.task.material.map_key]
        # attempt：点击落点后未出现寻路时的重试序号，从一开始。
        for attempt in range(1, self.task.MAP_TRAVEL_ATTEMPTS + 1):
            self.screenshot()  # 在重试边界检查用户停止。
            self.task.wake_from_power_saving_if_needed()
            self.task.close_all_panels(timeout_ms=3000)
            self.task.open_map()
            self.task.select_target_map()
            self.task.collapse_life_filter_panel_if_visible()
            self.input_coordinate(arrival_coordinate)
            self.task.click_point(*self.GO_POINT, offset=0)
            self.task.wait(300)
            self.task.close_map_after_navigation()
            if self.task.wait_auto_pathfinding_started(timeout_ms=15_000):
                if not self.task.wait_auto_pathfinding(
                    timeout_ms=self.task.AUTO_PATH_TIMEOUT_MS,
                    missing_threshold=3,
                ):
                    raise RuntimeError(
                        f"前往{TARGET_MAP_LABELS[self.task.material.map_key]}地图落点的寻路或过图超时"
                    )
                self.task._log(
                    f"已到达{TARGET_MAP_LABELS[self.task.material.map_key]}地图切换落点 {arrival_coordinate}"
                )
                return
            self.task._log(
                f"点击{TARGET_MAP_LABELS[self.task.material.map_key]}地图落点后未开始自动寻路，"
                f"第 {attempt}/{self.task.MAP_TRAVEL_ATTEMPTS} 次"
            )
            self.task.close_all_panels(timeout_ms=3000)
        raise RuntimeError(f"前往{TARGET_MAP_LABELS[self.task.material.map_key]}地图落点未开始自动寻路")

    def wait_arrival(self, coordinate: tuple[int, int]) -> None:
        deadline = self.task._make_deadline(5_000)
        stable = 0
        while not self.task._is_deadline_expired(deadline):
            image = self.screenshot()
            moving = self.task._vision.match_template(image, self.task.TEXT_AUTO_PATH, threshold=0.8).found
            if self.task.is_main_scene(image) and not moving and self.at_coordinate(image, coordinate):
                stable += 1
                if stable >= 3:
                    return
            else:
                stable = 0
            self.task.wait(300)
        raise RuntimeError(f"寻路结束但未确认到达世界坐标 {coordinate}")

    def panel_scope(self, image: np.ndarray) -> str | None:
        if self.matches(image, "switch_to_local", (920, 620, 120, 48)):
            return "interconnected"
        if self.matches(image, "switch_to_interconnected", (920, 620, 120, 48)):
            return "local"
        return None

    @staticmethod
    def line_panel_visible(image: np.ndarray) -> bool:
        """Detect the fixed panel frame when a transient toast covers its footer."""
        gray = cv2.cvtColor(image[200:580], cv2.COLOR_BGR2GRAY)
        left_edge = float(np.mean(gray[:, 856])) - float(np.mean(gray[:, 860]))
        right_edge = float(np.mean(gray[:, 1097])) - float(np.mean(gray[:, 1092]))
        return left_edge > 6 and right_edge > 6

    def open_lines(self, scope: str) -> None:
        image = self.screenshot()
        if self.panel_scope(image) is None and not self.line_panel_visible(image):
            if not self.task.is_main_scene(image):
                raise RuntimeError("无法在非主场景打开分线列表")
            self.task.click_point(*self.LINE_POINT, offset=0)
            self.task.wait(500)
        active_scope = None
        for _ in range(12):
            image = self.screenshot()
            active_scope = self.panel_scope(image)
            if active_scope is not None:
                break
            self.task.wait(500)
        if active_scope is None:
            raise RuntimeError("未识别到分线面板")
        if active_scope != scope:
            self.task.click_point(*self.SCOPE_POINT, offset=0)
            # Changing scope can itself move the character to another line.
            deadline = self.task._make_deadline(15_000)
            while not self.task._is_deadline_expired(deadline):
                self.task.wait(500)
                image = self.screenshot()
                if self.panel_scope(image) == scope:
                    return
                if (self.panel_scope(image) is None and not self.line_panel_visible(image)
                        and self.task.is_main_scene(image)):
                    self.task.click_point(*self.LINE_POINT, offset=0)
            raise RuntimeError("切换分线范围后未确认目标面板")

    def visible_lines(self, image: np.ndarray, scope: str, page: int) -> list[LifeLine]:
        if self.panel_scope(image) != scope:
            raise RuntimeError("分线面板范围不一致")
        hsv = cv2.cvtColor(image[40:600, 885:918], cv2.COLOR_BGR2HSV)
        colored = ((hsv[:, :, 1] > 65) & (hsv[:, :, 2] > 60)).astype(np.uint8)
        count, _, stats, centers = cv2.connectedComponentsWithStats(colored)
        lines = []
        for i in range(1, count):
            if stats[i, cv2.CC_STAT_AREA] < 70:
                continue
            y = 40 + round(centers[i][1])
            if not 55 <= y <= 580:
                continue  # Partial rows are read after scrolling.
            x = 985 if scope == "interconnected" else 928
            label = image[y-15:y+15, x:x+44]
            # Cyan-gray text, including the highlighted current row.
            mask = cv2.inRange(label, (110, 110, 110), (240, 240, 240))
            # The numeric prefix ends before the Chinese character “线”.
            runs = glyph_runs(mask)
            end = next((left for left, glyph in runs if glyph.shape[1] / glyph.shape[0] > 0.85), mask.shape[1])
            number = read_number(mask[:, :end])
            if number is None:
                raise RuntimeError("分线编号识别失败，禁止猜测目标线路")
            background = image[y-20:y+20, 1045:1080]
            current = float(np.mean(cv2.cvtColor(background, cv2.COLOR_BGR2GRAY))) > 65
            hue = float(np.median(hsv[max(0,y-40-4):y-40+5, 11:22, 0]))
            lines.append(LifeLine(number, (980, y), current, 15 <= hue <= 100, page))
        return sorted(lines, key=lambda line: line.point[1])

    def scroll_top(self) -> None:
        previous = None
        for _ in range(self.MAX_LINE_PAGES):
            image = self.screenshot()
            scope = self.panel_scope(image)
            if scope is None:
                raise RuntimeError("滚动分线列表时面板已关闭")
            numbers = tuple(line.number for line in self.visible_lines(image, scope, 0))
            # The translucent panel has an animated scene behind it; compare
            # identifiers rather than requiring its pixels to become static.
            if previous is not None and numbers == previous:
                return
            previous = numbers
            self.task.swipe(1000, 140, 1000, 545, 300)
            self.task.wait(300)
        raise RuntimeError("分线列表未能回到顶部")

    def list_lines(self, scope: str) -> list[LifeLine]:
        self.open_lines(scope)
        self.scroll_top()
        return [line for line in self.visible_lines(self.screenshot(), scope, 0)
                if 1 <= line.number <= 7]

    def close_lines(self) -> None:
        if self.panel_scope(self.screenshot()) is not None:
            self.task.click_point(800, 80, offset=0)
            self.task.wait(300)

    def change_line(self, scope: str, line: LifeLine) -> bool:
        self.open_lines(scope)
        self.scroll_top()
        candidates = self.visible_lines(self.screenshot(), scope, 0)
        target = next((item for item in candidates if item.number == line.number), None)
        if target is None or not target.available:
            return False
        self.task.click_point(*target.point, offset=0)
        self.task.wait(1000)
        if not self.task.wait_auto_pathfinding(timeout_ms=45_000, missing_threshold=3):
            raise RuntimeError("换线后场景未稳定")
        self.task.wait(2000)
        if self.line_panel_visible(self.screenshot()):
            self.task.click_point(800, 80, offset=0)
            self.task.wait(500)
        # Panel closure alone is not proof of switching. Re-read current highlight.
        lines = self.list_lines(scope)
        success = any(item.number == line.number and item.current for item in lines)
        self.close_lines()
        if not self.task.is_main_scene(self.screenshot()):
            raise RuntimeError("换线后未恢复主场景")
        return success


class SHRWTask(YmGameTask):
    """按材料内置地图与世界坐标执行一梦江湖生活资源采集。"""

    task_key = "SHRW"
    task_name = "生活任务"
    task_description = "按内置地图与坐标循环采集，支持固定次数、持续采集与换线"
    MATERIAL_SPECS = _material_specs()
    LIFE_COORDINATES = LIFE_COORDINATES

    # 坐标均由 1280x720 真机截图校准。
    POINT_MAP = (1195, 18)
    POINT_MAP_WORLD = (1235, 675)
    POINT_MAP_CLOSE = (1235, 42)
    POINT_LIFE_PANEL_COLLAPSE = (500, 342)
    # 场景交互菱形的中心；采毛的绒类产物位于同一动物的第二行。
    POINT_GATHER_ACTIONS = ((935, 466), (918, 562))
    POINT_GATHER_ACTION = POINT_GATHER_ACTIONS[0]
    POINT_TARGET_MAPS: ClassVar[dict[str, tuple[int, int]]] = {
        "zhongyuan": (672, 366),
        "jiangnan": (966, 275),
        "saibei": (599, 105),
        "buwenchun": (841, 90),
    }

    ROI_MAP_CLOSE = (1185, 0, 95, 90)
    ROI_GATHER_ACTIONS = (
        ((975, 425, 115, 80), (875, 420, 105, 100)),
        ((960, 520, 150, 80), (870, 515, 105, 95)),
    )
    ROI_GATHER_TEMPLATE_SEARCH = (
        (885, 425, 95, 75),
        (870, 520, 100, 75),
    )
    ROI_MAIN_HEALTH = (74, 27, 260, 20)
    # 跨图加载页底部的进度条。仅在未识别到主场景时使用，避免将普通
    # 场景中的明亮 UI 误判为过图。
    ROI_SCENE_LOADING_PROGRESS = (250, 592, 800, 24)

    # 地图落点未触发自动寻路时的最多尝试次数。
    MAP_TRAVEL_ATTEMPTS = 3
    MAP_WAIT_MS = 900
    PANEL_WAIT_MS = 550
    AUTO_PATH_TIMEOUT_MS = 360_000
    GATHER_COMPLETE_TIMEOUT_MS = 120_000
    SCENE_TRANSITION_TIMEOUT_MS = 45_000
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
        self.collection_strategy = str(self.shrw_settings["strategy"])
        self.collection_count = int(self.shrw_settings["count"])
        # 保留运行时兼容开关，旧调用方仍可通过 loop_lines 停止持续采集。
        self.loop_lines = self.collection_strategy == SHRW_STRATEGY_CONTINUOUS
        self._successful_gathers = 0
        self._known_unavailable_reason: str | None = None
        self._life_configuration_failed = False
        self._flow_failed = False

    def validate_life_coordinates(self) -> tuple[tuple[int, int], ...]:
        coordinates = self.LIFE_COORDINATES.get(self.material_key, ())
        reason = None
        if not coordinates:
            reason = f"该材料尚未配置采集坐标：{self.material.label}"
        elif any(isinstance(point, (tuple, list)) and tuple(point) == (0, 0) for point in coordinates):
            reason = f"该材料坐标仍为 (0, 0) 占位，暂不可执行：{self.material.label}"
        elif any(
            not isinstance(point, (tuple, list)) or len(point) != 2
            or any(type(value) is not int or not 0 <= value <= 9999 for value in point)
            for point in coordinates
        ):
            reason = f"{self.material.label}采集坐标必须为 0～9999 的整数世界坐标 (X, Y)"
        if reason:
            self._life_configuration_failed = True
            raise LifeConfigurationError(reason)
        self._life_configuration_failed = False
        return tuple(tuple(point) for point in coordinates)

    def on_start(self) -> None:
        # Must precede the base hook: it closes panels and can move the character.
        self.validate_life_coordinates()
        LifeUI(self).validate_assets()
        self._successful_gathers = 0
        self._known_unavailable_reason = None
        self._flow_failed = False
        super().on_start()

    def after_retry_recovery(self, retry_scope: str, failure=None) -> None:
        if not self._life_configuration_failed:
            super().after_retry_recovery(retry_scope, failure)

    @step(retry=0, timeout_ms=None)
    def collect_life_material(self) -> None:
        """所有已配置材料共用地图落点、换线与定点采集流程。"""
        coordinates = self.validate_life_coordinates()
        try:
            ui = LifeUI(self)  # 当前材料的地图、坐标与采集状态观察器。
            ui.validate_assets()
            LifeFlow(self, ui).run(coordinates)
        except StepStopException:
            raise
        except LifeTaskUnavailable as exc:
            self._known_unavailable_reason = str(exc)
            self._log(f"生活任务停止采集：{exc}")
            return
        except Exception as exc:
            self._flow_failed = True
            debug_path = self.save_debug_screenshot("shrw_flow_failed")
            raise RuntimeError(f"生活任务流程失败：{exc}，已保存截图：{debug_path}") from exc

    def _should_continue_collecting(self) -> bool:
        """Return whether another gather should run for the configured strategy."""
        if self.collection_strategy == SHRW_STRATEGY_CONTINUOUS:
            return self.loop_lines
        if self.collection_strategy == SHRW_STRATEGY_FIXED_COUNT:
            return self._successful_gathers < self.collection_count
        return False

    def before_retry(
        self,
        retry_scope: str,
        failure: Exception | str | None = None,
    ) -> None:
        """地图选择错误不触发通用“脱离卡死”，避免无关传送。"""
        if self._life_configuration_failed:
            return
        self._log(f"生活任务{retry_scope}重试前仅关闭地图/弹窗：{failure}")
        self.close_all_panels(timeout_ms=3000)


    def select_target_map(self) -> None:
        """在地图界面选中材料所在区域；角色尚未完成跨图。"""
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
        self._log(f"地图界面已选择{TARGET_MAP_LABELS[self.material.map_key]}区域")

    def open_map(self) -> None:
        """打开右上角地图，并以右上角关闭圆钮确认地图已经出现。"""
        for attempt in range(3):
            image = self.screenshot()
            if self.is_map_visible(image):
                return
            if not self.is_main_scene(image):
                self.wake_from_power_saving_if_needed()
                self.wait(500)
            self.click_point(*self.POINT_MAP, offset=0)
            self.wait(self.MAP_WAIT_MS)
            if self.is_map_visible(self.screenshot()):
                return
            self._log(f"地图入口第 {attempt + 1}/3 次点击未生效，重试")
            self.wait(400)
        raise RuntimeError("点击右上角地图后未打开地图")


    def collapse_life_filter_panel_if_visible(self) -> None:
        """坐标输入前收起可能保留的生活筛选侧栏。"""
        if self.is_life_filter_panel_visible(self.screenshot()):
            self.collapse_life_filter_panel()

    def collapse_life_filter_panel(self) -> None:
        """收起生活筛选侧栏，显示地图坐标输入区域。"""
        if not self.is_life_filter_panel_visible(self.screenshot()):
            return
        self.click_point(*self.POINT_LIFE_PANEL_COLLAPSE, offset=0)
        self.wait(self.PANEL_WAIT_MS)
        if self.is_life_filter_panel_visible(self.screenshot()):
            raise RuntimeError("地图生活筛选侧栏未能收起")


    def close_map_after_navigation(self) -> None:
        """点击世界坐标前往后关闭地图，便于观察自动寻路。"""
        if self.is_map_visible(self.screenshot()):
            self.click_point(*self.POINT_MAP_CLOSE, offset=0)
            self.wait(500)


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
        if self.is_stopped():
            self._log(f"生活任务已手动停止，已确认采集 {self._successful_gathers} 次")
            return
        if self._life_configuration_failed or self._flow_failed or any(
            not result.success for result in results
        ):
            self._log(f"生活任务未完成，已确认采集 {self._successful_gathers} 次")
            return
        if self._known_unavailable_reason:
            detail = f"停止原因：{self._known_unavailable_reason}"
        else:
            detail = f"共采集 {self._successful_gathers} 次 {self.material.label}"
        self._log(f"生活任务完成，{detail}")
