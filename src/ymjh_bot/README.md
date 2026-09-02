# ymjh_bot

中文 | [English](README_EN.md) | [返回 PlayAgent](../../README.md)

`ymjh_bot` 是 PlayAgent 中面向《一梦江湖》的任务队列应用。它负责游戏启动与登录、角色切换、任务编排、失败恢复、状态持久化，以及基于真机截图模板的界面识别。

## 运行要求

- 先按照[根目录 README](../../README.md)完成依赖安装
- ADB 设备应显示为 `device` 状态
- 游戏画面固定为 `1280 × 720`
- 同一设备同一时间只运行一个任务队列

检查设备：

```powershell
adb devices -l
```

如需设置默认设备，可编辑根目录 `.env`：

```dotenv
DEFAULT_ADB_PATH=adb
DEFAULT_ADB_SERIAL=127.0.0.1:16384
```

## 图形界面

启动任务队列管理器：

```powershell
uv run ymjh-bot
```

等价入口：

```powershell
uv run python -m ymjh_bot.main
```

基本使用流程：

1. 选择或填写 ADB 设备。
2. 使用 `角色1` 至 `角色5` 复选框选择任意角色组合。
3. 将任务加入队列并调整顺序；部分任务可在界面中设置运行策略。
4. 启动队列。角色始终按编号升序执行，每个角色使用一组全新的任务实例。
5. 通过运行日志查看当前角色、任务、步骤、重试、清理和最终摘要。

`调试任务（等待 10 秒）` 用于验证多角色切换。它在角色校验成功后仅等待十秒，不执行识图、点击或游戏恢复。

## 无界面运行

无界面执行器读取该设备由 GUI 保存的任务顺序、任务设置和角色配置：

```powershell
uv run python -m ymjh_bot.run_queue --serial 127.0.0.1:16384
```

常用选项：

```powershell
# 临时指定角色 1、3、5；--role 可以重复
uv run python -m ymjh_bot.run_queue --serial 127.0.0.1:16384 `
  --role 1 --role 3 --role 5

# 兼容选项：选择前 3 个角色
uv run python -m ymjh_bot.run_queue --serial 127.0.0.1:16384 --roles 3

# 清除断点后从任务图起点开始，保留任务顺序和设置
uv run python -m ymjh_bot.run_queue --serial 127.0.0.1:16384 --clear-progress

