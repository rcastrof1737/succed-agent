"""Load versioned scoring configs. Weights live in YAML so partners can tune them without code changes."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


class ConfigError(ValueError):
    pass


@lru_cache(maxsize=32)
def load(name: str) -> dict[str, Any]:
    """load('scoring/searcher_v1') -> dict. Validates weights sum to 100."""
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise ConfigError(f"Config not found: {path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    _validate(name, cfg)
    return cfg


def _validate(name: str, cfg: dict[str, Any]) -> None:
    if "dimensions" in cfg:
        total = sum(d["weight"] for d in cfg["dimensions"].values())
        if abs(total - 100) > 1e-6:
            raise ConfigError(f"{name}: dimension weights sum to {total}, expected 100")
        protected = set(cfg.get("protected_attributes", []))
        leaked = protected & set(cfg["dimensions"])
        if leaked:
            raise ConfigError(f"{name}: protected attributes used as dimensions: {sorted(leaked)}")
        for dname, d in cfg["dimensions"].items():
            parts = d.get("parts")
            if parts and abs(sum(p["share"] for p in parts) - 1) > 1e-6:
                raise ConfigError(f"{name}.{dname}: part shares must sum to 1")
    if "components" in cfg:
        total = sum(cfg["components"].values())
        if abs(total - 100) > 1e-6:
            raise ConfigError(f"{name}: component weights sum to {total}, expected 100")


def investor(investor_id: str) -> dict[str, Any]:
    return load(f"investors/{investor_id.replace('-', '_')}")
