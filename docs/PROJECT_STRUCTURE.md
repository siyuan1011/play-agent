# 项目结构说明

## 目录结构

```text
src/
├── botCore/                  # 基础能力与 Python DSL Runtime
│   ├── __init__.py           # 公共 API 出口
│   ├── adb_client.py         # ADBClient / DeviceInfo
│   ├── coords.py             # 坐标缩放、随机偏移、等待抖动
│   ├── execution.py          # DSL 单步执行、重试、超时、跳转解析
│   ├── loader.py             # Python 任务脚本动态加载
│   ├── logger.py             # RunLogger
│   ├── models.py             # ExecutionResult
│   ├── runner.py             # DSLTaskRunner
│   ├── task.py               # GameTask / step / 跳转异常
│   └── vision.py             # 模板匹配
│
├── game_bot/                 # 开发调试入口
│   ├── main.py               # 调试 GUI 入口
│   ├── run.py                # 调试 CLI，只运行 Python 任务脚本
│   ├── task_loader.py        # .py 任务加载
│   └── ui/main_window.py     # 调试窗口
│
└── ymjh_bot/                 # 一梦江湖子 bot
    ├── runner/               # 任务队列执行器
    ├── task/                 # 一梦江湖 Python DSL 任务
    ├── templates/            # 模板图片
    └── ui/                   # 一梦江湖任务队列 UI

docs/                         # 持续维护的正式文档
.local/sessions/              # 按会话归档的开发过程产物（Git 忽略）
logs/                         # 应用运行日志（Git 忽略）
tests/                        # 测试
launch_gui.py                 # 开发调试 GUI 快捷入口
```

## 模块职责

会话计划、临时脚本、截图和验证报告遵循 [开发产物管理](DEVELOPMENT_ARTIFACTS.md)。

### botCore

`botCore` 是唯一基础层，封装所有可复用能力：

- ADB：设备发现、连接、点击、滑动、截图
- Vision：模板匹配
- DSL：`GameTask`、`@step`、跳转、暂停停止响应
- Runner：`DSLTaskRunner`
- Loader：`load_task_class()`、`load_task_instance()`
- Logging：运行日志和截图标注

公共导入：

```python
from botCore import (
    ADBClient,
    DSLTaskRunner,
    GameTask,
    RunLogger,
    VisionEngine,
    load_task_class,
    load_task_instance,
    step,
)
```

### game_bot

`game_bot` 只用于开发调试，不承载正式游戏脚本 UI。

- `launch_gui.py` / `python -m game_bot.main`：打开调试窗口
- `python -m game_bot.run --task <task.py>`：运行单个 Python DSL 脚本

### 子 bot

实际游戏脚本和脚本 UI 放在对应子 bot 中。当前子 bot：

- `ymjh_bot/task/*.py`：一梦江湖任务脚本
- `ymjh_bot/ui/task_queue_window.py`：一梦江湖任务队列 UI
- `ymjh_bot/runner/task_queue_runner.py`：多任务队列执行

## 依赖关系

```text
botCore  ← 基础层
   ↑
game_bot / ymjh_bot / future_sub_bot
```

## 迁移说明

- YAML 支持已删除，不再维护 `yamlBot`、YAML 文件或 YAML runner。
- 旧 `dslBot` 已并入 `botCore`，任务脚本使用：

```python
from botCore import GameTask, step, StepJumpException
```
