from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SESSION_DIR = Path("output/sessions")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_session_id(session_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", session_id).strip("._")
    if not cleaned:
        raise ValueError("session_id không hợp lệ.")
    return cleaned


def resolve_session_path(session_id: str, session_dir: Path | None = None) -> Path:
    active_dir = session_dir or DEFAULT_SESSION_DIR
    active_dir.mkdir(parents=True, exist_ok=True)
    return active_dir / f"{sanitize_session_id(session_id)}.json"


def create_empty_session(session_id: str) -> dict[str, Any]:
    return {
        "session_id": sanitize_session_id(session_id),
        "title": "",
        "history": [],
        "facts": {},
        "case_summary": "",
        "pending_follow_up": None,
        "last_retrieval_query": "",
        "archived": False,
        "pinned": False,
        "updated_at": utc_now_iso(),
    }


def load_session(session_id: str, session_dir: Path | None = None) -> dict[str, Any]:
    path = resolve_session_path(session_id, session_dir)
    if not path.exists():
        return create_empty_session(session_id)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("session_id", sanitize_session_id(session_id))
    payload.setdefault("title", "")
    payload.setdefault("history", [])
    payload.setdefault("facts", {})
    payload.setdefault("case_summary", "")
    payload.setdefault("pending_follow_up", None)
    payload.setdefault("last_retrieval_query", "")
    payload.setdefault("archived", False)
    payload.setdefault("pinned", False)
    payload.setdefault("updated_at", utc_now_iso())
    return payload


def save_session(session: dict[str, Any], session_dir: Path | None = None, touch_updated_at: bool = True) -> Path:
    path = resolve_session_path(session["session_id"], session_dir)
    if touch_updated_at:
        session["updated_at"] = utc_now_iso()
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def append_history(session: dict[str, Any], role: str, content: str) -> None:
    session.setdefault("history", []).append(
        {
            "id": f"msg-{uuid.uuid4().hex[:12]}",
            "role": role,
            "content": content.strip(),
            "timestamp": utc_now_iso(),
        }
    )


def recent_history(session: dict[str, Any], max_messages: int = 6) -> list[dict[str, str]]:
    history = session.get("history", [])
    return history[-max_messages:]


def format_recent_history(session: dict[str, Any], max_messages: int = 6) -> str:
    items = recent_history(session, max_messages=max_messages)
    if not items:
        return "Chưa có hội thoại trước đó."

    blocks: list[str] = []
    for item in items:
        label = "Người dùng" if item["role"] == "user" else "Trợ lý"
        blocks.append(f"- {label}: {item['content']}")
    return "\n".join(blocks)


def format_case_state(session: dict[str, Any]) -> str:
    facts = session.get("facts", {})
    summary = str(session.get("case_summary", "")).strip()
    if not facts and not summary:
        return "Chưa có tình tiết vụ việc đã lưu."

    lines: list[str] = []
    if summary:
        lines.append(f"Tóm tắt: {summary}")
    if facts:
        lines.append("Facts:")
        for key in sorted(facts):
            value = facts[key]
            if value in (None, "", [], {}):
                continue
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)