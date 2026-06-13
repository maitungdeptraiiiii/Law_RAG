import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from law_rag.core.env_loader import load_project_env
load_project_env()

from openai import OpenAI
import traceback

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))
model = os.getenv("MEMORY_MODEL") or os.getenv("CHAT_MODEL", "gpt-5.4-mini")
print("Memory model:", model)

# Simulate update_case_memory
from law_rag.app.ask_law import MEMORY_UPDATE_SYSTEM_PROMPT
from law_rag.core.llm_client import chat_completion_json

try:
    result = chat_completion_json(
        client,
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": MEMORY_UPDATE_SYSTEM_PROMPT},
            {"role": "user", "content": "Hội thoại gần đây:\n(trống)\n\nTình tiết đã biết:\n(trống)\n\nCâu hỏi mới nhất của người dùng:\nđánh người bị tội gì\n"},
        ],
    )
    print("Memory update OK:", result)
except Exception as e:
    print("Memory update ERROR:", type(e).__name__, str(e)[:600])
    traceback.print_exc()
