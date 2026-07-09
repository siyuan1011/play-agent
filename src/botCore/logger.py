from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .models import ExecutionResult


class RunLogger:
    def __init__(self, base_dir: str | Path = "logs") -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.run_dir = Path(base_dir) / f"run_{ts}"
        self.shots_dir = self.run_dir / "shots"
        self.events_path = self.run_dir / "events.jsonl"
        self.shots_dir.mkdir(parents=True, exist_ok=True)

    def log_event(self, event: dict[str, Any]) -> None:
        event = dict(event)
        event.setdefault("ts", datetime.now().isoformat())
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def save_annotated(
        self,
        image: np.ndarray,
        *,
        point: tuple[int, int] | None = None,
        label: str | None = None,
    ) -> str:
        canvas = image.copy()
        if point:
            cv2.circle(canvas, point, 12, (0, 0, 255), 2)
        if label:
            cv2.putText(
                canvas,
                label,
                (16, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (50, 220, 50),
                2,
                cv2.LINE_AA,
            )
        ts = datetime.now().strftime("%H%M%S_%f")
        out_path = self.shots_dir / f"{ts}.png"
        cv2.imwrite(str(out_path), canvas)
        return str(out_path)

    def log_step_result(self, step_id: str, result: ExecutionResult) -> None:
        self.log_event(
            {
                "step_id": step_id,
                "success": result.success,
                "elapsed_ms": result.elapsed_ms,
                "reason": result.reason,
                "screenshot_path": result.screenshot_path,
                "ts": datetime.now().isoformat(),
            }
        )
