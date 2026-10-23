"""可用任务排序、转移及配置恢复的离线回归。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidget

from ymjh_bot.ui.task_queue_state import load_state, save_state
from ymjh_bot.ui.task_queue_window import TaskQueueWindow


class TaskPanel:
    """复用正式排序与转移逻辑，不启动设备或完整窗口。"""

    _sort_available_tasks = TaskQueueWindow._sort_available_tasks  # 正式排序逻辑。
    _update_available_list = TaskQueueWindow._update_available_list  # 正式候选列表渲染逻辑。
    _on_available_reordered = TaskQueueWindow._on_available_reordered  # 正式拖动处理逻辑。
    add_selected_tasks = TaskQueueWindow.add_selected_tasks  # 正式多选加入逻辑。

    def _save_state_from_ui(self):
        """self 为隔离面板，测试不写真实设备配置。"""

    def _update_selected_list(self):
        """self 为隔离面板，转移结果直接检查 selected_tasks。"""


def test_available_order_roundtrip_and_transfer(monkeypatch, tmp_path):
    """monkeypatch 设置离屏 Qt；tmp_path 保存独立测试配置。"""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])  # 保持 Qt 应用存活。
    panel = TaskPanel()  # 不操作设备的隔离面板。
    panel._state = {"selected_task_keys": ["MRYG", "RCGM"]}  # 模拟尚未保存候选排序的旧配置。
    panel.available_tasks = [
        {"key": key, "name": key} for key in ["DEBUG", "RCGM", "CGSS", "MRYG"]
    ]  # 完整任务目录；key 为各任务唯一标识。
    panel.selected_tasks = [{"key": "RCGM"}]  # 保留一个已入队任务，检查隐藏位置不丢失。
    panel.available_list = QListWidget()  # 离屏候选列表。
    panel.available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
    panel._sort_available_tasks()
    assert panel._state["available_task_order"] == ["MRYG", "RCGM", "CGSS", "DEBUG"]
    panel._update_available_list()
    item = panel.available_list.takeItem(2)  # 模拟将最后一个候选拖到最前。
    panel.available_list.insertItem(0, item)
    panel._on_available_reordered()
    assert panel._state["available_task_order"] == ["DEBUG", "RCGM", "MRYG", "CGSS"]
    path = tmp_path / "state.json"  # 独立持久化文件。
    save_state(path, panel._state)
    panel._state = load_state(path)
    panel._sort_available_tasks()
    panel._update_available_list()
    panel.available_list.selectAll()
    panel.add_selected_tasks()
    assert [task["key"] for task in panel.selected_tasks] == ["RCGM", "DEBUG", "MRYG", "CGSS"]  # task 为入队后的各任务。
    assert panel.available_list.count() == 0
    panel.selected_tasks = []
    panel._update_available_list()
    assert [
        panel.available_list.item(row).data(Qt.ItemDataRole.UserRole)["key"]
        for row in range(panel.available_list.count())  # row 为清空队列后恢复的候选行号。
    ] == ["DEBUG", "RCGM", "MRYG", "CGSS"]
    panel.available_list.close()
    app.processEvents()


def test_default_available_order():
    """没有历史队列时按截图顺序排列，新任务稳定追加。"""
    panel = TaskPanel()  # 仅使用排序逻辑的隔离面板。
    panel._state = {}
    panel.available_tasks = [
        {"key": key} for key in ["DEBUG", "CGSS", "MRYG", "RCGM", "NEW"]
    ]  # key 为任务标识，NEW 模拟新增任务。
    panel._sort_available_tasks()
    assert panel._state["available_task_order"] == ["RCGM", "MRYG", "CGSS", "DEBUG", "NEW"]
