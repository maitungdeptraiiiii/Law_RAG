from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "output" / "dev_backend_runtime.log"


def main() -> None:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    from law_rag.core.env_loader import load_project_env

    load_project_env()
    os.environ.setdefault("RAG_MODE", "openai")
    os.environ.setdefault("EMBEDDING_PROVIDER", "openai")
    os.environ.setdefault("EMBEDDING_MODEL", "text-embedding-3-small")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write("starting backend\n")
        uvicorn.run("law_rag.api.server:app", host="127.0.0.1", port=8000, log_level="info")
    except Exception:
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
