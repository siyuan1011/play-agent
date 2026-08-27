from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from ymjh_bot.ui.task_queue_state import default_state
from ymjh_bot.ui.task_queue_window import TaskQueueWindow


def make_window(tmp_path) -> tuple[QApplication, TaskQueueWindow]:
    app = QApplication.instance() or QApplication([])
    window = TaskQueueWindow()
    window.state_path = tmp_path / "state.json"
    window._state = default_state()
    window._apply_state_to_ui()
    return app, window


def test_gui_has_five_role_checkboxes_and_persists_arbitrary_selection(tmp_path) -> None:
    _app, window = make_window(tmp_path)
    try:
        assert [check.text() for check in window.role_checks.values()] == [
            "角色1",
            "角色2",
            "角色3",
            "角色4",
            "角色5",
        ]
        assert window._selected_role_indices_from_ui() == [0]

        window._state["progress"] = {
            "current_role_index": 0,
            "current_task_index": 1,
            "current_step_index": 2,
        }
        window.role_checks[2].setChecked(True)
        window.role_checks[4].setChecked(True)
        window.role_checks[0].setChecked(False)

        assert window._selected_role_indices_from_ui() == [2, 4]
        assert "progress" not in window._state
        persisted = json.loads(window.state_path.read_text(encoding="utf-8"))
        assert persisted["selected_role_indices"] == [2, 4]
        assert "progress" not in persisted
    finally:
        window.close()


def test_gui_blocks_start_when_no_role_is_checked(tmp_path, monkeypatch) -> None:
    _app, window = make_window(tmp_path)
    warnings: list[tuple[str, str]] = []
    try:
        window._current_serial = "test-device"
        window.serial_input.setText("test-device")
        window._suppress_state_switch = True
        window.device_combo.clear()
        window.device_combo.addItem("test-device")
        window.device_combo.setCurrentIndex(0)
        window._suppress_state_switch = False
        window.selected_tasks = [window.available_tasks[0]]
        window._update_selected_list()
        window._suppress_state_switch = True
        for check in window.role_checks.values():
            check.setChecked(False)
        window._suppress_state_switch = False
        monkeypatch.setattr(
            window,
            "_get_selected_task_instances",
            lambda: [object()],
        )
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda _parent, title, message: warnings.append((title, message)),
        )

        window.start_queue()

        assert warnings == [("未选择角色", "请至少勾选一个账号角色。")]
        assert window.thread is None
        assert window.worker is None
    finally:
        window.close()
