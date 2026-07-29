from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .config import state_dir


IMAGE_MARKER_RE = re.compile(r"MAIXPY_SKILL_IMAGE\s+(\S+)")


def new_run_id(source: Path) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = source.stem.replace(" ", "-")
    return f"{stamp}-{stem}"


def run_dir(run_id: str, cwd: Path | None = None) -> Path:
    return state_dir(cwd) / "runs" / run_id


def create_run_dir(run_id: str, cwd: Path | None = None) -> Path:
    path = run_dir(run_id, cwd)
    (path / "artifacts").mkdir(parents=True, exist_ok=True)
    return path


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_image_markers(stdout: str) -> list[str]:
    return IMAGE_MARKER_RE.findall(stdout)
