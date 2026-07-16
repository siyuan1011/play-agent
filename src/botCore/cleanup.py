"""Preview or remove expired runtime logs and screenshots.

The tool is intentionally scoped to ``logs/``. Test fixtures, templates, and
documentation assets are never candidates.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def _latest_mtime(path: Path) -> float:
    if path.is_file():
        return path.stat().st_mtime
    return max(
        (item.stat().st_mtime for item in path.rglob("*") if item.is_file()),
        default=path.stat().st_mtime,
    )


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def collect_expired_artifacts(
    logs_dir: Path,
    *,
    keep_days: int = 7,
    now: datetime | None = None,
) -> list[Path]:
    """Return expired artifacts without modifying the filesystem."""
    if keep_days < 0:
        raise ValueError("keep_days must be non-negative")
    if not logs_dir.is_dir():
        return []

    cutoff = (now or datetime.now()).timestamp() - timedelta(days=keep_days).total_seconds()
    managed_runs: list[Path] = []
    candidates: list[Path] = []

    for run_dir in logs_dir.rglob("run_*"):
        if not run_dir.is_dir() or run_dir.is_symlink():
            continue
        managed_runs.append(run_dir)
        try:
            if _latest_mtime(run_dir) < cutoff:
                candidates.append(run_dir)
        except OSError:
            continue

    for path in logs_dir.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if any(_is_inside(path, run_dir) for run_dir in managed_runs):
            continue
        try:
            if path.stat().st_mtime < cutoff:
                candidates.append(path)
        except OSError:
            continue

    return sorted(set(candidates), key=lambda item: str(item).lower())


def apply_cleanup(paths: list[Path]) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Delete collected candidates and return successful and failed paths."""
    removed: list[Path] = []
    failed: list[tuple[Path, str]] = []
    for path in paths:
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            failed.append((path, str(exc)))
            continue
        removed.append(path)
    return removed, failed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=Path, default=repo_root / "logs")
    parser.add_argument("--keep-days", type=int, default=7)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete listed artifacts. Without this flag the command is a dry run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        candidates = collect_expired_artifacts(
            args.logs_dir.resolve(),
            keep_days=args.keep_days,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    action = "DELETE" if args.apply else "WOULD DELETE"
    for path in candidates:
        print(f"{action}: {path}")

    if not args.apply:
        print(f"Dry run: {len(candidates)} expired artifact(s). Use --apply to delete.")
        return 0

    removed, failed = apply_cleanup(candidates)
    for path, error in failed:
        print(f"SKIPPED: {path} ({error})")
    print(f"Removed {len(removed)} artifact(s); skipped {len(failed)}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
