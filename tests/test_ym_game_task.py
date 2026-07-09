from pathlib import Path
import time

from botCore.vision import load_image
from ymjh_bot.task.QDYX_task import StartTask
from ymjh_bot.task.BPRW_task import BangpaiTask
from ymjh_bot.ui.task_queue_window import is_visible_task_class
from ymjh_bot.ym_game_task import LoginState, YmGameTask


GAME_WINDOW = "mCurrentFocus=Window{abc u0 com.netease.wyclx/com.netease.MainActivity}"
HOME_WINDOW = "mCurrentFocus=Window{abc u0 app.lawnchair/app.lawnchair.LawnchairLauncher}"


class ScriptedLoginTask(YmGameTask):
    LOGIN_TOTAL_TIMEOUT_MS = 500
    LOGIN_LOADING_TIMEOUT_MS = 50
    LOGIN_CLEANUP_TIMEOUT_MS = 200
    LOGIN_POLL_INTERVAL_MS = 10
    LOGIN_WAIT_AFTER_CLICK_MS = 10
    LOGIN_WAIT_AFTER_CLOSE_MS = 10

    def __init__(
        self,
        states: list[str | None] | None = None,
        *,
        process_output: str = "",
        window_output: str = GAME_WINDOW,
        window_error: bool = False,
        power_saving_results: list[bool] | None = None,
    ):
        super().__init__()
        self.states = states or []
        self.state_index = 0
        self.process_output = process_output
        self.window_output = window_output
        self.window_error = window_error
        self.power_saving_results = power_saving_results or []
        self.shell_calls: list[str] = []
        self.detect_calls: list[tuple[bool, float]] = []
        self.taps: list[str | None] = []
        self.clicked_points: list[tuple[int, int, int]] = []
        self.waits: list[int | float] = []
        self.logs: list[str] = []

    def shell(self, command: str) -> str:
        self.shell_calls.append(command)
        if command.startswith("pidof "):
            return self.process_output
        if command == "dumpsys window":
            if self.window_error:
                raise RuntimeError("dumpsys failed")
            return self.window_output
        return ""

    def detect_login_state(
        self,
        *,
        include_modal_controls: bool = False,
        threshold: float = 0.8,
    ) -> LoginState | None:
        self.detect_calls.append((include_modal_controls, threshold))
        state = self._current_state()
        if state is None:
            return None
        return LoginState(
            name=state,
            description=state,
            score=1.0,
            center=(100, 100),
            template_path=f"{state}.png",
        )

    def tap(self, x=None, y=None):
        state = self._current_state()
        self.taps.append(state)
        if state in {
            self.LOGIN_STATE_NOTICE,
            self.LOGIN_STATE_LOGIN,
            self.LOGIN_STATE_ROLE_CONFIRM,
            self.LOGIN_STATE_ROLE,
            self.LOGIN_STATE_POPUP,
        }:
            self._advance_state()

    def is_power_saving_mode(self) -> bool:
        return self.power_saving_results.pop(0) if self.power_saving_results else False

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.waits.append(ms)
        if self._current_state() is None and self.state_index < len(self.states) - 1:
            self._advance_state()
            return
        if ms:
            time.sleep(min(float(ms) / 1000.0, 0.01))

    def _log(self, message: str) -> None:
        self.logs.append(message)

    def _current_state(self) -> str | None:
        if not self.states:
            return None
        if self.state_index >= len(self.states):
            return self.states[-1]
        return self.states[self.state_index]

    def _advance_state(self) -> None:
        if self.state_index < len(self.states) - 1:
            self.state_index += 1


class FakeTaskPanelTask(ScriptedLoginTask):
    def __init__(self, image_results: list[bool]):
        super().__init__([])
        self.image_results = image_results
        self.wait_image_calls = []
        self.clicked_points = []
        self.wait_calls = []

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.wait_image_calls.append((template, timeout_ms, threshold))
        return self.image_results.pop(0)

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)


class HealthScreenshotTask(YmGameTask):
    def __init__(self, screenshot):
        super().__init__()
        self._screenshot = screenshot

    def screenshot(self):
        return self._screenshot


