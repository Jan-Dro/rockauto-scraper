"""
config.py — Load and expose typed application configuration from config.yaml.

Configuration values that are secrets (e.g. Discord webhook URL) are resolved
from environment variables via ${VAR_NAME} syntax inside config.yaml.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import yaml
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class VehicleConfig(BaseModel):
    year_range: str = "2009-2020"
    make: str = "Nissan"
    model: str = "370Z"
    brake_package: str = "Sport Akebono"


class RockAutoConfig(BaseModel):
    source_mode: str = "rss"  # "rss" | "html"
    rss_url: str = ""
    page_url: str = ""
    request_timeout: int = 15
    user_agent: str = "Mozilla/5.0 rockauto-closeout-watcher"


class MonitorConfig(BaseModel):
    interval_minutes: int = 30
    dry_run: bool = False
    debug_matching: bool = True


class MatchingConfig(BaseModel):
    required_keywords: list[str] = Field(default_factory=lambda: ["caliper"])
    front_keywords: list[str] = Field(default_factory=lambda: ["front"])
    right_keywords: list[str] = Field(
        default_factory=lambda: [
            "right",
            "front right",
            "right front",
            "passenger",
            "passenger side",
            "rh",
        ]
    )
    sport_keywords: list[str] = Field(
        default_factory=lambda: [
            "sport",
            "akebono",
            "4 piston",
            "4-piston",
            "with sport brakes",
            "w/ sport brakes",
        ]
    )
    reject_keywords: list[str] = Field(
        default_factory=lambda: [
            "left",
            "front left",
            "left front",
            "driver",
            "driver side",
            "lh",
            "rear",
            "rear left",
            "rear right",
        ]
    )


class DiscordConfig(BaseModel):
    webhook_url: str = ""


class StorageConfig(BaseModel):
    seen_items_file: str = "data/seen_items.json"


class AppConfig(BaseModel):
    vehicle: VehicleConfig = Field(default_factory=VehicleConfig)
    rockauto: RockAutoConfig = Field(default_factory=RockAutoConfig)
    monitor: MonitorConfig = Field(default_factory=MonitorConfig)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} placeholders with actual environment variables."""

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        resolved = os.environ.get(var_name, "")
        if not resolved:
            # Leave placeholder intact so callers can detect misconfiguration
            return match.group(0)
        return resolved

    return _ENV_VAR_RE.sub(replacer, value)


def _resolve_all_strings(obj: object) -> object:
    """Recursively resolve ${ENV_VAR} placeholders in dicts/lists/strings."""
    if isinstance(obj, dict):
        return {k: _resolve_all_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_all_strings(item) for item in obj]
    if isinstance(obj, str):
        return _resolve_env_vars(obj)
    return obj


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config(path: Optional[Path] = None) -> AppConfig:
    """Load AppConfig from a YAML file, resolving env-var placeholders."""
    config_path = path or _DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    resolved = _resolve_all_strings(raw)
    return AppConfig.model_validate(resolved)
