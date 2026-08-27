from __future__ import annotations

import subprocess

import cv2
import numpy as np

import botCore.adb_client as adb_client_module
from botCore import ADBClient


def test_all_adb_processes_hide_their_console_window_on_windows(monkeypatch) -> None:
    calls: list[tuple[list[str], dict]] = []
    screenshot = np.arange(20 * 20 * 3, dtype=np.uint8).reshape((20, 20, 3))
    encoded_ok, encoded = cv2.imencode(".png", screenshot)
    assert encoded_ok

    def fake_run(cmd, **kwargs):
        calls.append((list(cmd), kwargs))
        if kwargs["text"]:
            stdout = (
                "List of devices attached\n127.0.0.1:16384\tdevice\n"
                if cmd[-1] == "devices"
                else "connected to 127.0.0.1:16384\n"
            )
            stderr = ""
        else:
            stdout = encoded.tobytes()
            stderr = b""
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(adb_client_module.subprocess, "run", fake_run)

    assert ADBClient.list_devices()[0].serial == "127.0.0.1:16384"
    client = ADBClient()
    client.connect("127.0.0.1:16384")
    assert client.screenshot().shape == (20, 20, 3)

    assert len(calls) == 3
    for _cmd, kwargs in calls:
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is False
        assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
