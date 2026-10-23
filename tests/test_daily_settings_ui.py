"""日常任务设置面板的选项与布局回归。"""
from PySide6.QtWidgets import QApplication, QWidget, QLabel
from ymjh_bot.ui.task_queue_window import TaskQueueWindow

class SettingsPanel(QWidget):
    """只构建设置面板，避免读取或修改真实设备配置。"""
    _build_rcgm_settings_panel = TaskQueueWindow._build_rcgm_settings_panel  # 生产面板构建方法。
    _collect_rcgm_settings_from_ui = TaskQueueWindow._collect_rcgm_settings_from_ui  # 生产设置采集方法。
    _apply_rcgm_settings = TaskQueueWindow._apply_rcgm_settings  # 生产设置恢复方法。

    def confirm_task_settings(self):
        """self 为隔离测试面板；不写真实配置。"""

def test_daily_settings_panel(monkeypatch):
    """monkeypatch 设置无窗口测试环境；检查新选项可保存和恢复。"""
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    app = QApplication.instance() or QApplication([])  # 保持 Qt 应用对象存活。
    owner = SettingsPanel()  # 不连接设备的隔离面板对象。
    panel = owner._build_rcgm_settings_panel()  # 正式方法生成的设置区域。
    assert len(owner.rcgm_item_checks) == 5
    assert owner.rcgm_item_checks['shanhe'].text() == '山河器'
    assert not owner.rcgm_item_checks['shanhe'].isChecked()
    assert not any('数量输入 99' in label.text() for label in panel.findChildren(QLabel))  # label 为面板中的每个说明标签。
    owner.rcgm_item_checks['shanhe'].setChecked(True)
    settings = owner._collect_rcgm_settings_from_ui()  # 勾选山河器后的可持久化配置。
    owner._apply_rcgm_settings(settings)
    assert owner.rcgm_item_checks['shanhe'].isChecked()
    assert panel.layout().itemAtPosition(0, 4).widget() is owner.rcgm_item_checks['shanhe']
    assert panel.layout().itemAtPosition(0, 5).widget() is owner.rcgm_settings_confirm_btn
    panel.close()
    owner.close()
    app.processEvents()
