# Python DSL 任务开发指南

## 快速开始

### 1. 创建任务文件

在任务目录下创建 Python 文件，例如 `src/ymjh_bot/task/my_task.py`：

```python
from botCore import GameTask, step

class MyTask(GameTask):
    """我的自定义任务。"""

    # 配置
    design_resolution = (1280, 720)
    device_serial = "127.0.0.1:16384"
    loop_count = 1

    @step(retry=3, timeout_ms=10000)
    def step_1(self) -> bool:
        """步骤 1：关闭弹窗。"""
        while self.find_image("templates/btn_close.png"):
            self.click()
            self.wait(500)
        return True

    @step()
    def step_2(self) -> bool:
        """步骤 2：执行任务。"""
        if self.find_image("templates/btn_start.png"):
            self.click()
            self.wait(2000)
            return True
        return False
```

### 2. 运行任务

```bash
# 运行 DSL 任务
python -m game_bot.run --task src/ymjh_bot/task/my_task.py

# 指定设备
python -m game_bot.run --task src/ymjh_bot/task/my_task.py --serial 127.0.0.1:5555
```

## API 参考

### 类属性配置

```python
class MyTask(GameTask):
    design_resolution = (1280, 720)      # 设计分辨率
    device_serial = "127.0.0.1:16384"    # 设备串口
    adb_path = "adb"                     # ADB 路径
    loop_count = 1                       # 循环次数
```

### 装饰器

```python
@step(retry=3, timeout_ms=10000, enabled=True)
def my_step(self) -> bool:
    ...
```

- `retry`: 失败重试次数
- `timeout_ms`: 超时时间（毫秒）
- `enabled`: 是否启用此步骤

### 生命周期钩子

```python
def on_start(self) -> None:
    """任务开始时调用。"""
    self.close_all_popups()

def on_finish(self, results: list) -> None:
    """任务结束时调用。"""
    print(f"完成任务：{sum(1 for r in results if r.success)}/{len(results)}")
```

### 图像操作

```python
# 查找图像
if self.find_image("btn.png", threshold=0.8):
    self.click()

# 等待图像出现后点击
if self.wait_image_appear("btn_start.png", timeout_ms=5000):
    self.click()

# 只在截图指定区域中等待图像出现，ROI 格式为 (x, y, width, height)
if self.wait_image_appear(
    "btn_confirm.png",
    timeout_ms=5000,
    roi=(900, 500, 300, 200),
):
    self.click()

# 等待图像连续消失
self.wait_image_missing("popup.png", missing_threshold=3)
```

### 坐标操作

```python
# 点击设计分辨率坐标
self.click_point(500, 300)

# 点击（使用上次匹配的图像位置）
self.tap()

# 点击指定坐标
self.tap(100, 200)

# 滑动
self.swipe(100, 500, 900, 500)
```

### 等待

```python
# 简单等待
self.wait(2000)

# 等待图像出现
if self.wait_image_appear("btn.png", timeout_ms=5000):
    self.click()

# 等待图像消失
self.wait_image_missing("popup.png", missing_threshold=3)
```

## 完整示例

```python
from botCore import GameTask, step

class YmjhDailyTask(GameTask):
    """一梦江湖日常任务。"""

    design_resolution = (1280, 720)
    device_serial = "127.0.0.1:16384"
    loop_count = 1

    # 模板路径常量
    CLOSE_BTN = "templates/btn_close.png"
    START_BTN = "templates/btn_start.png"
    OK_BTN = "templates/btn_OK.png"

    def on_start(self) -> None:
        self._log("=== 任务开始 ===")
        self.close_all_popups()

    @step(retry=3)
    def close_all_popups(self) -> bool:
        """关闭所有弹窗。"""
        count = 0
        while self.find_image(self.CLOSE_BTN, threshold=0.7):
            self.click(offset=3)
            count += 1
            self.wait(500)
            if count > 10:
                break
        self._log(f"关闭了 {count} 个弹窗")
        return True

    @step()
    def start_task(self) -> bool:
        """开始任务。"""
        if self.find_image(self.START_BTN):
            self.click()
            self.wait(2000)
            return True
        return False

    @step(retry=2, timeout_ms=30000)
    def do_battle(self) -> bool:
        """执行战斗任务。"""
        self.wait_image_missing(
            self.OK_BTN,
            missing_threshold=3,
            callback=lambda found, count: self.click() if found else None,
        )
        return True

    def on_finish(self, results) -> None:
        success = sum(1 for r in results if r.success)
        self._log(f"=== 任务完成：{success}/{len(results)} ===")
```

## 最佳实践

1. **使用常量定义模板路径**
   ```python
   CLOSE_BTN = "templates/btn_close.png"
   ```

2. **复杂逻辑拆分为多个 `@step` 方法**
   ```python
   @step()
   def step1(self): ...

   @step()
   def step2(self): ...
   ```

3. **使用 `self._log()` 记录关键信息**

4. **添加适当的超时和重试**
   ```python
   @step(timeout_ms=30000, retry=3)
   ```

5. **使用生命周期钩子处理初始化和清理**
