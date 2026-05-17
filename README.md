# Law RAG

Law RAG là hệ thống hỏi đáp pháp luật Việt Nam dùng FastAPI, Next.js và retrieval kết hợp BM25 + vector search. Dự án dùng corpus luật đã crawl sẵn, hỗ trợ upload tài liệu riêng, OCR, chunk văn bản và embedding vào FAISS local hoặc MongoDB Atlas.

Backend có thể chạy bằng OpenAI API hoặc model local OpenAI-compatible như Ollama/LM Studio. Frontend có trang chat, trang admin, cấu hình runtime, upload tài liệu và xem nguồn tham khảo.

## Kiến Trúc

```text
Law-RAG/
|- law_rag/                 # Backend Python/FastAPI
|  |- api/server.py         # API server
|  |- app/ask_law.py        # Luồng hỏi đáp RAG
|  |- core/                 # Env loader, runtime config, LLM/embedding client
|  |- crawl/                # Crawl, kiểm tra framework, chunk luật
|  |- retrieval/            # BM25, FAISS, Atlas, hybrid retrieval
|  `- upload_pipeline.py    # Upload, OCR, chunk, embedding tài liệu riêng
|- law-rag-frontend/        # Frontend Next.js
|- docker/                  # Dockerfile backend/frontend và docker compose
|- output/                  # Corpus, chunks, indexes, sessions, uploads
|- requirements.txt
|- requirements-local.txt
`- .env                     # Cấu hình local, không commit lên Git
```

## Tính Năng Chính

- Chat hỏi đáp pháp luật bằng tiếng Việt, có trích dẫn nguồn.
- Hybrid retrieval: BM25 + vector FAISS.
- Có thể debug bằng BM25-only, vector-only hoặc hybrid.
- Upload PDF/DOCX/image, OCR bằng Tesseract/PaddleOCR, review text rồi đưa vào retrieval.
- Hỗ trợ tài liệu private/public cho upload.
- Hỗ trợ OpenAI API, local LLM OpenAI-compatible, SentenceTransformers local embedding.
- Có Dockerfile và Docker Compose để chạy cả backend/frontend.

## Yêu Cầu

- Python 3.11.
- Node.js 22.
- `pnpm`.
- Tesseract OCR nếu cần xử lý PDF scan hoặc ảnh.
- Docker Desktop nếu chạy bằng Docker.
- OpenAI API key nếu chạy chế độ OpenAI.
- Ollama/LM Studio/vLLM nếu chạy chế độ local LLM.

Trên Windows, Tesseract thường đặt ở:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

## Cấu Hình Môi Trường

Backend tự đọc file `.env` ở thư mục gốc. File này chứa secret thật nên không commit lên Git.

Ví dụ chạy bằng OpenAI:

```env
RAG_MODE=openai
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_CHAT_MODEL=gpt-5.4-mini
OPENAI_MEMORY_MODEL=gpt-5.4-mini
OPENAI_QUERY_REWRITE_MODEL=gpt-5.4-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Ví dụ chạy local:

```env
RAG_MODE=local
LLM_PROVIDER=local
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_API_KEY=local
LOCAL_CHAT_MODEL=qwen2.5:7b-instruct
LOCAL_MEMORY_MODEL=qwen2.5:7b-instruct
LOCAL_QUERY_REWRITE_MODEL=qwen2.5:1.5b-instruct
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=intfloat/multilingual-e5-base
LOCAL_EMBEDDING_PROVIDER=sentence-transformers
LOCAL_EMBEDDING_MODEL=intfloat/multilingual-e5-base
```

Frontend local đọc `law-rag-frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Khi dùng bản web trên domain, frontend Vercel dùng:

```env
NEXT_PUBLIC_API_URL=https://api.lawrag.online
```

## Chạy Local

Chạy backend:

```powershell
cd C:\Users\Admin\Desktop\Law-RAG
.\.venv\Scripts\python.exe -m uvicorn law_rag.api.server:app --reload --host 127.0.0.1 --port 8000
```

