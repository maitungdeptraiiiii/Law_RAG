from __future__ import annotations

import os

from openai import OpenAI

from .env_loader import load_project_env
from .runtime_config import embedding_model, embedding_provider


load_project_env()


DEFAULT_EMBEDDING_MODEL = embedding_model()


def embed_texts(texts: list[str], *, model: str | None = None, provider: str | None = None) -> list[list[float]]:
    active_provider = (provider or embedding_provider()).strip().casefold()
    active_model = embedding_model(model)

    if active_provider == "openai":
        return embed_texts_openai(texts, model=active_model)
    if active_provider == "local-openai":
        return embed_texts_openai_compatible(texts, model=active_model)
    if active_provider in {"sentence-transformers", "huggingface"}:
        return embed_texts_sentence_transformers(texts, model=active_model)

    raise RuntimeError(
        "EMBEDDING_PROVIDER khong hop le. "
        "Dung mot trong: openai, local-openai, sentence-transformers."
    )


def embed_query(text: str, *, model: str | None = None, provider: str | None = None) -> list[float]:
    vectors = embed_texts([text], model=model, provider=provider)
    if not vectors:
        raise RuntimeError("Khong tao duoc embedding cho query.")
    return vectors[0]


def embed_texts_openai(texts: list[str], *, model: str) -> list[list[float]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Thieu OPENAI_API_KEY khi EMBEDDING_PROVIDER=openai.")

    base_url = os.getenv("OPENAI_BASE_URL")
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def embed_texts_openai_compatible(texts: list[str], *, model: str) -> list[list[float]]:
    base_url = os.getenv("LOCAL_EMBEDDING_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    if not base_url:
        raise RuntimeError("Thieu LOCAL_EMBEDDING_BASE_URL khi EMBEDDING_PROVIDER=local-openai.")

    client = OpenAI(
        api_key=os.getenv("LOCAL_EMBEDDING_API_KEY") or os.getenv("LOCAL_LLM_API_KEY") or "local",
        base_url=base_url,
    )
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def embed_texts_sentence_transformers(texts: list[str], *, model: str) -> list[list[float]]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Can cai sentence-transformers de dung EMBEDDING_PROVIDER=sentence-transformers. "
            "Chay: pip install sentence-transformers"
        ) from exc

    encoder = SentenceTransformer(model)
    vectors = encoder.encode(texts, normalize_embeddings=False)
    return [vector.astype("float32").tolist() for vector in vectors]
