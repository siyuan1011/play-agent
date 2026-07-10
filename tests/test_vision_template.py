from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from botCore import VisionEngine
from botCore.vision import load_image


def test_template_match_found():
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    cv2.rectangle(screen, (120, 70), (170, 120), (255, 255, 255), thickness=-1)
    template = screen[70:120, 120:170].copy()

    tmp_dir = Path("logs/test_tmp/template") / str(uuid4())
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tpl_path = tmp_dir / "template.png"
    cv2.imwrite(str(tpl_path), template)

    engine = VisionEngine()
    result = engine.match_template(screen, str(tpl_path), threshold=0.95)

    assert result.found is True
    assert result.center is not None
    assert 140 <= result.center[0] <= 150
    assert 90 <= result.center[1] <= 100


def test_template_match_not_found():
    screen = np.zeros((200, 300, 3), dtype=np.uint8)
    template = np.full((40, 40, 3), 255, dtype=np.uint8)
    tmp_dir = Path("logs/test_tmp/template") / str(uuid4())
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tpl_path = tmp_dir / "template2.png"
    cv2.imwrite(str(tpl_path), template)

    engine = VisionEngine()
    result = engine.match_template(screen, str(tpl_path), threshold=0.99)

    assert result.found is False


def test_safe_zone_map_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    local_map = root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260709_211024.png"
    world_map = root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260709_211854.png"
    cases = [
        (
            local_map,
            root / "src/ymjh_bot/templates/map_btn_world.png",
            (1160, 610, 120, 110),
        ),
        (
            world_map,
            root / "src/ymjh_bot/templates/map_world_jinling.png",
            (850, 120, 120, 170),
        ),
        (
            local_map,
            root / "src/ymjh_bot/templates/map_jinling_jiming_temple.png",
            (460, 60, 130, 140),
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi in cases:
        assert template_path.exists()
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=0.95, roi=roi)

        assert result.found is True
        assert result.score >= 0.95


def test_menke_sheyan_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    screenshot_prefix = "\u95e8\u5ba2\u8bbe\u5bb4"
    cases = [
        (
            root / "screenshots" / f"{screenshot_prefix}3.png",
            root / "src/ymjh_bot/templates/btn_menke_sheyan_entry.png",
            (150, 470, 210, 145),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}4.png",
            root / "src/ymjh_bot/templates/btn_menke_invite_forward.png",
            (780, 135, 170, 520),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}5.png",
            root / "src/ymjh_bot/templates/btn_menke_banquet_invite.png",
            None,
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}6.png",
            root / "src/ymjh_bot/templates/btn_menke_confirm_invite.png",
            None,
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}7.png",
            root / "src/ymjh_bot/templates/btn_menke_get_item.png",
            (960, 530, 210, 100),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}7-1.png",
            root / "src/ymjh_bot/templates/btn_menke_one_key_submit.png",
            (960, 530, 210, 100),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}7-1.png",
            root / "src/ymjh_bot/templates/btn_menke_start_active.png",
            (220, 550, 200, 100),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}8.png",
            root / "src/ymjh_bot/templates/route_menke_warehouse_recommended.png",
            (560, 70, 660, 480),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}10.png",
            root / "src/ymjh_bot/templates/route_menke_mall.png",
            (560, 70, 660, 480),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}8.png",
            root / "src/ymjh_bot/templates/route_menke_stall.png",
            (560, 70, 660, 480),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}8-2.png",
            root / "src/ymjh_bot/templates/btn_menke_warehouse_submit.png",
            (760, 530, 230, 115),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}12.png",
            root / "src/ymjh_bot/templates/btn_menke_view_all_server.png",
            (600, 440, 250, 100),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}15.png",
            root / "src/ymjh_bot/templates/btn_menke_mall_buy_area.png",
            (800, 610, 290, 100),
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=0.95, roi=roi)

        assert result.found is True
        assert result.score >= 0.95


