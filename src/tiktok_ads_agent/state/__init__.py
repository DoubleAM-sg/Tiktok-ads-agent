"""Persistent state manager for .state/ JSON files."""

from tiktok_ads_agent.state.persistence import (
    BASELINES_PATH,
    CREATIVE_REGISTRY_PATH,
    DAILY_DIR,
    MONTHLY_DIR,
    OPT_LOG_PATH,
    STATE_ROOT,
    WEEKLY_DIR,
    init_state,
    load_json,
    load_snapshot,
    save_json,
    save_snapshot,
    snapshot_path,
)

__all__ = [
    "BASELINES_PATH",
    "CREATIVE_REGISTRY_PATH",
    "DAILY_DIR",
    "MONTHLY_DIR",
    "OPT_LOG_PATH",
    "STATE_ROOT",
    "WEEKLY_DIR",
    "init_state",
    "load_json",
    "load_snapshot",
    "save_json",
    "save_snapshot",
    "snapshot_path",
]