# 输出详细模板、坐标和轮询日志
uv run python -m ymjh_bot.run_queue --serial 127.0.0.1:16384 --debug
```

可用参数还包括 `--adb-path <路径>`。无界面执行器不会通过命令行选择任务；请先在 GUI 中保存该设备的任务队列。

## 角色、失败与进度语义

- 进度由“角色位置、任务位置、步骤位置”共同组成。
- 暂停会保留当前进度；继续后从保存位置恢复。
- 用户点击“停止”表示主动结束整条队列，并清除本次运行进度。
- 单个任务完整流程最多尝试三次；每次失败后先执行任务自己的安全清理。
- 重试耗尽且清理成功时，当前任务记为失败，当前角色剩余任务记为放弃，然后切换下一角色。
- 常规清理失败时，任务会强制重启游戏并验证安全主界面；恢复成功后切换下一角色，恢复失败则停止队列并保留进度。
- 运行摘要区分全部成功、完成但存在失败、用户停止和恢复失败，并统计成功、失败、放弃及未执行任务。

每个设备的配置和进度独立保存在：

```text
src/ymjh_bot/.task_queue_states/<安全化ADB序列号>.json
```

同一序列号具有运行锁，防止 GUI 和无界面队列重复启动。

## 可用任务

| Key | 界面名称 |
|---|---|
| `BPRW` | 帮派任务 |
| `CGSS` | 茶馆说书 |
| `DEBUG` | 调试任务（等待 10 秒） |
| `HSLJ` | 华山论剑 |
| `JHXS` | 江湖行商 |
| `JHYXB` | 江湖英雄榜 |
| `JYPY` | 聚义平冤 |
| `KYRW` | 课业任务 |
| `MKSY` | 门客设宴 |
| `MRYG` | 每日一卦 |
| `PZSY` | 破阵设宴 |
| `RCFB` | 日常副本 |
| `SHRW` | 生活任务 |
| `XSRW` | 悬赏任务 |
| `ZGWX` | 坐观万象 |

华山论剑支持分别配置 1v1、3v3 的首胜、固定场次或持续执行策略。生活任务支持材料类型、循环分线和分线范围设置。

## 目录结构

```text
src/ymjh_bot/
├── main.py                 # GUI 入口
├── run_queue.py            # 无界面队列入口
├── ym_game_task.py         # 游戏共享导航、识图和恢复能力
├── runner/                 # 队列执行器、角色切换和任务工厂
├── task/                   # Python DSL 任务
├── templates/              # 识图模板
├── ui/                     # 队列界面与状态持久化
├── lifecycle/              # 生命周期辅助逻辑
└── app/                    # 应用层辅助模块
```

新增任务时，在 `task/` 中创建 `*_task.py`，继承 `YmGameTask`，并设置唯一的 `task_key`、用户可见的 `task_name` 和带 `@step` 的步骤方法。

## 正式包打包（Windows x64）

当前正式包使用仓库根目录的 `ymjh_bot.spec` 构建，是 **PyInstaller 目录包（onedir）**，不是单文件包。`ymjh-bot.exe` 依赖同目录下的 `_internal/`，发布时必须分发整个 `ymjh-bot/` 目录或下述 ZIP，不能只复制 EXE。

请在 Windows x64 环境中使用 64 位 Python，并从仓库根目录执行。PyInstaller `6.22.1` 已锁定在项目依赖中，新环境先同步依赖：

```powershell
uv sync --dev
```

使用项目内置命令生成正式包：

```powershell
uv run ymjh-build-release
```

该命令会依次执行完整测试、调用 `ymjh_bot.spec` 构建、复制 `.env.example`、生成 ZIP，并写出 SHA-256 文件。仅当当前源码已经通过完整测试时，才可临时跳过测试阶段：

```powershell
uv run ymjh-build-release --skip-tests
```

构建配置会收集 `ymjh_bot.task` 的所有任务模块，并把 `templates/` 和 `task/` 作为运行数据打入目录包。GUI 使用无控制台窗口模式。输出如下：

```text
build/release/ymjh_bot/                  # PyInstaller 中间文件，不发布
dist/release/ymjh-bot/                   # 可运行目录，必须整体保留
└── ymjh-bot.exe
dist/release/ymjh-bot-windows-x64.zip    # 正式发布包
dist/release/ymjh-bot-windows-x64.zip.sha256
```

正式包不内置 ADB，也不会带入开发机的日志和队列进度。项目命令只会复制公开的 `.env.example`，不会复制开发机根目录的 `.env`，从而避免发布本地路径或设备序列号。

发布前应在一个不包含源码的空目录中解压 ZIP，并完成以下验收：

1. ZIP 解压后顶层为 `ymjh-bot/`，其中同时存在 `ymjh-bot.exe`、`.env` 和 `_internal/`。
2. 启动 `ymjh-bot.exe`，确认队列界面正常显示；该构建没有控制台窗口，运行信息在界面和 `logs/` 中查看。
3. 将 ADB 加入 `PATH`，或在 `.env`/界面中配置 ADB 路径和设备序列号，确认设备可连接。
4. 执行一次截图或调试任务，再用两个角色运行 `调试任务（等待 10 秒）`，确认任务启动、日志写入和角色切换正常。
5. 对照命令生成的 `.sha256` 文件复核发布包：

```powershell
Get-FileHash `
  -LiteralPath dist\release\ymjh-bot-windows-x64.zip `
  -Algorithm SHA256

Get-Content `
  -LiteralPath dist\release\ymjh-bot-windows-x64.zip.sha256
```

正式发布应从 PyInstaller 新生成的目录立即制作 ZIP，再到另一个空目录解压验收。不要先运行 `dist/release/ymjh-bot/ymjh-bot.exe` 再压缩该目录，否则运行时生成的日志或队列状态可能被带入正式包。源码、模板或依赖有变化时必须重新运行 PyInstaller。

## 日志与排查

队列日志按设备和运行批次保存：

```text
logs/<安全化ADB序列号>/run_<时间戳>/
├── events.jsonl
└── shots/
```

排查失败时优先查看 `events.jsonl` 中最后一个失败步骤、任务重试与角色推进记录，再查看日志引用的 `shots/*.png`。截图文件是失败现场证据，不代表识图过程会默认把每一帧写入磁盘。

## 测试

运行全部测试：

```powershell
uv run pytest -q
```

常用专项测试：

```powershell
uv run pytest tests/test_multi_role_queue.py tests/test_multi_role_gui.py -q
uv run pytest tests/test_rcfb_sidebar_tracker.py tests/test_xsrw_task_flow.py -q
uv run pytest tests/test_task_sidebar_state.py tests/test_bprw_task_flow.py -q
```

需要真实 ADB 设备的测试应使用 `integration` 标记；普通测试不得依赖当前模拟器状态。
