from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import cv2
import datetime

from botCore import ADBClient, ADBError, DSLTaskRunner, GameTask, RunLogger, VisionEngine
from game_bot.task_loader import load_task_for_gui


class RunnerWorker(QObject):
    progress = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, task: GameTask, adb_path: str, serial: str | None):
        super().__init__()
        self.task = task
        self.adb_path = adb_path
        self.serial = serial
        self.runner: DSLTaskRunner | None = None

    @Slot()
    def run(self) -> None:
        try:
            adb = ADBClient(adb_path=self.adb_path, serial=self.serial)
            vision = VisionEngine()
            logger = RunLogger()
            self.runner = DSLTaskRunner(
                task=self.task,
                adb_client=adb,
                vision=vision,
                logger=logger,
                event_callback=self.progress.emit,
                verbose=True,
            )
            self.runner.run()
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PlayAgent Dev Debugger")
        self.resize(900, 700)

        # Load .env file for default configuration
        self._load_env_config()

        self.current_file: Path | None = None
        self.task: GameTask | None = None
        self.worker: RunnerWorker | None = None
        self.thread: QThread | None = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        layout.addWidget(self._build_config_panel())
        layout.addWidget(self._build_log_panel(), 1)

    def _build_config_panel(self) -> QWidget:
        box = QGroupBox("Task Configuration")
        grid = QGridLayout(box)

        self.task_type_label = QLabel("Python DSL Task")
        self.task_type_label.setStyleSheet("font-weight: bold; font-size: 12px;")

        self.adb_path_edit = QLineEdit(self._env_adb_path or "adb")
        self.device_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_devices)

        # Custom serial input and connect button
        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("e.g., 127.0.0.1:5555")
        if self._env_serial:
            self.serial_input.setText(self._env_serial)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_serial)

        row = 0
        grid.addWidget(self.task_type_label, row, 0, 1, 4)
        row += 1

        grid.addWidget(QLabel("ADB Path"), row, 0)
        grid.addWidget(self.adb_path_edit, row, 1)
        grid.addWidget(QLabel("Device"), row, 2)
        device_row = QWidget()
        device_layout = QHBoxLayout(device_row)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_layout.addWidget(self.device_combo, 1)
        device_layout.addWidget(self.refresh_btn)
        grid.addWidget(device_row, row, 3)
        row += 1

        # Custom serial row
        grid.addWidget(QLabel("Custom Serial"), row, 0)
        serial_row = QWidget()
        serial_layout = QHBoxLayout(serial_row)
        serial_layout.setContentsMargins(0, 0, 0, 0)
        serial_layout.addWidget(self.serial_input, 1)
        serial_layout.addWidget(self.connect_btn)
        grid.addWidget(serial_row, row, 1, 1, 3)
        row += 1

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.load_btn = QPushButton("Load Task")
        self.screenshot_btn = QPushButton("Screenshot")
        self.run_btn = QPushButton("Run")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)

        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.screenshot_btn)
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.stop_btn)
        grid.addWidget(btn_row, row, 0, 1, 4)

        self.load_btn.clicked.connect(self.load_task)
        self.screenshot_btn.clicked.connect(self.take_screenshot)
        self.run_btn.clicked.connect(self.start_run)
        self.stop_btn.clicked.connect(self.stop_run)

        self.refresh_devices()
        return box

    def _build_log_panel(self) -> QWidget:
        box = QGroupBox("Run Log")
        layout = QVBoxLayout(box)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)

        # Clear log button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        btn_layout.addWidget(self.clear_log_btn)
        layout.addLayout(btn_layout)
        return box

    def refresh_devices(self) -> None:
        self.device_combo.clear()
        adb_path = self.adb_path_edit.text().strip() or "adb"
        try:
            devices = ADBClient.list_devices(adb_path=adb_path)
        except ADBError as exc:
            self.device_combo.addItem("")
            self._append_log(f"[WARN] {exc}")
            return
        if not devices:
            self.device_combo.addItem("")
            return
        for item in devices:
            self.device_combo.addItem(item.serial)

    def connect_serial(self) -> None:
        """Connect to a custom ADB serial port."""
        serial = self.serial_input.text().strip()
        if not serial:
            QMessageBox.warning(self, "Invalid Serial", "Please enter a serial port.")
            return
        adb_path = self.adb_path_edit.text().strip() or "adb"
        try:
            adb = ADBClient(adb_path=adb_path)
            adb.connect(serial)
            self._append_log(f"Connected to {serial}")
            self.refresh_devices()
            idx = self.device_combo.findText(serial)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
            QMessageBox.information(self, "Connect", f"Successfully connected to {serial}")
        except ADBError as exc:
            QMessageBox.critical(self, "Connect Failed", str(exc))
            self._append_log(f"[ERROR] Connect failed: {exc}")

    def load_task(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Task",
            str(Path.cwd()),
            "Python Task Files (*.py)"
        )
        if not path:
            return

        try:
            self.task = load_task_for_gui(path)
            self.task_type_label.setText(f"Python DSL: {Path(path).name}")
            self.current_file = Path(path)
            self._append_log(f"Loaded task: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Load Failed", str(exc))
            self._append_log(f"[ERROR] Load failed: {exc}")

    def take_screenshot(self) -> None:
        """Take a screenshot from the connected device."""
        adb_path = self.adb_path_edit.text().strip() or "adb"
        serial = self.device_combo.currentText().strip() or self.serial_input.text().strip() or None

        try:
            adb = ADBClient(adb_path=adb_path, serial=serial)
            adb.ensure_device()
            screenshot = adb.screenshot()

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_dir = Path.cwd() / "logs" / "manual_screenshots"
            default_dir.mkdir(parents=True, exist_ok=True)
            default_path = default_dir / f"screenshot_{timestamp}.png"

            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Screenshot",
                str(default_path),
                "PNG (*.png)"
            )
            if not path:
                return

            cv2.imwrite(path, screenshot)
            self._append_log(f"Screenshot saved: {path}")
            QMessageBox.information(self, "Screenshot", f"Screenshot saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Screenshot Failed", str(exc))
            self._append_log(f"[ERROR] Screenshot failed: {exc}")

    def start_run(self) -> None:
        if not hasattr(self, "task") or self.task is None:
            QMessageBox.warning(self, "No Task", "Please load a task first.")
            return

        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, "Busy", "Task is already running.")
            return

        # Get ADB configuration from GUI
        adb_path = self.adb_path_edit.text().strip() or "adb"
        serial = self.device_combo.currentText().strip() or self.serial_input.text().strip() or None

        self.thread = QThread(self)
        self.worker = RunnerWorker(self.task, adb_path, serial)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._append_log)
        self.worker.error.connect(self._on_run_error)
        self.worker.finished.connect(self._on_run_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_worker)
        self.thread.start()

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._append_log("Run started.")

    def stop_run(self) -> None:
        """Stop the currently running task."""
        if self.worker and self.worker.runner:
            self.worker.runner.stop()
            self._append_log("Stop requested.")
        else:
            self._append_log("[WARN] No active runner to stop")
        self.stop_btn.setEnabled(False)

    def _on_run_finished(self) -> None:
        self._append_log("Run finished.")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _cleanup_worker(self) -> None:
        """Clean up worker reference after thread finishes."""
        self.worker = None

    def _on_run_error(self, message: str) -> None:
        self._append_log(f"[ERROR] {message}")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

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
        self.log_view.append(text)

    def clear_log(self) -> None:
        """Clear all log messages."""
        self.log_view.clear()
