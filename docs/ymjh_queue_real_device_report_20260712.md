# ymjh_bot 16416 端口完整队列真机测试报告

## 测试概况

- 测试时间：2026-07-12 02:37 - 04:42
- 测试设备：`adb -s 127.0.0.1:16416`
- 队列状态文件：`E:\play-agent\src\ymjh_bot\.task_queue_states\127.0.0.1_16416.json`
- 截图目录：`E:\play-agent\screenshots\ymjh_queue_full_20260712_023709`
- 最终完成日志：`E:\play-agent\logs\queue_full_20260712_023709_resume_kyrw_npc_course_button.out.log`
- 最终结果：完整队列执行完成，日志出现 `QUEUE_COMPLETED`，状态文件已清空 `progress`

## 队列结果

| 序号 | 任务 | 结果 | 说明 |
|---:|---|---|---|
| 1 | 每日一卦 | 通过 | 队列继续推进 |
| 2 | 茶馆说书 | 通过 | 真机发现答题/座位流程问题后修复并通过 |
| 3 | 坐观万象 | 通过 | 完成 |
| 4 | 华山论剑 | 通过 | 1v1 领取；3v3 按配置最多 5 次，未拿到首胜奖励但达到上限后继续 |
| 5 | 江湖英雄榜 | 通过 | 2 场后挑战次数为 0，任务完成 |
| 6 | 帮派任务 | 通过/跳过 | 账号不在帮派，新增识别后按无帮派场景跳过 |
| 7 | 门客设宴 | 通过 | 无可邀约门客，验证后完成 |
| 8 | 破阵设宴 | 通过 | 无可邀约破阵，验证后完成 |
| 9 | 课业任务 | 通过 | 多轮真机修复后完成，任务栏追踪消失验证通过 |
| 10 | 日常副本 | 通过 | 匹配进入副本，副本追踪稳定消失后判定完成 |
| 11 | 聚义平冤 | 通过/跳过 | 行当页入口已消失，验证后完成 |

## 关键截图

| 截图 | 内容 |
|---|---|
| `00_start.png` | 队列开始 |
| `05_cgss_after_seat_fix.png` | 茶馆说书修复后继续 |
| `10_hslj_3v3_waiting.png`, `11_hslj_3v3_battle.png` | 华山论剑 3v3 等待/战斗 |
| `14_jhyxb_battle_state.png`, `15_jhyxb_long_battle.png` | 江湖英雄榜战斗 |
| `18_bprw_accept_missing.png` | 帮派列表/无帮派识别 |
| `26_kyrw_course_flow.png`, `28_kyrw_flow_2.png`, `29_kyrw_npc_course_button.png` | 课业任务追踪、提交、NPC 课业按钮处理 |
| `30_rcfb_watch.png` | 日常副本阶段 |
| `31_queue_completed.png` | 队列完成后最终画面 |

## 本次真机发现并修复的问题

| 问题 | 修复 |
|---|---|
| headless 队列不便从 UI 状态恢复 | 新增 `src/ymjh_bot/run_queue.py`，按保存状态恢复并写入进度 |
| 队列锁/进程 PID 可能复用导致误判 | 修复 `src/ymjh_bot/ui/task_queue_state.py` 的 stale PID 识别 |
| 茶馆说书答题/座位流程卡住 | 修复 `src/ymjh_bot/task/CGSS_task.py` 的答题轮询和座位点 |
| 华山论剑安全区/匹配超时阻断队列 | 修复 `src/ymjh_bot/task/HSLJ_task.py`，降低安全区失败影响，匹配超时后取消并继续 |
| 江湖英雄榜安全区失败阻断 | 修复 `src/ymjh_bot/task/JHYXB_task.py`，允许继续任务 |
| 帮派任务在无帮派账号上误进流程 | 修复 `src/ymjh_bot/task/BPRW_task.py`，新增 `text_BPRW_bangpai_list_title.png` 判断无帮派并跳过 |
| 课业 NPC 按钮文案从“悟禅”变为“课业” | 新增 `btn_kyrw_npc_course.png`，支持旧/新 NPC 动作按钮 |
| 课业恢复时停在 stale NPC 场景 | 增加接取失败后回跳悟禅活动入口重新寻路 |
| 课业追踪文案为“[止杀师门]库房(5/5)”而非旧课业模板 | 新增 `text_kyrw_shimen_sidebar.png` 并纳入追踪识别 |

## 未修复/条件说明

- 华山论剑 3v3 本次未在 5 次上限内拿到首胜奖励；按用户队列配置的 `first_win + count=5` 达上限后继续，不阻塞全队列。
- 帮派任务因当前账号未加入帮派跳过，不属于自动化失败。
- 聚义平冤入口在活动页已消失，按“今日入口已消失/已完成”处理并通过验证。

## 回归测试

- `pytest tests/test_kyrw_task.py tests/test_hslj_task.py tests/test_jhyxb_task.py tests/test_bangpai_task.py -q`：87 passed
- `pytest tests/test_cgss_task.py tests/test_task_queue_state.py tests/test_kyrw_task.py tests/test_hslj_task.py tests/test_jhyxb_task.py tests/test_bangpai_task.py -q`：112 passed
- `pytest tests/test_task_queue_runner_progress.py -q`：4 passed
- 新增模板人工校验：
  - `text_kyrw_shimen_sidebar.png` 在 `26_kyrw_course_flow.png` 左侧任务栏 ROI 中匹配成功，score `0.99999994`
  - `btn_kyrw_npc_course.png` 在 `28_kyrw_flow_2.png` NPC 动作 ROI 中匹配成功，score `1.0`

## 结论

本次已在 `127.0.0.1:16416` 真机端口完整跑完保存的 11 项任务队列。过程中发现的阻塞问题已修复并回归验证，最终日志记录 `QUEUE_COMPLETED`，状态文件保留队列配置但不再包含进度字段。