class FakeHealthRecoveryTask(YmGameTask):
    def __init__(self, health_ratios: list[float | None], *, emotion_found: bool = True):
        super().__init__()
        self.health_ratios = health_ratios
        self.emotion_found = emotion_found
        self.actions = []
        self.image_calls = []
        self.chat_collapse_calls = []
        self.wait_calls = []
        self.logs = []

    def collapse_chat_if_open(self, wait_after_click_ms: int = 800) -> bool:
        self.chat_collapse_calls.append(wait_after_click_ms)
        return False

    def detect_health_ratio(self) -> float | None:
        if not self.health_ratios:
            return None
        if len(self.health_ratios) == 1:
            return self.health_ratios[0]
        return self.health_ratios.pop(0)

    def find_image(self, template, threshold=0.8, roi=None) -> bool:
        self.image_calls.append((template, threshold, roi))
        if template == self.BTN_BIAOQING:
            self._last_match_center = (370, 692) if self.emotion_found else None
            return self.emotion_found
        return False

    def click(self, offset: int = 3) -> None:
        self.actions.append(("click", offset))

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.actions.append(("point", x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class FakeChatTask(YmGameTask):
    def __init__(self, chat_open_results: list[bool] | None = None, image_results: list[bool] | None = None):
        super().__init__()
        self.chat_open_results = chat_open_results or []
        self.image_results = image_results or []
        self.clicked_points = []
        self.wait_calls = []
        self.image_calls = []
        self.logs = []

    def is_chat_open(self) -> bool:
        return self.chat_open_results.pop(0) if self.chat_open_results else False

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.image_calls.append((template, timeout_ms, threshold))
        return self.image_results.pop(0) if self.image_results else False

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class FakeAutoBattleTask(YmGameTask):
    def __init__(self):
        super().__init__()
        self.actions = []
        self.wait_calls = []
        self.logs = []

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.actions.append(("point", x, y, offset))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
        self.actions.append(("swipe", x1, y1, x2, y2, duration_ms))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class FakeMovementTask(YmGameTask):
    def __init__(self, *, main_ready: bool = True, power_saving: bool = False):
        super().__init__()
        self.main_ready = main_ready
        self.power_saving = power_saving
        self.actions = []
        self.wait_calls = []
        self.main_ready_calls = []
        self.logs = []

    def is_game_main_ready(self, *, timeout_ms: int = 2000, threshold: float = 0.8) -> bool:
        self.main_ready_calls.append((timeout_ms, threshold))
        return self.main_ready

    def is_power_saving_mode(self) -> bool:
        return self.power_saving

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.actions.append(("point", x, y, offset))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
        self.actions.append(("swipe", x1, y1, x2, y2, duration_ms))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


class FakeFixedCoordinateTask(YmGameTask):
    def __init__(self):
        super().__init__()
        self.taps = []

    def tap(self, x=None, y=None):
        self.taps.append((x, y))


class FakeActivityPanelTask(YmGameTask):
    def __init__(self, image_results: list[bool]):
        super().__init__()
        self.image_results = image_results
        self.image_calls = []
        self.click_offsets = []
        self.clicked_points = []
        self.wait_calls = []
        self.logs = []

    def wait_image_appear(self, template, timeout_ms=10000, threshold=0.8, callback=None, interval_ms=500):
        self.image_calls.append((template, timeout_ms, threshold))
        return self.image_results.pop(0) if self.image_results else False

    def click(self, offset: int = 3) -> None:
        self.click_offsets.append(offset)

    def click_point(self, x: int, y: int, offset: int = 3) -> None:
        self.clicked_points.append((x, y, offset))

    def wait(self, ms):
        self.wait_calls.append(ms)

    def _log(self, message: str) -> None:
        self.logs.append(message)


def assert_value_error(message: str, callback) -> None:
    try:
        callback()
    except ValueError as exc:
        assert str(exc) == message
    else:
        raise AssertionError("Expected ValueError")


def auto_battle_round_actions(task: YmGameTask, repeat_count: int) -> list[tuple]:
    normal_attack = ("point", task.POINT_BATTLE_NORMAL_ATTACK[0], task.POINT_BATTLE_NORMAL_ATTACK[1], 0)
    return [
        *[normal_attack for _ in range(repeat_count)],
        *[
            ("point", x, y, 0)
            for x, y in task.POINT_BATTLE_SKILL_BUTTONS
            for _ in range(repeat_count)
        ],
    ]


def test_ym_game_task_reports_process_running_from_pid():
    task = ScriptedLoginTask(process_output="1234")

    assert task.is_game_process_running()

    assert task.shell_calls == [f"pidof {task.PACKAGE_NAME}"]


def test_enter_game_runs_full_login_flow_and_cleans_popups():
    task = ScriptedLoginTask(
        [
            YmGameTask.LOGIN_STATE_NOTICE,
            YmGameTask.LOGIN_STATE_LOGIN,
            None,
            YmGameTask.LOGIN_STATE_ROLE,
            None,
            YmGameTask.LOGIN_STATE_POPUP,
            YmGameTask.LOGIN_STATE_MAIN,
        ]
    )

    task.enter_game()

    assert task.taps == [
        YmGameTask.LOGIN_STATE_NOTICE,
        YmGameTask.LOGIN_STATE_LOGIN,
        YmGameTask.LOGIN_STATE_ROLE,
        YmGameTask.LOGIN_STATE_POPUP,
    ]
    assert "登录流程结束，主界面已清理" in task.logs


def test_enter_game_resumes_from_role_page():
    task = ScriptedLoginTask(
        [
            YmGameTask.LOGIN_STATE_ROLE,
            None,
            YmGameTask.LOGIN_STATE_MAIN,
        ]
    )

    task.enter_game()

    assert task.taps == [YmGameTask.LOGIN_STATE_ROLE]
    assert "登录流程结束，主界面已清理" in task.logs


def test_enter_game_confirms_online_role_popup():
    task = ScriptedLoginTask(
        [
            YmGameTask.LOGIN_STATE_LOGIN,
            YmGameTask.LOGIN_STATE_ROLE_CONFIRM,
            None,
            YmGameTask.LOGIN_STATE_ROLE,
            YmGameTask.LOGIN_STATE_MAIN,
        ]
    )

    task.enter_game()

    assert task.taps == [
        YmGameTask.LOGIN_STATE_LOGIN,
        YmGameTask.LOGIN_STATE_ROLE_CONFIRM,
        YmGameTask.LOGIN_STATE_ROLE,
    ]
    assert "登录流程结束，主界面已清理" in task.logs


def test_ym_game_task_skips_launch_when_game_is_foreground_and_clean():
    task = ScriptedLoginTask([YmGameTask.LOGIN_STATE_MAIN], window_output=GAME_WINDOW)

    task.ensure_game_started()

    assert task.shell_calls == ["dumpsys window"]
    assert task.taps == []
    assert task.clicked_points == []
    assert "检测到游戏已在前台，跳过启动" in task.logs


def test_ym_game_task_wakes_power_saving_foreground_before_login_flow():
    task = ScriptedLoginTask(
        [None, YmGameTask.LOGIN_STATE_MAIN],
        window_output=GAME_WINDOW,
        power_saving_results=[True],
    )

    task.ensure_game_started()

    assert task.shell_calls == ["dumpsys window"]
    assert task.clicked_points == [
        (task.POINT_RIGHT_JOYSTICK_CENTER[0], task.POINT_RIGHT_JOYSTICK_CENTER[1], 0)
    ]
    assert task.taps == []
    assert "检测到省电模式，点击右下角摇杆中心唤醒" in task.logs
    assert "检测到游戏已在前台，跳过启动" in task.logs
    assert "进入游戏主界面" not in task.logs


def test_ym_game_task_wakes_unrecognized_foreground_once_before_login_flow():
    task = ScriptedLoginTask(
        [None, YmGameTask.LOGIN_STATE_MAIN],
        window_output=GAME_WINDOW,
        power_saving_results=[False],
    )

    task.ensure_game_started()

    assert task.shell_calls == ["dumpsys window"]
    assert task.clicked_points == [
        (task.POINT_RIGHT_JOYSTICK_CENTER[0], task.POINT_RIGHT_JOYSTICK_CENTER[1], 0)
    ]
    assert task.taps == []
    assert "前台画面未识别，点击右下角摇杆中心尝试唤醒" in task.logs
    assert "检测到游戏已在前台，跳过启动" in task.logs
    assert "进入游戏主界面" not in task.logs


def test_ym_game_task_cleans_foreground_popup_instead_of_skipping():
    task = ScriptedLoginTask(
        [YmGameTask.LOGIN_STATE_POPUP, YmGameTask.LOGIN_STATE_MAIN],
        window_output=GAME_WINDOW,
        power_saving_results=[False],
    )

    task.ensure_game_started()

    assert task.shell_calls == ["dumpsys window"]
    assert task.taps == [YmGameTask.LOGIN_STATE_POPUP]
    assert task.clicked_points == []
    assert "检测到游戏在前台但未进入主界面，继续进入游戏" in task.logs


def test_ym_game_task_launches_when_pid_exists_but_foreground_is_home():
    task = ScriptedLoginTask(
        [YmGameTask.LOGIN_STATE_MAIN],
        process_output="1234",
        window_output=HOME_WINDOW,
    )

    assert task.is_game_process_running()
    task.shell_calls.clear()

    task.ensure_game_started()

    assert task.shell_calls == [
        "dumpsys window",
        f"monkey -p {task.PACKAGE_NAME} -c android.intent.category.LAUNCHER 1",
    ]


def test_ym_game_task_launches_when_foreground_cannot_be_parsed():
    task = ScriptedLoginTask([YmGameTask.LOGIN_STATE_MAIN], window_error=True)

    task.ensure_game_started()

    assert task.shell_calls == [
        "dumpsys window",
        f"monkey -p {task.PACKAGE_NAME} -c android.intent.category.LAUNCHER 1",
    ]


def test_enter_game_times_out_when_state_is_never_recognized():
    task = ScriptedLoginTask([None])

    try:
        task.enter_game()
    except RuntimeError as exc:
        assert str(exc) == "登录流程超时：长时间未识别到可操作界面"
    else:
        raise AssertionError("Expected RuntimeError")


def test_start_task_step_metadata_uses_single_long_running_attempt():
    steps = StartTask.get_steps()
    _, _, meta = steps[0]

    assert meta["retry"] == 0
    assert meta["timeout_ms"] == 360000
    assert StartTask.auto_recover_health is False


def test_detect_health_ratio_reads_reference_screenshots():
    root = Path(__file__).resolve().parents[1]

    low_ratio = HealthScreenshotTask(load_image(root / "screenshots" / "1.png")).detect_health_ratio()
    full_ratio = HealthScreenshotTask(load_image(root / "screenshots" / "5.png")).detect_health_ratio()
    chat_overlay_ratio = HealthScreenshotTask(
        load_image(root / "screenshots" / "hslj_debug_current_1v1.png")
    ).detect_health_ratio()

    assert low_ratio is not None
    assert low_ratio < YmGameTask.HEALTH_RECOVER_THRESHOLD
    assert full_ratio is not None
    assert full_ratio >= YmGameTask.HEALTH_FULL_THRESHOLD
    assert chat_overlay_ratio is None


def test_collapse_chat_if_open_clicks_chat_arrow():
    task = FakeChatTask(chat_open_results=[True])

    assert task.collapse_chat_if_open()

    assert task.clicked_points == [
        (task.POINT_CHAT_COLLAPSE_ARROW[0], task.POINT_CHAT_COLLAPSE_ARROW[1], 0)
    ]
    assert task.wait_calls == [800]
    assert "检测到聊天框展开，点击箭头收起" in task.logs


def test_close_all_panels_collapses_chat_before_and_after_closing():
    task = FakeChatTask(chat_open_results=[True, False], image_results=[False])

    task.close_all_panels()

    assert task.clicked_points == [
        (task.POINT_CHAT_COLLAPSE_ARROW[0], task.POINT_CHAT_COLLAPSE_ARROW[1], 0)
    ]
    assert task.wait_calls == [800]
    assert task.image_calls == [
        ([task.BTN_CLOSE, task.BTN_PANE_CLOSE, task.BTN_WELCOME_CLOSE], 5000, 0.8)
    ]


def test_recover_health_if_needed_meditates_until_full():
    task = FakeHealthRecoveryTask([0.79, 0.85, 0.90])

    task.recover_health_if_needed()

    assert task.chat_collapse_calls == [800]
    assert task.image_calls == [
        (task.BTN_BIAOQING, 0.9, task.ROI_BIAOQING_BUTTON)
    ]
    assert task.actions == [
        ("click", 0),
        ("point", task.POINT_EMOTION_SINGLE_TAB[0], task.POINT_EMOTION_SINGLE_TAB[1], 0),
        ("point", task.POINT_EMOTION_MEDITATE[0], task.POINT_EMOTION_MEDITATE[1], 0),
        ("point", task.POINT_EMOTION_COLLAPSE[0], task.POINT_EMOTION_COLLAPSE[1], 0),
        ("point", task.POINT_LIGHTNESS[0], task.POINT_LIGHTNESS[1], 0),
    ]
    assert task.wait_calls == [800, 800, 1000, task.HEALTH_RECOVER_POLL_INTERVAL_MS, 500, 1000]


def test_recover_health_if_needed_skips_when_health_is_not_low():
    task = FakeHealthRecoveryTask([0.80])

    task.recover_health_if_needed()

    assert task.chat_collapse_calls == [800]
    assert task.image_calls == [
        (task.BTN_BIAOQING, 0.9, task.ROI_BIAOQING_BUTTON)
    ]
    assert task.actions == []


def test_recover_health_if_needed_skips_when_emotion_button_is_missing():
    task = FakeHealthRecoveryTask([0.79], emotion_found=False)

    task.recover_health_if_needed()

    assert task.chat_collapse_calls == [800]
    assert task.image_calls == [
        (task.BTN_BIAOQING, 0.9, task.ROI_BIAOQING_BUTTON)
    ]
    assert task.health_ratios == [0.79]
    assert task.actions == []
    assert "未找到主界面表情按钮，跳过自动打坐" in task.logs


def test_auto_battle_clicks_normal_attack_skills_and_turns_page_by_default():
    task = FakeAutoBattleTask()

    task.auto_battle()

    page_actions = auto_battle_round_actions(task, repeat_count=3) * task.BATTLE_PAGE_ROUND_COUNT
    page_turn = ("swipe", 1118, 389, 1022, 449, 350)

    assert task.actions == [
        *page_actions,
        page_turn,
        *page_actions,
        page_turn,
    ]
    assert task.wait_calls == [500] * 146
    assert "自动战斗点击完成" in task.logs


def test_auto_battle_repeats_each_skill_position_before_next_skill():
    task = FakeAutoBattleTask()

    task.auto_battle(skill_pages=1, repeat_count=3, interval_ms=0)

    first_round = task.actions[:18]
    first_skill = ("point", task.POINT_BATTLE_SKILL_BUTTONS[0][0], task.POINT_BATTLE_SKILL_BUTTONS[0][1], 0)
    second_skill = ("point", task.POINT_BATTLE_SKILL_BUTTONS[1][0], task.POINT_BATTLE_SKILL_BUTTONS[1][1], 0)

    assert first_round[3:6] == [first_skill, first_skill, first_skill]
    assert first_round[6:9] == [second_skill, second_skill, second_skill]


def test_auto_battle_can_run_one_skill_page_without_turning_page():
    task = FakeAutoBattleTask()

    task.auto_battle(skill_pages=1, repeat_count=1, interval_ms=250)

    assert task.actions == auto_battle_round_actions(task, repeat_count=1) * task.BATTLE_PAGE_ROUND_COUNT
    assert task.wait_calls == [250] * 24


def test_turn_battle_skill_page_uses_fixed_design_coordinates():
    task = FakeAutoBattleTask()
    task._screen_resolution = (1920, 1080)

    task.turn_battle_skill_page(duration_ms=450)

    assert task.actions == [("swipe", 1118, 389, 1022, 449, 450)]


def test_walk_forward_drags_left_joystick_on_clean_main_scene():
    task = FakeMovementTask(main_ready=True)

    task.walk_forward(500)

    assert task.actions == [("swipe", 105, 455, 105, 385, 500)]
    assert task.main_ready_calls == [(2000, 0.8)]


def test_walk_uses_fixed_design_coordinates():
    task = FakeMovementTask(main_ready=True)
    task._screen_resolution = (1920, 1080)

    task.walk("向右", duration_ms=250)

    assert task.actions == [("swipe", 105, 455, 175, 455, 250)]


def test_fixed_click_point_and_roi_ignore_runtime_resolution():
    task = FakeFixedCoordinateTask()
    task._screen_resolution = (1920, 1080)

    task.click_point(100, 50, offset=0)

    assert task.taps == [(100, 50)]
    assert task.scale_roi((10, 20, 30, 40)) == (10, 20, 30, 40)


def test_open_activity_panel_uses_category_mapping_and_retries_verification():
    task = FakeActivityPanelTask([True, False, True])

    task.open_activity_panel("纷争", wait_after_open_ms=2500, wait_after_category_ms=1500)

    assert task.click_offsets == [0]
    assert task.clicked_points == [(462, 680, 0), (462, 680, 0)]
    assert task.wait_calls == [2500, 1500, 1500]
    assert task.image_calls == [
        (task.BTN_HD, 30000, 0.8),
        (task.ACTIVITY_TAB_FENZHENG_ACTIVE, 1500, 0.85),
        (task.ACTIVITY_TAB_FENZHENG_ACTIVE, 1500, 0.85),
    ]
    assert "活动 - 纷争界面未确认，重试 1/3" in task.logs
    assert "已打开活动 - 纷争界面" in task.logs


def test_walk_rejects_movement_when_main_scene_is_not_clean():
    task = FakeMovementTask(main_ready=False)

    try:
        task.walk_left()
    except RuntimeError as exc:
        assert str(exc) == "当前不是干净主界面，禁止移动"
    else:
        raise AssertionError("Expected RuntimeError")

    assert task.actions == []


def test_wake_from_power_saving_taps_right_joystick_center():
    task = FakeMovementTask(power_saving=True)

    assert task.wake_from_power_saving_if_needed()

    assert task.actions == [
        ("point", task.POINT_RIGHT_JOYSTICK_CENTER[0], task.POINT_RIGHT_JOYSTICK_CENTER[1], 0)
    ]
    assert task.wait_calls == [1000]
    assert "检测到省电模式，点击右下角摇杆中心唤醒" in task.logs


def test_auto_battle_rejects_invalid_arguments():
    task = FakeAutoBattleTask()

    assert_value_error("skill_pages must be at least 1", lambda: task.auto_battle(skill_pages=0))
    assert_value_error("repeat_count must be at least 1", lambda: task.auto_battle(repeat_count=0))
    assert_value_error(
        "interval_ms must be greater than or equal to 0",
        lambda: task.auto_battle(interval_ms=-1),
    )
    assert_value_error(
        "duration_ms must be greater than or equal to 0",
        lambda: task.turn_battle_skill_page(duration_ms=-1),
    )
    assert_value_error(
        "duration_ms must be greater than or equal to 0",
        lambda: task.walk_forward(duration_ms=-1),
    )
    assert_value_error("Unsupported walk direction: up", lambda: task.walk("up"))


def test_bangpai_task_steps_include_sidebar_execution_after_accept():
    step_names = [name for name, _, _ in BangpaiTask.get_steps()]

    assert step_names == [
        "close_all",
        "resume_existing_task",
        "open_bangpai_activity",
        "start_auto_pathfinding",
        "auto_pathfinding",
        "accept_task",
        "start_accepted_task",
        "run_task_flow",
    ]


def test_hidden_and_abstract_tasks_are_not_visible():
    class VisibleTask(YmGameTask):
        pass

    class HiddenTask(YmGameTask):
        task_visible = False

    assert is_visible_task_class(VisibleTask)
    assert not is_visible_task_class(HiddenTask)
    assert not is_visible_task_class(YmGameTask)


def test_switch_task_panel_switches_when_sidebar_is_already_active():
    task = FakeTaskPanelTask([True, True])

    task.switch_task_panel("江湖")

    assert task.wait_image_calls == [
        (task.ICON_TASK_ACTIVE, 3000, 0.8),
        (task.ICON_TASK_JH, 3000, 0.8),
    ]
    assert task.clicked_points == [(174, 124, 3)]
    assert task.wait_calls == [500]


def test_switch_task_panel_opens_sidebar_when_not_active():
    task = FakeTaskPanelTask([False, True, True])

    task.switch_task_panel("任务")

    assert task.wait_image_calls == [
        (task.ICON_TASK_ACTIVE, 3000, 0.8),
        (task.ICON_TASK_ACTIVE, 3000, 0.8),
        (task.ICON_TASK_RW, 3000, 0.8),
    ]
    assert task.clicked_points == [
        (22, 160, 3),
        (88, 124, 3),
    ]
    assert task.wait_calls == [500, 500]


def test_switch_task_panel_raises_when_sidebar_cannot_open():
    task = FakeTaskPanelTask([False, False])

    try:
        task.switch_task_panel("奇遇")
    except RuntimeError as exc:
        assert str(exc) == "未能打开任务侧栏"
    else:
        raise AssertionError("Expected RuntimeError")

    assert task.clicked_points == [(22, 160, 3)]


def test_switch_task_panel_rejects_unknown_panel():
    task = FakeTaskPanelTask([])

    try:
        task.switch_task_panel("帮派")
    except ValueError as exc:
        assert str(exc) == "Unsupported task panel: 帮派"
    else:
        raise AssertionError("Expected ValueError")
