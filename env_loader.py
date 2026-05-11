from __future__ import annotations

import os
from pathlib import Path


ENV_FILE_PATH = Path(__file__).with_name("env.txt")

ENV_KEY_ALIASES = {
    "OPENAI_API_KEY": ["OPENAI_API_KEY", "openai_api"],
    "MONGODB_ATLAS_URI": ["MONGODB_ATLAS_URI", "atlas-uri", "atlas_uri"],
    "MONGODB_ATLAS_DB": ["MONGODB_ATLAS_DB", "atlas-db", "atlas_db"],
    "MONGODB_ATLAS_COLLECTION": ["MONGODB_ATLAS_COLLECTION", "atlas-collection", "atlas_collection"],
    "MONGODB_ATLAS_VECTOR_INDEX": ["MONGODB_ATLAS_VECTOR_INDEX", "atlas-vector-index", "atlas_vector_index"],
}


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if not key:
        return None
    return key, value


def load_project_env(env_file: Path | None = None) -> None:
    path = env_file or ENV_FILE_PATH
    if not path.exists():
        return

    loaded_values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        key, value = parsed
        loaded_values[key] = value

    for target_key, aliases in ENV_KEY_ALIASES.items():
        for alias in aliases:
            value = loaded_values.get(alias)
            if value:
                os.environ.setdefault(target_key, value)
                break


load_project_env()