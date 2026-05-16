from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from .env_loader import load_project_env
from .runtime_config import llm_provider, local_llm_base_url


load_project_env()


JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _local_extra_body() -> dict[str, str] | None:
    if llm_provider() != "local":
        return None
    return {"keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "2h")}


def get_chat_client() -> OpenAI:
    provider = llm_provider()

    if provider == "local":
        base_url = local_llm_base_url() or os.getenv("OPENAI_BASE_URL")
        if not base_url:
            raise RuntimeError("Thieu LOCAL_LLM_BASE_URL khi LLM_PROVIDER=local.")
        return OpenAI(
            api_key=os.getenv("LOCAL_LLM_API_KEY") or "local",
            base_url=base_url,
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Thieu OPENAI_API_KEY trong environment.")

    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def chat_completion_text(
    client: OpenAI,
    *,
    model: str,
    temperature: float,
    messages: list[dict[str, str]],
) -> str:
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=messages,
        extra_body=_local_extra_body(),
    )
    return response.choices[0].message.content or ""


def chat_completion_json(
    client: OpenAI,
    *,
    model: str,
    temperature: float,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=messages,
            extra_body=_local_extra_body(),
        )
        content = response.choices[0].message.content or "{}"
    except Exception as exc:
        if "response_format" not in str(exc):
            raise
        # Some local OpenAI-compatible servers do not implement response_format.
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                *messages,
                {
                    "role": "user",
                    "content": "Chi tra ve mot JSON object hop le, khong them markdown hay giai thich.",
                },
            ],
            extra_body=_local_extra_body(),
        )
        content = response.choices[0].message.content or "{}"

    return parse_json_object(content)


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        match = JSON_OBJECT_RE.search(content)
        if not match:
            return {}
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
