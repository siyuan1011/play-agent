import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QListWidget, QTextEdit

from ymjh_bot.ui.task_queue_state import (
    HSLJ_STRATEGY_FIXED_COUNT,
    HSLJ_STRATEGY_FIRST_WIN,
    HSLJ_STRATEGY_INFINITE,
)
from ymjh_bot.ui.task_queue_window import TaskQueueWindow


def test_task_queue_lists_show_task_names_without_keys():
    app = QApplication.instance() or QApplication([])
    window = TaskQueueWindow.__new__(TaskQueueWindow)
    window.available_list = QListWidget()
    window.selected_list = QListWidget()
    window.available_tasks = [
        {"key": "BPRW", "name": "帮派任务", "description": "帮派任务自动执行"},
        {"key": "HSLJ", "name": "华山论剑", "description": "完成华山论剑"},
    ]
    window.selected_tasks = [
        {"key": "HSLJ", "name": "华山论剑", "description": "完成华山论剑"},
    ]
    window._suppress_queue_save = False
    window._render_task_settings_for_selection = lambda: None

    window._update_available_list()
    window._update_selected_list()

    assert app is not None
    assert window.available_list.item(0).text() == "帮派任务"
    assert "BPRW" not in window.available_list.item(0).text()
    assert window.available_list.item(0).toolTip() == "帮派任务自动执行"
    assert window.selected_list.item(0).text() == "华山论剑"
    assert "HSLJ" not in window.selected_list.item(0).text()


def test_hslj_settings_rows_are_exclusive_and_collect_new_schema():
    app = QApplication.instance() or QApplication([])
    window = TaskQueueWindow.__new__(TaskQueueWindow)
    window._queue_editing_enabled = True
    window._settings_panel = window._build_task_settings_panel()

    window._apply_hslj_settings(
        {
            "1v1": {"strategy": HSLJ_STRATEGY_FIXED_COUNT, "count": 2},
            "3v3": {"strategy": HSLJ_STRATEGY_INFINITE, "count": 5},
        }
    )

    one_v_one_checks = window.hslj_mode_widgets["1v1"]["checks"]
    one_v_one_count = window.hslj_mode_widgets["1v1"]["count_edit"]
    assert app is not None
    assert one_v_one_checks[HSLJ_STRATEGY_FIXED_COUNT].isChecked()
    assert not one_v_one_count.isHidden()

    one_v_one_checks[HSLJ_STRATEGY_INFINITE].setChecked(True)

    assert one_v_one_checks[HSLJ_STRATEGY_INFINITE].isChecked()
    assert not one_v_one_checks[HSLJ_STRATEGY_FIXED_COUNT].isChecked()
    assert one_v_one_count.isHidden()
    assert window._collect_hslj_settings_from_ui()["1v1"] == {
        "strategy": HSLJ_STRATEGY_INFINITE,
        "count": 2,
    }


def test_hslj_default_settings_show_first_win_and_3v3_fixed_count():
    app = QApplication.instance() or QApplication([])
    window = TaskQueueWindow.__new__(TaskQueueWindow)
    window._queue_editing_enabled = True
    window._settings_panel = window._build_task_settings_panel()

    window._apply_hslj_settings(
        {
            "1v1": {"strategy": HSLJ_STRATEGY_FIRST_WIN, "count": 5},
            "3v3": {"strategy": HSLJ_STRATEGY_FIXED_COUNT, "count": 5},
        }
    )

    assert app is not None
    assert window.hslj_mode_widgets["1v1"]["checks"][HSLJ_STRATEGY_FIRST_WIN].isChecked()
    assert window.hslj_mode_widgets["1v1"]["count_edit"].isHidden()
    assert window.hslj_mode_widgets["3v3"]["checks"][HSLJ_STRATEGY_FIXED_COUNT].isChecked()
    assert not window.hslj_mode_widgets["3v3"]["count_edit"].isHidden()


def test_queue_window_screenshot_button_saves_current_device(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    window = TaskQueueWindow.__new__(TaskQueueWindow)
    window.repo_root = tmp_path
    window.adb_path_edit = QLineEdit("adb")
    window.device_combo = QComboBox()
    window.device_combo.addItem("127.0.0.1:16416")
    window.serial_input = QLineEdit()
    window._current_serial = "127.0.0.1:16416"
    window.log_view = QTextEdit()

    class FakeADB:
        def __init__(self, adb_path, serial):
            self.adb_path = adb_path
            self.serial = serial

        def ensure_device(self):
            return None

        def screenshot(self):
            return object()

    writes = []

    def fake_imwrite(path, image):
        writes.append((path, image))
        return True

    monkeypatch.setattr("ymjh_bot.ui.task_queue_window.ADBClient", FakeADB)
    monkeypatch.setattr("ymjh_bot.ui.task_queue_window.cv2.imwrite", fake_imwrite)

    window.take_screenshot()

    assert app is not None
    assert len(writes) == 1
    assert Path(writes[0][0]).is_relative_to(tmp_path / "logs" / "manual_screenshots")
    assert "ymjh_queue_127.0.0.1_16416_" in writes[0][0]
    log_text = window.log_view.toPlainText()
    assert "截图已保存：" in log_text
    assert re.search(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] 截图已保存：", log_text)


def test_queue_window_append_log_keeps_existing_full_timestamp():
    app = QApplication.instance() or QApplication([])
    window = TaskQueueWindow.__new__(TaskQueueWindow)
    window.log_view = QTextEdit()

    window._append_log("[2026-07-08 15:04:05] 已带时间")

    assert app is not None
    assert window.log_view.toPlainText() == "[2026-07-08 15:04:05] 已带时间"
