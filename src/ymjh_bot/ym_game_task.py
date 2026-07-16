"""Shared task base for Yi Meng Jiang Hu automation."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from botCore import GameTask, RunLogger, StepStopException, VisionEngine
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

    STARTUP_LOG_DISPLAY_NAME: str | None = None
    DEFER_FOREGROUND_WAKE_TO_ON_START = False
    RETURN_TO_SAFE_ZONE_ON_START = False
    LEAVE_TEAM_ON_START = False
    STARTUP_CLOSE_SETTLE_WAIT_MS = 0
    STARTUP_FINAL_CLOSE_TIMEOUT_MS = 3000
    SAFE_ZONE_RETURN_FAILURE_LOG = "返回安全区未完成，保持当前主界面继续：{error}"

    TEMPLATES_DIR = TEMPLATES_DIR

    BTN_OK = str(TEMPLATES_DIR / "btn_OK.png")
    BTN_CLOSE = str(TEMPLATES_DIR / "btn_close.png")
    BTN_PANE_CLOSE = str(TEMPLATES_DIR / "btn_pane_close.png")
    BTN_MODAL_OK = str(TEMPLATES_DIR / "btn_modal_ok.png")
    BTN_QUICK_MENU_FLOWER = str(TEMPLATES_DIR / "btn_quick_menu_flower.png")
    BTN_QUICK_MENU_FLOWER_NEW = str(TEMPLATES_DIR / "btn_quick_menu_flower_new.png")
    BTN_ESCAPE_STUCK = str(TEMPLATES_DIR / "btn_escape_stuck.png")
    BTN_WELCOME_CLOSE = str(TEMPLATES_DIR / "btn_welcome_close.png")
    BTN_ROLE_CONFIRM = str(TEMPLATES_DIR / "btn_role_confirm.png")
    BTN_HD = str(TEMPLATES_DIR / "btn_HD.png")
    BTN_JRYX = str(TEMPLATES_DIR / "btn_JRYX.png")
    BTN_TRJH = str(TEMPLATES_DIR / "btn_TRJH.png")
    BTN_ZZDL = str(TEMPLATES_DIR / "btn_ZZDL.png")
    BTN_BIAOQING = str(TEMPLATES_DIR / "btn_biaoqing.png")
    BTN_CHAT_SEND = str(TEMPLATES_DIR / "btn_chat_send.png")
    BTN_EMOTION_MEDITATE = str(TEMPLATES_DIR / "btn_emotion_meditate.png")
    HEALTH_BAR_ANCHOR = str(TEMPLATES_DIR / "health_bar_anchor.png")
    ICON_TASK_ACTIVE = str(TEMPLATES_DIR / "icon_task_active.png")
    ICON_TASK_RW = str(TEMPLATES_DIR / "icon_task_rw.png")
    ICON_TASK_JH = str(TEMPLATES_DIR / "icon_task_jh.png")
    ICON_TASK_QY = str(TEMPLATES_DIR / "icon_task_qy.png")
    TEXT_TASK_PANEL_TITLE = str(TEMPLATES_DIR / "text_task_panel_title.png")
    TEXT_AUTO_PATH = str(TEMPLATES_DIR / "text_zidongxunlu.png")
    TEXT_POWER_SAVING = str(TEMPLATES_DIR / "text_power_saving.png")
    ACTIVITY_TAB_JIANGHU_ACTIVE = str(TEMPLATES_DIR / "activity_tab_jianghu_active.png")
    ACTIVITY_TAB_BANGPAI_ACTIVE = str(TEMPLATES_DIR / "activity_tab_bangpai_active.png")
    ACTIVITY_TAB_FENZHENG_ACTIVE = str(TEMPLATES_DIR / "activity_tab_fenzheng_active.png")
    ACTIVITY_TAB_HANGDANG_ACTIVE = str(TEMPLATES_DIR / "activity_tab_hangdang_active.png")
    ACTIVITY_TAB_YOULI_ACTIVE = str(TEMPLATES_DIR / "activity_tab_youli_active.png")
    ACTIVITY_TAB_SHEJIAO_ACTIVE = str(TEMPLATES_DIR / "activity_tab_shejiao_active.png")
    MAP_BTN_WORLD = str(TEMPLATES_DIR / "map_btn_world.png")
    MAP_BTN_REGION = str(TEMPLATES_DIR / "map_btn_region.png")
    MAP_WORLD_JINLING = str(TEMPLATES_DIR / "map_world_jinling.png")
    MAP_JINLING_JIMING_TEMPLE = str(TEMPLATES_DIR / "map_jinling_jiming_temple.png")
    ICON_SAFE_POINT = str(TEMPLATES_DIR / "icon_safe_point.png")
    ICON_SAFE_POINT_CURRENT = str(TEMPLATES_DIR / "icon_safe_point_current.png")
    TEXT_TEAM_PANEL_TITLE = str(TEMPLATES_DIR / "text_team_panel_title.png")
    BTN_TEAM_QUICK = str(TEMPLATES_DIR / "btn_team_quick.png")
    BTN_TEAM_LEAVE = str(TEMPLATES_DIR / "btn_team_leave.png")
    BTN_TEAM_AUTO_MATCH = str(TEMPLATES_DIR / "btn_team_auto_match.png")
    BTN_TEAM_CREATE_10_RAID = str(TEMPLATES_DIR / "btn_team_create_10_raid.png")
    BTN_TEAM_CANCEL_MATCH = str(TEMPLATES_DIR / "btn_team_cancel_match.png")
    BTN_TEAM_REFRESH_LIST = str(TEMPLATES_DIR / "btn_team_refresh_list.png")
    BTN_TEAM_FOLLOW_OK = str(TEMPLATES_DIR / "btn_team_follow_ok.png")
    ICON_TEAM_SHOUT = str(TEMPLATES_DIR / "icon_team_shout.png")
    ICON_TEAM_EMPTY_SLOT = str(TEMPLATES_DIR / "icon_team_empty_slot.png")
    TEXT_TEAM_QUICK_CATEGORY_HANGDANG = str(TEMPLATES_DIR / "text_team_quick_category_hangdang.png")
    TEXT_TEAM_QUICK_CATEGORY_HANGDANG_ACTIVE = str(TEMPLATES_DIR / "text_team_quick_category_hangdang_active.png")
    TEXT_TEAM_QUICK_CATEGORY_JIANGHU = str(TEMPLATES_DIR / "text_team_quick_category_jianghu.png")
    TEXT_TEAM_QUICK_CATEGORY_JIANGHU_ACTIVE = str(TEMPLATES_DIR / "text_team_quick_category_jianghu_active.png")
    TEXT_TEAM_TARGET_JIANGHU_XINGSHANG = str(TEMPLATES_DIR / "text_team_target_jianghu_xingshang.png")
    TEXT_TEAM_TARGET_JUYI_PINGYUAN = str(TEMPLATES_DIR / "text_team_target_juyi_pingyuan.png")
    TEXT_TEAM_TARGET_DAILY = str(TEMPLATES_DIR / "text_team_target_daily.png")

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
    POINT_MAIN_TEAM_WHEN_TASK_PANEL_OPEN = (22, 420)
    POINT_MINIMAP = (1260, 90)
    POINT_SAFE_POINT_FALLBACK = (535, 35)
    POINT_TEAM_QUICK_BOTTOM = (1106, 663)
    POINT_TEAM_QUICK_RETURN = (1150, 116)
    POINT_TEAM_LEAVE = (1106, 663)
    POINT_TEAM_START_MATCH = (295, 663)
    POINT_TEAM_SHOUT = (613, 116)
    POINT_TASK_TAB_TASK = (88, 124)
    POINT_TASK_TAB_JIANGHU = (174, 124)
    POINT_TASK_TAB_QIYU = (258, 124)
    POINT_EMOTION_SINGLE_TAB = (405, 505)
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

    ROI_HEALTH_ANCHOR_SEARCH = (0, 0, 380, 90)
    ROI_HEALTH_BAR_FROM_ANCHOR = (1, 3, 260, 20)
    ROI_BIAOQING_BUTTON = (330, 650, 90, 70)
    ROI_EMOTION_PANEL = (250, 480, 730, 240)
    ROI_CHAT_SEND_BUTTON = (500, 640, 160, 80)
    ROI_POWER_SAVING = (480, 470, 340, 140)
    ROI_CENTER_MODAL_OK = (730, 440, 250, 120)
    ROI_ACTIVITY_CATEGORY_TABS = (40, 630, 930, 90)
    ROI_QUICK_MENU_BUTTON = (0, 600, 120, 120)
    ROI_ESCAPE_STUCK_ITEM = (220, 450, 150, 110)
    ROI_MAP_WORLD_BUTTON = (1160, 610, 120, 110)
    ROI_MAP_REGION_BUTTON = (1160, 610, 120, 110)
    ROI_MAP_WORLD_JINLING = (850, 120, 120, 170)
    ROI_MAP_JINLING_JIMING_TEMPLE = (460, 60, 130, 140)
    ROI_MAP_SAFE_POINT = (440, 0, 130, 80)
    ROI_MAP_CLOSE = (1180, 0, 100, 95)
    ROI_TASK_PANEL_TITLE = (190, 35, 180, 100)
    ROI_TEAM_PANEL_TITLE = (35, 0, 170, 65)
    ROI_TEAM_PANEL_BOTTOM_RIGHT = (1010, 600, 220, 115)
    ROI_TEAM_QUICK_ACTIONS = (880, 620, 370, 90)
    ROI_TEAM_QUICK_LEFT_PANEL = (40, 90, 280, 560)
    ROI_TEAM_CREATE_ACTION = (320, 620, 190, 90)
    ROI_TEAM_MATCH_ACTION = (230, 620, 140, 90)
    ROI_TEAM_SHOUT = (580, 85, 80, 65)
    ROI_TEAM_MEMBER_SLOTS = (
        (275, 250, 70, 80),
        (465, 250, 70, 80),
        (655, 250, 70, 80),
        (845, 250, 70, 80),
        (1035, 250, 70, 80),
        (275, 435, 70, 80),
        (465, 435, 70, 80),
        (655, 435, 70, 80),
        (845, 435, 70, 80),
        (1035, 435, 70, 80),
    )
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
    HEALTH_BAR_ANCHOR_THRESHOLD = 0.80
    EMOTION_MEDITATE_THRESHOLD = 0.90
    ESCAPE_STUCK_MENU_THRESHOLD = 0.90
    ESCAPE_STUCK_ITEM_THRESHOLD = 0.90
    ESCAPE_STUCK_CONFIRM_THRESHOLD = 0.95
    ESCAPE_STUCK_MENU_TIMEOUT_MS = 1500
    ESCAPE_STUCK_ITEM_TIMEOUT_MS = 2500
    ESCAPE_STUCK_CONFIRM_TIMEOUT_MS = 3000
    ESCAPE_STUCK_POLL_INTERVAL_MS = 300
    ESCAPE_STUCK_MENU_OPEN_WAIT_MS = 500
    ESCAPE_STUCK_CLEANUP_TIMEOUT_MS = 1000
    ESCAPE_STUCK_COMPLETE_WAIT_MS = 8000
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
    ACTIVITY_PANEL_TEMPLATES = list(ACTIVITY_CATEGORY_TEMPLATES.values())
    ACTIVITY_PANEL_OPEN_ATTEMPTS = 2
    ACTIVITY_ENTRY_FIND_TIMEOUT_MS = 5000
    ACTIVITY_PANEL_VERIFY_TIMEOUT_MS = 3000
    ACTIVITY_OPERATION_TIMEOUT_MS = 30000
    ACTIVITY_CATEGORY_VERIFY_TIMEOUT_MS = 1500
    ACTIVITY_CATEGORY_VERIFY_THRESHOLD = 0.85
    MAP_TEMPLATE_THRESHOLD = 0.9
    MAP_OPEN_TIMEOUT_MS = 2500
    MAP_SWITCH_TIMEOUT_MS = 5000
    MAP_STATE_POLL_INTERVAL_MS = 300
    AUTO_PATH_START_TIMEOUT_MS = 5000
    SAFE_ZONE_RETURN_MAX_ATTEMPTS = 3
    TEAM_RECRUIT_INTERVAL_MS = 10000
    TEAM_TEMPLATE_THRESHOLD = 0.9
    TASK_PANEL_ACTIVE_WAIT_MS = 3000
    TASK_PANEL_TITLE_THRESHOLD = 0.9
    MAP_CLOSE_TEMPLATES = [BTN_CLOSE, BTN_WELCOME_CLOSE, BTN_PANE_CLOSE]
    ICON_SAFE_POINT_TEMPLATES = [ICON_SAFE_POINT, ICON_SAFE_POINT_CURRENT]

    TEAM_TARGET_JIANGHU_XINGSHANG = "行当玩法-江湖行商"
    TEAM_TARGET_JUYI_PINGYUAN = "行当玩法-聚义平冤"
    TEAM_TARGET_JIANGHU_DAILY = "江湖纪事-日常"
    TEAM_TARGET_ALIASES = {
        "江湖行商": TEAM_TARGET_JIANGHU_XINGSHANG,
        "行当玩法-江湖行商": TEAM_TARGET_JIANGHU_XINGSHANG,
        "聚义平冤": TEAM_TARGET_JUYI_PINGYUAN,
        "行当玩法-聚义平冤": TEAM_TARGET_JUYI_PINGYUAN,
        "日常": TEAM_TARGET_JIANGHU_DAILY,
        "江湖纪事-日常": TEAM_TARGET_JIANGHU_DAILY,
        "落日马场-日常": TEAM_TARGET_JIANGHU_DAILY,
    }
    TEAM_TARGET_CONFIGS = {
        TEAM_TARGET_JIANGHU_XINGSHANG: {
            "display": "行当玩法-江湖行商",
            "quick_category_templates": [
                TEXT_TEAM_QUICK_CATEGORY_HANGDANG,
                TEXT_TEAM_QUICK_CATEGORY_HANGDANG_ACTIVE,
            ],
            "quick_item_template": TEXT_TEAM_TARGET_JIANGHU_XINGSHANG,
        },
        TEAM_TARGET_JUYI_PINGYUAN: {
            "display": "行当玩法-聚义平冤",
            "quick_category_templates": [
                TEXT_TEAM_QUICK_CATEGORY_HANGDANG,
                TEXT_TEAM_QUICK_CATEGORY_HANGDANG_ACTIVE,
            ],
            "quick_item_template": TEXT_TEAM_TARGET_JUYI_PINGYUAN,
        },
        TEAM_TARGET_JIANGHU_DAILY: {
            "display": "江湖纪事-日常",
            "quick_category_templates": [
                TEXT_TEAM_QUICK_CATEGORY_JIANGHU,
                TEXT_TEAM_QUICK_CATEGORY_JIANGHU_ACTIVE,
            ],
            "quick_item_template": TEXT_TEAM_TARGET_DAILY,
        },
    }

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
    ACTIVITY_ENTRY_CLICK_UP_OFFSET = 10

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
        if not self.auto_ensure_game_started:
            return

        if self.DEFER_FOREGROUND_WAKE_TO_ON_START and self.is_game_foreground():
            self._log("检测到游戏已在前台，省电唤醒交给 on_start")
            return

        self.ensure_game_started()

    def reset_startup_state(self) -> None:
        """Reset task-specific state before the shared startup cleanup."""

    def after_startup_panel_close(self) -> None:
        """Handle task-specific dialogs after each startup panel cleanup pass."""

    def on_start(self) -> None:
        """Log task startup and normalize the game scene before DSL steps run."""
        self.reset_startup_state()
        task_name = self.STARTUP_LOG_DISPLAY_NAME or getattr(self, "task_name", self.__class__.__name__)
        suffix = "" if task_name.endswith("任务") else "任务"
        self._log("=" * 40)
        self._log(f"{task_name}{suffix}开始")
        self._log("=" * 40)

        self.close_all_panels()
        self.after_startup_panel_close()
        if self.wake_from_power_saving_if_needed():
            self.close_all_panels()
            self.after_startup_panel_close()

        if self.STARTUP_CLOSE_SETTLE_WAIT_MS:
            self.wait(self.STARTUP_CLOSE_SETTLE_WAIT_MS)

        if self.RETURN_TO_SAFE_ZONE_ON_START:
            try:
                self.return_to_safe_zone()
            except RuntimeError as exc:
                self._log(self.SAFE_ZONE_RETURN_FAILURE_LOG.format(error=exc))

        if self.LEAVE_TEAM_ON_START:
            self.leave_team_if_present()
            self.close_all_panels(timeout_ms=self.STARTUP_FINAL_CLOSE_TIMEOUT_MS)

    def before_step(self, step_name: str, step_meta: dict[str, Any]) -> None:
        """Run shared Yi Meng Jiang Hu guards before each task step."""
        super().before_step(step_name, step_meta)
        self.recover_health_if_needed()

    def before_retry(
        self,
        retry_scope: str,
        failure: Exception | str | None = None,
    ) -> None:
        """Try image-only stuck recovery before an abnormal retry starts."""
        super().before_retry(retry_scope, failure)
        scope_name = "步骤" if retry_scope == "step" else "任务"
        self._log(f"{scope_name}异常即将重试，尝试脱离卡死")
        if not self.try_escape_stuck():
            self._log("脱离卡死未完成，保持原异常并继续正常重试")

    def try_escape_stuck(self) -> bool:
        """Try the strict image-only escape flow twice with one cleanup between attempts."""
        for attempt in range(1, 3):
            try:
                if self._try_escape_stuck_once(attempt):
                    return True
            except StepStopException:
                raise
            except Exception as exc:
                self._log(f"第 {attempt}/2 次脱离卡死识图流程异常：{exc}")

            if attempt == 1:
                self._log("首次脱离卡死识别未完成，关闭面板后再完整尝试一次")
                try:
                    self.close_all_panels(timeout_ms=self.ESCAPE_STUCK_CLEANUP_TIMEOUT_MS)
                except StepStopException:
                    raise
                except Exception as exc:
                    self._log(f"脱离卡死重试前关闭面板失败：{exc}")

        return False

    def _try_escape_stuck_once(self, attempt: int) -> bool:
        menu_templates = [self.BTN_QUICK_MENU_FLOWER, self.BTN_QUICK_MENU_FLOWER_NEW]
        if not self.wait_find_image_in_roi(
            menu_templates,
            self.ROI_QUICK_MENU_BUTTON,
            timeout_ms=self.ESCAPE_STUCK_MENU_TIMEOUT_MS,
            description="右下角菜单按钮",
            threshold=self.ESCAPE_STUCK_MENU_THRESHOLD,
            interval_ms=self.ESCAPE_STUCK_POLL_INTERVAL_MS,
        ):
            self._log(f"第 {attempt}/2 次未识别到菜单按钮，不执行任何兜底点击")
            return False

        if not self.find_image(
            self.BTN_ESCAPE_STUCK,
            threshold=self.ESCAPE_STUCK_ITEM_THRESHOLD,
            roi=self.scale_roi(self.ROI_ESCAPE_STUCK_ITEM),
        ):
            if not self.wait_find_image_in_roi(
                menu_templates,
                self.ROI_QUICK_MENU_BUTTON,
                timeout_ms=self.ESCAPE_STUCK_MENU_TIMEOUT_MS,
                description="右下角菜单按钮复核",
                threshold=self.ESCAPE_STUCK_MENU_THRESHOLD,
                interval_ms=self.ESCAPE_STUCK_POLL_INTERVAL_MS,
            ):
                self._log(f"第 {attempt}/2 次菜单按钮复核失败，不执行点击")
                return False

            self._log("识别到菜单按钮，点击模板中心打开功能面板")
            self.click(offset=0)
            self.wait(self.ESCAPE_STUCK_MENU_OPEN_WAIT_MS)
            if not self.wait_find_image_in_roi(
                self.BTN_ESCAPE_STUCK,
                self.ROI_ESCAPE_STUCK_ITEM,
                timeout_ms=self.ESCAPE_STUCK_ITEM_TIMEOUT_MS,
                description="脱离卡死菜单项",
                threshold=self.ESCAPE_STUCK_ITEM_THRESHOLD,
                interval_ms=self.ESCAPE_STUCK_POLL_INTERVAL_MS,
            ):
                self._log(f"第 {attempt}/2 次未识别到脱离卡死，不执行任何兜底点击")
                return False

        self._log("识别到脱离卡死，点击模板中心")
        self.click(offset=0)
        if not self.wait_find_image_in_roi(
            self.BTN_MODAL_OK,
            self.ROI_CENTER_MODAL_OK,
            timeout_ms=self.ESCAPE_STUCK_CONFIRM_TIMEOUT_MS,
            description="脱离卡死确认按钮",
            threshold=self.ESCAPE_STUCK_CONFIRM_THRESHOLD,
            interval_ms=self.ESCAPE_STUCK_POLL_INTERVAL_MS,
        ):
            self._log(f"第 {attempt}/2 次未识别到脱离卡死确认按钮，不执行任何兜底点击")
            return False

        self._log("识别到脱离卡死确认按钮，点击模板中心")
        self.click(offset=0)
        self.wait(self.ESCAPE_STUCK_COMPLETE_WAIT_MS)
        self._log("脱离卡死完成")
        return True

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
        vision = getattr(self, "_vision", None)
        if vision is None:
            vision = VisionEngine()
            self._vision = vision

        anchor = vision.match_template(
            screenshot,
            self.HEALTH_BAR_ANCHOR,
            threshold=self.HEALTH_BAR_ANCHOR_THRESHOLD,
            roi=self.ROI_HEALTH_ANCHOR_SEARCH,
        )
        self._last_match_score = anchor.score
        if not anchor.found or not anchor.bbox:
            return None

        anchor_x, anchor_y, _, _ = anchor.bbox
        offset_x, offset_y, width, height = self.ROI_HEALTH_BAR_FROM_ANCHOR
        x = anchor_x + offset_x
        y = anchor_y + offset_y
        x2 = x + width
        y2 = y + height
        if x < 0 or y < 0 or x2 > screen_width or y2 > screen_height:
            return None

        region = screenshot[y:y2, x:x2, :3]
        if region.size == 0:
            return None

        red_columns = self._red_health_columns(region)
        filled_width = self._anchored_true_run(red_columns, reference_width=width)
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
            if not self.click_template_if_available(
                self.BTN_EMOTION_MEDITATE,
                timeout_ms=3000,
                description="打坐表情",
                threshold=self.EMOTION_MEDITATE_THRESHOLD,
                roi=self.ROI_EMOTION_PANEL,
                wait_after_click_ms=1000,
            ):
                raise RuntimeError("未找到打坐表情")

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

    def _anchored_true_run(self, values: np.ndarray, *, reference_width: int | None = None) -> int:
        reference_width = max(1, reference_width or len(values))
        anchor_start = int(round(self.HEALTH_ANCHOR_START_COLUMN * len(values) / reference_width))
        anchor_end = int(round(self.HEALTH_ANCHOR_END_COLUMN * len(values) / reference_width))
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
                role_entry_center = self._last_match_center
                if self.confirm_center_modal_ok_if_visible(
                    "在线角色确认",
                    wait_after_click_ms=self.LOGIN_WAIT_AFTER_CLICK_MS,
                ):
                    continue
                if role_entry_center:
                    self.tap(*role_entry_center)
                else:
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
        max_attempts: int | None = None,
    ) -> None:
        """Close visible panels by repeatedly tapping known close buttons."""
        targets = templates or [self.BTN_CLOSE, self.BTN_PANE_CLOSE, self.BTN_WELCOME_CLOSE]
        effective_max_attempts = max_attempts
        if effective_max_attempts is None:
            effective_max_attempts = getattr(self, "CLOSE_ALL_MAX_ATTEMPTS", None)
        close_purchase_dialog = getattr(self, "close_purchase_dialog_if_needed", None)
        attempts = 0
        reached_limit = False
        self.collapse_chat_if_open()

        while True:
            if effective_max_attempts is not None and attempts >= effective_max_attempts:
                reached_limit = True
                break

            if callable(close_purchase_dialog) and close_purchase_dialog():
                attempts += 1
                continue

            if not self.wait_image_appear(targets, timeout_ms=timeout_ms):
                break

            self.click()
            self.wait(wait_after_click_ms)
            attempts += 1

        self.collapse_chat_if_open()
        if reached_limit:
            self._log(f"关闭弹窗达到上限 {effective_max_attempts} 次，继续后续流程")
        else:
            self._log("已关闭所有弹窗")

    def return_to_safe_zone(
        self,
        path_timeout_ms: int = 90000,
        wait_after_click_ms: int = 1000,
    ) -> None:
        """Use the map to auto-path back to Jinling Jiming Temple."""
        if not self.is_game_main_ready():
            raise RuntimeError("当前不是干净主界面，无法返回鸡鸣寺安全区")

        for attempt in range(1, self.SAFE_ZONE_RETURN_MAX_ATTEMPTS + 1):
            self._log(f"开始返回鸡鸣寺安全区，第 {attempt}/{self.SAFE_ZONE_RETURN_MAX_ATTEMPTS} 次")
            self.ensure_local_map_open(wait_after_click_ms=wait_after_click_ms)
            self.ensure_world_map_open(wait_after_click_ms=wait_after_click_ms)
            self.ensure_jinling_region_map_open(wait_after_click_ms=wait_after_click_ms)
            if self.click_safe_point_and_verify_auto_path(wait_after_click_ms=wait_after_click_ms):
                break

            self._log(f"第 {attempt} 次点击鸡鸣寺安全点后未检测到自动寻路，清理界面后重试")
            self.close_all_panels()
            if attempt >= self.SAFE_ZONE_RETURN_MAX_ATTEMPTS:
                debug_path = self.save_debug_screenshot("safe_zone_auto_path_not_started")
                raise RuntimeError(f"点击鸡鸣寺安全点后未开始自动寻路，已保存截图：{debug_path}")

        self.wait_auto_pathfinding(timeout_ms=path_timeout_ms)
        self._log("已回到鸡鸣寺安全区")

    def ensure_local_map_open(self, *, wait_after_click_ms: int) -> None:
        """Open and verify the local/region map."""
        if self.is_local_map_visible_quiet():
            return

        self._log("点击小地图打开区域地图")
        self.click_point(self.POINT_MINIMAP[0], self.POINT_MINIMAP[1], offset=0)
        self.wait(wait_after_click_ms)
        if self.wait_until_map_state(
            self.is_local_map_visible_quiet,
            timeout_ms=self.MAP_OPEN_TIMEOUT_MS,
        ):
            return

        self._raise_map_state_error("safe_zone_open_local_map_failed", "未打开大地图/区域地图")

    def ensure_world_map_open(self, *, wait_after_click_ms: int) -> None:
        """Switch from the local map to the world map and verify it."""
        if self.is_world_map_visible_quiet():
            return

        try:
            self._click_map_target(
                self.MAP_BTN_WORLD,
                self.ROI_MAP_WORLD_BUTTON,
                "地图世界按钮",
                wait_after_click_ms=wait_after_click_ms,
            )
        except RuntimeError as exc:
            self._raise_map_state_error("safe_zone_open_world_map_failed", str(exc))

        if self.wait_until_map_state(
            self.is_world_map_visible_quiet,
            timeout_ms=self.MAP_SWITCH_TIMEOUT_MS,
        ):
            return

        self._raise_map_state_error("safe_zone_open_world_map_failed", "未进入世界地图")

    def ensure_jinling_region_map_open(self, *, wait_after_click_ms: int) -> None:
        """Switch from the world map to Jinling's region map and verify it."""
        if self.is_local_map_visible_quiet() and not self.is_world_map_visible_quiet():
            return

        try:
            self._click_map_target(
                self.MAP_WORLD_JINLING,
                self.ROI_MAP_WORLD_JINLING,
                "世界地图金陵",
                wait_after_click_ms=wait_after_click_ms,
            )
        except RuntimeError as exc:
            self._raise_map_state_error("safe_zone_open_jinling_map_failed", str(exc))

        if self.wait_until_map_state(
            self.is_local_map_visible_quiet,
            timeout_ms=self.MAP_SWITCH_TIMEOUT_MS,
        ):
            return

        self._raise_map_state_error("safe_zone_open_jinling_map_failed", "未进入金陵区域地图")

    def click_safe_point_and_verify_auto_path(self, *, wait_after_click_ms: int) -> bool:
        """Click the Jiming Temple safe point and verify auto-pathfinding starts."""
        if not self.click_template_if_available(
            self.ICON_SAFE_POINT_TEMPLATES,
            timeout_ms=5000,
            description="鸡鸣寺安全点",
            threshold=self.MAP_TEMPLATE_THRESHOLD,
            roi=self.ROI_MAP_SAFE_POINT,
            wait_after_click_ms=wait_after_click_ms,
        ):
            self._log("未找到鸡鸣寺安全点模板，使用固定坐标兜底点击")
            self.click_point(self.POINT_SAFE_POINT_FALLBACK[0], self.POINT_SAFE_POINT_FALLBACK[1], offset=0)
            self.wait(wait_after_click_ms)

        self.close_map_if_open(wait_after_click_ms=wait_after_click_ms)
        return self.wait_auto_pathfinding_started()

    def wait_auto_pathfinding_started(self, timeout_ms: int | None = None) -> bool:
        """Wait until the auto-pathfinding indicator appears."""
        found = self.wait_image_appear(
            self.TEXT_AUTO_PATH,
            timeout_ms=timeout_ms or self.AUTO_PATH_START_TIMEOUT_MS,
            threshold=0.8,
        )
        if not found:
            self._log(f"未检测到自动寻路标志，最高得分 {self._last_match_score:.3f}")
        return found

    def close_map_if_open(self, *, wait_after_click_ms: int) -> None:
        """Close the map when it remains open after choosing a destination."""
        if self.click_template_if_available(
            self.MAP_CLOSE_TEMPLATES,
            timeout_ms=1500,
            description="地图关闭按钮",
            threshold=self.MAP_TEMPLATE_THRESHOLD,
            roi=self.ROI_MAP_CLOSE,
            wait_after_click_ms=wait_after_click_ms,
        ):
            return

        self._log("未检测到地图关闭按钮，可能已自动关闭地图，继续等待自动寻路完成")

    def is_local_map_visible_quiet(self) -> bool:
        """Return whether a local/region map is visible."""
        if self.find_image_once(
            self.MAP_BTN_WORLD,
            threshold=self.MAP_TEMPLATE_THRESHOLD,
            roi=self.scale_roi(self.ROI_MAP_WORLD_BUTTON),
        ):
            return True
        return self.find_image_once(
            self.MAP_JINLING_JIMING_TEMPLE,
            threshold=self.MAP_TEMPLATE_THRESHOLD,
            roi=self.scale_roi(self.ROI_MAP_JINLING_JIMING_TEMPLE),
        )

    def is_world_map_visible_quiet(self) -> bool:
        """Return whether the world map is visible."""
        return self.find_image_once(
            self.MAP_BTN_REGION,
            threshold=self.MAP_TEMPLATE_THRESHOLD,
            roi=self.scale_roi(self.ROI_MAP_REGION_BUTTON),
        )

    def wait_until_map_state(self, predicate, *, timeout_ms: int) -> bool:
        """Wait until a map-state predicate succeeds."""
        deadline = self._make_deadline(timeout_ms)
        while not self._is_deadline_expired(deadline):
            if predicate():
                return True
            self.wait(self.MAP_STATE_POLL_INTERVAL_MS)
        return predicate()

    def _raise_map_state_error(self, prefix: str, message: str) -> None:
        debug_path = self.save_debug_screenshot(prefix)
        raise RuntimeError(f"{message}，已保存截图：{debug_path}")

    def _click_map_target(
        self,
        template: str | list[str],
        roi: tuple[int, int, int, int],
        description: str,
        *,
        wait_after_click_ms: int,
    ) -> None:
        if not self.wait_find_image_in_roi(
            template,
            roi,
            timeout_ms=5000,
            description=description,
            threshold=self.MAP_TEMPLATE_THRESHOLD,
        ):
            raise RuntimeError(f"未找到{description}")
        self.click(offset=0)
        self.wait(wait_after_click_ms)

    def save_debug_screenshot(self, prefix: str) -> str:
        """Save the current screen for debugging."""
        logger = self._logger
        if logger is None:
            logger = getattr(self, "_fallback_debug_logger", None)
        if logger is None:
            serial = str(getattr(getattr(self, "_adb", None), "serial", "debug") or "debug")
            safe_serial = re.sub(r"[^\w.-]+", "_", serial, flags=re.UNICODE).strip("._")
            logger = RunLogger(
                base_dir=self.TEMPLATES_DIR.parents[2] / "logs" / (safe_serial or "debug")
            )
            self._fallback_debug_logger = logger

        path = logger.save_screenshot(self.screenshot(), prefix=prefix)
        self._log(f"已保存调试截图：{path}")
        return path

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
                self._debug(f"Found image: {template} (score={match.score:.3f})")
            return True

        self._last_match_center = None
        if log_missing:
            self._debug(f"Image not found: {template} (score={match.score:.3f})")
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

    def normalize_team_target(self, target: str) -> str:
        """Normalize supported team target aliases to their canonical names."""
        normalized = self.TEAM_TARGET_ALIASES.get(target.strip())
        if normalized is None:
            raise ValueError(f"Unsupported team target: {target}")
        return normalized

    def is_team_panel_open(self) -> bool:
        """Return whether any team panel is visible."""
        return self.find_image_once(
            self.TEXT_TEAM_PANEL_TITLE,
            threshold=self.TEAM_TEMPLATE_THRESHOLD,
            roi=self.scale_roi(self.ROI_TEAM_PANEL_TITLE),
        )

    def is_quick_team_panel_open(self) -> bool:
        """Return whether the convenient team list is visible."""
        return self.find_image_once(
            self.BTN_TEAM_REFRESH_LIST,
            threshold=self.TEAM_TEMPLATE_THRESHOLD,
            roi=self.scale_roi(self.ROI_TEAM_QUICK_ACTIONS),
        )

    def is_in_team(self) -> bool:
        """Return whether the open normal team panel represents an active team."""
        return not self.find_image_once(
            self.BTN_TEAM_QUICK,
            threshold=self.TEAM_TEMPLATE_THRESHOLD,
            roi=self.scale_roi(self.ROI_TEAM_PANEL_BOTTOM_RIGHT),
        )

    def open_team_panel(
        self,
        *,
        timeout_ms: int = 3000,
        wait_after_click_ms: int = 1000,
    ) -> None:
        """Open the normal team panel from the left sidebar."""
        if self.is_quick_team_panel_open():
            self._log("当前在便捷组队界面，返回我的队伍")
            self.click_point(self.POINT_TEAM_QUICK_RETURN[0], self.POINT_TEAM_QUICK_RETURN[1], offset=0)
            self.wait(wait_after_click_ms)
            if self.is_quick_team_panel_open():
                raise RuntimeError("未能从便捷组队界面返回队伍面板")

        if self.is_team_panel_open():
            return

        self.collapse_chat_if_open()
        self._log("点击侧边栏队伍按钮")
        for index, point in enumerate((self.POINT_MAIN_TEAM, self.POINT_MAIN_TEAM_WHEN_TASK_PANEL_OPEN), start=1):
            self.click_point(point[0], point[1], offset=0)
            self.wait(wait_after_click_ms)
            if self.wait_find_image_in_roi(
                self.TEXT_TEAM_PANEL_TITLE,
                self.ROI_TEAM_PANEL_TITLE,
                timeout_ms=timeout_ms,
                description="队伍面板",
                threshold=self.TEAM_TEMPLATE_THRESHOLD,
            ):
                return
            if index == 1:
                self._log("常规队伍入口未打开面板，尝试任务栏展开状态下的队伍入口")

        raise RuntimeError("未能打开队伍面板")

    def open_quick_team_panel(
        self,
        *,
        timeout_ms: int = 3000,
        wait_after_click_ms: int = 1000,
    ) -> None:
        """Open the convenient team list from the team panel."""
        if self.is_quick_team_panel_open():
            return

        self.open_team_panel(timeout_ms=timeout_ms, wait_after_click_ms=wait_after_click_ms)
        if self.is_in_team():
            raise RuntimeError("当前已处于组队状态，请先退出队伍")

        self._log("打开便捷组队界面")
        self.click_point(self.POINT_TEAM_QUICK_BOTTOM[0], self.POINT_TEAM_QUICK_BOTTOM[1], offset=0)
        self.wait(wait_after_click_ms)
        if not self.wait_find_image_in_roi(
            self.BTN_TEAM_REFRESH_LIST,
            self.ROI_TEAM_QUICK_ACTIONS,
            timeout_ms=timeout_ms,
            description="便捷组队界面",
            threshold=self.TEAM_TEMPLATE_THRESHOLD,
        ):
            raise RuntimeError("未能打开便捷组队界面")

    def create_team(
        self,
        target: str,
        *,
        min_member_count: int = 3,
        timeout_ms: int = 5000,
        wait_after_click_ms: int = 1000,
    ) -> None:
        """Create a targeted 10-player raid and recruit until the minimum is reached."""
        if not 1 <= min_member_count <= len(self.ROI_TEAM_MEMBER_SLOTS):
            raise ValueError("min_member_count must be between 1 and 10")

        target_name = self.normalize_team_target(target)
        self.open_team_panel(timeout_ms=timeout_ms, wait_after_click_ms=wait_after_click_ms)
        if self.is_in_team():
            raise RuntimeError("当前已处于组队状态，请先退出队伍")

        self.open_quick_team_panel(timeout_ms=timeout_ms, wait_after_click_ms=wait_after_click_ms)
        self.select_quick_team_target(target_name, wait_after_click_ms=wait_after_click_ms)
        if not self.click_template_if_available(
            self.BTN_TEAM_CREATE_10_RAID,
            timeout_ms=timeout_ms,
            description="创建10人团按钮",
            threshold=self.TEAM_TEMPLATE_THRESHOLD,
            roi=self.ROI_TEAM_CREATE_ACTION,
            wait_after_click_ms=wait_after_click_ms,
        ):
            raise RuntimeError("未找到创建10人团按钮")

        if not self.wait_for_normal_team_state(expected_in_team=True, timeout_ms=timeout_ms):
            debug_path = self.save_debug_screenshot("team_create_state_failed")
            raise RuntimeError(f"创建队伍后未进入组队状态，已保存截图：{debug_path}")

        self._log("创建队伍成功，开始自动匹配")
        self.click_point(self.POINT_TEAM_START_MATCH[0], self.POINT_TEAM_START_MATCH[1], offset=0)
        self.wait(wait_after_click_ms)
        if not self.wait_find_image_in_roi(
            self.BTN_TEAM_CANCEL_MATCH,
            self.ROI_TEAM_MATCH_ACTION,
            timeout_ms=timeout_ms,
            description="取消匹配按钮",
            threshold=self.TEAM_TEMPLATE_THRESHOLD,
        ):
            debug_path = self.save_debug_screenshot("team_match_start_failed")
            raise RuntimeError(f"创建队伍后未进入匹配状态，已保存截图：{debug_path}")

        self._log(f"已进入自动匹配，等待队伍人数达到 {min_member_count}")
        self.wait_for_team_members(min_member_count)

    def quick_team(
        self,
        target: str,
        *,
        timeout_ms: int = 5000,
        wait_after_click_ms: int = 1000,
    ) -> None:
        """Use convenient team matching for a supported target."""
        target_name = self.normalize_team_target(target)
        self.open_quick_team_panel(timeout_ms=timeout_ms, wait_after_click_ms=wait_after_click_ms)
        self.select_quick_team_target(target_name, wait_after_click_ms=wait_after_click_ms)

        if not self.click_template_if_available(
            self.BTN_TEAM_AUTO_MATCH,
            timeout_ms=timeout_ms,
            description="自动匹配按钮",
            threshold=0.9,
            roi=self.ROI_TEAM_QUICK_ACTIONS,
            wait_after_click_ms=wait_after_click_ms,
        ):
            raise RuntimeError("未找到自动匹配按钮")

        self.confirm_center_modal_ok_if_visible("便捷组队自动匹配")
        self._log("已点击便捷组队自动匹配")

    def wait_for_normal_team_state(self, *, expected_in_team: bool, timeout_ms: int) -> bool:
        """Wait until the normal team panel shows the requested team state."""
        deadline = self._make_deadline(timeout_ms)
        while not self._is_deadline_expired(deadline):
            if (
                not self.is_quick_team_panel_open()
                and self.is_team_panel_open()
                and self.is_in_team() is expected_in_team
            ):
                return True
            self.wait(250)
        return False

    def is_team_matching(self, screenshot: np.ndarray | None = None) -> bool:
        """Return whether the normal team panel shows the cancel-match action."""
        screen = self.screenshot() if screenshot is None else screenshot
        match = self._match_team_template(
            screen,
            self.BTN_TEAM_CANCEL_MATCH,
            threshold=self.TEAM_TEMPLATE_THRESHOLD,
            roi=self.scale_roi(self.ROI_TEAM_MATCH_ACTION),
        )
        return match.found

    def count_team_members(self, screenshot: np.ndarray | None = None) -> int:
        """Count occupied slots in the current 10-player raid from one screenshot."""
        screen = self.screenshot() if screenshot is None else screenshot
        empty_count = 0
        for roi in self.ROI_TEAM_MEMBER_SLOTS:
            match = self._match_team_template(
                screen,
                self.ICON_TEAM_EMPTY_SLOT,
                threshold=0.85,
                roi=self.scale_roi(roi),
            )
            empty_count += int(match.found)
        return len(self.ROI_TEAM_MEMBER_SLOTS) - empty_count

    def click_team_shout(self, screenshot: np.ndarray | None = None) -> None:
        """Click the one-key shout speaker, falling back to its fixed point."""
        screen = self.screenshot() if screenshot is None else screenshot
        match = self._match_team_template(
            screen,
            self.ICON_TEAM_SHOUT,
            threshold=self.TEAM_TEMPLATE_THRESHOLD,
            roi=self.scale_roi(self.ROI_TEAM_SHOUT),
        )
        if match.found and match.center:
            self.click_point(match.center[0], match.center[1], offset=0)
            return

        self._log("未识别到一键喊话小喇叭，使用固定坐标点击")
        self.click_point(self.POINT_TEAM_SHOUT[0], self.POINT_TEAM_SHOUT[1], offset=0)

    def _match_team_template(
        self,
        screenshot: np.ndarray,
        template: str,
        *,
        threshold: float,
        roi: tuple[int, int, int, int],
    ):
        """Match a team template, lazily supplying vision for standalone helpers."""
        vision = getattr(self, "_vision", None)
        if vision is None:
            vision = VisionEngine()
            self._vision = vision
        return vision.match_template(screenshot, template, threshold=threshold, roi=roi)

    def wait_for_team_members(self, min_member_count: int) -> None:
        """Recruit indefinitely until the team reaches the requested size."""
        while True:
            if self.is_stopped():
                raise StepStopException("Stop requested")

            screen = self.screenshot()
            member_count = self.count_team_members(screen)
            if member_count >= min_member_count:
                self._log(f"队伍人数已达到要求：{member_count}/{min_member_count}")
                return

            if not self.is_team_matching(screen):
                debug_path = self.save_debug_screenshot("team_matching_interrupted")
                raise RuntimeError(f"队伍人数未达标时匹配状态已结束，已保存截图：{debug_path}")

            self._log(f"当前队伍人数：{member_count}/{min_member_count}，发送一键喊话")
            self.click_team_shout(screen)
            self.wait(self.TEAM_RECRUIT_INTERVAL_MS)

    def select_quick_team_target(
        self,
        target: str,
        *,
        wait_after_click_ms: int = 800,
    ) -> None:
        """Select a supported target in the convenient team left filter."""
        target_name = self.normalize_team_target(target)
        config = self.TEAM_TARGET_CONFIGS[target_name]
        item_template = config["quick_item_template"]

        if not self.click_template_if_available(
            item_template,
            timeout_ms=1000,
            description=f"便捷组队目标 {config['display']}",
            threshold=0.85,
            roi=self.ROI_TEAM_QUICK_LEFT_PANEL,
            wait_after_click_ms=wait_after_click_ms,
        ):
            if not self.click_template_if_available(
                config["quick_category_templates"],
                timeout_ms=2000,
                description=f"便捷组队分类 {config['display']}",
                threshold=0.85,
                roi=self.ROI_TEAM_QUICK_LEFT_PANEL,
                wait_after_click_ms=wait_after_click_ms,
            ):
                raise RuntimeError(f"未找到便捷组队分类：{config['display']}")
            if not self.click_template_if_available(
                item_template,
                timeout_ms=2000,
                description=f"便捷组队目标 {config['display']}",
                threshold=0.85,
                roi=self.ROI_TEAM_QUICK_LEFT_PANEL,
                wait_after_click_ms=wait_after_click_ms,
            ):
                raise RuntimeError(f"未找到便捷组队目标：{config['display']}")

        self._log(f"已选择便捷组队目标：{config['display']}")

    def leave_team(
        self,
        *,
        timeout_ms: int = 5000,
        wait_after_click_ms: int = 1000,
    ) -> bool:
        """Leave the current team if one exists."""
        self.open_team_panel()
        if not self.is_in_team():
            self._log("当前未组队，跳过退出队伍")
            return False

        self._log("退出队伍")
        self.click_point(self.POINT_TEAM_LEAVE[0], self.POINT_TEAM_LEAVE[1], offset=0)
        self.wait(wait_after_click_ms)
        self.confirm_center_modal_ok_if_visible("退出队伍确认", wait_after_click_ms=wait_after_click_ms)

        if not self.wait_find_image_in_roi(
            self.BTN_TEAM_QUICK,
            self.ROI_TEAM_PANEL_BOTTOM_RIGHT,
            timeout_ms=timeout_ms,
            description="未组队状态",
            threshold=0.9,
        ):
            raise RuntimeError("退出队伍后未回到未组队状态")

        return True

    def confirm_center_modal_ok_if_visible(
        self,
        description: str,
        *,
        wait_after_click_ms: int = 1000,
        threshold: float = 0.85,
    ) -> bool:
        """Click the centered OK button when a confirmation dialog is visible."""
        if not self.find_image_once(
            [self.BTN_MODAL_OK, self.BTN_TEAM_FOLLOW_OK],
            threshold=threshold,
            roi=self.scale_roi(self.ROI_CENTER_MODAL_OK),
        ):
            return False

        self._log(f"检测到{description}，点击确定")
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
        """Open and verify the activity panel before any category coordinate is tapped."""
        deadline = self._make_deadline(timeout_ms)
        self._ensure_activity_panel_open(
            deadline=deadline,
            wait_after_open_ms=wait_after_open_ms,
        )

        if category is None:
            return

        if isinstance(category, str):
            self._open_activity_category(
                category,
                max_attempts=3,
                wait_after_click_ms=wait_after_category_ms or 1500,
                deadline=deadline,
            )
            return

        if not self._is_activity_panel_open():
            self._raise_activity_error(
                "activity_coordinate_precondition_failed",
                "活动页状态丢失，禁止点击活动分类坐标",
            )

        self.click_point(category[0], category[1], offset=0)
        if wait_after_category_ms > 0:
            self._wait_with_deadline(wait_after_category_ms, deadline)

        template = self.ACTIVITY_CATEGORY_TEMPLATES.get(category_name or "")
        if template is not None:
            if not self._wait_activity_category_active(template, deadline=deadline):
                self._raise_activity_error(
                    "activity_coordinate_category_failed",
                    f"未能确认活动 - {category_name}界面",
                )
            self._log(f"已打开活动 - {category_name}界面")
            return

        if not self._wait_activity_panel_open(deadline=deadline):
            self._raise_activity_error(
                "activity_coordinate_panel_lost",
                "点击活动分类坐标后活动页状态丢失",
            )
        if category_name:
            self._log(f"已点击活动分类坐标 - {category_name}")

    def click_activity_entry(self) -> None:
        """Click the matched activity entry slightly above the template center."""
        if not self._last_match_center:
            return
        x, y = self._last_match_center
        self.tap(x, max(0, y - self.ACTIVITY_ENTRY_CLICK_UP_OFFSET))

    def open_activity_category(
        self,
        category_name: str,
        *,
        max_attempts: int = 3,
        wait_after_click_ms: int = 1500,
    ) -> None:
        deadline = self._make_deadline(self.ACTIVITY_OPERATION_TIMEOUT_MS)
        self._open_activity_category(
            category_name,
            max_attempts=max_attempts,
            wait_after_click_ms=wait_after_click_ms,
            deadline=deadline,
        )

    def _open_activity_category(
        self,
        category_name: str,
        *,
        max_attempts: int,
        wait_after_click_ms: int,
        deadline: float | None,
    ) -> None:
        point = self.ACTIVITY_CATEGORY_POINTS.get(category_name)
        template = self.ACTIVITY_CATEGORY_TEMPLATES.get(category_name)
        if point is None or template is None:
            raise ValueError(f"Unsupported activity category: {category_name}")

        if self._is_activity_category_active(template):
            self._log(f"已打开活动 - {category_name}界面")
            return

        for attempt in range(1, max_attempts + 1):
            if self._is_deadline_expired(deadline):
                break

            if not self._is_activity_panel_open():
                self._log(f"活动页状态丢失，重新打开后再切换到{category_name}")
                self._ensure_activity_panel_open(
                    deadline=deadline,
                    wait_after_open_ms=self.ACTIVITY_PANEL_VERIFY_TIMEOUT_MS,
                )

            if self._is_activity_category_active(template):
                self._log(f"已打开活动 - {category_name}界面")
                return

            self.click_point(point[0], point[1], offset=0)
            if wait_after_click_ms > 0:
                self._wait_with_deadline(wait_after_click_ms, deadline)
            if self._wait_activity_category_active(template, deadline=deadline):
                self._log(f"已打开活动 - {category_name}界面")
                return
            self._log(f"活动 - {category_name}界面未确认，重试 {attempt}/{max_attempts}")

        self._raise_activity_error(
            "activity_category_switch_failed",
            f"未能切换到活动 - {category_name}界面",
        )

    def _ensure_activity_panel_open(
        self,
        *,
        deadline: float | None,
        wait_after_open_ms: int,
    ) -> None:
        if self._is_activity_panel_open():
            self._log("已打开活动界面")
            return

        for attempt in range(1, self.ACTIVITY_PANEL_OPEN_ATTEMPTS + 1):
            if self._is_deadline_expired(deadline):
                break

            collapse_wait_ms = self._bounded_timeout_ms(deadline, 800)
            self.collapse_chat_if_open(wait_after_click_ms=collapse_wait_ms)

            entry_timeout_ms = self._bounded_timeout_ms(deadline, self.ACTIVITY_ENTRY_FIND_TIMEOUT_MS)
            if entry_timeout_ms <= 0:
                break
            if not self.wait_image_appear(self.BTN_HD, timeout_ms=entry_timeout_ms):
                self._log(f"未找到活动入口，重试打开活动界面 {attempt}/{self.ACTIVITY_PANEL_OPEN_ATTEMPTS}")
                continue

            self.click_activity_entry()
            verify_timeout_ms = max(wait_after_open_ms, self.ACTIVITY_PANEL_VERIFY_TIMEOUT_MS)
            if self._wait_activity_panel_open(
                deadline=deadline,
                timeout_ms=verify_timeout_ms,
            ):
                self._log("已打开活动界面")
                return

            self._log(f"活动入口点击后界面未确认，重试 {attempt}/{self.ACTIVITY_PANEL_OPEN_ATTEMPTS}")

        self._raise_activity_error(
            "activity_panel_open_failed",
            "未能确认活动界面已打开",
        )

    def _is_activity_panel_open(self) -> bool:
        return self.find_image_once(
            self.ACTIVITY_PANEL_TEMPLATES,
            threshold=self.ACTIVITY_CATEGORY_VERIFY_THRESHOLD,
            roi=self.scale_roi(self.ROI_ACTIVITY_CATEGORY_TABS),
        )

    def _wait_activity_panel_open(
        self,
        *,
        deadline: float | None,
        timeout_ms: int | None = None,
    ) -> bool:
        effective_timeout_ms = self._bounded_timeout_ms(
            deadline,
            timeout_ms or self.ACTIVITY_PANEL_VERIFY_TIMEOUT_MS,
        )
        if effective_timeout_ms <= 0:
            return False
        return self.wait_find_image_in_roi(
            self.ACTIVITY_PANEL_TEMPLATES,
            self.ROI_ACTIVITY_CATEGORY_TABS,
            timeout_ms=effective_timeout_ms,
            description="活动页底部分栏",
            threshold=self.ACTIVITY_CATEGORY_VERIFY_THRESHOLD,
            interval_ms=300,
        )

    def _is_activity_category_active(self, template: str) -> bool:
        return self.find_image_once(
            template,
            threshold=self.ACTIVITY_CATEGORY_VERIFY_THRESHOLD,
            roi=self.scale_roi(self.ROI_ACTIVITY_CATEGORY_TABS),
        )

    def _wait_activity_category_active(
        self,
        template: str,
        *,
        deadline: float | None,
    ) -> bool:
        timeout_ms = self._bounded_timeout_ms(deadline, self.ACTIVITY_CATEGORY_VERIFY_TIMEOUT_MS)
        if timeout_ms <= 0:
            return False
        return self.wait_find_image_in_roi(
            template,
            self.ROI_ACTIVITY_CATEGORY_TABS,
            timeout_ms=timeout_ms,
            description="活动分类激活状态",
            threshold=self.ACTIVITY_CATEGORY_VERIFY_THRESHOLD,
            interval_ms=300,
        )

    def _wait_with_deadline(self, wait_ms: int, deadline: float | None) -> None:
        bounded_wait_ms = self._bounded_timeout_ms(deadline, wait_ms)
        if bounded_wait_ms > 0:
            self.wait(bounded_wait_ms)

    def _bounded_timeout_ms(self, deadline: float | None, requested_ms: int) -> int:
        if deadline is None:
            return max(0, requested_ms)
        return max(0, min(requested_ms, self._remaining_ms(deadline)))

    def _raise_activity_error(self, screenshot_prefix: str, message: str) -> None:
        try:
            debug_path = self.save_debug_screenshot(screenshot_prefix)
        except Exception as exc:
            self._log(f"活动界面异常截图保存失败：{exc}")
            raise RuntimeError(message) from exc
        raise RuntimeError(f"{message}，已保存截图：{debug_path}")

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

            if not self.wait_image_appear(
                self.ICON_TASK_ACTIVE,
                timeout_ms=self.TASK_PANEL_ACTIVE_WAIT_MS,
                threshold=threshold,
            ):
                if not self.find_image(
                    self.TEXT_TASK_PANEL_TITLE,
                    threshold=self.TASK_PANEL_TITLE_THRESHOLD,
                    roi=self.scale_roi(self.ROI_TASK_PANEL_TITLE),
                ):
                    raise RuntimeError("未能打开任务侧栏")

                self._log("点击任务栏后打开全屏任务面板，关闭面板并恢复任务侧栏")
                self.close_all_panels()

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
            callback=lambda found, count: self._debug("自动寻路中..."),
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

    def click_template_if_available(
        self,
        template: str | list[str],
        *,
        timeout_ms: int | None = 3000,
        description: str,
        threshold: float = 0.8,
        roi: tuple[int, int, int, int] | None = None,
        wait_after_click_ms: int = 1000,
    ) -> bool:
        """Click a template when it appears, optionally constrained to a design-resolution ROI."""
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

        self.click(offset=0)
        if wait_after_click_ms > 0:
            self.wait(wait_after_click_ms)
        return True

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