Nếu chưa có virtual environment:

```powershell
cd C:\Users\Admin\Desktop\Law-RAG
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-local.txt
```

Chạy frontend:

```powershell
cd C:\Users\Admin\Desktop\Law-RAG\law-rag-frontend
pnpm.cmd install
pnpm.cmd dev
```

Mở frontend:

```text
http://localhost:3000
```

Nếu port `3000` bận, Next.js sẽ tự chuyển sang port khác, thường là `3001`.

Kiểm tra backend:

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/runtime/status
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## Chạy Bằng Docker

Chạy từ thư mục gốc:

```powershell
cd C:\Users\Admin\Desktop\Law-RAG
docker compose -f docker/docker-compose.yml up -d
```

Mở:

```text
http://localhost:3000
```

Kiểm tra:

```powershell
curl http://127.0.0.1:8000/health
```

Dừng:

```powershell
docker compose -f docker/docker-compose.yml down
```

Nếu port mặc định bị chiếm:

```powershell
$env:BACKEND_PORT=8001
$env:FRONTEND_PORT=3001
docker compose -f docker/docker-compose.yml up -d
```

Khi đó mở:

```text
http://localhost:3001
```

Build lại image:

```powershell
docker compose -f docker/docker-compose.yml build
```

Lưu ý Docker:

- Backend mount `../output:/app/output`, nên dữ liệu runtime vẫn nằm trên máy host.
- Nếu backend trong container cần gọi Ollama/LM Studio trên máy host, dùng `LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1`.
- `.dockerignore` loại uploads, sessions, eval output và private runtime data để tránh đóng gói dữ liệu cá nhân vào image.

## Chạy Bản Web Với Domain `lawrag.online`

Bản web hiện tại không host backend trên Render. Frontend chạy trên Vercel, còn backend chạy trực tiếp trên máy cá nhân và public qua Cloudflare Tunnel.

Sơ đồ đang dùng:

```text
https://www.lawrag.online/chat  -> frontend trên Vercel
https://api.lawrag.online       -> Cloudflare Tunnel
Cloudflare Tunnel               -> backend FastAPI trên máy cá nhân
```

Điều này có nghĩa là domain chỉ hoạt động đầy đủ khi máy cá nhân đang bật, backend đang chạy và Cloudflare Tunnel đang chạy. Nếu tắt máy hoặc dừng tunnel, frontend vẫn mở được nhưng chat sẽ không gọi được API.

### Khởi Động Web Public

Terminal 1: chạy backend.

```powershell
cd C:\Users\Admin\Desktop\Law-RAG
.\.venv\Scripts\python.exe -m uvicorn law_rag.api.server:app --host 127.0.0.1 --port 8000
```

Terminal 2: chạy Cloudflare Tunnel.

```powershell
cloudflared tunnel run lawrag-api
```

Kiểm tra:

```powershell
curl http://127.0.0.1:8000/health
curl https://api.lawrag.online/health
```

Sau đó mở:

```text
https://www.lawrag.online/chat
```

### Dừng Web Public

Dừng backend hoặc tunnel bằng `Ctrl + C` ở terminal đang chạy.

Nếu `cloudflared` đang chạy nền:

```powershell
Get-Process cloudflared
Stop-Process -Name cloudflared -Force
```

### DNS Route Cloudflare

Lệnh này chỉ cần chạy khi cấu hình DNS route lần đầu hoặc đổi tunnel/domain:

```powershell
cloudflared tunnel route dns lawrag-api api.lawrag.online
```

Không cần chạy lại lệnh này mỗi lần bật máy. Mỗi lần muốn host lại chỉ cần chạy backend và:

```powershell
cloudflared tunnel run lawrag-api
```

## Runtime Và API Key

Trong trang Admin có thể chuyển runtime giữa `Local` và `OpenAI API`.

