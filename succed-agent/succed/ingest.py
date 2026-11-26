"""Import companies from CSV/JSON (partner listing feeds, broker exports, registry pulls)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import CompanyProfile

BOOL_FIELDS = {"second_tier_management"}
LIST_FIELDS = {"improvement_levers"}
NUM_FIELDS = {f for f, i in CompanyProfile.model_fields.items()
              if "float" in str(i.annotation) or "int" in str(i.annotation)}


def _parse(row: dict[str, str]) -> dict:
    out: dict = {"flags": {}}
    for k, v in row.items():
        if v is None or v == "":
            continue
        if k.startswith("flag_"):
            out["flags"][k[5:]] = v.strip().lower() in ("1", "true", "yes", "si", "sí")
        elif k in BOOL_FIELDS:
            out[k] = v.strip().lower() in ("1", "true", "yes", "si", "sí")
        elif k in LIST_FIELDS:
            out[k] = [x.strip() for x in v.split("|") if x.strip()]
        elif k in NUM_FIELDS:
            out[k] = float(v) if "." in v else int(v) if v.lstrip("-").isdigit() else float(v)
        else:
            out[k] = v
    return out


def load_csv(path: str | Path) -> list[CompanyProfile]:
    with open(path, newline="", encoding="utf-8") as f:
        return [CompanyProfile(**_parse(r)) for r in csv.DictReader(f)]


def load_json(path: str | Path) -> list[CompanyProfile]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [CompanyProfile(**d) for d in (data if isinstance(data, list) else [data])]


def load_any(path: str | Path) -> list[CompanyProfile]:
    return load_csv(path) if str(path).lower().endswith(".csv") else load_json(path)


def dedupe(companies: Iterable[CompanyProfile]) -> list[CompanyProfile]:
    seen, out = set(), []
    for c in companies:
        key = (c.alias.lower(), c.country)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out