def test_menke_sheyan_templates_avoid_key_false_positives():
    root = Path(__file__).resolve().parents[1]
    screenshot_prefix = "\u95e8\u5ba2\u8bbe\u5bb4"
    cases = [
        (
            root / "screenshots" / f"{screenshot_prefix}8-1.png",
            root / "src/ymjh_bot/templates/btn_menke_warehouse_submit.png",
            (760, 530, 230, 115),
        ),
        (
            root / "screenshots" / f"{screenshot_prefix}11.png",
            root / "src/ymjh_bot/templates/route_menke_warehouse_recommended.png",
            (560, 70, 660, 480),
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=0.8, roi=roi)

        assert result.found is False


def test_pozhen_sheyan_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    menke_prefix = "\u95e8\u5ba2\u8bbe\u5bb4"
    pozhen_prefix = "\u7834\u9635\u8bbe\u5bb4"
    cases = [
        (
            root / "screenshots" / f"{menke_prefix}3.png",
            root / "src/ymjh_bot/templates/btn_pozhen_sheyan_entry.png",
            (540, 230, 260, 160),
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}4.png",
            root / "src/ymjh_bot/templates/btn_menke_invite_forward.png",
            (780, 135, 170, 520),
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}5.png",
            root / "src/ymjh_bot/templates/btn_menke_banquet_invite.png",
            None,
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}7-1.png",
            root / "src/ymjh_bot/templates/btn_pozhen_get_item.png",
            (960, 530, 210, 110),
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}7-2.png",
            root / "src/ymjh_bot/templates/btn_pozhen_one_key_submit.png",
            (960, 530, 210, 110),
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}7-1.png",
            root / "src/ymjh_bot/templates/btn_pozhen_submit_5_tab.png",
            (110, 365, 215, 65),
            0.95,
        ),
        (
            root / "screenshots" / f"{pozhen_prefix}7-1.png",
            root / "src/ymjh_bot/templates/btn_pozhen_submit_6_tab.png",
            (295, 365, 205, 65),
            0.95,
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi, threshold in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=threshold, roi=roi)

        assert result.found is True
        assert result.score >= threshold


