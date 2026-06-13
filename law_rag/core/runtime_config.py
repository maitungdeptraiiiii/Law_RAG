from __future__ import annotations

import os

from .env_loader import load_project_env


load_project_env()


OPENAI_DEFAULT_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5.4-mini")
OPENAI_DEFAULT_MEMORY_MODEL = os.getenv("OPENAI_MEMORY_MODEL", OPENAI_DEFAULT_CHAT_MODEL)
OPENAI_DEFAULT_QUERY_REWRITE_MODEL = os.getenv("OPENAI_QUERY_REWRITE_MODEL", OPENAI_DEFAULT_CHAT_MODEL)
OPENAI_DEFAULT_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

LOCAL_DEFAULT_CHAT_MODEL = os.getenv("LOCAL_CHAT_MODEL", "qwen2.5:7b-instruct")
LOCAL_DEFAULT_MEMORY_MODEL = os.getenv("LOCAL_MEMORY_MODEL", LOCAL_DEFAULT_CHAT_MODEL)
LOCAL_DEFAULT_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
LOCAL_DEFAULT_EMBEDDING_PROVIDER = os.getenv("LOCAL_EMBEDDING_PROVIDER", "sentence-transformers")
LOCAL_DEFAULT_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "intfloat/multilingual-e5-base")


def runtime_mode() -> str:
    mode = os.getenv("RAG_MODE", "openai").strip().casefold()
    if mode not in {"openai", "local"}:
        raise RuntimeError("RAG_MODE khong hop le. Dung mot trong: openai, local.")
    return mode


def llm_provider() -> str:
    explicit_provider = os.getenv("LLM_PROVIDER")
    if explicit_provider:
        return explicit_provider.strip().casefold()
    return "local" if runtime_mode() == "local" else "openai"


def chat_model() -> str:
    explicit_model = os.getenv("CHAT_MODEL")
    if explicit_model:
        return explicit_model
    return LOCAL_DEFAULT_CHAT_MODEL if runtime_mode() == "local" else OPENAI_DEFAULT_CHAT_MODEL


def memory_model() -> str:
    explicit_model = os.getenv("MEMORY_MODEL")
    if explicit_model:
        return explicit_model
    return LOCAL_DEFAULT_MEMORY_MODEL if runtime_mode() == "local" else OPENAI_DEFAULT_MEMORY_MODEL


def query_rewrite_model() -> str:
    if runtime_mode() == "local":
        local_model = os.getenv("LOCAL_QUERY_REWRITE_MODEL")
        if local_model:
            return local_model
        explicit_model = os.getenv("QUERY_REWRITE_MODEL")
        if explicit_model:
            return explicit_model
        return os.getenv("LOCAL_CHAT_MODEL") or LOCAL_DEFAULT_CHAT_MODEL

    explicit_model = os.getenv("QUERY_REWRITE_MODEL")
    if explicit_model:
        return explicit_model
    return OPENAI_DEFAULT_QUERY_REWRITE_MODEL


def local_llm_base_url() -> str:
    return os.getenv("LOCAL_LLM_BASE_URL") or LOCAL_DEFAULT_LLM_BASE_URL


def embedding_provider() -> str:
    explicit_provider = os.getenv("EMBEDDING_PROVIDER")
    if explicit_provider:
        return explicit_provider.strip().casefold()
    return LOCAL_DEFAULT_EMBEDDING_PROVIDER if runtime_mode() == "local" else "openai"


def embedding_model(default: str | None = None) -> str:
    explicit_model = os.getenv("EMBEDDING_MODEL")
    if explicit_model:
        return explicit_model
    if default:
        return default
    return LOCAL_DEFAULT_EMBEDDING_MODEL if runtime_mode() == "local" else OPENAI_DEFAULT_EMBEDDING_MODEL


def default_vector_dir() -> str:
    explicit_dir = os.getenv("VECTOR_DIR")
    if explicit_dir:
        return explicit_dir
    corpus_name = os.getenv("CORPUS_NAME", "vbpl_business_guidance_mvp")
    suffix = "local" if runtime_mode() == "local" else "openai"
    return f"output/{corpus_name}/retrieval/vector-{suffix}"
