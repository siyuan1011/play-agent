"""State helpers for the YMJH task queue UI."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import re
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_STATE: dict[str, Any] = {
    "adb_path": "adb",
    "serial": "",
    "selected_role_indices": [0],
    "selected_task_keys": [],
    "task_settings": {},
}

MAX_ROLE_COUNT = 5

HSLJ_TASK_KEY = "HSLJ"
HSLJ_MODE_KEYS = ("1v1", "3v3")
HSLJ_STRATEGY_FIRST_WIN = "first_win"
HSLJ_STRATEGY_INFINITE = "infinite"
HSLJ_STRATEGY_FIXED_COUNT = "fixed_count"
HSLJ_STRATEGIES = {
    HSLJ_STRATEGY_FIRST_WIN,
    HSLJ_STRATEGY_INFINITE,
    HSLJ_STRATEGY_FIXED_COUNT,
}

DEFAULT_HSLJ_COUNT = 5
DEFAULT_HSLJ_SETTINGS: dict[str, Any] = {
    "1v1": {
        "strategy": HSLJ_STRATEGY_FIRST_WIN,
        "count": DEFAULT_HSLJ_COUNT,
    },
    "3v3": {
        "strategy": HSLJ_STRATEGY_FIXED_COUNT,
        "count": DEFAULT_HSLJ_COUNT,
    },
}

SHRW_TASK_KEY = "SHRW"
SHRW_TASK_TYPE_LABELS: dict[str, str] = {
    "mining": "挖矿",
    "herb": "采草",
    "logging": "伐木",
    "wool": "采毛",
}
SHRW_MATERIAL_OPTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "mining": (
        ("stone", "碎石"),
        ("brass_ore", "黄铜矿"),
        ("silver_ore", "立银矿"),
        ("gold_ore", "金矿"),
        ("emerald_ore", "祖母绿矿"),
        ("tungsten_ore", "钨晶矿"),
    ),
    "herb": (
        ("weed", "杂草"),
        ("wildflower", "野花"),
        ("vermilion_fruit", "朱果"),
        ("earth_spirit_fruit", "地灵果"),
        ("wild_ginseng", "野山参"),
        ("lingzhi", "灵芝"),
    ),
    "logging": (
        ("deadwood", "枯木"),
        ("green_bamboo", "翠竹"),
        ("elm", "榆树"),
        ("maple", "枫树"),
        ("pine", "松树"),
        ("eucalyptus", "桉树"),
    ),
    "wool": (
        ("wool", "羊毛"),
        ("reindeer_hair", "驯鹿毛"),
        ("cashmere", "羊绒"),
        ("reindeer_down", "驯鹿绒"),
    ),
}
SHRW_LINE_SCOPE_LABELS: dict[str, str] = {
    "local": "本服分线",
    "interconnected": "互联分线",
}
DEFAULT_SHRW_SETTINGS: dict[str, Any] = {
    "task_type": "mining",
    "material": "stone",
    "loop_lines": False,
    "line_scope": "local",
}

_SHRW_TASK_TYPE_ALIASES = {
    **{key: key for key in SHRW_TASK_TYPE_LABELS},
    **{label: key for key, label in SHRW_TASK_TYPE_LABELS.items()},
    "采矿": "mining",
    "采药": "herb",
    "砍伐": "logging",
}
_SHRW_MATERIAL_ALIASES = {
    alias: material_key
    for options in SHRW_MATERIAL_OPTIONS.values()
    for material_key, label in options
    for alias in (material_key, label)
}
_SHRW_MATERIAL_ALIASES["钨金矿"] = "tungsten_ore"
_SHRW_LINE_SCOPE_ALIASES = {
    "local": "local",
    "本服": "local",
    "本服分线": "local",
    "server": "local",
    "interconnected": "interconnected",
    "互联": "interconnected",
    "互联分线": "interconnected",
    "cross_server": "interconnected",
}

TASK_KEY_ALIASES: dict[str, str] = {
    "launch": "QDYX",
    "start": "QDYX",
    "bangpai": "BPRW",
    "cgss": "CGSS",
    "hslj": HSLJ_TASK_KEY,
    "jhyxb": "JHYXB",
    "kyrw": "KYRW",
    "menke_sheyan": "MKSY",
    "mksy": "MKSY",
    "mryg": "MRYG",
    "life": SHRW_TASK_KEY,
    "shrw": SHRW_TASK_KEY,
    "生活任务": SHRW_TASK_KEY,
    "生活技能": SHRW_TASK_KEY,
    "pozhen_sheyan": "PZSY",
    "pzsy": "PZSY",
    "zgwx": "ZGWX",
}

SAFE_SERIAL_FALLBACK = "default"


def default_state() -> dict[str, Any]:
    """Return a fresh default state dictionary."""
    return deepcopy(DEFAULT_STATE)


def load_state(path: Path) -> dict[str, Any]:
    """Load queue UI state from JSON, falling back to defaults."""
    state = default_state()
    if not path.exists():
        return state

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return state

    if not isinstance(data, dict):
        return state

    state.update({key: value for key, value in data.items() if key in state or key == "progress"})
    if not isinstance(state.get("selected_task_keys"), list):
        state["selected_task_keys"] = []
    else:
        state["selected_task_keys"] = normalize_task_keys(state["selected_task_keys"])
    state["adb_path"] = str(state.get("adb_path") or "adb")
    state["serial"] = str(state.get("serial") or "")
    if "selected_role_indices" in data:
        state["selected_role_indices"] = normalize_selected_role_indices(
            data.get("selected_role_indices")
        )
    elif "role_count" in data:
        state["selected_role_indices"] = role_indices_from_count(data.get("role_count"))
    if not isinstance(state.get("task_settings"), dict):
        state["task_settings"] = {}
    else:
        state["task_settings"] = normalize_task_settings(state["task_settings"])

    progress = normalize_progress(state.get("progress"))
    if progress is None:
        state.pop("progress", None)
    else:
        state["progress"] = progress
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Persist queue UI state to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = default_state()
    serializable.update({key: value for key, value in state.items() if key in serializable})
    serializable["selected_role_indices"] = normalize_selected_role_indices(
        serializable.get("selected_role_indices")
    )
    serializable["selected_task_keys"] = normalize_task_keys(serializable.get("selected_task_keys"))
    serializable["task_settings"] = normalize_task_settings(serializable.get("task_settings"))
    if "progress" in state:
        progress = normalize_progress(state.get("progress"))
        if progress is not None:
            serializable["progress"] = progress
    path.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clear_progress(state: dict[str, Any]) -> dict[str, Any]:
    """Return state with progress removed while preserving queue/settings."""
    updated = deepcopy(state)
    updated.pop("progress", None)
    return updated


def role_indices_from_count(value: Any) -> list[int]:
    """Migrate a legacy leading-role count to explicit zero-based role indices."""
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 1
    return list(range(max(1, min(count, MAX_ROLE_COUNT))))


def normalize_selected_role_indices(value: Any) -> list[int]:
    """Normalize an explicit role selection while preserving an intentional empty list."""
    if not isinstance(value, list):
        return [0]

    selected: set[int] = set()
    for raw_index in value:
        try:
            role_index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if 0 <= role_index < MAX_ROLE_COUNT:
            selected.add(role_index)
    return sorted(selected)


def safe_serial_name(serial: str | None) -> str:
    """Return a filesystem-safe name for an ADB serial."""
    value = str(serial or "").strip()
    if not value:
        return SAFE_SERIAL_FALLBACK
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    safe = safe.strip("._-")
    return safe or SAFE_SERIAL_FALLBACK


def state_path_for_serial(state_dir: Path, serial: str | None) -> Path:
    """Return the per-serial state path."""
    return state_dir / f"{safe_serial_name(serial)}.json"


def load_state_for_serial(
    state_dir: Path,
    serial: str | None,
    *,
    legacy_path: Path | None = None,
    fallback_adb_path: str | None = None,
) -> tuple[dict[str, Any], Path]:
    """Load the state for a serial, migrating the legacy single-state file when applicable."""
    requested_serial = str(serial or "").strip()
    target_path = state_path_for_serial(state_dir, requested_serial)
    if target_path.exists():
        state = load_state(target_path)
        if requested_serial:
            state["serial"] = requested_serial
        return state, target_path

    if legacy_path and legacy_path.exists():
        legacy_state = load_state(legacy_path)
        legacy_serial = str(legacy_state.get("serial") or "").strip()
        if not requested_serial or requested_serial == legacy_serial:
            migrated_serial = requested_serial or legacy_serial
            legacy_state["serial"] = migrated_serial
            if fallback_adb_path and not legacy_state.get("adb_path"):
                legacy_state["adb_path"] = fallback_adb_path
            target_path = state_path_for_serial(state_dir, migrated_serial)
            save_state(target_path, legacy_state)
            return load_state(target_path), target_path

    state = default_state()
    state["serial"] = requested_serial
    if fallback_adb_path:
        state["adb_path"] = fallback_adb_path
    return state, target_path


def normalize_task_settings(settings: Any) -> dict[str, Any]:
    """Normalize known task settings while preserving unknown task keys."""
    if not isinstance(settings, dict):
        return {}

    normalized: dict[str, Any] = {}
    for raw_key, value in settings.items():
        key = normalize_task_key(raw_key)
        if key == HSLJ_TASK_KEY:
            normalized[key] = normalize_hslj_settings(value)
        elif key == SHRW_TASK_KEY:
            normalized[key] = normalize_shrw_settings(value)
        else:
            normalized[key] = deepcopy(value)
    return normalized


def normalize_shrw_settings(settings: Any) -> dict[str, Any]:
    """Normalize life-task settings into stable persisted identifiers."""
    normalized = deepcopy(DEFAULT_SHRW_SETTINGS)
    if not isinstance(settings, dict):
        return normalized

    raw_task_type = str(settings.get("task_type", normalized["task_type"]) or "").strip()
    task_type = _SHRW_TASK_TYPE_ALIASES.get(raw_task_type, str(normalized["task_type"]))
    normalized["task_type"] = task_type

    raw_material = str(settings.get("material", normalized["material"]) or "").strip()
    material = _SHRW_MATERIAL_ALIASES.get(raw_material, raw_material)
    allowed_materials = {key for key, _label in SHRW_MATERIAL_OPTIONS[task_type]}
    if material not in allowed_materials:
        material = SHRW_MATERIAL_OPTIONS[task_type][0][0]
    normalized["material"] = material

    raw_loop = settings.get("loop_lines", normalized["loop_lines"])
    if isinstance(raw_loop, str):
        normalized["loop_lines"] = raw_loop.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
            "是",
            "开启",
        }
    else:
        normalized["loop_lines"] = bool(raw_loop)

    raw_scope = str(settings.get("line_scope", normalized["line_scope"]) or "").strip()
    normalized["line_scope"] = _SHRW_LINE_SCOPE_ALIASES.get(
        raw_scope,
        str(normalized["line_scope"]),
    )
    return normalized


def normalize_task_key(task_key: Any) -> str:
    """Return the current persisted task key for a saved or legacy key."""
    key = str(task_key or "").strip()
    return TASK_KEY_ALIASES.get(key, key)


def normalize_task_keys(task_keys: Any) -> list[str]:
    """Normalize persisted task keys while preserving order and removing duplicates."""
    if not isinstance(task_keys, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_key in task_keys:
        key = normalize_task_key(raw_key)
        if not key or key in seen:
            continue
        normalized.append(key)
        seen.add(key)
    return normalized


def normalize_hslj_settings(settings: Any) -> dict[str, Any]:
    """Normalize Huashan Lunjian settings."""
    normalized = deepcopy(DEFAULT_HSLJ_SETTINGS)
    if not isinstance(settings, dict):
        return normalized

    if "1v1" in settings or "3v3" in settings:
        for mode in HSLJ_MODE_KEYS:
            normalized[mode] = normalize_hslj_mode_setting(
                settings.get(mode),
                default=normalized[mode],
            )
        return normalized

    return normalize_legacy_hslj_settings(settings, normalized)


def normalize_hslj_mode_setting(settings: Any, *, default: dict[str, Any]) -> dict[str, Any]:
    """Normalize settings for one Huashan Lunjian mode."""
    normalized = deepcopy(default)
    if not isinstance(settings, dict):
        return normalized

    strategy = str(settings.get("strategy", normalized["strategy"]) or "").strip()
    if strategy not in HSLJ_STRATEGIES:
        strategy = str(default["strategy"])
    normalized["strategy"] = strategy

    try:
        count = int(settings.get("count", normalized["count"]))
    except (TypeError, ValueError):
        count = int(default["count"])
    normalized["count"] = max(1, min(count, 9999))
    return normalized


def normalize_legacy_hslj_settings(
    settings: dict[str, Any],
    normalized: dict[str, Any],
) -> dict[str, Any]:
    """Migrate legacy Huashan Lunjian count/infinite settings."""
    try:
        count = int(settings.get("lunjian_count", DEFAULT_HSLJ_COUNT))
    except (TypeError, ValueError):
        count = DEFAULT_HSLJ_COUNT

    normalized["3v3"] = {
        "strategy": (
            HSLJ_STRATEGY_INFINITE
            if bool(settings.get("infinite", False))
            else HSLJ_STRATEGY_FIXED_COUNT
        ),
        "count": max(1, min(count, 9999)),
    }
    return normalized


def normalize_progress(progress: Any) -> dict[str, int] | None:
    """Normalize progress-like input to the persisted schema."""
    if not isinstance(progress, dict):
        return None
    try:
        role_index = int(progress.get("current_role_index", 0))
        task_index = int(progress.get("current_task_index", 0))
        step_index = int(progress.get("current_step_index", 0))
    except (TypeError, ValueError):
        return None
    return {
        "current_role_index": max(0, role_index),
        "current_task_index": max(0, task_index),
        "current_step_index": max(0, step_index),
    }


def _windows_process_created_at(handle: int) -> float | None:
    """Return the Windows process creation timestamp for an open process handle."""
    filetime_fields = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

    class FILETIME(ctypes.Structure):
        _fields_ = filetime_fields

    creation = FILETIME()
    exit_time = FILETIME()
    kernel_time = FILETIME()
    user_time = FILETIME()
    if not ctypes.windll.kernel32.GetProcessTimes(
        handle,
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    ):
        return None
    value = (creation.dwHighDateTime << 32) + creation.dwLowDateTime
    return (value - 116444736000000000) / 10000000


def is_pid_alive(pid: int, *, since: float | None = None) -> bool:
    """Return whether a process id appears to still be running."""
    if pid <= 0:
        return False
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            if since is not None:
                created_at = _windows_process_created_at(handle)
                if created_at is not None and created_at > since + 1:
                    return False
            return True
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


class SerialRunLock:
    """Process-level lock for a single ADB serial."""

    def __init__(self, lock_path: Path, serial: str):
        self.lock_path = lock_path
        self.serial = serial
        self.acquired = False

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "serial": self.serial,
            "created_at": time.time(),
        }
        while True:
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._is_stale():
                    self._remove_stale()
                    continue
                return False
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False)
            self.acquired = True
            return True

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if int(data.get("pid") or -1) == os.getpid():
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass
        self.acquired = False

    def _is_stale(self) -> bool:
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True
        try:
            pid = int(data.get("pid", 0))
        except (TypeError, ValueError):
            return True
        created_at = data.get("created_at")
        try:
            since = float(created_at) if created_at is not None else None
        except (TypeError, ValueError):
            since = None
        return not is_pid_alive(pid, since=since)

    def _remove_stale(self) -> None:
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def lock_path_for_serial(state_dir: Path, serial: str | None) -> Path:
    """Return the lock path for a serial."""
    return state_dir / "locks" / f"{safe_serial_name(serial)}.lock"


def serial_run_lock(state_dir: Path, serial: str | None) -> SerialRunLock:
    """Create a run lock object for a serial."""
    return SerialRunLock(lock_path_for_serial(state_dir, serial), str(serial or "").strip())


def task_keys_from_infos(task_infos: list[dict[str, Any]]) -> list[str]:
    """Extract persisted task keys from selected task info records."""
    keys: list[str] = []
    for task_info in task_infos:
        key = task_info.get("key")
        if key is not None:
            keys.append(str(key))
    return normalize_task_keys(keys)


def restore_selected_tasks(
    available_tasks: list[dict[str, Any]],
    selected_task_keys: list[Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Restore selected task records in saved order, skipping missing keys."""
    by_key = {str(task["key"]): task for task in available_tasks if task.get("key") is not None}
    restored: list[dict[str, Any]] = []
    missing: list[str] = []

    restored_keys: set[str] = set()
    for raw_key in selected_task_keys:
        key = normalize_task_key(raw_key)
        if key in restored_keys:
            continue
        restored_keys.add(key)
        task_info = by_key.get(key)
        if task_info is None:
            missing.append(str(raw_key))
            continue
        restored.append(task_info.copy())

    return restored, missing
