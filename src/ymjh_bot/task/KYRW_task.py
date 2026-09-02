"""课业任务 - Python DSL 实现。"""

from dataclasses import dataclass

import cv2
import numpy as np

from botCore import ImageMatchResult, step

from ymjh_bot.ym_game_task import TaskSidebarStateError, YmGameTask


@dataclass(frozen=True, slots=True)
class _YinshiState:
    """从一张科举诗词排序面板截图推导出的状态。"""

    visible: bool
    screenshot: np.ndarray
    cards: tuple[ImageMatchResult, ...] = ()
    correct_slots: frozenset[int] = frozenset()


class KYRWTask(YmGameTask):
    """一梦江湖课业任务。"""

    task_key = "KYRW"
    task_name = "课业任务"
    task_description = "课业任务自动执行"

    BTN_KEYE_ACTIVITY_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_forward.png")
    BTN_KEYE_ENTRY_FORWARD = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_panel_keye_forward.png")
    BTN_NPC_KEYE_ACTION_TEMPLATES = [
        str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_npc_wuchan.png"),
        str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_npc_keye.png"),
    ]
    BTN_DIALOG_NEXT = str(YmGameTask.TEMPLATES_DIR / "btn_dialog_next.png")
    BTN_KEYE_USE = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_shiyong.png")
    TEXT_KEYE_PREFIX = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_keye.png")
    TEXT_ZHISHA_PREFIX = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_zhisha.png")
    TEXT_ZHUOJIAN_PREFIX = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_zhuojian.png")
    TEXT_LIEXUE_PREFIX = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_liexue.png")
    TEXT_XUNDAO_PREFIX = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_xundao.png")
    TEXT_DUANXIN_PREFIX = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_duanxin.png")
    KEYE_SIDEBAR_TEMPLATES = [
        TEXT_KEYE_PREFIX,
        TEXT_ZHISHA_PREFIX,
        TEXT_ZHUOJIAN_PREFIX,
        TEXT_LIEXUE_PREFIX,
        TEXT_XUNDAO_PREFIX,
        TEXT_DUANXIN_PREFIX,
    ]
    TEXT_EXISTING_KEYE_TOAST = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_existing_keye_toast.png")
    TEXT_KEYE_COMPLETE = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_complete.png")
    ROUTE_MALL = str(YmGameTask.TEMPLATES_DIR / "route_mall.png")
    ROUTE_STALL = str(YmGameTask.TEMPLATES_DIR / "route_stall.png")
    BTN_ONE_KEY_SUBMIT = str(YmGameTask.TEMPLATES_DIR / "btn_kyrw_one_key_submit.png")
    BTN_VIEW_ALL_SERVER = str(YmGameTask.TEMPLATES_DIR / "btn_view_all_server.png")
    BTN_MALL_BUY_AREA = str(YmGameTask.TEMPLATES_DIR / "btn_mall_buy_area.png")
    BTN_BUY = str(YmGameTask.TEMPLATES_DIR / "btn_buy.png")
    BTN_MODAL_CANCEL = str(YmGameTask.TEMPLATES_DIR / "btn_modal_cancel.png")
    TEXT_YINSHI_INSTRUCTION = str(YmGameTask.TEMPLATES_DIR / "text_kyrw_yinshi_instruction.png")
    ICON_YINSHI_CARD_TOP = str(YmGameTask.TEMPLATES_DIR / "icon_kyrw_yinshi_card_top.png")
    ICON_YINSHI_CORRECT = str(YmGameTask.TEMPLATES_DIR / "icon_kyrw_yinshi_correct.png")

    # 固定坐标点 (设计分辨率 1280x720 下)
    POINT_KEYE_ACTIVITY_FORWARD = (215, 276)
    POINT_KEYE_ENTRY_FORWARD = (276, 498)
    POINT_NPC_TALK = (1005, 465)
    POINT_NPC_ACTION = (1100, 465)
    POINT_KEYE_CARD_DEFAULT = (354, 265)
    POINT_TASK_LIST_SCROLL_START = (190, 330)
    POINT_TASK_LIST_SCROLL_END = (190, 190)
    POINT_TASK_LIST_SCROLL_UP_START = (190, 190)
    POINT_TASK_LIST_SCROLL_UP_END = (190, 330)
    POINT_DIALOG_NEXT = (1230, 690)
    POINT_MALL_BUY = (949, 663)
    POINT_COMPLETE_OK = (854, 508)

    ROI_KEYE_ACTIVITY_ENTRY = (120, 210, 220, 115)
    ROI_ROUTE_PANEL = (330, 120, 880, 520)
    ROI_TRADE_ACTION = (520, 440, 330, 120)
    ROI_YINSHI_INSTRUCTION = (20, 560, 900, 120)
    ROI_YINSHI_CARD_TOPS = (250, 40, 900, 150)
    ROI_YINSHI_CORRECT_MARKS = (250, 420, 900, 130)

    TASK_FLOW_TIMEOUT_MS = 900000
    AUTO_PATHFIND_TO_NPC_ATTEMPTS = 2
    MAX_ITEM_ACQUIRE_ROUNDS = 60
    MAX_STALL_BUY_RETRIES = 2
    MAX_ALL_SERVER_BUY_RETRIES = 2
    MAX_NPC_ACCEPT_RECOVERY = 2
    TRADE_BUY_THRESHOLD = 0.7
    KEYE_FLOW_IDLE_WAIT_MS = 1000
    KEYE_TASK_MISSING_CONFIRMATIONS = 3
    KEYE_FLOW_STATE_HANDLED = "handled"
    KEYE_FLOW_STATE_IDLE = "idle"
    TASK_LIST_SCROLL_DURATION_MS = 1000
    TASK_LIST_SCROLL_UP_DURATION_MS = 400
    TASK_LIST_SCROLL_SETTLE_MS = 500
    TASK_LIST_SCROLL_UP_COUNT = 2
    YINSHI_INSTRUCTION_THRESHOLD = 0.9
    YINSHI_CARD_THRESHOLD = 0.9
    YINSHI_CORRECT_THRESHOLD = 0.85
    YINSHI_CARD_DUPLICATE_DISTANCE = 60
    YINSHI_CORRECT_MAX_CARD_WIDTH_RATIO = 0.75
    YINSHI_CARD_FINGERPRINT_THRESHOLD = 0.85
    YINSHI_DRAG_DURATION_MS = 200
    YINSHI_DRAG_SETTLE_MS = 200
    YINSHI_DRAG_RETRIES = 1
    YINSHI_DRAG_Y_OFFSET_FROM_TOP_BOTTOM = 150
    YINSHI_COMPLETE_WAIT_MS = 500

    def __init__(self, default_interval_ms: int | None = None):
        super().__init__(default_interval_ms=default_interval_ms)
        self._item_acquire_rounds = 0
        self._npc_accept_recoveries = 0

    def reset_startup_state(self) -> None:
        """在通用启动清理前重置本次运行计数器。"""
        self._item_acquire_rounds = 0
        self._npc_accept_recoveries = 0

    def after_startup_panel_close(self) -> None:
        """每轮启动清理后关闭科举完成弹窗。"""
        self.close_keye_completion_dialog_if_visible()

    @step(retry=1, timeout_ms=60000)
    def resume_existing_keye(self) -> None:
        """接取前优先查找已布置的课业任务。"""
        self.close_all_panels(timeout_ms=0)
        if self.click_keye_task_from_sidebar(max_scrolls=5, required=False):
            self._log("检测到已布置课业任务，跳过接取流程")
            self.jump_to("run_keye_flow")

        self._log("未发现已布置课业任务，继续活动接取流程")

    @step(retry=3, timeout_ms=30000)
    def open_keye_activity(self) -> None:
        """打开活动-江湖并点击课业活动入口。"""
        self.open_activity_panel(
            "江湖",
            wait_after_category_ms=2000,
        )

        if self.wait_image_appear(
            self.BTN_KEYE_ACTIVITY_FORWARD,
            timeout_ms=5000,
            threshold=0.9,
            roi=self.scale_roi(self.ROI_KEYE_ACTIVITY_ENTRY),
        ):
            self.click(offset=0)
        else:
            self._log("未识别到活动页课业入口，使用固定坐标点击")
            self.click_point(
                self.POINT_KEYE_ACTIVITY_FORWARD[0],
                self.POINT_KEYE_ACTIVITY_FORWARD[1],
                offset=0,
            )
        self.wait(1500)

    @step(retry=0, timeout_ms=390000)
    def enter_keye_from_activity_panel(self) -> None:
        """在课业活动面板点击课业前往，并等待自动寻路结束。"""
        if self.wait_image_appear(
            self.BTN_KEYE_ENTRY_FORWARD,
            timeout_ms=10000,
            threshold=0.9,
            roi=self.scale_roi((175, 440, 205, 110)),
        ):
            self.click(offset=0)
        else:
            self._log("未识别到课业面板前往按钮，使用固定坐标点击")
            self.click_point(
                self.POINT_KEYE_ENTRY_FORWARD[0],
                self.POINT_KEYE_ENTRY_FORWARD[1],
                offset=0,
            )
        self.wait(1500)

        self._log("等待接取前自动寻路结束")
        for attempt in range(1, self.AUTO_PATHFIND_TO_NPC_ATTEMPTS + 1):
            if self.wait_auto_pathfinding(timeout_ms=120000):
                self._log("接取前自动寻路已结束")
                return
            if attempt < self.AUTO_PATHFIND_TO_NPC_ATTEMPTS:
                self._log(
                    "接取前自动寻路尚未结束，"
                    f"重试等待 {attempt + 1}/{self.AUTO_PATHFIND_TO_NPC_ATTEMPTS}"
                )

        self._log("接取前自动寻路等待超时")
        raise RuntimeError("接取前自动寻路等待超时")

    @step(retry=3, timeout_ms=180000)
    def accept_or_open_keye_panel(self) -> None:
        """进入课业面板，并处理已布置课业提示。"""
        if not self.click_npc_keye_action_if_visible(timeout_ms=6000, wait_after_click_ms=1200):
            self._log("未识别到NPC课业动作按钮，使用固定坐标点击课业动作")

        self.click_point(self.POINT_NPC_ACTION[0], self.POINT_NPC_ACTION[1], offset=0)
        self.wait(2000)

        if self.try_continue_after_keye_panel_opened():
            return

        self._log("未进入课业面板，尝试先点击NPC对话按钮")
        self.click_point(self.POINT_NPC_TALK[0], self.POINT_NPC_TALK[1], offset=0)
        self.wait(1500)
        self.click_point(self.POINT_NPC_ACTION[0], self.POINT_NPC_ACTION[1], offset=0)
        self.wait(2000)

        if self.try_continue_after_keye_panel_opened():
            return

        self.close_all_panels(timeout_ms=3000)
        if self.click_keye_task_from_sidebar(max_scrolls=5, required=False):
            self.jump_to("run_keye_flow")

        if self._npc_accept_recoveries < self.MAX_NPC_ACCEPT_RECOVERY:
            self._npc_accept_recoveries += 1
            self._log("进入课业面板失败，重新从课业活动入口接取")
            self.close_all_panels(timeout_ms=3000)
            self.jump_to("open_keye_activity")

        raise RuntimeError("进入课业面板后未检测到可执行课业，且接取恢复次数已耗尽")

    def try_continue_after_keye_panel_opened(self) -> bool:
        """科举面板可能已打开时继续流程。"""
        if self.cancel_refresh_confirm_if_visible():
            self.jump_to("resume_existing_keye")

        if self.try_select_default_keye_card():
            self.jump_to("run_keye_flow")

        return False

    def click_npc_keye_action_if_visible(
        self,
        *,
        timeout_ms: int,
        wait_after_click_ms: int = 1500,
    ) -> bool:
        """角色科举操作按钮可见时点击它。"""
        if not self.wait_image_appear(
            self.BTN_NPC_KEYE_ACTION_TEMPLATES,
            timeout_ms=timeout_ms,
            threshold=0.85,
            roi=self.scale_roi((900, 400, 360, 130)),
        ):
            return False

        self._log("点击NPC课业动作按钮")
        self.click(offset=0)
        self.wait(wait_after_click_ms)
        return True

    def _handle_keye_flow_state_once(self) -> str:
        """处理一个稳定的科举界面，并返回其结果状态。"""
        if self.close_keye_completion_dialog_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.cancel_refresh_confirm_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.handle_yinshi_task_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.click_keye_use_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.handle_submit_panel_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.handle_acquire_route_panel_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.handle_trade_panel_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.click_dialog_confirm_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        if self.click_npc_keye_action_if_visible(timeout_ms=600):
            return self.KEYE_FLOW_STATE_HANDLED
        if self.click_dialog_next_if_visible():
            return self.KEYE_FLOW_STATE_HANDLED
        return self.KEYE_FLOW_STATE_IDLE

    def handle_yinshi_task_if_visible(self) -> bool:
        """仅根据卡片位置和正确标记，对可见诗词面板进行排序。"""
        state = self._read_yinshi_state()
        if not state.visible:
            return False
        expected_count = len(state.cards)
        if expected_count < 2:
            self._raise_yinshi_error(
                "检测到吟诗作对界面，但无法确认至少两张诗句卡片",
                "kyrw_yinshi_cards_unconfirmed",
            )

        self._log(f"检测到吟诗作对任务，共识别到 {expected_count} 张诗句卡片")
        for target_index in range(expected_count):
            state = self._read_yinshi_state()
            if not state.visible:
                self._log("吟诗作对界面已退出，继续课业流程")
                return True
            self._validate_yinshi_card_count(state, expected_count)

            if target_index in state.correct_slots:
                self._log(f"吟诗作对槽位 {target_index + 1} 已正确，跳过拖动")
                continue

            target_correct = False
            for source_index in range(target_index + 1, expected_count):
                state = self._read_yinshi_state()
                if not state.visible:
                    self._log("吟诗作对界面已退出，继续课业流程")
                    return True
                self._validate_yinshi_card_count(state, expected_count)

                if target_index in state.correct_slots:
                    self._log(f"吟诗作对槽位 {target_index + 1} 已正确，停止尝试候选卡片")
                    target_correct = True
                    break

                source_card = state.cards[source_index]
                source_fingerprint = self._yinshi_card_fingerprint(state.screenshot, source_card)
                moved = False
                for drag_attempt in range(self.YINSHI_DRAG_RETRIES + 1):
                    target_card = state.cards[target_index]
                    self._log(
                        f"吟诗作对：拖动槽位 {source_index + 1} 到槽位 {target_index + 1}"
                    )
                    self._drag_yinshi_card(source_card, target_card)

                    updated = self._read_yinshi_state()
                    if not updated.visible:
                        self._log("吟诗作对界面已退出，继续课业流程")
                        return True
                    self._validate_yinshi_card_count(updated, expected_count)

                    if target_index in updated.correct_slots:
                        self._log(f"吟诗作对槽位 {target_index + 1} 排列正确")
                        target_correct = True
                        moved = True
                        state = updated
                        break

                    target_fingerprint = self._yinshi_card_fingerprint(
                        updated.screenshot,
                        updated.cards[target_index],
                    )
                    similarity = self._yinshi_fingerprint_similarity(
                        source_fingerprint,
                        target_fingerprint,
                    )
                    if similarity >= self.YINSHI_CARD_FINGERPRINT_THRESHOLD:
                        moved = True
                        state = updated
                        break

                    if drag_attempt < self.YINSHI_DRAG_RETRIES:
                        self._log(
                            "吟诗作对拖动未生效，"
                            f"重试 {drag_attempt + 1}/{self.YINSHI_DRAG_RETRIES}"
                        )
                        state = updated
                        source_card = state.cards[source_index]

                if not moved:
                    self._raise_yinshi_error(
                        f"吟诗作对槽位 {source_index + 1} 拖动到 "
                        f"{target_index + 1} 后未生效",
                        "kyrw_yinshi_drag_failed",
                    )
                if target_correct:
                    break

            if target_correct:
                continue

            state = self._read_yinshi_state()
            if not state.visible:
                self._log("吟诗作对界面已退出，继续课业流程")
                return True
            self._validate_yinshi_card_count(state, expected_count)
            if target_index not in state.correct_slots:
                self._raise_yinshi_error(
                    f"吟诗作对槽位 {target_index + 1} 已尝试全部候选卡片仍未出现红勾",
                    "kyrw_yinshi_no_correct_candidate",
                )

        final_state = self._read_yinshi_state()
        if not final_state.visible:
            self._log("吟诗作对排序完成，界面已退出")
            return True
        self._validate_yinshi_card_count(final_state, expected_count)
        if len(final_state.correct_slots) != expected_count:
            self._raise_yinshi_error(
                "吟诗作对完成检查时仍存在未正确排列的槽位",
                "kyrw_yinshi_incomplete",
            )

        self._log("吟诗作对所有槽位均已出现红勾，等待界面自行退出")
        self.wait(self.YINSHI_COMPLETE_WAIT_MS)
        return True

    def _read_yinshi_state(self, screenshot: np.ndarray | None = None) -> _YinshiState:
        """读取诗词面板可见性、动态卡片位置和正确槽位。"""
        frame = self.screenshot() if screenshot is None else screenshot
        marker = self._vision.match_template(
            frame,
            self.TEXT_YINSHI_INSTRUCTION,
            threshold=self.YINSHI_INSTRUCTION_THRESHOLD,
            roi=self.scale_roi(self.ROI_YINSHI_INSTRUCTION),
        )
        if not marker.found:
            return _YinshiState(visible=False, screenshot=frame)

        card_matches = self._vision.match_all_templates(
            frame,
            self.ICON_YINSHI_CARD_TOP,
            threshold=self.YINSHI_CARD_THRESHOLD,
            roi=self.scale_roi(self.ROI_YINSHI_CARD_TOPS),
        )
        cards = tuple(self._merge_yinshi_card_matches(card_matches))
        correct_matches = self._vision.match_all_templates(
            frame,
            self.ICON_YINSHI_CORRECT,
            threshold=self.YINSHI_CORRECT_THRESHOLD,
            roi=self.scale_roi(self.ROI_YINSHI_CORRECT_MARKS),
        )
        correct_slots = self._map_yinshi_correct_slots(cards, correct_matches)
        return _YinshiState(
            visible=True,
            screenshot=frame,
            cards=cards,
            correct_slots=frozenset(correct_slots),
        )

    def _merge_yinshi_card_matches(
        self,
        matches: list[ImageMatchResult],
    ) -> list[ImageMatchResult]:
        """合并重复峰值，并返回从左到右排序的卡片匹配结果。"""
        selected: list[ImageMatchResult] = []
        for match in sorted(matches, key=lambda item: item.score, reverse=True):
            if match.center is None or match.bbox is None:
                continue
            if any(
                abs(match.center[0] - existing.center[0]) < self.YINSHI_CARD_DUPLICATE_DISTANCE
                for existing in selected
                if existing.center is not None
            ):
                continue
            selected.append(match)
        return sorted(selected, key=lambda item: item.center[0] if item.center else -1)

    def _map_yinshi_correct_slots(
        self,
        cards: tuple[ImageMatchResult, ...],
        correct_matches: list[ImageMatchResult],
    ) -> set[int]:
        """将每个红色正确标记映射到最近的动态识别卡片。"""
        if not correct_matches:
            return set()
        if not cards:
            self._raise_yinshi_error(
                "识别到吟诗作对红勾，但未识别到诗句卡片",
                "kyrw_yinshi_correct_without_cards",
            )

        correct_slots: set[int] = set()
        for correct in correct_matches:
            if correct.center is None:
                continue
            nearest_index = min(
                range(len(cards)),
                key=lambda index: abs(cards[index].center[0] - correct.center[0]),
            )
            card = cards[nearest_index]
            if card.center is None or card.bbox is None:
                continue
            card_width = card.bbox[2] - card.bbox[0]
            max_distance = max(
                1,
                int(card_width * self.YINSHI_CORRECT_MAX_CARD_WIDTH_RATIO),
            )
            if abs(card.center[0] - correct.center[0]) > max_distance:
                self._raise_yinshi_error(
                    "吟诗作对红勾无法映射到对应卡片",
                    "kyrw_yinshi_correct_unmapped",
                )
            correct_slots.add(nearest_index)
        return correct_slots

    def _drag_yinshi_card(
        self,
        source: ImageMatchResult,
        target: ImageMatchResult,
    ) -> None:
        """将一张动态识别的卡片拖入另一张卡片的槽位。"""
        if source.center is None or source.bbox is None or target.center is None or target.bbox is None:
            raise RuntimeError("吟诗作对卡片坐标不完整")
        source_y = source.bbox[3] + self.YINSHI_DRAG_Y_OFFSET_FROM_TOP_BOTTOM
        target_y = target.bbox[3] + self.YINSHI_DRAG_Y_OFFSET_FROM_TOP_BOTTOM
        self.swipe(
            source.center[0],
            source_y,
            target.center[0],
            target_y,
            duration_ms=self.YINSHI_DRAG_DURATION_MS,
        )
        self.wait(self.YINSHI_DRAG_SETTLE_MS)

    @staticmethod
    def _yinshi_card_fingerprint(
        screenshot: np.ndarray,
        card: ImageMatchResult,
    ) -> np.ndarray:
        """在不识别文字内容的情况下提取卡片的纯文本视觉指纹。"""
        if card.center is None or card.bbox is None:
            return np.empty((0, 0), dtype=np.uint8)
        height, width = screenshot.shape[:2]
        center_x = card.center[0]
        x1 = max(0, center_x - 32)
        x2 = min(width, center_x + 32)
        y1 = max(0, card.bbox[3] - 5)
        y2 = min(height, card.bbox[3] + 280)
        crop = screenshot[y1:y2, x1:x2]
        if crop.size == 0:
            return np.empty((0, 0), dtype=np.uint8)
        return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _yinshi_fingerprint_similarity(
        expected: np.ndarray,
        actual: np.ndarray,
    ) -> float:
        """返回两张卡片指纹之间归一化的视觉相似度。"""
        if expected.size == 0 or actual.size == 0:
            return 0.0
        if actual.shape != expected.shape:
            actual = cv2.resize(actual, (expected.shape[1], expected.shape[0]))
        if float(np.std(expected)) < 1e-6 or float(np.std(actual)) < 1e-6:
            return 0.0
        result = cv2.matchTemplate(actual, expected, cv2.TM_CCOEFF_NORMED)
        return float(result[0, 0])

    def _validate_yinshi_card_count(self, state: _YinshiState, expected_count: int) -> None:
        """拒绝卡片数量发生意外变化的可见诗词面板。"""
        if len(state.cards) == expected_count:
            return
        self._raise_yinshi_error(
            f"吟诗作对卡片数量异常：预期 {expected_count}，实际 {len(state.cards)}",
            "kyrw_yinshi_card_count_changed",
        )

    def _raise_yinshi_error(self, message: str, screenshot_prefix: str) -> None:
        """抛出明确失败前保存当前诗词面板截图。"""
        debug_path = self.save_debug_screenshot(screenshot_prefix)
        raise RuntimeError(f"{message}，已保存截图：{debug_path}")

    @step(retry=1, timeout_ms=TASK_FLOW_TIMEOUT_MS)
    def run_keye_flow(self) -> None:
        """循环执行当前课业，处理对话、寻路、物品获取和提交。"""
        deadline = self._make_deadline(self.TASK_FLOW_TIMEOUT_MS)
        missing_confirmations = 0

        while not self._is_deadline_expired(deadline):
            if not self.wait_auto_pathfinding(timeout_ms=30000):
                self._debug("课业自动寻路或过图尚未稳定，继续等待")
                continue

            state = self._handle_keye_flow_state_once()
            if state == self.KEYE_FLOW_STATE_HANDLED:
                missing_confirmations = 0
                continue

            if self.click_keye_task_from_sidebar(max_scrolls=2, required=False):
                missing_confirmations = 0
                continue

            missing_confirmations += 1
            self._log(
                "任务栏暂未找到课业追踪，继续确认完成状态 "
                f"({missing_confirmations}/{self.KEYE_TASK_MISSING_CONFIRMATIONS})"
            )
            if missing_confirmations >= self.KEYE_TASK_MISSING_CONFIRMATIONS:
                self._log("课业追踪已稳定消失，进入完成验证")
                return

            remaining_ms = self._remaining_ms(deadline)
            if remaining_ms > 0:
                self.wait(min(self.KEYE_FLOW_IDLE_WAIT_MS, remaining_ms))

        debug_path = self.save_debug_screenshot("kyrw_keye_flow_timeout")
        raise RuntimeError(f"课业任务执行流程超时，已保存截图：{debug_path}")

    @step(retry=1, timeout_ms=60000)
    def verify_completion(self) -> None:
        """验证活动页的课业入口已消失。"""
        self.close_all_panels()
        self.open_activity_panel(
            "江湖",
            wait_after_category_ms=2000,
        )

        if self.wait_image_appear(
            self.BTN_KEYE_ACTIVITY_FORWARD,
            timeout_ms=5000,
            threshold=0.9,
            roi=self.scale_roi(self.ROI_KEYE_ACTIVITY_ENTRY),
        ):
            self._log("完成验证：活动页仍存在课业入口，继续接取课业")
            self.jump_to("open_keye_activity")

        self._log("完成验证：活动页课业入口已消失")

    def try_select_default_keye_card(self) -> bool:
        """点击可见的科举卡片；若出现已有科举提示则处理。"""
        if not self.find_image_once([self.BTN_CLOSE, self.BTN_PANE_CLOSE], threshold=0.8):
            return False

        self._log("点击默认课业卡片")
        self.click_point(self.POINT_KEYE_CARD_DEFAULT[0], self.POINT_KEYE_CARD_DEFAULT[1], offset=0)
        self.wait(1000)

        if self.click_dialog_next_if_visible():
            self._log("课业卡片已进入剧情，继续执行课业流程")
            return True

        if self.find_image_once(
            self.TEXT_EXISTING_KEYE_TOAST,
            threshold=0.85,
            roi=self.scale_roi((450, 300, 420, 90)),
        ):
            self._log("检测到已有当前布置课业，关闭面板后继续执行")
            self.close_all_panels(timeout_ms=3000)
            return True

        self.close_all_panels(timeout_ms=3000)
        return self.click_keye_task_from_sidebar(max_scrolls=5, required=False)

    def click_keye_task_from_sidebar(self, *, max_scrolls: int, required: bool) -> bool:
        """在左侧任务栏中查找并点击科举任务。"""
        if not self.find_keye_task_in_sidebar(max_scrolls=max_scrolls):
            if required:
                self._log("任务栏未找到课业任务")
            return False

        self._log("点击任务栏课业任务")
        self.click(offset=0)
        self.wait(1500)
        return True

    def find_keye_task_in_sidebar(self, *, max_scrolls: int) -> bool:
        """在江湖任务面板中查找科举任务文本。"""
        self.ensure_left_task_sidebar_visible()
        self._confirm_keye_sidebar_jianghu()
        for _ in range(self.TASK_LIST_SCROLL_UP_COUNT):
            self.scroll_task_list_up()
            self._confirm_keye_sidebar_jianghu()

        for attempt in range(max_scrolls + 1):
            if self.wait_image_appear(
                self.KEYE_SIDEBAR_TEMPLATES,
                timeout_ms=1500,
                threshold=0.85,
                roi=self.scale_roi((40, 135, 330, 430)),
            ):
                return True

            if attempt < max_scrolls:
                self._log(f"任务栏未找到课业任务，向下翻页 {attempt + 1}/{max_scrolls}")
                self.scroll_task_list_down()
                self._confirm_keye_sidebar_jianghu()

        return False

    def _confirm_keye_sidebar_jianghu(self) -> None:
        """确认科举侧栏扫描仍位于江湖页签。"""
        try:
            self.switch_task_panel("江湖", timeout_ms=6000, threshold=0.8)
        except TaskSidebarStateError as exc:
            self._log(f"切换任务面板 江湖 失败：{exc}")
            raise TaskSidebarStateError(
                "课业任务不存在前置检查不完整：江湖任务页签未成功确认并扫描"
            ) from exc

    def ensure_left_task_sidebar_visible(self) -> None:
        """围绕通用已验证侧栏打开器的兼容包装。"""
        self.ensure_task_sidebar_open(timeout_ms=6000, threshold=0.85)

    def scroll_task_list_down(self) -> None:
        """向下滚动任务列表以显示较低条目。"""
        start = self.POINT_TASK_LIST_SCROLL_START
        end = self.POINT_TASK_LIST_SCROLL_END
        self.swipe(
            start[0],
            start[1],
            end[0],
            end[1],
            duration_ms=self.TASK_LIST_SCROLL_DURATION_MS,
        )
        self.wait(self.TASK_LIST_SCROLL_SETTLE_MS)

    def scroll_task_list_up(self) -> None:
        """将任务列表上滚一页，同时归一到其第一页。"""
        start = self.POINT_TASK_LIST_SCROLL_UP_START
        end = self.POINT_TASK_LIST_SCROLL_UP_END
        self.swipe(
            start[0],
            start[1],
            end[0],
            end[1],
            duration_ms=self.TASK_LIST_SCROLL_UP_DURATION_MS,
        )
        self.wait(self.TASK_LIST_SCROLL_SETTLE_MS)

    def handle_acquire_route_panel_if_visible(self) -> bool:
        """处理受支持的物品获取途径面板。"""
        if not self.is_acquire_route_panel_visible():
            return False

        self._item_acquire_rounds += 1
        if self._item_acquire_rounds > self.MAX_ITEM_ACQUIRE_ROUNDS:
            raise RuntimeError("课业物品获取次数超过安全上限")

        self._log(f"检测到课业物品获取途径面板，开始第 {self._item_acquire_rounds} 次获取")
        if self.try_mall_route():
            self.handle_submit_panel_if_visible(timeout_ms=1500)
            return True
        if self.try_stall_route():
            self.handle_submit_panel_if_visible(timeout_ms=1500)
            return True

        self.close_transient_panels()
        raise RuntimeError("课业物品未找到支持的获取途径")

    def is_acquire_route_panel_visible(self) -> bool:
        """返回是否出现任一受支持的物品获取途径。"""
        return self.find_image(
            [self.ROUTE_MALL, self.ROUTE_STALL],
            threshold=0.8,
            roi=self.scale_roi(self.ROI_ROUTE_PANEL),
        )

    def ensure_acquire_route_panel_open(self) -> bool:
        """确保获取途径面板当前可见。"""
        if self.is_acquire_route_panel_visible():
            return True
        if self.click_keye_task_from_sidebar(max_scrolls=2, required=False):
            return self.wait_acquire_route_panel_visible(timeout_ms=5000)
        return False

    def wait_acquire_route_panel_visible(self, timeout_ms: int = 3000) -> bool:
        """等待任一受支持的获取途径出现。"""
        return self.wait_image_appear(
            [self.ROUTE_MALL, self.ROUTE_STALL],
            timeout_ms=timeout_ms,
            threshold=0.8,
            roi=self.scale_roi(self.ROI_ROUTE_PANEL),
        )

    def try_mall_route(self) -> bool:
        """按默认数量从商城购买所选任务物品。"""
        if not self.ensure_acquire_route_panel_open():
            return False
        if not self.click_template_if_available(
            self.ROUTE_MALL,
            timeout_ms=800,
            description="商城购买路径",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.85,
            wait_after_click_ms=2000,
        ):
            return False

        if not self.buy_from_mall_default_quantity():
            self._log("商城未找到默认购买按钮")
            self.close_transient_panels()
            return False

        return True

    def buy_from_mall_default_quantity(self) -> bool:
        """点击一次商城购买区域，不改变物品数量。"""
        if self.click_template_if_available(
            self.BTN_MALL_BUY_AREA,
            timeout_ms=5000,
            description="商城默认数量购买按钮",
            roi=(800, 610, 290, 100),
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            return True

        self._log("未识别到商城默认数量购买按钮，使用固定坐标点击")
        self.click_point(self.POINT_MALL_BUY[0], self.POINT_MALL_BUY[1], offset=0)
        self.wait(1500)
        return True

    def try_stall_route(self) -> bool:
        """从本服摊位或全服摊位购买所选任务物品。"""
        if not self.ensure_acquire_route_panel_open():
            return False
        if not self.click_template_if_available(
            self.ROUTE_STALL,
            timeout_ms=800,
            description="摆摊购买路径",
            roi=self.ROI_ROUTE_PANEL,
            threshold=0.8,
            wait_after_click_ms=2500,
        ):
            return False

        for _ in range(self.MAX_STALL_BUY_RETRIES):
            if self.buy_from_current_trade_panel("摆摊购买按钮", timeout_ms=2500):
                return True

        if not self.click_template_if_available(
            self.BTN_VIEW_ALL_SERVER,
            timeout_ms=2500,
            description="查看全服按钮",
            roi=self.ROI_TRADE_ACTION,
            threshold=0.85,
            wait_after_click_ms=2500,
        ):
            self._log("摆摊未找到商品，且未出现查看全服按钮")
            self.close_transient_panels()
            return False

        for _ in range(self.MAX_ALL_SERVER_BUY_RETRIES):
            if self.buy_from_current_trade_panel("全服摆摊购买按钮", timeout_ms=3000):
                return True

        self._log("本服/全服摆摊均未找到可购买商品")
        self.close_transient_panels()
        raise RuntimeError("本服/全服摆摊均未找到可购买商品")

    def handle_trade_panel_if_visible(self) -> bool:
        """处理已经打开的交易面板。"""
        if self.buy_from_current_trade_panel("自动打开的交易购买按钮", timeout_ms=600):
            self.handle_submit_panel_if_visible(timeout_ms=1500)
            return True

        if not self.click_template_if_available(
            self.BTN_VIEW_ALL_SERVER,
            timeout_ms=600,
            description="自动打开的查看全服按钮",
            roi=self.ROI_TRADE_ACTION,
            threshold=0.85,
            wait_after_click_ms=2500,
        ):
            return False

        if self.buy_from_current_trade_panel("自动打开的全服摆摊购买按钮", timeout_ms=3000):
            self.handle_submit_panel_if_visible(timeout_ms=1500)
            return True

        self._log("自动打开的全服摆摊未找到可购买商品")
        self.close_transient_panels()
        return True

    def buy_from_current_trade_panel(self, description: str, *, timeout_ms: int) -> bool:
        """在当前交易面板点击购买，必要时确认二次提示。"""
        if not self.click_template_if_available(
            self.BTN_BUY,
            timeout_ms=timeout_ms,
            description=description,
            roi=self.ROI_TRADE_ACTION,
            threshold=self.TRADE_BUY_THRESHOLD,
            wait_after_click_ms=1500,
        ):
            return False

        confirmed = self.confirm_purchase_if_needed()
        if not confirmed and self.wait_image_appear(
            self.BTN_BUY,
            timeout_ms=800,
            threshold=self.TRADE_BUY_THRESHOLD,
            interval_ms=300,
            roi=self.scale_roi(self.ROI_TRADE_ACTION),
        ):
            self._log("购买按钮点击后仍可见，重试点击")
            self.click(offset=0)
            self.wait(1500)
            self.confirm_purchase_if_needed()

        return True

    def handle_submit_panel_if_visible(self, *, timeout_ms: int = 600) -> bool:
        """一键提交面板出现时提交最终任务物品。"""
        if not self.click_template_if_available(
            self.BTN_ONE_KEY_SUBMIT,
            timeout_ms=timeout_ms,
            description="课业一键提交按钮",
            roi=(900, 330, 340, 240),
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            return False

        self.confirm_submit_if_needed()
        self.wait(1500)
        return True

    def click_dialog_confirm_if_visible(self) -> bool:
        """在通用下一步箭头前点击必需的对话确认按钮。"""
        return self.click_template_if_available(
            self.BTN_OK,
            timeout_ms=600,
            description="课业剧情确定按钮",
            roi=(900, 400, 360, 120),
            threshold=0.85,
            wait_after_click_ms=1500,
        )

    def click_dialog_next_if_visible(self) -> bool:
        """右下角剧情或对话下一步箭头可见时点击它。"""
        if not self.click_template_if_available(
            self.BTN_DIALOG_NEXT,
            timeout_ms=600,
            description="剧情继续箭头",
            roi=(1180, 640, 100, 80),
            threshold=0.85,
            wait_after_click_ms=1500,
        ):
            return False
        return True

    def click_keye_use_if_visible(self) -> bool:
        """科举“使用”按钮出现在屏幕任意位置时点击它。"""
        return self.click_template_if_available(
            self.BTN_KEYE_USE,
            timeout_ms=600,
            description="课业使用按钮",
            threshold=0.85,
            wait_after_click_ms=1500,
        )

    def close_keye_completion_dialog_if_visible(self) -> bool:
        """最终科举完成弹窗可见时关闭它。"""
        if not self.find_image(
            self.TEXT_KEYE_COMPLETE,
            threshold=0.85,
            roi=self.scale_roi((350, 250, 600, 220)),
        ):
            return False

        self._log("检测到课业完成对话，点击确定")
        self.click_point(self.POINT_COMPLETE_OK[0], self.POINT_COMPLETE_OK[1], offset=0)
        self.wait(1000)
        return True

    def cancel_refresh_confirm_if_visible(self) -> bool:
        """取消飞雪剑刷新提示，避免消耗物品。"""
        if not self.find_image_once(
            self.BTN_MODAL_CANCEL,
            threshold=0.85,
            roi=self.scale_roi((300, 450, 250, 120)),
        ):
            return False

        self._log("检测到课业刷新消耗确认，点击取消")
        self.click(offset=0)
        self.wait(1000)
        return True

    def confirm_purchase_if_needed(self) -> bool:
        """若存在购买提示则确认。"""
        return self.click_template_if_available(
            self.BTN_MODAL_OK,
            timeout_ms=2000,
            description="购买二次确认按钮",
            threshold=0.85,
            wait_after_click_ms=2000,
        )

    def confirm_submit_if_needed(self) -> bool:
        """若存在任务提交提示则确认。"""
        return self.click_template_if_available(
            [self.BTN_MODAL_OK, self.BTN_OK],
            timeout_ms=3000,
            description="课业提交确认按钮",
            threshold=0.85,
            wait_after_click_ms=1500,
        )

    def close_transient_panels(self, max_attempts: int = 4) -> bool:
        """获取操作后关闭临时面板。"""
        closed = False
        for _ in range(max_attempts):
            if self.wait_image_appear([self.BTN_CLOSE, self.BTN_PANE_CLOSE], timeout_ms=800, threshold=0.8):
                self.click(offset=0)
                self.wait(1000)
                closed = True
                continue
            break
        return closed

    def click_template_if_available(
        self,
        template: str | list[str],
        *,
        timeout_ms: int | None,
        description: str,
        threshold: float = 0.8,
        wait_after_click_ms: int = 1000,
        roi: tuple[int, int, int, int] | None = None,
    ) -> bool:
        """模板出现在可选的设计分辨率区域内时点击它。"""
        scaled_roi = None if roi is None else self.scale_roi(roi)
        found = self.wait_image_appear(
            template,
            timeout_ms=timeout_ms,
            threshold=threshold,
            roi=scaled_roi,
        )

        if not found:
            return False

        self._log(f"点击{description}")
        self.click(offset=0)
        self.wait(wait_after_click_ms)
        return True

    def on_finish(self, results: list) -> None:
        """任务结束处理。"""
        success_count = sum(1 for r in results if r.success)
        self._log("=" * 40)
        self._log(f"课业任务完成：{success_count}/{len(results)} 步骤成功")
        self._log("=" * 40)
