from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .models import ExecutionResult


class RunLogger:
    DEFAULT_RETENTION_DAYS = 7

    def __init__(
        self,
        base_dir: str | Path = "logs",
        *,
        retention_days: int | None = DEFAULT_RETENTION_DAYS,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        if retention_days is not None:
            self.prune_expired_runs(retention_days=retention_days)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.run_dir = self.base_dir / f"run_{ts}"
        self.shots_dir = self.run_dir / "shots"
        self.events_path = self.run_dir / "events.jsonl"
        self.shots_dir.mkdir(parents=True, exist_ok=True)

    def prune_expired_runs(
        self,
        *,
        retention_days: int | None = None,
        now: datetime | None = None,
    ) -> list[Path]:
        """Delete only expired ``run_*`` directories managed by this logger."""
        days = self.retention_days if retention_days is None else retention_days
        if days is None:
            return []
        if days < 0:
            raise ValueError("retention_days must be non-negative or None")

        cutoff = (now or datetime.now()).timestamp() - timedelta(days=days).total_seconds()
        removed: list[Path] = []
        for run_dir in self.base_dir.glob("run_*"):
            if not run_dir.is_dir() or run_dir.is_symlink():
                continue
            try:
                latest_mtime = max(
                    (path.stat().st_mtime for path in run_dir.rglob("*") if path.is_file()),
                    default=run_dir.stat().st_mtime,
                )
                if latest_mtime >= cutoff:
                    continue
                shutil.rmtree(run_dir)
            except OSError:
                continue
            removed.append(run_dir)
        return removed

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
        return self.save_screenshot(image, prefix="shot", point=point, label=label)

    def save_screenshot(
        self,
        image: np.ndarray,
        *,
        prefix: str = "screenshot",
        point: tuple[int, int] | None = None,
        label: str | None = None,
    ) -> str:
        """Save a diagnostic screenshot inside the current run directory."""
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
        safe_prefix = re.sub(r"[^\w.-]+", "_", prefix, flags=re.UNICODE).strip("._")
        safe_prefix = safe_prefix or "screenshot"
        ts = datetime.now().strftime("%H%M%S_%f")
        out_path = self.shots_dir / f"{safe_prefix}_{ts}.png"
        if not cv2.imwrite(str(out_path), canvas):
            raise RuntimeError(f"Failed to save screenshot: {out_path}")
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
