from __future__ import annotations

import os
from pathlib import Path


ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ".env"

ENV_KEY_ALIASES = {
    "RAG_MODE": ["RAG_MODE", "rag_mode", "mode"],
    "OPENAI_API_KEY": ["OPENAI_API_KEY", "openai_api"],
    "OPENAI_BASE_URL": ["OPENAI_BASE_URL", "openai_base_url"],
    "OPENAI_CHAT_MODEL": ["OPENAI_CHAT_MODEL", "openai_chat_model"],
    "OPENAI_MEMORY_MODEL": ["OPENAI_MEMORY_MODEL", "openai_memory_model"],
    "OPENAI_QUERY_REWRITE_MODEL": ["OPENAI_QUERY_REWRITE_MODEL", "openai_query_rewrite_model"],
    "OPENAI_EMBEDDING_MODEL": ["OPENAI_EMBEDDING_MODEL", "openai_embedding_model"],
    "LLM_PROVIDER": ["LLM_PROVIDER", "llm_provider"],
    "LOCAL_LLM_BASE_URL": ["LOCAL_LLM_BASE_URL", "local_llm_base_url"],
    "LOCAL_LLM_API_KEY": ["LOCAL_LLM_API_KEY", "local_llm_api_key"],
    "LOCAL_CHAT_MODEL": ["LOCAL_CHAT_MODEL", "local_chat_model"],
    "LOCAL_MEMORY_MODEL": ["LOCAL_MEMORY_MODEL", "local_memory_model"],
    "LOCAL_QUERY_REWRITE_MODEL": ["LOCAL_QUERY_REWRITE_MODEL", "local_query_rewrite_model"],
    "LOCAL_EMBEDDING_PROVIDER": ["LOCAL_EMBEDDING_PROVIDER", "local_embedding_provider"],
    "LOCAL_EMBEDDING_MODEL": ["LOCAL_EMBEDDING_MODEL", "local_embedding_model"],
    "VECTOR_DIR": ["VECTOR_DIR", "vector_dir"],
    "CHAT_MODEL": ["CHAT_MODEL", "chat_model"],
    "MEMORY_MODEL": ["MEMORY_MODEL", "memory_model"],
    "QUERY_REWRITE_MODEL": ["QUERY_REWRITE_MODEL", "query_rewrite_model"],
    "EMBEDDING_PROVIDER": ["EMBEDDING_PROVIDER", "embedding_provider"],
    "EMBEDDING_MODEL": ["EMBEDDING_MODEL", "embedding_model"],
    "LOCAL_EMBEDDING_BASE_URL": ["LOCAL_EMBEDDING_BASE_URL", "local_embedding_base_url"],
    "LOCAL_EMBEDDING_API_KEY": ["LOCAL_EMBEDDING_API_KEY", "local_embedding_api_key"],
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
