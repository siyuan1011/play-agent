from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QRadioButton

from ymjh_bot.ui.task_queue_window import TaskQueueWindow


def make_window() -> tuple[QApplication, TaskQueueWindow]:
    app = QApplication.instance() or QApplication([])
    window = TaskQueueWindow()
    return app, window


def test_life_settings_widgets_use_dynamic_radio_choices() -> None:
    _app, window = make_window()
    try:
        assert [
            window.shrw_task_type_combo.itemText(index)
            for index in range(window.shrw_task_type_combo.count())
        ] == ["挖矿", "采草", "伐木", "采毛"]
        assert list(window.shrw_material_checks) == [
            "stone",
            "brass_ore",
            "silver_ore",
            "gold_ore",
            "emerald_ore",
            "tungsten_ore",
        ]
        assert all(
            isinstance(check, QRadioButton)
            for check in window.shrw_material_checks.values()
        )
        assert all(
            isinstance(check, QRadioButton)
            for check in window.shrw_line_scope_checks.values()
        )
    finally:
        window.close()


def test_changing_life_type_rebuilds_materials_and_keeps_valid_selection() -> None:
    _app, window = make_window()
    try:
        window.shrw_task_type_combo.setCurrentIndex(
            window.shrw_task_type_combo.findData("herb")
        )
        assert list(window.shrw_material_checks) == [
            "weed",
            "wildflower",
            "vermilion_fruit",
            "earth_spirit_fruit",
            "wild_ginseng",
            "lingzhi",
        ]
        assert window.shrw_material_checks["weed"].isChecked()
    finally:
        window.close()


def test_apply_and_collect_life_settings_round_trip() -> None:
    _app, window = make_window()
    try:
        window._apply_shrw_settings(
            {
                "task_type": "logging",
                "material": "maple",
                "loop_lines": True,
                "line_scope": "interconnected",
            }
        )

        assert window._collect_shrw_settings_from_ui() == {
            "task_type": "logging",
            "material": "maple",
            "loop_lines": True,
            "line_scope": "interconnected",
        }
        assert window.shrw_line_scope_group.checkedButton() is window.shrw_line_scope_checks[
            "interconnected"
        ]
        assert not window.shrw_line_scope_checks["local"].isChecked()
    finally:
        window.close()


def test_render_and_confirm_life_settings_for_selected_task(tmp_path) -> None:
    _app, window = make_window()
    try:
        task_info = next(task for task in window.available_tasks if task["key"] == "SHRW")
        window.selected_tasks = [task_info]
        window._update_selected_list()
        window.selected_list.setCurrentRow(0)
        window.state_path = tmp_path / "state.json"

        window._render_task_settings_for_selection()
        assert window.task_settings_stack.currentWidget() is window.shrw_settings_widget

        window.shrw_task_type_combo.setCurrentIndex(
            window.shrw_task_type_combo.findData("wool")
        )
        window.shrw_material_checks["cashmere"].setChecked(True)
        window.shrw_loop_lines_check.setChecked(True)
        window.shrw_line_scope_checks["interconnected"].setChecked(True)
        window.confirm_task_settings()

        assert window._state["task_settings"]["SHRW"] == {
            "task_type": "wool",
            "material": "cashmere",
            "loop_lines": True,
            "line_scope": "interconnected",
        }
    finally:
        window.close()
