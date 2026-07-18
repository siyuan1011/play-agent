from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from botCore import VisionEngine


def test_match_all_templates_returns_multiple_peaks_for_one_template(tmp_path: Path) -> None:
    rng = np.random.default_rng(20260717)
    template = rng.integers(0, 256, size=(11, 11, 3), dtype=np.uint8)
    screenshot = np.zeros((90, 110, 3), dtype=np.uint8)
    screenshot[20:31, 10:21] = template
    screenshot[50:61, 60:71] = template
    template_path = tmp_path / "close.png"
    assert cv2.imwrite(str(template_path), template)

    matches = VisionEngine().match_all_templates(
        screenshot,
        str(template_path),
        threshold=0.99,
    )

    assert [match.center for match in matches] == [(15, 25), (65, 55)]
    assert all(match.found for match in matches)


def test_single_match_interface_remains_compatible(tmp_path: Path) -> None:
    rng = np.random.default_rng(7)
    template = rng.integers(0, 256, size=(9, 9, 3), dtype=np.uint8)
    screenshot = np.zeros((50, 50, 3), dtype=np.uint8)
    screenshot[12:21, 18:27] = template
    template_path = tmp_path / "close.png"
    assert cv2.imwrite(str(template_path), template)

    match = VisionEngine().match_template(screenshot, str(template_path), threshold=0.99)

    assert match.found
    assert match.center == (22, 16)


def test_binary_template_match_preserves_roi_coordinates(tmp_path: Path) -> None:
    template = np.full((12, 18, 3), 220, dtype=np.uint8)
    cv2.putText(
        template,
        "T",
        (3, 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.35,
        (0, 0, 0),
        1,
        cv2.LINE_AA,
    )
    screenshot = np.full((60, 90, 3), 220, dtype=np.uint8)
    screenshot[25:37, 40:58] = template
    template_path = tmp_path / "tab.png"
    assert cv2.imwrite(str(template_path), template)

    match = VisionEngine().match_binary_template(
        screenshot,
        str(template_path),
        mode="otsu_dark",
        threshold=0.99,
        roi=(35, 20, 30, 25),
    )

    assert match.found
    assert match.center == (49, 31)
    assert match.bbox == (40, 25, 58, 37)


def test_binary_template_rejects_unknown_mode(tmp_path: Path) -> None:
    template = np.zeros((5, 5, 3), dtype=np.uint8)
    template_path = tmp_path / "template.png"
    assert cv2.imwrite(str(template_path), template)

    with pytest.raises(ValueError, match="Unsupported binary template mode"):
        VisionEngine().match_binary_template(
            template,
            str(template_path),
            mode="unknown",  # type: ignore[arg-type]
        )
