# YMJH 任务队列测试报告 - 2026-07-09

## 测试对象

- ADB serial: `127.0.0.1:16416`
- 保存队列: `MRYG -> CGSS -> ZGWX -> BPRW`
- 状态文件: `src/ymjh_bot/.task_queue_states/127.0.0.1_16416.json`
- 正式运行日志: `logs/queue_manual_20260709_201539.out.log`
- 结构化事件: `logs/127.0.0.1_16416/run_20260709_201539_823164/events.jsonl`
- 现场截图:
  - `screenshots/ymjh_queue_watch_20260709_2019.png`
  - `screenshots/ymjh_queue_watch_20260709_2020.png`
  - `screenshots/ymjh_queue_final_20260709_2021.png`

## 执行摘要

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| ADB 连接 | 通过 | `127.0.0.1:16416` 为 `device`，游戏前台包为 `com.netease.wyclx` |
| 分辨率探测 | 警告 | `wm size=720x1280`，截图为 `1280x720`，runner 已切换使用截图尺寸 |
| 本地全量单测 | 失败 | `216 passed, 2 skipped, 2 failed`，失败集中在 `ZGWX` 轮询参数测试 |
| 相关单测 | 失败 | `39 passed, 2 failed`，同样为 `ZGWX` 测试期望与代码参数不一致 |
| 每日一卦 | 通过 | 4/4 步骤成功，20:16:45 完成 |
| 茶馆说书 | 阻塞 | 进入茶馆成功，但 `click_answer` 固定点击第三选项，约 3.5 分钟未完成 |
| 坐观万象 | 未触达 | 被茶馆说书阻塞，队列未进入第 3 个任务 |
| 帮派任务 | 未触达 | 被茶馆说书阻塞，队列未进入第 4 个任务 |

## 关键现场发现

1. `MRYG` 正常完成。
   - `close_all`、`open_huodong`、`auto_pathfinding`、`enter_panel` 全部 OK。
   - 日志记录: `每日一卦任务完成：4/4 步骤成功`。

2. `CGSS` 能打开活动入口、自动寻路并进入茶馆。
   - `open_huodong` OK。
   - `auto_pathfinding` OK，用时约 36 秒。
   - `enter_chaguan` OK。

3. `CGSS` 在答题循环中不可靠。
   - `src/ymjh_bot/task/CGSS_task.py` 固定 `POINT_ANSWER = (1232, 540)`，即第三选项。
   - `click_answer` 步骤 `timeout_ms=None`，退出条件只有识别到 `btn_TCCG.png`。
   - 现场截图显示高额奖励次数从 `1/5` 仅推进到 `2/5`，脚本仍持续点击第三选项，未出现退出按钮。
   - 单测只覆盖“退出按钮最终出现”的理想路径，没有覆盖答题次数不推进或长时间未完成。

4. `ZGWX` 单测与实现不一致。
   - 当前代码使用开始轮询间隔 `1500ms`，测试期望 `500ms`。
   - 当前代码使用完成检测 `missing_threshold=20`、`interval_ms=5000`，测试期望 `60`、`500ms`。
   - 需要确认这是有意调参还是回归；确认后同步代码或测试。

## 修复计划

1. 修复 `CGSS.click_answer` 的无限循环风险。
   - 给 `click_answer` 增加总超时或最大答题轮数。
   - 增加现场状态日志，例如每 N 次记录当前 `btn_TCCG` 匹配分、答题循环次数。
   - 超时后保存截图并抛出明确异常，避免阻塞后续任务。

2. 修复茶馆答题策略。
   - 不再固定点击第三选项。
   - 短期方案: 四个选项轮询或随机点击，至少避免长期卡同一错误答案。
   - 稳定方案: 基于题目/选项 OCR 或题库映射选择正确答案，并验证奖励次数推进。

3. 补充 `CGSS` 单测。
   - 覆盖固定选项长时间未出现退出按钮时会超时失败。
   - 覆盖选项轮询/随机策略调用顺序。
   - 覆盖失败时会留下可诊断日志或截图路径。

4. 处理 `ZGWX` 测试漂移。
   - 若 1500ms 和 5000ms 是新策略，更新 `tests/test_zgwx_task.py` 期望。
   - 若不是有意修改，则恢复 `ZGWX_task.py` 的轮询参数。
   - 修复后重跑全量 `pytest`。

5. 复测顺序。
   - 先跑 `pytest -q`，确保单测全绿。
   - 再跑完整队列 `MRYG -> CGSS -> ZGWX -> BPRW`。
   - 若 `CGSS` 通过，再记录 `ZGWX` 和 `BPRW` 的现场耗时、完成截图和异常点。
