from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np


_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run_adb_process(
    cmd: Sequence[str],
    *,
    text: bool,
    timeout_sec: int,
) -> subprocess.CompletedProcess:
    """Run an ADB command without opening a console window on Windows."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=text,
        timeout=timeout_sec,
        check=False,
        creationflags=_CREATE_NO_WINDOW,
    )


class ADBError(RuntimeError):
    pass


@dataclass(slots=True)
class DeviceInfo:
    serial: str
    state: str


class ADBClient:
    def __init__(self, adb_path: str = "adb", serial: str | None = None, timeout_sec: int = 15):
        self.adb_path = adb_path
        self.serial = serial
        self.timeout_sec = timeout_sec

    @staticmethod
    def list_devices(adb_path: str = "adb", timeout_sec: int = 10) -> list[DeviceInfo]:
        cmd = [adb_path, "devices"]
        try:
            proc = _run_adb_process(
                cmd,
                text=True,
                timeout_sec=timeout_sec,
            )
        except FileNotFoundError:
            raise ADBError(f"ADB not found: {adb_path}. Please install ADB or set correct path.")
        if proc.returncode != 0:
            raise ADBError(proc.stderr.strip() or "adb devices failed")
        devices: list[DeviceInfo] = []
        for line in proc.stdout.splitlines():
            if "\t" not in line or line.startswith("List of devices"):
                continue
            serial, state = line.split("\t", 1)
            devices.append(DeviceInfo(serial=serial.strip(), state=state.strip()))
        return devices

    def connect(self, serial: str) -> None:
        proc = self._run(["connect", serial], check=False, text=True)
        text = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0 and "already connected" not in text.lower():
            raise ADBError(text.strip() or f"Failed to connect {serial}")
        self.serial = serial

    def ensure_device(self) -> None:
        devices = self.list_devices(self.adb_path, timeout_sec=self.timeout_sec)
        if self.serial:
            if any(d.serial == self.serial and d.state == "device" for d in devices):
                return
            raise ADBError(f"Device serial not found or not ready: {self.serial}")
        ready = [d for d in devices if d.state == "device"]
        if len(ready) == 1:
            self.serial = ready[0].serial
            return
        if len(ready) == 0:
            raise ADBError("No active adb device found.")
        raise ADBError("Multiple devices found. Please select a device serial.")

    def get_screen_size(self) -> tuple[int, int]:
        out = self.shell("wm size")
        match = re.search(r"(\d+)x(\d+)", out)
        if not match:
            raise ADBError(f"Unable to parse wm size output: {out}")
        return int(match.group(1)), int(match.group(2))

    def screenshot(self) -> np.ndarray:
        cmd = [self.adb_path, *self._device_prefix(), "exec-out", "screencap", "-p"]
        proc = _run_adb_process(
            cmd,
            text=False,
            timeout_sec=self.timeout_sec,
        )
        if proc.returncode != 0:
            raise ADBError(proc.stderr.decode(errors="ignore").strip() or "screencap failed")
        raw = proc.stdout
        if not raw or len(raw) < 100:
            raise ADBError(f"Screenshot empty or too small: {len(raw)} bytes")
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ADBError(f"Failed to decode screenshot bytes. Size: {len(raw)}, header: {raw[:20]}")
        return image

    def tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {int(x)} {int(y)}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
        self.shell(
            f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}"
        )

    def shell(self, command: str) -> str:
        proc = self._run(["shell", command], check=False, text=True)
        if proc.returncode != 0:
            raise ADBError(proc.stderr.strip() or f"adb shell failed: {command}")
        return (proc.stdout or "").strip()

    def launch_app(self, package_name: str, activity: str | None = None) -> None:
        """
        启动 Android 应用。

        Args:
            package_name: 应用包名，如 com.example.app
            activity: 可选的 Activity 名称，如 com.example.app.MainActivity
                      如果不指定，将尝试启动默认 Activity
        """
        if activity:
            component = f"{package_name}/{activity}"
        else:
            component = f"{package_name}/.{self._get_launch_activity(package_name)}"
        self.shell(f"am start -n {component}")

    def _get_launch_activity(self, package_name: str) -> str:
        """获取应用的默认启动 Activity"""
        out = self.shell(f"cmd package resolve-activity --components {package_name}")
        for line in out.splitlines():
            if line.startswith("com.") or line.startswith(package_name):
                return line.split("/")[-1]
        raise ADBError(f"Unable to find launch activity for package: {package_name}")

    def _device_prefix(self) -> list[str]:
        return ["-s", self.serial] if self.serial else []

    def _run(
        self,
        args: Sequence[str],
        *,
        check: bool,
        text: bool,
    ) -> subprocess.CompletedProcess:
        cmd = [self.adb_path, *self._device_prefix(), *args]
        proc = _run_adb_process(
            cmd,
            text=text,
            timeout_sec=self.timeout_sec,
        )
        if check and proc.returncode != 0:
            stderr = proc.stderr if text else proc.stderr.decode(errors="ignore")
            raise ADBError(stderr.strip() or "adb command failed")
        return proc
