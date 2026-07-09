"""Task Queue Manager UI - Transfer box for selecting and ordering multiple tasks."""

from __future__ import annotations

import datetime
import os
import re
from pathlib import Path

import cv2
from dotenv import load_dotenv
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from botCore import ADBClient, ADBError, GameTask, RunLogger, VisionEngine, load_task_class
from ymjh_bot.runner.task_queue_runner import TaskQueueRunner
from ymjh_bot.ui.task_queue_state import (
    DEFAULT_HSLJ_COUNT,
    HSLJ_TASK_KEY,
    HSLJ_MODE_KEYS,
    HSLJ_STRATEGY_FIRST_WIN,
    HSLJ_STRATEGY_FIXED_COUNT,
    HSLJ_STRATEGY_INFINITE,
    clear_progress,
    load_state_for_serial,
    normalize_hslj_settings,
    restore_selected_tasks,
    safe_serial_name,
    save_state,
    serial_run_lock,
    task_keys_from_infos,
)

HSLJ_STRATEGY_OPTIONS = (
    (HSLJ_STRATEGY_FIRST_WIN, "刷首胜"),
    (HSLJ_STRATEGY_INFINITE, "无限刷"),
    (HSLJ_STRATEGY_FIXED_COUNT, "固定次数"),
)


_LOG_TIMESTAMP_PATTERN = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]")


def _format_log_text(text: str) -> str:
    if _LOG_TIMESTAMP_PATTERN.match(text):
        return text
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {text}"


def is_visible_task_class(task_class: type[GameTask]) -> bool:
    """Return whether a loaded task class should appear in the queue UI."""
    return bool(getattr(task_class, "task_visible", True)) and not bool(
        task_class.__dict__.get("__abstract_task__", False)
    )


