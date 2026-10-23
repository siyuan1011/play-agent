"""关闭窗口时的队列停止顺序和 ADB 服务清理回归。"""

import subprocess
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QMainWindow

from botCore import ADBClient, ADBError
from ymjh_bot.ui.task_queue_window import TaskQueueWindow


class ShutdownWindow(QMainWindow):
    """复用正式关闭逻辑，不加载真实设备配置。"""

    closeEvent = TaskQueueWindow.closeEvent  # 待验证的正式窗口关闭方法。


@pytest.fixture
def window(monkeypatch):
    """monkeypatch：隔离 Qt 环境与真实 ADB 服务调用。"""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])  # 保持 Qt 应用存活。
    owner = ShutdownWindow()  # 不创建真实任务的测试窗口。
    owner.thread = None  # 默认没有运行中的线程。
    owner.worker = None  # 默认没有运行中的队列。
    owner._closing = False  # 尚未开始关闭。
    owner._adb_shutdown_done = False  # 尚未清理服务。
    owner.adb_path_edit = QLineEdit("custom-adb.exe", owner)  # 自定义 ADB 路径。
    owner._append_log = Mock()  # 不写真实日志。
    owner.stop_queue = Mock()  # 不修改设备进度。
    owner._release_run_lock = Mock()  # 不访问真实运行锁。
    monkeypatch.setattr(ADBClient, "kill_server", Mock())
    yield owner
    owner.thread = None
    owner.close()
    app.processEvents()


def test_idle_close_cleans_adb_once(window):
    """window：无运行队列的隔离窗口。"""
    event = QCloseEvent()  # 模拟正常窗口关闭。
    window.closeEvent(event)
    window.closeEvent(event)
    assert event.isAccepted()
    ADBClient.kill_server.assert_called_once_with(adb_path="custom-adb.exe")
    window._release_run_lock.assert_called()


def test_close_waits_for_worker_initialization_and_exit(window, monkeypatch):
    """window：隔离窗口；monkeypatch：截获关闭重试，避免实际定时器。"""
    monkeypatch.setattr("ymjh_bot.ui.task_queue_window.QTimer.singleShot", Mock())
    window.thread = Mock()  # 模拟尚在运行的后台线程。
    window.thread.isRunning.return_value = True
    window.worker = Mock()  # 模拟尚未构造 runner 的工作对象。
    window.worker.runner = None
    event = QCloseEvent()  # 线程运行期间的关闭请求。
    window.closeEvent(event)
    assert not event.isAccepted()
    ADBClient.kill_server.assert_not_called()
    window.worker.runner = Mock()  # 下一轮关闭检查时 runner 已初始化。
    window.closeEvent(event)
    window.worker.runner.stop.assert_called_once()
    window.stop_queue.assert_called_once()
    ADBClient.kill_server.assert_not_called()
    window.thread.isRunning.return_value = False
    window.closeEvent(event)
    assert event.isAccepted()
    ADBClient.kill_server.assert_called_once()


def test_cleanup_failure_is_visible_and_does_not_block_exit(window, monkeypatch):
    """window：隔离窗口；monkeypatch：截获错误提示。"""
    warning = Mock()  # 记录服务停止失败提示。
    monkeypatch.setattr("ymjh_bot.ui.task_queue_window.QMessageBox.warning", warning)
    ADBClient.kill_server.side_effect = ADBError("服务停止超时")
    event = QCloseEvent()  # 即使清理失败也应接受的关闭事件。
    window.closeEvent(event)
    assert event.isAccepted()
    warning.assert_called_once_with(window, "ADB 服务清理失败", "服务停止超时")


def test_kill_server_uses_global_command(monkeypatch):
    """monkeypatch：截获子进程，确保不操作真实设备。"""
    run = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))  # 成功的命令结果。
    monkeypatch.setattr("botCore.adb_client._run_adb_process", run)
    ADBClient.kill_server("custom-adb.exe", timeout_sec=3)
    run.assert_called_once_with(["custom-adb.exe", "kill-server"], text=True, timeout_sec=3)


@pytest.mark.parametrize("failure", [FileNotFoundError("missing"), subprocess.TimeoutExpired("adb", 10)])
def test_kill_server_wraps_process_failure(monkeypatch, failure):
    """monkeypatch：隔离子进程；failure：启动失败或命令超时异常。"""
    monkeypatch.setattr("botCore.adb_client._run_adb_process", Mock(side_effect=failure))
    with pytest.raises(ADBError, match="停止 ADB 服务失败"):
        ADBClient.kill_server()


def test_kill_server_reports_nonzero_exit(monkeypatch):
    """monkeypatch：模拟 ADB 返回非零退出码。"""
    monkeypatch.setattr(
        "botCore.adb_client._run_adb_process",
        Mock(return_value=subprocess.CompletedProcess([], 1, "", "server error")),
    )
    with pytest.raises(ADBError, match="server error"):
        ADBClient.kill_server()
