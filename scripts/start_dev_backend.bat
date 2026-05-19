@echo off
cd /d C:\Users\Admin\Desktop\Law-RAG
set RAG_MODE=openai
set EMBEDDING_PROVIDER=openai
set EMBEDDING_MODEL=text-embedding-3-small
.venv\Scripts\python.exe scripts\dev_backend_runner.py > output\backend.bat.log 2>&1
