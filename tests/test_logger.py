import json
from datetime import datetime

from botCore import RunLogger


def test_run_logger_adds_timestamp_to_plain_event(tmp_path):
    logger = RunLogger(base_dir=tmp_path)

    logger.log_event({"message": "x"})

    event = json.loads(logger.events_path.read_text(encoding="utf-8").strip())
    assert event["message"] == "x"
    datetime.fromisoformat(event["ts"])
