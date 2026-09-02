"""Build the distributable Windows x64 release for ``ymjh_bot``."""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


APP_NAME = "ymjh-bot"
ARCHIVE_NAME = f"{APP_NAME}-windows-x64.zip"


@dataclass(frozen=True)
class ReleasePaths:
    """Resolved paths used by one release build."""

    project_root: Path
    spec_file: Path
    env_template: Path
    work_dir: Path
    dist_dir: Path
    bundle_dir: Path
    executable: Path
    archive: Path
    checksum: Path

    @classmethod
    def from_root(cls, project_root: Path) -> "ReleasePaths":
        root = project_root.resolve()
        dist_dir = root / "dist" / "release"
        bundle_dir = dist_dir / APP_NAME
        archive = dist_dir / ARCHIVE_NAME
        return cls(
            project_root=root,
            spec_file=root / "ymjh_bot.spec",
            env_template=root / ".env.example",
            work_dir=root / "build" / "release",
            dist_dir=dist_dir,
            bundle_dir=bundle_dir,
            executable=bundle_dir / f"{APP_NAME}.exe",
            archive=archive,
            checksum=archive.with_suffix(f"{archive.suffix}.sha256"),
        )


def find_project_root(start: Path | None = None) -> Path:
    """Find the source checkout containing the release specification."""

    starts = [start or Path.cwd(), Path(__file__).resolve().parent]
    for initial in starts:
        current = initial.resolve()
        for candidate in (current, *current.parents):
            if (
                (candidate / "pyproject.toml").is_file()
                and (candidate / "ymjh_bot.spec").is_file()
                and (candidate / "src" / "ymjh_bot" / "main.py").is_file()
            ):
                return candidate
    raise RuntimeError(
        "Could not locate the project root. Run this command from the PlayAgent source checkout."
    )


def validate_build_host() -> None:
    """Reject hosts that cannot produce the documented Windows x64 artifact."""

    if platform.system() != "Windows" or sys.maxsize <= 2**32:
        raise RuntimeError("The formal release must be built with 64-bit Python on Windows.")


def run_command(command: Sequence[str], *, cwd: Path) -> None:
    """Run one build stage and fail immediately when it exits unsuccessfully."""

    print(f"> {subprocess.list2cmdline(list(command))}", flush=True)
    subprocess.run(list(command), cwd=cwd, check=True)


def run_tests(paths: ReleasePaths) -> None:
    run_command(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=paths.project_root,
    )


def run_pyinstaller(paths: ReleasePaths) -> None:
    run_command(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(paths.dist_dir),
            "--workpath",
            str(paths.work_dir),
            str(paths.spec_file),
        ],
        cwd=paths.project_root,
    )


def prepare_bundle(paths: ReleasePaths) -> None:
    """Validate the build and add only the public runtime configuration."""

    if not paths.executable.is_file():
        raise RuntimeError(f"PyInstaller did not produce {paths.executable}")
    if not (paths.bundle_dir / "_internal").is_dir():
        raise RuntimeError("PyInstaller bundle is missing its _internal directory")
    if not paths.env_template.is_file():
        raise RuntimeError(f"Missing public configuration template: {paths.env_template}")

    shutil.copy2(paths.env_template, paths.bundle_dir / ".env")


def create_archive(paths: ReleasePaths) -> None:
    """Create a deterministic-layout ZIP with the bundle directory at its root."""

    paths.dist_dir.mkdir(parents=True, exist_ok=True)
    temporary_archive = paths.archive.with_suffix(f"{paths.archive.suffix}.tmp")
    temporary_archive.unlink(missing_ok=True)

    with zipfile.ZipFile(
        temporary_archive,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for source in sorted(paths.bundle_dir.rglob("*")):
            if not source.is_file():
                continue
            relative = Path(paths.bundle_dir.name) / source.relative_to(paths.bundle_dir)
            archive.write(source, relative.as_posix())
    temporary_archive.replace(paths.archive)


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum(paths: ReleasePaths) -> str:
    checksum = calculate_sha256(paths.archive)
    temporary_checksum = paths.checksum.with_suffix(f"{paths.checksum.suffix}.tmp")
    temporary_checksum.write_text(
        f"{checksum}  {paths.archive.name}\n",
        encoding="ascii",
    )
    temporary_checksum.replace(paths.checksum)
    return checksum


def _has_tests(paths: ReleasePaths) -> bool:
    """Return whether the checkout still contains runnable pytest files."""
    tests_dir = paths.project_root / "tests"
    return tests_dir.is_dir() and any(tests_dir.rglob("test_*.py"))


def build_release(*, skip_tests: bool = False) -> ReleasePaths:
    validate_build_host()
    paths = ReleasePaths.from_root(find_project_root())

    for required in (paths.spec_file, paths.env_template):
        if not required.is_file():
            raise RuntimeError(f"Required release input is missing: {required}")

    if skip_tests:
        print("[1/4] Tests skipped by request", flush=True)
    elif _has_tests(paths):
        print("[1/4] Running tests", flush=True)
        run_tests(paths)
    else:
        print("[1/4] No tests found; skipping test stage", flush=True)

    print("[2/4] Building PyInstaller directory bundle", flush=True)
    run_pyinstaller(paths)
    prepare_bundle(paths)

    print("[3/4] Creating release archive", flush=True)
    create_archive(paths)

    print("[4/4] Writing SHA-256 checksum", flush=True)
    checksum = write_checksum(paths)
    print(f"Release: {paths.archive}", flush=True)
    print(f"SHA256:  {checksum}", flush=True)
    return paths


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the formal ymjh_bot Windows x64 release archive."
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="skip pytest (intended only when tests have already passed in this checkout)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        build_release(skip_tests=args.skip_tests)
    except KeyboardInterrupt:
        print("Release build interrupted.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Release build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
