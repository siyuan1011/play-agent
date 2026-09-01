from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np


@dataclass(slots=True)
class ImageMatchResult:
    found: bool
    score: float
    center: tuple[int, int] | None
    bbox: tuple[int, int, int, int] | None
    template_path: str | None = None


class VisionEngine:
    def match_binary_template(
        self,
        screenshot: np.ndarray,
        template_paths: str | list[str],
        *,
        mode: Literal["otsu_dark", "light_foreground"],
        threshold: float = 0.85,
        roi: tuple[int, int, int, int] | None = None,
    ) -> ImageMatchResult:
        """Match foreground shapes after removing most color/background variation."""
        if mode not in {"otsu_dark", "light_foreground"}:
            raise ValueError(f"Unsupported binary template mode: {mode}")
        candidates = [template_paths] if isinstance(template_paths, str) else template_paths
        region = screenshot
        offset_x, offset_y = 0, 0
        if roi:
            x, y, width, height = roi
            offset_x, offset_y = x, y
            region = screenshot[y : y + height, x : x + width]

        best = ImageMatchResult(found=False, score=0.0, center=None, bbox=None)
        if region.size == 0:
            return best
        binary_region = self._to_binary_foreground(region, mode)
        for template_path in candidates:
            template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
            if template is None:
                continue
            binary_template = self._to_binary_foreground(template, mode)
            if (
                binary_region.shape[0] < binary_template.shape[0]
                or binary_region.shape[1] < binary_template.shape[1]
                or float(np.std(binary_template)) < 1e-6
            ):
                continue

            response = cv2.matchTemplate(
                binary_region,
                binary_template,
                cv2.TM_CCOEFF_NORMED,
            )
            _, max_value, _, max_location = cv2.minMaxLoc(response)
            score = float(max_value)
            if score <= best.score:
                continue

            x1 = max_location[0] + offset_x
            y1 = max_location[1] + offset_y
            x2 = x1 + binary_template.shape[1]
            y2 = y1 + binary_template.shape[0]
            best = ImageMatchResult(
                found=score >= threshold,
                score=score,
                center=(int((x1 + x2) / 2), int((y1 + y2) / 2)),
                bbox=(x1, y1, x2, y2),
                template_path=str(template_path),
            )

        if best.score < threshold:
            best.found = False
        return best

    @staticmethod
    def _to_binary_foreground(
        image: np.ndarray,
        mode: Literal["otsu_dark", "light_foreground"],
    ) -> np.ndarray:
        if image.ndim == 2:
            gray = image
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            bgr = image[:, :, :3]
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        if mode == "otsu_dark":
            _, binary = cv2.threshold(
                gray,
                0,
                255,
                cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU,
            )
            return binary
        if mode == "light_foreground":
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            light_mask = (gray >= 145) & (hsv[:, :, 1] <= 120)
            return light_mask.astype(np.uint8) * 255
        raise AssertionError(f"Unhandled binary template mode: {mode}")

    def match_all_templates(
        self,
        screenshot: np.ndarray,
        template_paths: str | list[str],
        *,
        threshold: float = 0.85,
        roi: tuple[int, int, int, int] | None = None,
    ) -> list[ImageMatchResult]:
        """Return every distinct template match at or above ``threshold``.

        Matches are suppressed around each selected peak for the same template so
        that one visual target does not produce a dense cluster of results.  The
        caller may still merge nearby results produced by different templates.
        """
        candidates = [template_paths] if isinstance(template_paths, str) else template_paths
        region = screenshot
        offset_x, offset_y = 0, 0
        if roi:
            x, y, w, h = roi
            offset_x, offset_y = x, y
            region = screenshot[y : y + h, x : x + w]

        matches: list[ImageMatchResult] = []
        for tpl_path in candidates:
            tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
            if tpl is None:
                continue
            if region.shape[0] < tpl.shape[0] or region.shape[1] < tpl.shape[1]:
                continue

            if float(np.std(tpl)) < 1e-6:
                response = cv2.matchTemplate(region, tpl, cv2.TM_SQDIFF_NORMED)
                scores = 1.0 - response
            else:
                scores = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)

            # Work on a copy because each accepted peak is suppressed before the
            # next search.  Half-template suppression removes duplicate peaks
            # while retaining separate close buttons on the same screen.
            remaining = scores.copy()
            tpl_h, tpl_w = tpl.shape[:2]
            suppress_x = max(1, tpl_w // 2)
            suppress_y = max(1, tpl_h // 2)
            while remaining.size:
                _, max_val, _, max_loc = cv2.minMaxLoc(remaining)
                score = float(max_val)
                if score < threshold:
                    break

                x1 = max_loc[0] + offset_x
                y1 = max_loc[1] + offset_y
                x2 = x1 + tpl_w
                y2 = y1 + tpl_h
                matches.append(
                    ImageMatchResult(
                        found=True,
                        score=score,
                        center=(int((x1 + x2) / 2), int((y1 + y2) / 2)),
                        bbox=(x1, y1, x2, y2),
                        template_path=str(tpl_path),
                    )
                )

                peak_x, peak_y = max_loc
                left = max(0, peak_x - suppress_x)
                right = min(remaining.shape[1], peak_x + suppress_x + 1)
                top = max(0, peak_y - suppress_y)
                bottom = min(remaining.shape[0], peak_y + suppress_y + 1)
                remaining[top:bottom, left:right] = -np.inf

        matches.sort(key=lambda match: match.score, reverse=True)
        return matches

    def match_template(
        self,
        screenshot: np.ndarray,
        template_paths: str | list[str],
        *,
        threshold: float = 0.85,
        roi: tuple[int, int, int, int] | None = None,
    ) -> ImageMatchResult:
        candidates = [template_paths] if isinstance(template_paths, str) else template_paths
        region = screenshot
        offset_x, offset_y = 0, 0
        if roi:
            x, y, w, h = roi
            offset_x, offset_y = x, y
            region = screenshot[y : y + h, x : x + w]

        best = ImageMatchResult(found=False, score=0.0, center=None, bbox=None)
        for tpl_path in candidates:
            tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
            if tpl is None:
                continue
            if region.shape[0] < tpl.shape[0] or region.shape[1] < tpl.shape[1]:
                continue
            # Constant-color templates are unstable with CCOEFF. Fall back to SQDIFF.
            if float(np.std(tpl)) < 1e-6:
                response = cv2.matchTemplate(region, tpl, cv2.TM_SQDIFF_NORMED)
                min_val, _, min_loc, _ = cv2.minMaxLoc(response)
                score = 1.0 - float(min_val)
                loc = min_loc
            else:
                response = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(response)
                score = float(max_val)
                loc = max_loc
            if score > best.score:
                x1 = loc[0] + offset_x
                y1 = loc[1] + offset_y
                x2 = x1 + tpl.shape[1]
                y2 = y1 + tpl.shape[0]
                best = ImageMatchResult(
                    found=score >= threshold,
                    score=score,
                    center=(int((x1 + x2) / 2), int((y1 + y2) / 2)),
                    bbox=(x1, y1, x2, y2),
                    template_path=str(tpl_path),
                )
        if best.score < threshold:
            best.found = False
        return best


def load_image(path: str | Path) -> np.ndarray:
    image_path = Path(path)
    try:
        encoded = np.fromfile(image_path, dtype=np.uint8)
    except OSError as exc:
        raise FileNotFoundError(f"Unable to load image: {path}") from exc
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR) if encoded.size else None
    if image is None:
        raise FileNotFoundError(f"Unable to load image: {path}")
    return image
