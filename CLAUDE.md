# Project Context

## 项目概述

这是一个 Android 模拟器游戏自动化项目。任务定义统一使用 Python DSL，YAML 支持已移除。

## 架构

- **botCore**: 唯一基础层，包含 ADB、视觉、日志、Python DSL、任务加载和 DSL runner
- **game_bot**: 开发调试 GUI/CLI，只用于内部调试 Python 任务脚本
- **ymjh_bot**: 一梦江湖子 bot，包含正式任务脚本、模板、任务队列 runner 和 UI

## 开发规范

- 会话过程文件统一存放于 `.local/sessions/<会话标识>/`，遵守根目录 `AGENTS.md` 和 [开发产物管理](docs/DEVELOPMENT_ARTIFACTS.md)；不要向 `docs/` 或旧 `artifacts/` 写入临时报告与探针。
- 使用 `uv` 管理依赖和虚拟环境
- 子 bot 任务脚本统一从 `botCore` 导入 DSL API
- 一梦江湖任务放在 `src/ymjh_bot/task/`
- 模板图片放在对应子 bot 的 `templates/` 目录

## 常用命令

```bash
# 运行 Python DSL 任务
python -m game_bot.run --task src/ymjh_bot/task/QDYX_task.py

# 开发调试 GUI
python -m game_bot.main
python launch_gui.py
```

## 偏好设置

- 响应使用简洁的中文
- 代码修改前先读取文件
- 优先使用 Edit 工具而非重写整个文件