class QueueRunnerWorker(QObject):
    """Worker for running task queue in background thread."""
    progress = Signal(str)
    progress_state = Signal(dict)
    finished = Signal()
    error = Signal(str)

    def __init__(
        self,
        task_instances: list[GameTask],
        adb_path: str,
        serial: str | None,
        log_dir: Path | None = None,
        initial_progress: dict | None = None,
    ):
        super().__init__()
        self.task_instances = task_instances
        self.adb_path = adb_path
        self.serial = serial
        self.log_dir = log_dir
        self.initial_progress = initial_progress
        self.runner: TaskQueueRunner | None = None

    @Slot()
    def run(self) -> None:
        try:
            adb = ADBClient(adb_path=self.adb_path, serial=self.serial)
            vision = VisionEngine()
            logger = RunLogger(base_dir=self.log_dir or "logs")
            self.runner = TaskQueueRunner(
                task_list=self.task_instances,
                adb_client=adb,
                vision=vision,
                logger=logger,
                event_callback=self.progress.emit,
                progress_callback=self.progress_state.emit,
            )
            if self.initial_progress:
                self.runner.load_progress(self.initial_progress)
            self.runner.run()
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class TaskQueueWindow(QMainWindow):
    """Task Queue Manager with transfer box UI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("任务队列管理器")
        self.resize(1000, 700)

        self._load_env_config()
        self.repo_root = Path(__file__).resolve().parents[3]
        self.state_dir = Path(__file__).resolve().parent.parent / ".task_queue_states"
        self.legacy_state_path = Path(__file__).resolve().parent.parent / ".task_queue_state.json"
        self._state, self.state_path = load_state_for_serial(
            self.state_dir,
            self._env_serial or "",
            legacy_path=self.legacy_state_path,
            fallback_adb_path=self._env_adb_path or "adb",
        )
        if not self._state.get("adb_path"):
            self._state["adb_path"] = self._env_adb_path or "adb"
        if not self._state.get("serial") and self._env_serial:
            self._state["serial"] = self._env_serial

        self.worker: QueueRunnerWorker | None = None
        self.thread: QThread | None = None
        self._run_lock = None
        self.available_tasks: list[dict] = []  # [{"key": str, "name": str, "class": type, "file": str}]
        self.selected_tasks: list[dict] = []  # Same structure as available_tasks
        self._pending_logs: list[str] = []
        self._suppress_queue_save = False
        self._suppress_state_switch = False
        self._current_serial = str(self._state.get("serial") or "")
        self._stop_requested_by_user = False
        self._queue_editing_enabled = True

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        layout.addWidget(self._build_config_panel())
        layout.addWidget(self._build_transfer_panel(), 1)
        layout.addWidget(self._build_task_settings_panel())
        layout.addWidget(self._build_control_panel())
        layout.addWidget(self._build_log_panel(), 1)
        self._flush_pending_logs()

        self._scan_available_tasks(restore_saved=True)

    def _build_config_panel(self) -> QWidget:
        """Build ADB configuration panel."""
        box = QGroupBox("ADB 配置")
        grid = QGridLayout(box)

        self.adb_path_edit = QLineEdit(str(self._state.get("adb_path") or self._env_adb_path or "adb"))
        self.device_combo = QComboBox()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_devices)

        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("例如：127.0.0.1:5555")
        if self._state.get("serial"):
            self.serial_input.setText(str(self._state["serial"]))
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.connect_serial)

        row = 0
        grid.addWidget(QLabel("ADB 路径"), row, 0)
        grid.addWidget(self.adb_path_edit, row, 1)
        grid.addWidget(QLabel("设备"), row, 2)
        device_row = QWidget()
        device_layout = QHBoxLayout(device_row)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.addWidget(self.device_combo, 1)
        device_layout.addWidget(self.refresh_btn)
        grid.addWidget(device_row, row, 3)
        row += 1

        grid.addWidget(QLabel("自定义序列号"), row, 0)
        serial_row = QWidget()
        serial_layout = QHBoxLayout(serial_row)
        serial_layout.setContentsMargins(0, 0, 0, 0)
        serial_layout.addWidget(self.serial_input, 1)
        serial_layout.addWidget(self.connect_btn)
        grid.addWidget(serial_row, row, 1, 1, 3)
        row += 1

        self.refresh_devices()
        self.adb_path_edit.editingFinished.connect(self._save_state_from_ui)
        self.device_combo.currentTextChanged.connect(self._on_device_changed)
        return box

    def _build_transfer_panel(self) -> QWidget:
        """Build transfer box for task selection."""
        box = QGroupBox("任务选择")
        layout = QHBoxLayout(box)

        # Left: Available tasks
        left_group = QGroupBox("可用任务")
        left_layout = QVBoxLayout(left_group)
        self.available_list = QListWidget()
        self.available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        left_layout.addWidget(self.available_list)
        self.refresh_tasks_btn = QPushButton("刷新任务")
        self.refresh_tasks_btn.clicked.connect(self.refresh_tasks)
        left_layout.addWidget(self.refresh_tasks_btn)

        # Middle: Buttons
        btn_layout = QVBoxLayout()
        btn_layout.addStretch()
        self.add_btn = QPushButton("→")
        self.add_btn.clicked.connect(self.add_selected_tasks)
        btn_layout.addWidget(self.add_btn)
        self.remove_btn = QPushButton("←")
        self.remove_btn.clicked.connect(self.remove_selected_tasks)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()
        layout.addWidget(left_group)
        layout.addLayout(btn_layout)

        # Right: Selected tasks (queue)
        right_group = QGroupBox("任务队列（拖动排序）")
        right_layout = QVBoxLayout(right_group)
        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.selected_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.selected_list.model().rowsMoved.connect(self._on_queue_reordered)
        self.selected_list.currentRowChanged.connect(self._on_selected_task_changed)
        right_layout.addWidget(self.selected_list)
        self.clear_tasks_btn = QPushButton("清空任务")
        self.clear_tasks_btn.clicked.connect(self.clear_selected_tasks)
        right_layout.addWidget(self.clear_tasks_btn)

        layout.addWidget(right_group)
        return box

    def _build_task_settings_panel(self) -> QWidget:
        """Build per-task settings panel."""
        box = QGroupBox("任务设置")
        layout = QVBoxLayout(box)
        self.task_settings_stack = QStackedWidget()

        self.no_task_settings_widget = QWidget()
        no_task_layout = QVBoxLayout(self.no_task_settings_widget)
        self.no_task_settings_label = QLabel("请选择任务")
        no_task_layout.addWidget(self.no_task_settings_label)
        no_task_layout.addStretch()

        self.hslj_settings_widget = QWidget()
        hslj_layout = QGridLayout(self.hslj_settings_widget)
        self.hslj_mode_widgets: dict[str, dict[str, object]] = {}
        self.hslj_strategy_groups: dict[str, QButtonGroup] = {}
        hslj_layout.addWidget(QLabel("模式"), 0, 0)
        hslj_layout.addWidget(QLabel("策略"), 0, 1)
        hslj_layout.addWidget(QLabel("次数"), 0, 2)
        for row, mode in enumerate(HSLJ_MODE_KEYS, start=1):
            self._add_hslj_mode_settings_row(hslj_layout, row, mode)

        self.hslj_settings_confirm_btn = QPushButton("确定")
        self.hslj_settings_confirm_btn.clicked.connect(self.confirm_task_settings)
        hslj_layout.addWidget(self.hslj_settings_confirm_btn, 1, 3, len(HSLJ_MODE_KEYS), 1)
        hslj_layout.setColumnStretch(1, 1)

        self.task_settings_stack.addWidget(self.no_task_settings_widget)
        self.task_settings_stack.addWidget(self.hslj_settings_widget)
        layout.addWidget(self.task_settings_stack)
        return box

    def _add_hslj_mode_settings_row(self, layout: QGridLayout, row: int, mode: str) -> None:
        """Add one Huashan mode strategy row."""
        layout.addWidget(QLabel(mode), row, 0)

        strategy_widget = QWidget()
        strategy_layout = QHBoxLayout(strategy_widget)
        strategy_layout.setContentsMargins(0, 0, 0, 0)

        group = QButtonGroup(self.hslj_settings_widget)
        group.setExclusive(True)
        checks: dict[str, QCheckBox] = {}
        for strategy, label in HSLJ_STRATEGY_OPTIONS:
            check = QCheckBox(label)
            group.addButton(check)
            checks[strategy] = check
            strategy_layout.addWidget(check)
            check.toggled.connect(lambda _checked, mode=mode: self._update_hslj_mode_count_state(mode))
        strategy_layout.addStretch()
        layout.addWidget(strategy_widget, row, 1)

        count_edit = QLineEdit()
        count_edit.setValidator(QIntValidator(1, 9999, count_edit))
        count_edit.setFixedWidth(80)
        layout.addWidget(count_edit, row, 2)

        self.hslj_strategy_groups[mode] = group
        self.hslj_mode_widgets[mode] = {
            "checks": checks,
            "count_edit": count_edit,
        }

    def _build_control_panel(self) -> QWidget:
        """Build control buttons panel."""
        box = QGroupBox("控制")
        layout = QHBoxLayout(box)
        layout.addStretch()

        self.start_btn = QPushButton("开始队列")
        self.start_btn.clicked.connect(self.start_queue)
        layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self.pause_queue)
        self.pause_btn.setEnabled(False)
        layout.addWidget(self.pause_btn)

        self.resume_btn = QPushButton("继续")
        self.resume_btn.clicked.connect(self.resume_queue)
        self.resume_btn.setEnabled(False)
        layout.addWidget(self.resume_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_queue)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        self.reset_progress_btn = QPushButton("重置进度")
        self.reset_progress_btn.clicked.connect(self.reset_progress)
        layout.addWidget(self.reset_progress_btn)

        self.screenshot_btn = QPushButton("截图")
        self.screenshot_btn.clicked.connect(self.take_screenshot)
        layout.addWidget(self.screenshot_btn)

        layout.addStretch()
        return box

    def _build_log_panel(self) -> QWidget:
        """Build log output panel."""
        box = QGroupBox("日志输出")
        layout = QVBoxLayout(box)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        btn_layout.addWidget(self.clear_log_btn)
        layout.addLayout(btn_layout)
        return box

    def _scan_available_tasks(self, restore_saved: bool = False) -> None:
        """Scan task directory for available Python DSL tasks."""
        task_dir = Path(__file__).parent.parent / "task"
        if not task_dir.exists():
            self._append_log(f"[警告] 未找到任务目录：{task_dir}")
            return

        self.available_tasks = []
        for file_path in sorted(task_dir.glob("*_task.py")):
            if file_path.name.startswith("_"):
                continue
            try:
                task_class = self._load_task_class_from_file(file_path)
                if task_class and is_visible_task_class(task_class):
                    self.available_tasks.append({
                        "key": getattr(task_class, "task_key", task_class.__name__),
                        "name": getattr(task_class, "task_name", task_class.__name__),
                        "description": getattr(task_class, "task_description", ""),
                        "class": task_class,
                        "file": str(file_path),
                    })
            except Exception as e:
                self._append_log(f"[警告] 加载 {file_path.name} 失败：{e}")

        self._update_available_list()
        if restore_saved:
            self._restore_selected_tasks_from_state()

    def _load_task_class_from_file(self, file_path: Path) -> type[GameTask] | None:
        """Load GameTask subclass from a Python file."""
        return load_task_class(file_path)

    def _update_available_list(self) -> None:
        """Update the available tasks list widget."""
        self.available_list.clear()
        selected_keys = {str(task_info.get("key")) for task_info in self.selected_tasks}
        for task_info in self.available_tasks:
            if str(task_info.get("key")) in selected_keys:
                continue
            item = QListWidgetItem(str(task_info.get("name") or task_info.get("key") or ""))
            item.setToolTip(task_info.get("description", ""))
            item.setData(Qt.ItemDataRole.UserRole, task_info)
            self.available_list.addItem(item)

    def _update_selected_list(self) -> None:
        """Update the selected tasks list widget."""
        self._suppress_queue_save = True
        self.selected_list.clear()
        for task_info in self.selected_tasks:
            item = QListWidgetItem(str(task_info.get("name") or task_info.get("key") or ""))
            item.setToolTip(task_info.get("description", ""))
            item.setData(Qt.ItemDataRole.UserRole, task_info)
            self.selected_list.addItem(item)
        self._suppress_queue_save = False
        if self.selected_list.count() > 0 and self.selected_list.currentRow() < 0:
            self.selected_list.setCurrentRow(0)
        self._render_task_settings_for_selection()

    def _sync_selected_tasks_from_widget(self) -> None:
        """Persist the current visual order after drag-and-drop reordering."""
        ordered_tasks = []
        for row in range(self.selected_list.count()):
            task_info = self.selected_list.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(task_info, dict):
                ordered_tasks.append(task_info)
        self.selected_tasks = ordered_tasks

    def add_selected_tasks(self) -> None:
        """Add selected available tasks to queue."""
        selected_indexes = self.available_list.selectedIndexes()
        if not selected_indexes:
            return

        for index in sorted(selected_indexes, key=lambda i: i.row(), reverse=True):
            item = self.available_list.item(index.row())
            if item is None:
                continue
            task_info = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(task_info, dict):
                continue
            key = str(task_info.get("key"))
            if any(str(selected.get("key")) == key for selected in self.selected_tasks):
                continue
            self.selected_tasks.append(task_info.copy())

        self._update_selected_list()
        self._update_available_list()
        self._save_state_from_ui()

    def remove_selected_tasks(self) -> None:
        """Remove selected tasks from queue."""
        self._sync_selected_tasks_from_widget()
        selected_indexes = self.selected_list.selectedIndexes()
        if not selected_indexes:
            return

        for index in sorted(selected_indexes, key=lambda i: i.row(), reverse=True):
            row = index.row()
            if 0 <= row < len(self.selected_tasks):
                self.selected_tasks.pop(row)

        self._update_selected_list()
        self._update_available_list()
        self._save_state_from_ui()

    def clear_selected_tasks(self) -> None:
        """Clear all selected tasks from the queue."""
        self.selected_tasks = []
        self._update_selected_list()
        self._update_available_list()
        self._clear_saved_progress()
        self._append_log("任务队列已清空。")

    def _on_selected_task_changed(self, row: int) -> None:
        """Render settings when queue selection changes."""
        self._render_task_settings_for_selection()

    def _selected_task_info(self) -> dict | None:
        """Return the currently selected queued task info."""
        item = self.selected_list.currentItem()
        if item is None:
            return None
        task_info = item.data(Qt.ItemDataRole.UserRole)
        return task_info if isinstance(task_info, dict) else None

    def _render_task_settings_for_selection(self) -> None:
        """Render saved settings for the currently selected task."""
        if not hasattr(self, "task_settings_stack"):
            return
        task_info = self._selected_task_info()
        if not task_info:
            self.no_task_settings_label.setText("请选择任务")
            self.task_settings_stack.setCurrentWidget(self.no_task_settings_widget)
            return

        task_key = str(task_info.get("key") or "")
        if task_key != HSLJ_TASK_KEY:
            self.no_task_settings_label.setText("该任务暂无参数配置")
            self.task_settings_stack.setCurrentWidget(self.no_task_settings_widget)
            return

        settings = normalize_hslj_settings(
            (self._state.get("task_settings") or {}).get(HSLJ_TASK_KEY)
        )
        self._apply_hslj_settings(settings)
        self.task_settings_stack.setCurrentWidget(self.hslj_settings_widget)

    def _apply_hslj_settings(self, settings: dict) -> None:
        """Apply normalized Huashan settings to the UI."""
        for mode in HSLJ_MODE_KEYS:
            mode_settings = settings.get(mode, {})
            widgets = self.hslj_mode_widgets[mode]
            checks = widgets["checks"]
            count_edit = widgets["count_edit"]
            if not isinstance(checks, dict) or not isinstance(count_edit, QLineEdit):
                continue

            strategy = str(mode_settings.get("strategy") or HSLJ_STRATEGY_FIRST_WIN)
            check = checks.get(strategy) or checks[HSLJ_STRATEGY_FIRST_WIN]
            check.setChecked(True)
            count_edit.setText(str(mode_settings.get("count") or DEFAULT_HSLJ_COUNT))
            self._update_hslj_mode_count_state(mode)

    def _update_hslj_mode_count_state(self, mode: str) -> None:
        """Show and enable the fixed-count input only for fixed-count strategy."""
        if not hasattr(self, "hslj_mode_widgets") or mode not in self.hslj_mode_widgets:
            return
        widgets = self.hslj_mode_widgets[mode]
        checks = widgets["checks"]
        count_edit = widgets["count_edit"]
        if not isinstance(checks, dict) or not isinstance(count_edit, QLineEdit):
            return
        fixed_checked = bool(checks[HSLJ_STRATEGY_FIXED_COUNT].isChecked())
        count_edit.setVisible(fixed_checked)
        count_edit.setEnabled(bool(getattr(self, "_queue_editing_enabled", True)) and fixed_checked)

    def _collect_hslj_settings_from_ui(self) -> dict:
        """Collect Huashan settings from the UI in the persisted schema."""
        settings: dict[str, dict[str, object]] = {}
        for mode in HSLJ_MODE_KEYS:
            widgets = self.hslj_mode_widgets[mode]
            checks = widgets["checks"]
            count_edit = widgets["count_edit"]
            if not isinstance(checks, dict) or not isinstance(count_edit, QLineEdit):
                continue

            strategy = HSLJ_STRATEGY_FIRST_WIN
            for candidate, check in checks.items():
                if check.isChecked():
                    strategy = str(candidate)
                    break

            try:
                count = int(count_edit.text())
            except ValueError:
                count = DEFAULT_HSLJ_COUNT
            count = max(1, min(count, 9999))
            count_edit.setText(str(count))
            settings[mode] = {
                "strategy": strategy,
                "count": count,
            }
        return normalize_hslj_settings(settings)

    def confirm_task_settings(self) -> None:
        """Persist the currently selected task settings."""
        task_info = self._selected_task_info()
        if not task_info:
            return
        if str(task_info.get("key") or "") != HSLJ_TASK_KEY:
            return

        task_settings = dict(self._state.get("task_settings") or {})
        task_settings[HSLJ_TASK_KEY] = self._collect_hslj_settings_from_ui()
        self._state["task_settings"] = task_settings
        self._save_state_from_ui()
        self._append_log("华山论剑任务设置已保存。")

    def _get_selected_task_instances(self) -> list[GameTask]:
        """Create task instances from selected tasks."""
        self._sync_selected_tasks_from_widget()
        instances = []
        for task_info in self.selected_tasks:
            try:
                if str(task_info.get("key") or "") == HSLJ_TASK_KEY:
                    settings = normalize_hslj_settings(
                        (self._state.get("task_settings") or {}).get(HSLJ_TASK_KEY)
                    )
                    instance = task_info["class"](
                        hslj_settings=settings,
                    )
                else:
                    instance = task_info["class"]()
                instances.append(instance)
            except Exception as e:
                self._append_log(f"[错误] 创建任务实例失败：{e}")
        return instances

    def start_queue(self) -> None:
        """Start executing the task queue."""
        serial = self._current_ui_serial().strip()
        if not serial:
            QMessageBox.warning(self, "未选择设备", "请先选择或输入设备端口。")
            return
        if serial != self._current_serial:
            self._switch_to_serial(serial)

        if not self.selected_tasks:
            QMessageBox.warning(self, "未选择任务", "请至少选择一个任务。")
            return

        task_instances = self._get_selected_task_instances()
        if not task_instances:
            return

        adb_path = self.adb_path_edit.text().strip() or "adb"
        self._save_state_from_ui()
        initial_progress = self._state.get("progress")
        self._stop_requested_by_user = False
        run_lock = serial_run_lock(self.state_dir, serial)
        if not run_lock.acquire():
            QMessageBox.warning(self, "端口已占用", f"{serial} 已有任务运行中，请勿重复启动。")
            return
        self._run_lock = run_lock

        self.thread = QThread(self)
        self.worker = QueueRunnerWorker(
            task_instances,
            adb_path,
            serial,
            self.repo_root / "logs" / safe_serial_name(serial),
            initial_progress if isinstance(initial_progress, dict) else None,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._append_log)
        self.worker.progress_state.connect(self._on_progress_state)
        self.worker.error.connect(self._on_run_error)
        self.worker.finished.connect(self._on_run_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_worker)
        self.thread.start()

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_queue_editing_enabled(False)
        self._append_log("任务队列已开始。")
        if initial_progress:
            self._append_log(f"恢复进度：任务={initial_progress.get('current_task_index', 0)}, 步骤={initial_progress.get('current_step_index', 0)}")

    def pause_queue(self) -> None:
        """Pause the task queue."""
        if self.worker and self.worker.runner:
            self.worker.runner.pause()
            self._save_progress(self.worker.runner.get_progress())
            self._append_log("已请求暂停。")
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
        else:
            self._append_log("[警告] 没有可暂停的运行队列")

    def resume_queue(self) -> None:
        """Resume the paused task queue."""
        if self.worker and self.worker.runner:
            self.worker.runner.resume()
            self._append_log("已继续。")
            self.resume_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
        else:
            self._append_log("[警告] 没有可继续的运行队列")

    def stop_queue(self) -> None:
        """Stop the task queue."""
        self._stop_requested_by_user = True
        self._clear_saved_progress()
        if self.worker and self.worker.runner:
            self.worker.runner.stop()
            self._append_log("已请求停止。")
            self.stop_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)
        else:
            self._append_log("[警告] 没有可停止的运行队列")

    def _on_run_finished(self) -> None:
        """Called when queue execution finishes."""
        if self._stop_requested_by_user:
            self._append_log("任务队列已停止。")
        else:
            self._clear_saved_progress()
            self._append_log("任务队列已完成。")
        self._stop_requested_by_user = False
        self._reset_buttons()
        self._release_run_lock()

    def _on_run_error(self, message: str) -> None:
        """Called when queue execution errors."""
        self._append_log(f"[错误] {message}")
        if self._stop_requested_by_user:
            self._clear_saved_progress()
        elif self.worker and self.worker.runner:
            self._save_progress(self.worker.runner.get_progress())
        self._stop_requested_by_user = False
        self._reset_buttons()
        self._release_run_lock()

    def _reset_buttons(self) -> None:
        """Reset control buttons to initial state."""
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self._set_queue_editing_enabled(True)

    def _cleanup_worker(self) -> None:
        """Clean up worker reference after thread finishes."""
        self.worker = None
        self.thread = None

    def _release_run_lock(self) -> None:
        """Release the current serial run lock if held."""
        if self._run_lock is None:
            return
        self._run_lock.release()
        self._run_lock = None

    def _load_env_config(self) -> None:
        """Load default ADB configuration from .env file."""
        env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()

        self._env_adb_path = os.getenv("DEFAULT_ADB_PATH")
        self._env_serial = os.getenv("DEFAULT_ADB_SERIAL")

    def _append_log(self, text: str) -> None:
        """Append text to log view."""
        text = _format_log_text(text)
        if hasattr(self, "log_view"):
            self.log_view.append(text)
        else:
            self._pending_logs.append(text)

    def _flush_pending_logs(self) -> None:
        """Flush logs captured before the log widget existed."""
        for text in self._pending_logs:
            self.log_view.append(text)
        self._pending_logs.clear()

    def clear_log(self) -> None:
        """Clear all log messages."""
        self.log_view.clear()

    def refresh_tasks(self) -> None:
        """Manually rescan built-in task scripts."""
        self._sync_selected_tasks_from_widget()
        self._save_state_from_ui()
        self._scan_available_tasks(restore_saved=True)
        self._append_log("任务已刷新。")

    def reset_progress(self) -> None:
        """Clear saved task progress without changing the queue order."""
        if self.worker and self.worker.runner:
            QMessageBox.warning(self, "队列运行中", "请先停止队列，再重置进度。")
            return
        self._clear_saved_progress()
        self._append_log("进度已重置。")

    def take_screenshot(self) -> None:
        """Save a screenshot from the currently selected device."""
        serial = self._current_ui_serial().strip()
        if not serial:
            QMessageBox.warning(self, "未选择设备", "请先选择或输入设备端口。")
            return

        adb_path = self.adb_path_edit.text().strip() or "adb"
        try:
            adb = ADBClient(adb_path=adb_path, serial=serial)
            adb.ensure_device()
            screenshot = adb.screenshot()
            output_dir = self.repo_root / "screenshots"
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"ymjh_queue_{safe_serial_name(serial)}_{timestamp}.png"
            if not cv2.imwrite(str(output_path), screenshot):
                raise RuntimeError("cv2.imwrite 返回失败")
        except Exception as exc:
            self._append_log(f"[错误] 截图失败：{exc}")
            QMessageBox.critical(self, "截图失败", str(exc))
            return

        self._append_log(f"截图已保存：{output_path}")

    def _current_ui_serial(self) -> str:
        """Return the serial currently selected or typed in the UI."""
        return (
            self.device_combo.currentText().strip()
            or self.serial_input.text().strip()
            or self._current_serial
        )

    def _on_device_changed(self, serial: str) -> None:
        """Switch state when the selected device changes."""
        if self._suppress_state_switch:
            return
        serial = serial.strip()
        if not serial or serial == self._current_serial:
            return
        self._switch_to_serial(serial)

    def _switch_to_serial(self, serial: str) -> None:
        """Persist current state, then load the state for another serial."""
        serial = serial.strip()
        if serial == self._current_serial:
            return
        if hasattr(self, "adb_path_edit"):
            self._save_state_from_ui()

        fallback_adb_path = self.adb_path_edit.text().strip() if hasattr(self, "adb_path_edit") else None
        self._state, self.state_path = load_state_for_serial(
            self.state_dir,
            serial,
            legacy_path=self.legacy_state_path,
            fallback_adb_path=fallback_adb_path or self._env_adb_path or "adb",
        )
        self._state["serial"] = serial
        self._current_serial = serial
        self._apply_state_to_ui()
        self._append_log(f"已切换到端口状态：{serial}")

    def _apply_state_to_ui(self) -> None:
        """Apply loaded state to existing widgets."""
        if not hasattr(self, "adb_path_edit"):
            return
        self._suppress_state_switch = True
        try:
            self.adb_path_edit.setText(str(self._state.get("adb_path") or self._env_adb_path or "adb"))
            serial = str(self._state.get("serial") or "")
            self.serial_input.setText(serial)
            if serial:
                idx = self.device_combo.findText(serial)
                if idx < 0:
                    self.device_combo.addItem(serial)
                    idx = self.device_combo.findText(serial)
                if idx >= 0:
                    self.device_combo.setCurrentIndex(idx)
            self._restore_selected_tasks_from_state()
            self._render_task_settings_for_selection()
        finally:
            self._suppress_state_switch = False

    def refresh_devices(self) -> None:
        """Refresh connected ADB devices."""
        current_serial = self._current_serial or self.serial_input.text().strip()
        self._suppress_state_switch = True
        self.device_combo.clear()
        adb_path = self.adb_path_edit.text().strip() or "adb"
        try:
            devices = ADBClient.list_devices(adb_path=adb_path)
        except ADBError as exc:
            self.device_combo.addItem("")
            self._append_log(f"[警告] {exc}")
            self._suppress_state_switch = False
            return
        if not devices:
            self.device_combo.addItem("")
            if current_serial:
                self.device_combo.addItem(current_serial)
                self.device_combo.setCurrentIndex(1)
            self._suppress_state_switch = False
            return
        for item in devices:
            self.device_combo.addItem(item.serial)
        if current_serial:
            idx = self.device_combo.findText(current_serial)
            if idx < 0:
                self.device_combo.addItem(current_serial)
                idx = self.device_combo.findText(current_serial)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
        self._suppress_state_switch = False

    def connect_serial(self) -> None:
        """Connect to a custom ADB serial port."""
        serial = self.serial_input.text().strip()
        if not serial:
            QMessageBox.warning(self, "序列号无效", "请输入设备序列号。")
            return
        adb_path = self.adb_path_edit.text().strip() or "adb"
        try:
            adb = ADBClient(adb_path=adb_path)
            adb.connect(serial)
            self._append_log(f"已连接到 {serial}")
            self.refresh_devices()
            idx = self.device_combo.findText(serial)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
            self._switch_to_serial(serial)
            self._save_state_from_ui()
            QMessageBox.information(self, "连接成功", f"已成功连接到 {serial}")
        except ADBError as exc:
            QMessageBox.critical(self, "连接失败", str(exc))
            self._append_log(f"[错误] 连接失败：{exc}")

    @Slot(dict)
    def _on_progress_state(self, progress: dict) -> None:
        """Persist progress snapshots emitted by the running queue."""
        if self._stop_requested_by_user:
            return
        self._save_progress(progress)

    def _save_progress(self, progress: dict) -> None:
        """Save current queue progress."""
        self._state["progress"] = {
            "current_task_index": int(progress.get("current_task_index", 0)),
            "current_step_index": int(progress.get("current_step_index", 0)),
        }
        self._save_state_from_ui()

    def _clear_saved_progress(self) -> None:
        """Clear persisted progress while preserving settings and queue order."""
        self._state = clear_progress(self._state)
        self._save_state_from_ui()

    def _restore_selected_tasks_from_state(self) -> None:
        """Restore selected tasks according to persisted keys."""
        selected, missing = restore_selected_tasks(
            self.available_tasks,
            self._state.get("selected_task_keys", []),
        )
        self.selected_tasks = selected
        self._update_selected_list()
        self._update_available_list()
        for key in missing:
            self._append_log(f"[警告] 未找到已保存任务，已跳过：{key}")
        if missing:
            self._save_state_from_ui()

    def _save_state_from_ui(self) -> None:
        """Persist current UI settings and selected task order."""
        if not hasattr(self, "adb_path_edit"):
            return
        self._sync_selected_tasks_from_widget()
        self._state["adb_path"] = self.adb_path_edit.text().strip() or "adb"
        self._state["serial"] = self._current_serial
        self._state["selected_task_keys"] = task_keys_from_infos(self.selected_tasks)
        save_state(self.state_path, self._state)

    def _on_queue_reordered(self, *args) -> None:
        """Persist queue order after drag-and-drop."""
        if self._suppress_queue_save:
            return
        self._sync_selected_tasks_from_widget()
        self._save_state_from_ui()

    def _set_queue_editing_enabled(self, enabled: bool) -> None:
        """Enable or disable controls that mutate the selected queue."""
        self._queue_editing_enabled = enabled
        self.available_list.setEnabled(enabled)
        self.selected_list.setEnabled(enabled)
        self.add_btn.setEnabled(enabled)
        self.remove_btn.setEnabled(enabled)
        self.clear_tasks_btn.setEnabled(enabled)
        self.refresh_tasks_btn.setEnabled(enabled)
        self.reset_progress_btn.setEnabled(enabled)
        self.serial_input.setEnabled(enabled)
        self.device_combo.setEnabled(enabled)
        self.connect_btn.setEnabled(enabled)
        for mode in getattr(self, "hslj_mode_widgets", {}):
            widgets = self.hslj_mode_widgets[mode]
            checks = widgets["checks"]
            if isinstance(checks, dict):
                for check in checks.values():
                    check.setEnabled(enabled)
            self._update_hslj_mode_count_state(mode)
        if hasattr(self, "hslj_settings_confirm_btn"):
            self.hslj_settings_confirm_btn.setEnabled(enabled)


def main():
    """Entry point for the Task Queue Manager."""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = TaskQueueWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