Khi chọn `OpenAI API`, có thể nhập OpenAI API key ở frontend. Backend sẽ ghi key vào `.env` để các lần chạy sau dùng lại. Key không được trả ngược lại frontend.

Khi chọn `Local`, backend tự chuyển embedding về:

```env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=intfloat/multilingual-e5-base
```

Trạng thái runtime có thể kiểm tra tại:

```powershell
curl http://127.0.0.1:8000/api/runtime/status
```

## Upload, OCR Và Embedding

Luồng upload:

1. `POST /api/uploads` lưu file vào `output/uploads`.
2. Backend OCR/trích text và lưu metadata upload.
3. Người dùng review text.
4. `PATCH /api/uploads/{upload_id}` lưu tài liệu đã xử lý.
5. `POST /api/uploads/{upload_id}/embed` build embedding riêng.

Upload private được lưu tại:

```text
output/upload_documents/private/<upload_id>/
|- chunks.json
|- chunks.jsonl
|- embeddings/api/
`- embeddings/local/
```

Các thư mục upload, session và private runtime data không nên commit lên Git.

## Pipeline Dữ Liệu

Crawl:

```powershell
python -m law_rag.crawl.crawl_laws --docx luat.docx --output output/laws --clean
```

Kiểm tra framework chunk:

```powershell
python -m law_rag.crawl.chunk_framework_check --input output/laws --json-out output/chunk_framework_report.json
```

Chunk:

```powershell
python -m law_rag.crawl.chunk_laws --input output/laws --output-dir output/chunks
```

Build BM25:

```powershell
python -m law_rag.retrieval.retrieve_chunks build --chunks output/chunks/all_chunks.jsonl --output output/chunks/retrieval/bm25_index.json
```

Build FAISS OpenAI:

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector-openai --backend faiss
```

Build FAISS local:

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector-local --backend faiss
```

Build Atlas:

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend atlas
```

## Kiểm Tra

Backend:

```powershell
python -m compileall law_rag
python -c "import law_rag.api.server; print('import ok')"
```

Frontend:

```powershell
cd law-rag-frontend
pnpm.cmd lint
pnpm.cmd build
```

Docker smoke test:

```powershell
$env:BACKEND_PORT=18000
$env:FRONTEND_PORT=13000
docker compose -f docker/docker-compose.yml up -d
curl http://127.0.0.1:18000/health
curl http://127.0.0.1:13000/
docker compose -f docker/docker-compose.yml down
```

## API Chính

- `GET /health`
- `GET /api/runtime/status`
- `POST /api/runtime/config`
- `POST /api/chat/ask`
- `POST /api/chat/ask/stream`
- `GET /api/sessions`
- `GET /api/documents`
- `GET /api/admin/corpus-status`
- `POST /api/admin/jobs/crawl`
- `POST /api/admin/jobs/chunk`
- `POST /api/admin/jobs/index-bm25`
- `POST /api/admin/jobs/index-vector`
- `POST /api/admin/debug/query`
- `POST /api/uploads`
- `PATCH /api/uploads/{upload_id}`
- `POST /api/uploads/{upload_id}/embed`
- `GET /api/uploads/processed`

## Ghi Chú Vận Hành

- Không commit `.env`, uploads, sessions hoặc private upload data.
- `.gitignore` đã ignore các file runtime nhạy cảm, nhưng nếu file đã từng được Git track thì cần `git rm --cached` để gỡ khỏi index.
- Nếu dùng OpenAI mode mà thiếu `OPENAI_API_KEY`, chat/embedding OpenAI sẽ lỗi nhưng health check vẫn chạy.
- Nếu dùng local mode, cần chạy Ollama/LM Studio hoặc endpoint OpenAI-compatible tương ứng.
- Nếu dùng SentenceTransformers lần đầu, model local embedding có thể mất thời gian tải từ Hugging Face.
- `https://www.lawrag.online/chat` phụ thuộc vào backend đang chạy trên máy cá nhân qua Cloudflare Tunnel.
