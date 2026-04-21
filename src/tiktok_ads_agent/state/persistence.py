"""State persistence helpers.

All state lives under ``.state/`` at the repo root and is committed
back to ``main`` by the cadence workflows. The layout mirrors the
Meta-ads-agent pattern:

    .state/
        baselines.json              # CPA baselines per adgroup
        optimization_log.json       # every pause/activate decision
        creative_registry.json      # user-provided creative metadata
        daily_snapshots/YYYY-MM-DD.json
        weekly_snapshots/YYYY-WNN.json
        monthly_snapshots/YYYY-MM.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tiktok_ads_agent.models.schemas import Snapshot

STATE_ROOT = Path(".state")
DAILY_DIR = STATE_ROOT / "daily_snapshots"
WEEKLY_DIR = STATE_ROOT / "weekly_snapshots"
MONTHLY_DIR = STATE_ROOT / "monthly_snapshots"

BASELINES_PATH = STATE_ROOT / "baselines.json"
OPT_LOG_PATH = STATE_ROOT / "optimization_log.json"
CREATIVE_REGISTRY_PATH = STATE_ROOT / "creative_registry.json"


def init_state() -> list[Path]:
    """Ensure all directories + cumulative files exist. Returns created paths."""

    created: list[Path] = []
    for directory in (STATE_ROOT, DAILY_DIR, WEEKLY_DIR, MONTHLY_DIR):
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(directory)
            (directory / ".gitkeep").touch()

    for path, default in (
        (BASELINES_PATH, {}),
        (OPT_LOG_PATH, []),
        (CREATIVE_REGISTRY_PATH, {}),
    ):
        if not path.exists():
            path.write_text(json.dumps(default, indent=2) + "\n")
            created.append(path)

    return created


def _snapshot_dir(cadence: str) -> Path:
    match cadence:
        case "daily":
            return DAILY_DIR
        case "weekly":
            return WEEKLY_DIR
        case "monthly":
            return MONTHLY_DIR
        case _:
            raise ValueError(f"unknown cadence: {cadence}")


def snapshot_path(cadence: str, period_id: str) -> Path:
    """Resolve the on-disk path for a snapshot without writing it."""

    return _snapshot_dir(cadence) / f"{period_id}.json"


def save_snapshot(snapshot: Snapshot) -> Path:
    """Write ``snapshot`` as pretty JSON, creating parent dirs if needed."""

    path = snapshot_path(snapshot.cadence, snapshot.period_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.model_dump_json(indent=2) + "\n")
    return path


def load_snapshot(cadence: str, period_id: str) -> Snapshot | None:
    """Load a previously committed snapshot, or ``None`` if missing."""

    path = snapshot_path(cadence, period_id)
    if not path.exists():
        return None
    return Snapshot.model_validate_json(path.read_text())


def load_json(path: Path, default: Any) -> Any:
    """Read a cumulative JSON file, falling back to ``default`` if missing."""

    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: Path, data: Any) -> None:
    """Overwrite ``path`` with ``data`` serialised as pretty JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
