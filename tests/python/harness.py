"""Shared test helpers for happycow Python unit tests.

Provides stdlib-only tempfile/subprocess utilities so individual test
modules stay focused on assertions rather than boilerplate.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_script(
    script: Path | str,
    args: list[str] | None = None,
    *,
    env: dict | None = None,
    cwd: Path | str | None = None,
) -> subprocess.CompletedProcess:
    """Run a Python script in a subprocess; return the CompletedProcess."""
    cmd = [sys.executable, str(script)] + (args or [])
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=merged_env,
        cwd=str(cwd) if cwd else None,
    )


def write_json(path: Path, obj) -> None:
    """Write obj as JSON to path, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class TempDir:
    """Context manager providing a temporary directory removed on exit."""

    def __enter__(self) -> Path:
        self._path = Path(tempfile.mkdtemp())
        return self._path

    def __exit__(self, *_) -> None:
        shutil.rmtree(self._path, ignore_errors=True)