def test_jhyxb_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    activity_fenzheng = "\u6d3b\u52a8-\u7eb7\u4e89"
    jhyxb = "\u6c5f\u6e56\u82f1\u96c4\u699c"
    cases = [
        (
            root / "screenshots" / f"{activity_fenzheng}.png",
            root / "src/ymjh_bot/templates/btn_jhyxb_activity_open.png",
            (720, 500, 240, 120),
            0.95,
        ),
        (
            root / "screenshots" / f"{jhyxb}.png",
            root / "src/ymjh_bot/templates/title_jhyxb.png",
            (170, 45, 260, 75),
            0.95,
        ),
        (
            root / "screenshots" / f"{jhyxb}.png",
            root / "src/ymjh_bot/templates/btn_jhyxb_match.png",
            (950, 520, 230, 120),
            0.95,
        ),
        (
            root / "screenshots" / f"{jhyxb}.png",
            root / "src/ymjh_bot/templates/icon_jhyxb_first_chest.png",
            (385, 545, 95, 75),
            0.95,
        ),
        (
            root / "screenshots" / f"{jhyxb}-\u51c6\u5907.png",
            root / "src/ymjh_bot/templates/btn_jhyxb_ready.png",
            (520, 40, 240, 120),
            0.95,
        ),
        (
            root / "screenshots" / "jhyxb_debug_after_timeout.png",
            root / "src/ymjh_bot/templates/text_jhyxb_challenge_zero.png",
            (880, 560, 60, 55),
            0.95,
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi, threshold in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=threshold, roi=roi)

        assert result.found is True
        assert result.score >= threshold


def test_hslj_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    cases = [
        (
            root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260708_234214.png",
            root / "src/ymjh_bot/templates/text_exit.png",
            (540, 630, 180, 80),
            0.95,
        ),
        (
            root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260708_234230.png",
            root / "src/ymjh_bot/templates/btn_hslj_match.png",
            (850, 535, 220, 115),
            0.95,
        ),
        (
            root / "screenshots" / "hslj_match_button_missing_20260709_102308_652091.png",
            root / "src/ymjh_bot/templates/btn_hslj_match_3v3.png",
            (850, 535, 220, 115),
            0.95,
        ),
        (
            root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260708_234923.png",
            root / "src/ymjh_bot/templates/btn_hslj_match_exit.png",
            (850, 535, 220, 115),
            0.95,
        ),
        (
            root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260709_112937.png",
            root / "src/ymjh_bot/templates/btn_hslj_match_exit_3v3.png",
            (850, 535, 220, 115),
            0.95,
        ),
        (
            root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260709_112329.png",
            root / "src/ymjh_bot/templates/text_hslj_match_success.png",
            (500, 360, 300, 120),
            0.95,
        ),
        (
            root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260708_235916.png",
            root / "src/ymjh_bot/templates/icon_hslj_first_win.png",
            (900, 450, 130, 100),
            0.95,
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi, threshold in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=threshold, roi=roi)

        assert result.found is True
        assert result.score >= threshold


def test_bangpai_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    menke_prefix = "\u95e8\u5ba2\u8bbe\u5bb4"
    cases = [
        (
            root / "screenshots" / "bangpai_debug_after_sidebar_click.png",
            root / "src/ymjh_bot/templates/text_bangpai.png",
            (40, 135, 330, 430),
            0.9,
        ),
        (
            root / "screenshots" / "bangpai_debug_after_sidebar_click.png",
            root / "src/ymjh_bot/templates/route_bangpai_stall.png",
            (720, 120, 480, 500),
            0.95,
        ),
        (
            root / "screenshots" / "bangpai_debug_after_sidebar_click.png",
            root / "src/ymjh_bot/templates/route_bangpai_warehouse.png",
            (720, 120, 480, 500),
            0.95,
        ),
        (
            root / "screenshots" / f"{menke_prefix}13.png",
            root / "src/ymjh_bot/templates/btn_buy.png",
            (520, 440, 330, 120),
            0.95,
        ),
        (
            root / "screenshots" / f"{menke_prefix}12.png",
            root / "src/ymjh_bot/templates/btn_menke_view_all_server.png",
            (600, 440, 250, 100),
            0.95,
        ),
        (
            root / "screenshots" / f"{menke_prefix}8-2.png",
            root / "src/ymjh_bot/templates/btn_menke_warehouse_submit.png",
            (760, 530, 230, 115),
            0.95,
        ),
        (
            root / "screenshots" / "bangpai_debug_current_after_loop_timeout.png",
            root / "src/ymjh_bot/templates/btn_bangpai_one_key_submit.png",
            (900, 330, 340, 160),
            0.95,
        ),
        (
            root / "screenshots" / "bangpai_debug_before_full_run.png",
            root / "src/ymjh_bot/templates/text_power_saving.png",
            (480, 470, 340, 140),
            0.95,
        ),
        (
            root / "screenshots" / "bangpai_debug_task_complete.png",
            root / "src/ymjh_bot/templates/text_bangpai_task_complete.png",
            (40, 570, 650, 90),
            0.95,
        ),
        (
            root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260709_180549.png",
            root / "src/ymjh_bot/templates/text_bangpai_daily.png",
            (40, 135, 330, 430),
            0.95,
        ),
        (
            root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260709_194405.png",
            root / "src/ymjh_bot/templates/text_bangpai_daily.png",
            (40, 135, 330, 430),
            0.95,
        ),
        (
            root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260709_194405.png",
            root / "src/ymjh_bot/templates/btn_modal_ok.png",
            None,
            0.95,
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi, threshold in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=threshold, roi=roi)

        assert result.found is True
        assert result.score >= threshold

    daily_result = engine.match_template(
        load_image(root / "screenshots" / "ymjh_queue_127.0.0.1_16416_20260709_180549.png"),
        str(root / "src/ymjh_bot/templates/text_bangpai.png"),
        threshold=0.7,
        roi=(40, 135, 330, 430),
    )
    assert daily_result.found is False


def test_kyrw_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    kyrw_dir = root / "screenshots" / "kyrw_wuchan_20260707"
    cases = [
        (
            kyrw_dir / "01_activity_jianghu_wuchan_entry.png",
            root / "src/ymjh_bot/templates/btn_kyrw_activity_wuchan_forward.png",
            (120, 210, 220, 115),
            0.95,
        ),
        (
            kyrw_dir / "03_wuchan_detail_course_forward.png",
            root / "src/ymjh_bot/templates/btn_kyrw_panel_course_forward.png",
            (175, 440, 205, 110),
            0.95,
        ),
        (
            kyrw_dir / "09_npc_puzhao_wuchan_button.png",
            root / "src/ymjh_bot/templates/btn_kyrw_npc_wuchan.png",
            (900, 400, 360, 130),
            0.95,
        ),
        (
            kyrw_dir / "36_manual_accept_current_state.png",
            root / "src/ymjh_bot/templates/text_kyrw_course_sidebar.png",
            (40, 135, 330, 430),
            0.95,
        ),
        (
            kyrw_dir / "26_single_tap_wuchanchang_toast.png",
            root / "src/ymjh_bot/templates/text_kyrw_existing_course_toast.png",
            (450, 300, 420, 90),
            0.95,
        ),
        (
            kyrw_dir / "46_stage_5_acquire_route_mall.png",
            root / "src/ymjh_bot/templates/route_kyrw_mall.png",
            (330, 120, 880, 520),
            0.95,
        ),
        (
            kyrw_dir / "49_after_buy_18_humabing.png",
            root / "src/ymjh_bot/templates/btn_kyrw_one_key_submit.png",
            (900, 330, 340, 160),
            0.95,
        ),
        (
            kyrw_dir / "51_course_complete_dialog.png",
            root / "src/ymjh_bot/templates/text_kyrw_complete.png",
            (350, 250, 600, 220),
            0.95,
        ),
        (
            kyrw_dir / "40_course_path_or_dialog.png",
            root / "src/ymjh_bot/templates/btn_kyrw_dialog_next.png",
            (1180, 640, 100, 80),
            0.95,
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi, threshold in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=threshold, roi=roi)

        assert result.found is True
        assert result.score >= threshold


def test_zgwx_templates_match_reference_screenshots():
    root = Path(__file__).resolve().parents[1]
    zgwx_dir = root / "screenshots" / "zgwx"
    cases = [
        (
            zgwx_dir / "zgwx_02_activity_youli_panel.png",
            root / "src/ymjh_bot/templates/btn_bangpai_task_forward.png",
            (120, 250, 220, 120),
            0.95,
        ),
        (
            zgwx_dir / "zgwx_04_auto_path_wait_1.png",
            root / "src/ymjh_bot/templates/text_zgwx_meditating.png",
            None,
            0.95,
        ),
        (
            zgwx_dir / "zgwx_05_meditation_wait_min_1.png",
            root / "src/ymjh_bot/templates/text_zgwx_meditating.png",
            None,
            0.9,
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi, threshold in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=threshold, roi=roi)

        assert result.found is True
        assert result.score >= threshold


def test_zgwx_templates_avoid_completion_false_positives():
    root = Path(__file__).resolve().parents[1]
    zgwx_dir = root / "screenshots" / "zgwx"
    cases = [
        (
            zgwx_dir / "zgwx_08_activity_youli_verify_complete.png",
            root / "src/ymjh_bot/templates/btn_bangpai_task_forward.png",
            (120, 250, 220, 120),
            0.8,
        ),
        (
            zgwx_dir / "zgwx_03_after_activity_forward.png",
            root / "src/ymjh_bot/templates/text_zgwx_meditating.png",
            None,
            0.9,
        ),
        (
            zgwx_dir / "zgwx_06_after_meditation_complete.png",
            root / "src/ymjh_bot/templates/text_zgwx_meditating.png",
            None,
            0.9,
        ),
    ]

    engine = VisionEngine()
    for screenshot_path, template_path, roi, threshold in cases:
        result = engine.match_template(load_image(screenshot_path), str(template_path), threshold=threshold, roi=roi)

        assert result.found is False


def test_kyrw_reuses_bangpai_stall_route_template():
    root = Path(__file__).resolve().parents[1]
    engine = VisionEngine()
    result = engine.match_template(
        load_image(root / "screenshots" / "bangpai_debug_after_sidebar_click.png"),
        str(root / "src/ymjh_bot/templates/route_bangpai_stall.png"),
        threshold=0.95,
        roi=(720, 120, 480, 500),
    )

    assert result.found is True
    assert result.score >= 0.95
