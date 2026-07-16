from datetime import datetime, timedelta
import os

from botCore.cleanup import apply_cleanup, collect_expired_artifacts, main


def _set_age(path, *, now: datetime, days: int) -> None:
    timestamp = (now - timedelta(days=days)).timestamp()
    os.utime(path, (timestamp, timestamp))


def test_cleanup_preview_and_apply_only_expired_logs(tmp_path, capsys):
    now = datetime(2026, 7, 16, 12, 0, 0)
    logs_dir = tmp_path / "logs"
    old_run = logs_dir / "device" / "run_20260701_000000_000000"
    recent_run = logs_dir / "device" / "run_20260715_000000_000000"
    old_manual = logs_dir / "manual_screenshots" / "old.png"
    recent_manual = logs_dir / "manual_screenshots" / "recent.png"
    for path in (old_run / "events.jsonl", recent_run / "events.jsonl", old_manual, recent_manual):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    _set_age(old_run / "events.jsonl", now=now, days=10)
    _set_age(recent_run / "events.jsonl", now=now, days=1)
    _set_age(old_manual, now=now, days=10)
    _set_age(recent_manual, now=now, days=1)

    candidates = collect_expired_artifacts(logs_dir, keep_days=7, now=now)

    assert candidates == [old_run, old_manual]
    removed, failed = apply_cleanup(candidates)
    assert removed == candidates
    assert failed == []
    assert not old_run.exists()
    assert not old_manual.exists()
    assert recent_run.exists()
    assert recent_manual.exists()
    assert capsys.readouterr().out == ""


def test_cleanup_cli_is_dry_run_by_default(tmp_path, capsys):
    old_log = tmp_path / "logs" / "old.out.log"
    old_log.parent.mkdir(parents=True)
    old_log.write_text("old", encoding="utf-8")
    _set_age(old_log, now=datetime.now(), days=10)

    assert main(["--logs-dir", str(old_log.parent), "--keep-days", "7"]) == 0
    assert old_log.exists()
    assert "WOULD DELETE" in capsys.readouterr().out
