"""Shared task base for Yi Meng Jiang Hu automation."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from botCore import GameTask
from botCore.coords import apply_random_offset


TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass(slots=True)
class LoginState:
    """Detected login-flow state from one screenshot."""

    name: str
    description: str
    score: float
    center: tuple[int, int] | None
    template_path: str | None = None


class YmGameTask(GameTask):
    """Base class for Yi Meng Jiang Hu tasks."""

    __abstract_task__ = True

    FIXED_RESOLUTION = (1280, 720)
    design_resolution = FIXED_RESOLUTION
    loop_count = 1

    PACKAGE_NAME = "com.netease.wyclx"
    auto_ensure_game_started = True
    auto_recover_health = True
    task_visible = True

    TEMPLATES_DIR = TEMPLATES_DIR

    BTN_OK = str(TEMPLATES_DIR / "btn_OK.png")
    BTN_CLOSE = str(TEMPLATES_DIR / "btn_close.png")
    BTN_PANE_CLOSE = str(TEMPLATES_DIR / "btn_pane_close.png")
    BTN_MODAL_OK = str(TEMPLATES_DIR / "btn_modal_ok.png")
    BTN_WELCOME_CLOSE = str(TEMPLATES_DIR / "btn_welcome_close.png")
    BTN_ROLE_CONFIRM = str(TEMPLATES_DIR / "btn_role_confirm.png")
    BTN_HD = str(TEMPLATES_DIR / "btn_HD.png")
    BTN_JRYX = str(TEMPLATES_DIR / "btn_JRYX.png")
    BTN_TRJH = str(TEMPLATES_DIR / "btn_TRJH.png")
    BTN_ZZDL = str(TEMPLATES_DIR / "btn_ZZDL.png")
    BTN_BIAOQING = str(TEMPLATES_DIR / "btn_biaoqing.png")
    BTN_CHAT_SEND = str(TEMPLATES_DIR / "btn_chat_send.png")
    ICON_TASK_ACTIVE = str(TEMPLATES_DIR / "icon_task_active.png")
    ICON_TASK_RW = str(TEMPLATES_DIR / "icon_task_rw.png")
    ICON_TASK_JH = str(TEMPLATES_DIR / "icon_task_jh.png")
    ICON_TASK_QY = str(TEMPLATES_DIR / "icon_task_qy.png")
    TEXT_AUTO_PATH = str(TEMPLATES_DIR / "text_zidongxunlu.png")
    TEXT_POWER_SAVING = str(TEMPLATES_DIR / "text_power_saving.png")
    TAB_BANGPAI_ACTIVE = str(TEMPLATES_DIR / "tab_bangpai_active.png")
    ACTIVITY_TAB_JIANGHU_ACTIVE = str(TEMPLATES_DIR / "activity_tab_jianghu_active.png")
    ACTIVITY_TAB_BANGPAI_ACTIVE = str(TEMPLATES_DIR / "activity_tab_bangpai_active.png")
    ACTIVITY_TAB_FENZHENG_ACTIVE = str(TEMPLATES_DIR / "activity_tab_fenzheng_active.png")
    ACTIVITY_TAB_HANGDANG_ACTIVE = str(TEMPLATES_DIR / "activity_tab_hangdang_active.png")
    ACTIVITY_TAB_YOULI_ACTIVE = str(TEMPLATES_DIR / "activity_tab_youli_active.png")
    ACTIVITY_TAB_SHEJIAO_ACTIVE = str(TEMPLATES_DIR / "activity_tab_shejiao_active.png")

    # 固定坐标点 (设计分辨率 1280x720 下)
    POINT_WAKE_SCREEN = (640, 360)
    POINT_HUODONG_JIANGHU = (192, 680)
    POINT_HUODONG_BANGPAI = (332, 680)
    POINT_HUODONG_FENZHENG = (462, 680)
    POINT_HUODONG_HANGDANG = (612, 680)
    POINT_HUODONG_YOULI = (756, 680)
    POINT_HUODONG_SHEJIAO = (882, 680)
    POINT_MAIN_TASK = (22, 160)
    POINT_MAIN_TEAM = (22, 276)
    POINT_MINIMAP = (1198, 45)
    POINT_LOCAL_MAP_WORLD = (1235, 668)
    POINT_WORLD_MAP_JINLING = (902, 215)
    POINT_JINLING_JIMING_TEMPLE = (532, 122)
    POINT_MAP_CLOSE = (1238, 45)
    POINT_TASK_TAB_TASK = (88, 124)
    POINT_TASK_TAB_JIANGHU = (174, 124)
    POINT_TASK_TAB_QIYU = (258, 124)
    POINT_EMOTION_SINGLE_TAB = (405, 505)
    POINT_EMOTION_MEDITATE = (725, 578)
    POINT_EMOTION_COLLAPSE = (934, 503)
    POINT_LIGHTNESS = (1240, 420)
    POINT_CHAT_COLLAPSE_ARROW = (680, 356)
    POINT_DIRECTION_JOYSTICK_CENTER = (105, 455)
    POINT_BATTLE_NORMAL_ATTACK = (1135, 553)
    POINT_RIGHT_JOYSTICK_CENTER = POINT_BATTLE_NORMAL_ATTACK
    POINT_BATTLE_SKILL_BUTTONS = (
        (1118, 389),
        (1022, 449),
        (995, 559),
        (933, 651),
        (1055, 653),
    )
    DIRECTION_JOYSTICK_RADIUS = 70
    BATTLE_SKILL_PAGE_COUNT = 2
    BATTLE_PAGE_ROUND_COUNT = 2
    BATTLE_NORMAL_ATTACK_COUNT = 3
    BATTLE_SKILL_BUTTON_COUNT = 4
    BATTLE_SKILL_BUTTON_TAP_COUNT = 1

    ROI_HEALTH_BAR = (74, 27, 260, 20)
    ROI_BIAOQING_BUTTON = (330, 650, 90, 70)
    ROI_CHAT_SEND_BUTTON = (500, 640, 160, 80)
    ROI_POWER_SAVING = (480, 470, 340, 140)
    ROI_CENTER_MODAL_OK = (730, 440, 250, 120)
    HEALTH_FULL_WIDTH = 255
    HEALTH_RECOVER_THRESHOLD = 0.80
    HEALTH_FULL_THRESHOLD = 0.90
    HEALTH_COLUMN_MIN_FILL_RATIO = 0.30
    HEALTH_ANCHOR_START_COLUMN = 8
    HEALTH_ANCHOR_END_COLUMN = 26
    HEALTH_RECOVER_TIMEOUT_MS = 300000
    HEALTH_RECOVER_POLL_INTERVAL_MS = 2000
    HEALTH_RED_MIN_VALUE = 120
    HEALTH_RED_MIN_DELTA = 45
    ACTIVITY_CATEGORY_POINTS = {
        "江湖": POINT_HUODONG_JIANGHU,
        "帮派": POINT_HUODONG_BANGPAI,
        "纷争": POINT_HUODONG_FENZHENG,
        "行当": POINT_HUODONG_HANGDANG,
        "游历": POINT_HUODONG_YOULI,
        "社交": POINT_HUODONG_SHEJIAO,
    }
    ACTIVITY_CATEGORY_TEMPLATES = {
        "江湖": ACTIVITY_TAB_JIANGHU_ACTIVE,
        "帮派": ACTIVITY_TAB_BANGPAI_ACTIVE,
        "纷争": ACTIVITY_TAB_FENZHENG_ACTIVE,
        "行当": ACTIVITY_TAB_HANGDANG_ACTIVE,
        "游历": ACTIVITY_TAB_YOULI_ACTIVE,
        "社交": ACTIVITY_TAB_SHEJIAO_ACTIVE,
    }
    ACTIVITY_CATEGORY_VERIFY_TIMEOUT_MS = 1500
    ACTIVITY_CATEGORY_VERIFY_THRESHOLD = 0.85

    LOGIN_STATE_NOTICE = "notice"
    LOGIN_STATE_LOGIN = "login"
    LOGIN_STATE_ROLE_CONFIRM = "role_confirm"
    LOGIN_STATE_ROLE = "role"
    LOGIN_STATE_POPUP = "popup"
    LOGIN_STATE_MAIN = "main"

    LOGIN_TOTAL_TIMEOUT_MS = 300000
    LOGIN_LOADING_TIMEOUT_MS = 120000
    LOGIN_CLEANUP_TIMEOUT_MS = 60000
    LOGIN_POLL_INTERVAL_MS = 500
    LOGIN_WAIT_AFTER_CLICK_MS = 1500
    LOGIN_WAIT_AFTER_CLOSE_MS = 800

    WALK_DIRECTIONS = {
        "forward": (0, -1),
        "backward": (0, 1),
        "left": (-1, 0),
        "right": (1, 0),
        "前": (0, -1),
        "后": (0, 1),
        "左": (-1, 0),
        "右": (1, 0),
        "向前": (0, -1),
        "向后": (0, 1),
        "向左": (-1, 0),
        "向右": (1, 0),
    }

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._recovering_health = False

    def before_start(self) -> None:
        """Ensure the game is ready before task-specific setup runs."""
        if self.auto_ensure_game_started:
            self.ensure_game_started()

    def before_step(self, step_name: str, step_meta: dict[str, Any]) -> None:
        """Run shared Yi Meng Jiang Hu guards before each task step."""
        super().before_step(step_name, step_meta)
        self.recover_health_if_needed()

    def is_power_saving_mode(self) -> bool:
        """Return whether the current game view is the power-saving overlay."""
        return self.find_image(
            self.TEXT_POWER_SAVING,
            threshold=0.8,
            roi=self.scale_roi(self.ROI_POWER_SAVING),
        )

    def wake_from_power_saving_if_needed(self) -> bool:
        """Wake the game from power-saving mode by tapping the lower-right joystick center."""
        if not self.is_power_saving_mode():
            return False

        self._log("检测到省电模式，点击右下角摇杆中心唤醒")
        self.click_point(self.POINT_RIGHT_JOYSTICK_CENTER[0], self.POINT_RIGHT_JOYSTICK_CENTER[1], offset=0)
        self.wait(1000)
        return True

    def wake_foreground_screen_once(self) -> None:
        """Try to wake an unrecognized foreground game scene without entering login flow."""
        self._log("前台画面未识别，点击右下角摇杆中心尝试唤醒")
        self.click_point(self.POINT_RIGHT_JOYSTICK_CENTER[0], self.POINT_RIGHT_JOYSTICK_CENTER[1], offset=0)
        self.wait(1000)

    def is_chat_open(self) -> bool:
        """Return whether the chat panel is expanded."""
        return self.find_image(
            self.BTN_CHAT_SEND,
            threshold=0.9,
            roi=self.scale_roi(self.ROI_CHAT_SEND_BUTTON),
        )

    def collapse_chat_if_open(self, wait_after_click_ms: int = 800) -> bool:
        """Collapse the expanded chat panel when the Send button is visible."""
        if not self.is_chat_open():
            return False

        self._log("检测到聊天框展开，点击箭头收起")
        self.click_point(self.POINT_CHAT_COLLAPSE_ARROW[0], self.POINT_CHAT_COLLAPSE_ARROW[1], offset=0)
        self.wait(wait_after_click_ms)
        return True

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        """Tap a fixed 1280x720 coordinate without runtime resolution scaling."""
        if offset > 0:
            x, y = apply_random_offset((x, y), offset)
        self.tap(x, y)

    def walk(self, direction: str, duration_ms: int = 500) -> None:
        """Drag the lower-left movement joystick in the requested direction."""
        if duration_ms < 0:
            raise ValueError("duration_ms must be greater than or equal to 0")

        vector = self.WALK_DIRECTIONS.get(direction)
        if vector is None:
            raise ValueError(f"Unsupported walk direction: {direction}")

        if not self.is_game_main_ready():
            raise RuntimeError("当前不是干净主界面，禁止移动")

        start = self.POINT_DIRECTION_JOYSTICK_CENTER
        end = (
            start[0] + vector[0] * self.DIRECTION_JOYSTICK_RADIUS,
            start[1] + vector[1] * self.DIRECTION_JOYSTICK_RADIUS,
        )
        self.swipe(start[0], start[1], end[0], end[1], duration_ms=duration_ms)

    def walk_forward(self, duration_ms: int = 500) -> None:
        """Walk forward by dragging the movement joystick upward."""
        self.walk("forward", duration_ms=duration_ms)

    def walk_backward(self, duration_ms: int = 500) -> None:
        """Walk backward by dragging the movement joystick downward."""
        self.walk("backward", duration_ms=duration_ms)

    def walk_left(self, duration_ms: int = 500) -> None:
        """Walk left by dragging the movement joystick leftward."""
        self.walk("left", duration_ms=duration_ms)

    def walk_right(self, duration_ms: int = 500) -> None:
        """Walk right by dragging the movement joystick rightward."""
        self.walk("right", duration_ms=duration_ms)

    def auto_battle(self, interval_ms: int = 500) -> None:
        """Run the fixed two-page battle rhythm and return to the first skill page."""
        if interval_ms < 0:
            raise ValueError("interval_ms must be greater than or equal to 0")

        self._log(
            f"开始自动战斗：技能页 {self.BATTLE_SKILL_PAGE_COUNT} 页，每页循环 {self.BATTLE_PAGE_ROUND_COUNT} 轮，"
            f"普攻 {self.BATTLE_NORMAL_ATTACK_COUNT} 次，技能位各点击 {self.BATTLE_SKILL_BUTTON_TAP_COUNT} 次"
        )

        skill_points = self.POINT_BATTLE_SKILL_BUTTONS[: self.BATTLE_SKILL_BUTTON_COUNT]
        for _ in range(self.BATTLE_SKILL_PAGE_COUNT):
            for _ in range(self.BATTLE_PAGE_ROUND_COUNT):
                self._tap_battle_button(
                    self.POINT_BATTLE_NORMAL_ATTACK,
                    self.BATTLE_NORMAL_ATTACK_COUNT,
                    interval_ms,
                )
                for skill_point in skill_points:
                    self._tap_battle_button(
                        skill_point,
                        self.BATTLE_SKILL_BUTTON_TAP_COUNT,
                        interval_ms,
                    )

            self.turn_battle_skill_page()
            self.wait(interval_ms)

        self._log("自动战斗点击完成")

    def turn_battle_skill_page(self, duration_ms: int = 350) -> None:
        """Turn the battle skill wheel by swiping from the first skill to the second."""
        if duration_ms < 0:
            raise ValueError("duration_ms must be greater than or equal to 0")

        start = self.POINT_BATTLE_SKILL_BUTTONS[0]
        end = self.POINT_BATTLE_SKILL_BUTTONS[1]
        self.swipe(start[0], start[1], end[0], end[1], duration_ms=duration_ms)

    def _tap_battle_button(
        self,
        point: tuple[int, int],
        tap_count: int,
        interval_ms: int,
    ) -> None:
        for _ in range(tap_count):
            self.click_point(point[0], point[1], offset=0)
            self.wait(interval_ms)

    def detect_health_ratio(self) -> float | None:
        """Return the visible HP bar fill ratio, or None when it cannot be read."""
        screenshot = self.screenshot()
        if screenshot.ndim < 3 or screenshot.shape[2] < 3:
            return None

        screen_height, screen_width = screenshot.shape[:2]
        x, y, width, height = self.ROI_HEALTH_BAR
        x2 = min(screen_width, x + width)
        y2 = min(screen_height, y + height)
        if x < 0 or y < 0 or x >= x2 or y >= y2:
            return None

        region = screenshot[y:y2, x:x2, :3]
        if region.size == 0:
            return None

        red_columns = self._red_health_columns(region)
        filled_width = self._anchored_true_run(red_columns)
        if filled_width <= 0:
            return None
        full_width = max(1, self.HEALTH_FULL_WIDTH)
        return min(1.0, filled_width / full_width)

    def recover_health_if_needed(self) -> None:
        """Meditate until HP is full when the main-scene HP bar is low."""
        if not self.auto_recover_health or self._recovering_health:
            return

        self.collapse_chat_if_open()
        if not self.find_image(
            self.BTN_BIAOQING,
            threshold=0.9,
            roi=self.scale_roi(self.ROI_BIAOQING_BUTTON),
        ):
            self._log("未找到主界面表情按钮，跳过自动打坐")
            return

        try:
            health_ratio = self.detect_health_ratio()
        except Exception as exc:
            self._log(f"血量检测失败，跳过自动打坐：{exc}")
            return

        if health_ratio is None:
            self._log("未能识别血条，跳过自动打坐")
            return
        if health_ratio >= self.HEALTH_RECOVER_THRESHOLD:
            return

        self._recovering_health = True
        try:
            self._log(f"检测到血量较低：{health_ratio:.1%}，开始打坐恢复")
            self.click(0)
            self.wait(800)
            self.click_point(self.POINT_EMOTION_SINGLE_TAB[0], self.POINT_EMOTION_SINGLE_TAB[1], offset=0)
            self.wait(800)
            self.click_point(self.POINT_EMOTION_MEDITATE[0], self.POINT_EMOTION_MEDITATE[1], offset=0)
            self.wait(1000)

            if not self.wait_health_full():
                raise RuntimeError("打坐回血超时：血量未回满")

            self.click_point(self.POINT_EMOTION_COLLAPSE[0], self.POINT_EMOTION_COLLAPSE[1], offset=0)
            self.wait(500)
            self.click_point(self.POINT_LIGHTNESS[0], self.POINT_LIGHTNESS[1], offset=0)
            self.wait(1000)
            self._log("血量已回满，退出打坐")
        finally:
            self._recovering_health = False

    def wait_health_full(self) -> bool:
        """Wait until HP reaches the configured full threshold."""
        deadline = self._make_deadline(self.HEALTH_RECOVER_TIMEOUT_MS)
        while not self._is_deadline_expired(deadline):
            health_ratio = self.detect_health_ratio()
            if health_ratio is not None and health_ratio >= self.HEALTH_FULL_THRESHOLD:
                return True
            if health_ratio is not None:
                self._log(f"打坐回血中：{health_ratio:.1%}")
            self.wait(self.HEALTH_RECOVER_POLL_INTERVAL_MS)
        return False

    def _red_health_columns(self, region: np.ndarray) -> np.ndarray:
        channels = region.astype(np.int16)
        blue = channels[:, :, 0]
        green = channels[:, :, 1]
        red = channels[:, :, 2]
        red_mask = (
            (red >= self.HEALTH_RED_MIN_VALUE)
            & (red >= green + self.HEALTH_RED_MIN_DELTA)
            & (red >= blue + self.HEALTH_RED_MIN_DELTA)
        )
        min_pixels = max(1, int(round(region.shape[0] * self.HEALTH_COLUMN_MIN_FILL_RATIO)))
        return red_mask.sum(axis=0) >= min_pixels

    def _anchored_true_run(self, values: np.ndarray) -> int:
        anchor_start = int(round(self.HEALTH_ANCHOR_START_COLUMN * len(values) / self.ROI_HEALTH_BAR[2]))
        anchor_end = int(round(self.HEALTH_ANCHOR_END_COLUMN * len(values) / self.ROI_HEALTH_BAR[2]))
        best = 0
        current = 0
        start = 0
        for index, value in enumerate(values):
            if bool(value):
                if current == 0:
                    start = index
                current += 1
                if start <= anchor_end and index >= anchor_start:
                    best = max(best, current)
            else:
                current = 0
        return best

    @staticmethod
    def _longest_true_run(values: np.ndarray) -> int:
        longest = 0
        current = 0
        for value in values:
            if bool(value):
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    def is_game_process_running(self) -> bool:
        """Return whether the game process currently exists on the device."""
        try:
            return bool(self.shell(f"pidof {self.PACKAGE_NAME}").strip())
        except Exception:
            return False

    @classmethod
    def _extract_package_from_window_line(cls, line: str) -> str | None:
        """Extract the package name from a dumpsys window focus line."""
        match = re.search(r"\b([A-Za-z][\w]*(?:\.[\w]+)+)/", line)
        if not match:
            return None
        return match.group(1)

    @classmethod
    def _extract_foreground_package(cls, window_dump: str) -> str | None:
        """Return the focused package from a dumpsys window dump."""
        for marker in ("mCurrentFocus=", "mFocusedApp="):
            for line in window_dump.splitlines():
                if marker not in line:
                    continue
                package_name = cls._extract_package_from_window_line(line)
                if package_name:
                    return package_name
        return None

    def get_foreground_package(self) -> str | None:
        """Return the current foreground package, or None when unavailable."""
        try:
            return self._extract_foreground_package(self.shell("dumpsys window"))
        except Exception:
            return None

    def is_game_foreground(self) -> bool:
        """Return whether the game package owns the focused window."""
        return self.get_foreground_package() == self.PACKAGE_NAME

    def is_game_main_ready(self, *, timeout_ms: int = 2000, threshold: float = 0.8) -> bool:
        """Return whether the game main scene is visible and free of startup popups."""
        deadline = self._make_deadline(timeout_ms)
        while True:
            state = self.detect_login_state(include_modal_controls=True, threshold=threshold)
            if state and state.name == self.LOGIN_STATE_MAIN:
                return True
            if state is not None or self._is_deadline_expired(deadline):
                return False
            self.wait(self.LOGIN_POLL_INTERVAL_MS)

    def ensure_game_started(self, *, force: bool = False) -> None:
        """Start and enter the game when it is not ready in the foreground."""
        if not force and self.is_game_foreground():
            woke_from_power_saving = self.wake_from_power_saving_if_needed()
            if woke_from_power_saving and self.is_game_main_ready():
                self._log("检测到游戏已在前台，跳过启动")
                return

            state = self.detect_login_state(include_modal_controls=True)
            if state and state.name == self.LOGIN_STATE_MAIN:
                self._log("检测到游戏已在前台，跳过启动")
                return

            if state is None and not woke_from_power_saving:
                self.wake_foreground_screen_once()
                if self.is_game_main_ready():
                    self._log("检测到游戏已在前台，跳过启动")
                    return

            self._log("检测到游戏在前台但未进入主界面，继续进入游戏")
        else:
            self.start_game_app()

        self.enter_game()

    def start_game_app(self, wait_after_launch_ms: int = 5000) -> None:
        """Launch the Yi Meng Jiang Hu Android package."""
        self._log("启动应用")
        self.shell(f"monkey -p {self.PACKAGE_NAME} -c android.intent.category.LAUNCHER 1")
        self.wait(wait_after_launch_ms)
        self._log("应用启动完成")

    def enter_game(self) -> None:
        """Enter the game main scene from the launcher/login screens."""
        self._log("进入游戏主界面")
        deadline = self._make_deadline(self.LOGIN_TOTAL_TIMEOUT_MS)
        loading_started_at: float | None = None
        last_state_name: str | None = None

        while not self._is_deadline_expired(deadline):
            state = self.detect_login_state(include_modal_controls=True)
            if state is None:
                if loading_started_at is None:
                    loading_started_at = time.perf_counter()
                    self._log("等待登录流程加载...")
                elif self._elapsed_ms(loading_started_at) > self.LOGIN_LOADING_TIMEOUT_MS:
                    raise RuntimeError("登录流程超时：长时间未识别到可操作界面")
                self.wait(self.LOGIN_POLL_INTERVAL_MS)
                continue

            loading_started_at = None
            if state.name != last_state_name:
                self._log(f"登录状态：{state.description}")
                last_state_name = state.name

            if state.name == self.LOGIN_STATE_NOTICE:
                self.tap()
                self.wait(self.LOGIN_WAIT_AFTER_CLICK_MS)
                continue

            if state.name == self.LOGIN_STATE_LOGIN:
                self.tap()
                self.wait(self.LOGIN_WAIT_AFTER_CLICK_MS)
                continue

            if state.name == self.LOGIN_STATE_ROLE_CONFIRM:
                self.tap()
                self.wait(self.LOGIN_WAIT_AFTER_CLICK_MS)
                continue

            if state.name == self.LOGIN_STATE_ROLE:
                self.tap()
                self.wait(self.LOGIN_WAIT_AFTER_CLICK_MS)
                continue

            if state.name in {self.LOGIN_STATE_POPUP, self.LOGIN_STATE_MAIN}:
                cleanup_timeout = min(self.LOGIN_CLEANUP_TIMEOUT_MS, self._remaining_ms(deadline))
                if self.close_startup_panels(timeout_ms=cleanup_timeout):
                    self._log("登录流程结束，主界面已清理")
                    return
                last_state_name = None
                continue

            self.wait(self.LOGIN_POLL_INTERVAL_MS)

        raise RuntimeError("登录流程超时：未能进入干净主界面")

    def detect_login_state(
        self,
        *,
        include_modal_controls: bool = False,
        threshold: float = 0.8,
    ) -> LoginState | None:
        """Detect the current login-flow state from a single screenshot."""
        screenshot = self.screenshot()
        for state_name, description, templates in self._login_state_targets(include_modal_controls):
            match = self._vision.match_template(screenshot, templates, threshold=threshold)
            self._last_match_score = match.score
            if not match.found or not match.center:
                continue
            self._last_match_center = match.center
            return LoginState(
                name=state_name,
                description=description,
                score=match.score,
                center=match.center,
                template_path=match.template_path,
            )

        self._last_match_center = None
        return None

    def close_startup_panels(
        self,
        *,
        timeout_ms: int = LOGIN_CLEANUP_TIMEOUT_MS,
        threshold: float = 0.8,
    ) -> bool:
        """Close startup popups until the clean main scene is stable."""
        deadline = self._make_deadline(timeout_ms)
        consecutive_clean = 0

        while not self._is_deadline_expired(deadline):
            state = self.detect_login_state(include_modal_controls=True, threshold=threshold)
            if state is None:
                consecutive_clean = 0
                self.wait(self.LOGIN_POLL_INTERVAL_MS)
                continue

            if state.name == self.LOGIN_STATE_POPUP:
                consecutive_clean = 0
                self._log(f"关闭启动弹窗：{state.description}")
                self.tap()
                self.wait(self.LOGIN_WAIT_AFTER_CLOSE_MS)
                continue

            if state.name == self.LOGIN_STATE_MAIN:
                consecutive_clean += 1
                if consecutive_clean >= 2:
                    return True
                self.wait(self.LOGIN_POLL_INTERVAL_MS)
                continue

            return False

        raise RuntimeError("登录后活动弹窗清理超时")

    def _login_state_targets(
        self,
        include_modal_controls: bool,
    ) -> tuple[tuple[str, str, list[str]], ...]:
        popup_targets = self._startup_close_targets(include_modal_controls)
        return (
            (self.LOGIN_STATE_NOTICE, "公告页 - 朕知道了", [self.BTN_ZZDL]),
            (self.LOGIN_STATE_LOGIN, "登录页 - 踏入江湖", [self.BTN_TRJH]),
            (self.LOGIN_STATE_ROLE_CONFIRM, "在线角色确认 - 确定", [self.BTN_ROLE_CONFIRM]),
            (self.LOGIN_STATE_ROLE, "角色页 - 进入游戏", [self.BTN_JRYX]),
            (self.LOGIN_STATE_POPUP, "活动弹窗", popup_targets),
            (self.LOGIN_STATE_MAIN, "干净主界面", [self.BTN_HD]),
        )

    def _startup_close_targets(self, include_modal_controls: bool) -> list[str]:
        targets = [self.BTN_CLOSE, self.BTN_PANE_CLOSE, self.BTN_WELCOME_CLOSE]
        if include_modal_controls:
            targets.extend([self.BTN_MODAL_OK, self.BTN_OK])
        return targets

    @staticmethod
    def _make_deadline(timeout_ms: int | None) -> float | None:
        return None if timeout_ms is None else time.perf_counter() + timeout_ms / 1000.0

    @staticmethod
    def _is_deadline_expired(deadline: float | None) -> bool:
        return deadline is not None and time.perf_counter() >= deadline

    @staticmethod
    def _remaining_ms(deadline: float | None) -> int:
        if deadline is None:
            return 0
        return max(0, int((deadline - time.perf_counter()) * 1000))

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return int((time.perf_counter() - started_at) * 1000)

    def tap_when_found(self, found: bool, missing_count: int) -> None:
        """Tap the last matched target while it is still visible."""
        if found:
            self.tap()
        else:
            self._log(f"未找到点击目标图标 (连续 {missing_count} 次)")

    def close_all_panels(
        self,
        templates: str | list[str] | None = None,
        *,
        timeout_ms: int = 5000,
        wait_after_click_ms: int = 500,
        back_safe: bool = False,
    ) -> None:
        """Close visible panels by repeatedly tapping known close buttons."""
        targets = templates or [self.BTN_CLOSE, self.BTN_PANE_CLOSE, self.BTN_WELCOME_CLOSE]
        self.collapse_chat_if_open()
        while self.wait_image_appear(targets, timeout_ms=timeout_ms):
            self.click()
            self.wait(wait_after_click_ms)
        self.collapse_chat_if_open()
        self._log("已关闭所有弹窗")
        if back_safe:
            self.return_to_safe_zone()

    def return_to_safe_zone(
        self,
        path_timeout_ms: int = 90000,
        wait_after_click_ms: int = 1000,
    ) -> None:
        """Use the map to auto-path back to Jinling Jiming Temple."""
        if not self.is_game_main_ready():
            raise RuntimeError("当前不是干净主界面，无法返回鸡鸣寺安全区")

        self._log("开始返回鸡鸣寺安全区")
        for point in (
            self.POINT_MINIMAP,
            self.POINT_LOCAL_MAP_WORLD,
            self.POINT_WORLD_MAP_JINLING,
            self.POINT_JINLING_JIMING_TEMPLE,
            self.POINT_MAP_CLOSE,
        ):
            self.click_point(point[0], point[1], offset=0)
            self.wait(wait_after_click_ms)

        self.wait_auto_pathfinding(timeout_ms=path_timeout_ms)
        self._log("已回到鸡鸣寺安全区")

    def find_image_once(
        self,
        template: str | list[str],
        *,
        threshold: float = 0.8,
        roi: tuple[int, int, int, int] | None = None,
        log_found: bool = False,
        log_missing: bool = False,
    ) -> bool:
        """Check one screenshot without producing repeated wait-loop noise."""
        templates = [template] if isinstance(template, str) else template
        match = self._vision.match_template(self.screenshot(), templates, threshold=threshold, roi=roi)
        self._last_match_score = match.score
        if match.found and match.center:
            self._last_match_center = match.center
            if log_found:
                self._log(f"Found image: {template} (score={match.score:.3f})")
            return True

        self._last_match_center = None
        if log_missing:
            self._log(f"Image not found: {template} (score={match.score:.3f})")
        return False

    def confirm_match_leave_team_dialog_if_needed(
        self,
        activity_name: str,
        *,
        wait_after_click_ms: int = 1200,
        threshold: float = 0.85,
    ) -> bool:
        """Confirm the PvP prompt that asks whether to leave the current team."""
        if not self.find_image_once(
            self.BTN_MODAL_OK,
            threshold=threshold,
            roi=self.scale_roi(self.ROI_CENTER_MODAL_OK),
        ):
            return False

        self._log(f"检测到{activity_name}单人匹配退队确认，点击确定")
        self.click(offset=0)
        self.wait(wait_after_click_ms)
        return True

    def open_activity_panel(
        self,
        category: str | tuple[int, int] | None = None,
        category_name: str | None = None,
        *,
        timeout_ms: int = 30000,
        wait_after_open_ms: int = 2000,
        wait_after_category_ms: int = 0,
    ) -> None:
        """Open the activity panel and optionally switch to a category tab."""
        self.wait_image_appear(self.BTN_HD, timeout_ms=timeout_ms)
        self.click(0)
        self.wait(wait_after_open_ms)
        self._log("已打开活动界面")

        if category is None:
            return

        if isinstance(category, str):
            self.open_activity_category(
                category,
                wait_after_click_ms=wait_after_category_ms or 1500,
            )
            return

        self.click_point(category[0], category[1], offset=0)
        if wait_after_category_ms > 0:
            self.wait(wait_after_category_ms)
        if category_name:
            self._log(f"已打开活动 - {category_name}界面")

    def open_activity_category(
        self,
        category_name: str,
        *,
        max_attempts: int = 3,
        wait_after_click_ms: int = 1500,
    ) -> None:
        point = self.ACTIVITY_CATEGORY_POINTS.get(category_name)
        template = self.ACTIVITY_CATEGORY_TEMPLATES.get(category_name)
        if point is None or template is None:
            raise ValueError(f"Unsupported activity category: {category_name}")

        for attempt in range(1, max_attempts + 1):
            self.click_point(point[0], point[1], offset=0)
            if wait_after_click_ms > 0:
                self.wait(wait_after_click_ms)
            if self.wait_image_appear(
                template,
                timeout_ms=self.ACTIVITY_CATEGORY_VERIFY_TIMEOUT_MS,
                threshold=self.ACTIVITY_CATEGORY_VERIFY_THRESHOLD,
            ):
                self._log(f"已打开活动 - {category_name}界面")
                return
            self._log(f"活动 - {category_name}界面未确认，重试 {attempt}/{max_attempts}")

        raise RuntimeError(f"未能切换到活动 - {category_name}界面")

    def switch_task_panel(
        self,
        panel: str,
        *,
        timeout_ms: int = 3000,
        threshold: float = 0.8,
        wait_after_click_ms: int = 500,
    ) -> None:
        """Open the task sidebar and switch to the requested task panel tab."""
        panel_targets = {
            "任务": (self.POINT_TASK_TAB_TASK, self.ICON_TASK_RW),
            "江湖": (self.POINT_TASK_TAB_JIANGHU, self.ICON_TASK_JH),
            "奇遇": (self.POINT_TASK_TAB_QIYU, self.ICON_TASK_QY),
        }
        if panel not in panel_targets:
            raise ValueError(f"Unsupported task panel: {panel}")

        if not self.wait_image_appear(self.ICON_TASK_ACTIVE, timeout_ms=timeout_ms, threshold=threshold):
            self._log("任务侧栏未激活，点击任务栏")
            self.click_point(self.POINT_MAIN_TASK[0], self.POINT_MAIN_TASK[1])
            self.wait(wait_after_click_ms)

            if not self.wait_image_appear(self.ICON_TASK_ACTIVE, timeout_ms=timeout_ms, threshold=threshold):
                raise RuntimeError("未能打开任务侧栏")

        tab_point, active_template = panel_targets[panel]
        self.click_point(tab_point[0], tab_point[1])
        self.wait(wait_after_click_ms)

        if not self.wait_image_appear(active_template, timeout_ms=timeout_ms, threshold=threshold):
            raise RuntimeError(f"未能切换到任务面板：{panel}")

        self._log(f"已切换到任务面板：{panel}")

    def wait_auto_pathfinding(
        self,
        *,
        timeout_ms: int | None = None,
        threshold: float = 0.8,
        missing_threshold: int = 3,
    ) -> None:
        """Wait until the auto-pathfinding indicator disappears."""
        self.wait_image_missing(
            self.TEXT_AUTO_PATH,
            timeout_ms=timeout_ms,
            threshold=threshold,
            missing_threshold=missing_threshold,
            callback=lambda found, count: self._log("自动寻路中..."),
        )

    def require_image(
        self,
        template: str | list[str],
        *,
        timeout_ms: int | None,
        description: str,
        threshold: float = 0.8,
    ) -> None:
        """Wait for an image and fail the step if it is not found."""
        if not self.wait_image_appear(template, timeout_ms=timeout_ms, threshold=threshold):
            raise RuntimeError(f"未找到{description}")

    def ensure_bangpai_activity_tab(self, max_attempts: int = 3) -> None:
        """Switch to the activity Bangpai tab and verify it is active."""
        self.open_activity_category("帮派", max_attempts=max_attempts)

    def wait_find_image_in_roi(
        self,
        template: str | list[str],
        roi: tuple[int, int, int, int],
        *,
        timeout_ms: int | None,
        description: str,
        threshold: float = 0.8,
        interval_ms: int = 500,
    ) -> bool:
        """Wait for an image inside a design-resolution ROI."""
        deadline = None if timeout_ms is None else time.perf_counter() + timeout_ms / 1000.0
        scaled_roi = self.scale_roi(roi)

        while deadline is None or time.perf_counter() < deadline:
            if self.find_image(template, threshold=threshold, roi=scaled_roi):
                return True
            self.wait(interval_ms)

        self._log(f"未找到{description}")
        return False

    def scale_roi(self, roi: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """Return a fixed 1280x720 ROI without runtime resolution scaling."""
        return roi
