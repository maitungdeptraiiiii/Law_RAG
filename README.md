# Law RAG

Law RAG là hệ thống hỏi đáp pháp luật Việt Nam dùng FastAPI, Next.js và retrieval kết hợp BM25 + vector search. Dự án hỗ trợ dữ liệu luật có sẵn, upload tài liệu riêng, OCR PDF scan, chunk văn bản và embedding vào FAISS local hoặc MongoDB Atlas.

## Kiến trúc

```text
Law-RAG/
|- law_rag/                 # Backend Python/FastAPI
|  |- api/server.py         # API server
|  |- app/ask_law.py        # Luồng hỏi đáp RAG
|  |- core/                 # Env loader, LLM/embedding config
|  |- crawl/                # Crawl, kiểm tra framework, chunk luật
|  |- retrieval/            # BM25, FAISS, Atlas, hybrid retrieval
|  `- upload_pipeline.py    # Lưu upload, chunk, build embedding riêng
|- law-rag-frontend/        # Frontend Next.js
|- docker/                  # Dockerfile backend/frontend và compose
|- output/                  # Dữ liệu luật, chunks, indexes, sessions, uploads
|- requirements.txt
|- requirements-local.txt
`- .env                     # Cấu hình backend/Docker Compose local
```

## Tính năng chính

- Chat hỏi đáp pháp luật bằng tiếng Việt, có trích dẫn nguồn chunk.
- Hybrid retrieval: BM25 + vector FAISS, có lựa chọn vector-only hoặc BM25-only khi debug.
- Quản lý corpus và pipeline crawl/chunk/index trong trang admin.
- Upload PDF/DOCX/image, OCR bằng Tesseract/PaddleOCR, review text, lưu tài liệu riêng.
- Embed upload vào FAISS riêng theo workspace private/public.
- Hỗ trợ OpenAI, local OpenAI-compatible LLM, SentenceTransformers local embedding và MongoDB Atlas Vector Search.
- Docker image sẵn trên Docker Hub:
  - `maitung123/law-rag-backend:latest`
  - `maitung123/law-rag-frontend:latest`

## Yêu cầu

- Python 3.11 khuyến nghị.
- Node.js 22 khuyến nghị cho frontend Next.js 16.
- `pnpm`.
- Tesseract OCR nếu xử lý PDF scan hoặc ảnh. Trên Windows nên có `C:\Program Files\Tesseract-OCR\tesseract.exe` và language data `vie.traineddata`.
- OpenAI API key nếu chạy `RAG_MODE=openai` hoặc `EMBEDDING_PROVIDER=openai`.
- Docker Desktop nếu chạy bằng Docker.

## Cấu hình Backend

Backend tự nạp file `.env` ở thư mục gốc. Các biến quan trọng:

```env
RAG_MODE=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_CHAT_MODEL=gpt-5.4-mini
OPENAI_MEMORY_MODEL=gpt-5.4-mini
OPENAI_QUERY_REWRITE_MODEL=gpt-5.4-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
VECTOR_DIR=output/chunks/retrieval/vector-openai

LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_API_KEY=local
LOCAL_CHAT_MODEL=qwen2.5:7b-instruct
LOCAL_MEMORY_MODEL=qwen2.5:7b-instruct
LOCAL_QUERY_REWRITE_MODEL=qwen2.5:7b-instruct
LOCAL_EMBEDDING_PROVIDER=sentence-transformers
LOCAL_EMBEDDING_MODEL=intfloat/multilingual-e5-base

MONGODB_ATLAS_URI=
MONGODB_ATLAS_DB=law_rag
MONGODB_ATLAS_COLLECTION=legal_chunks
MONGODB_ATLAS_VECTOR_INDEX=legal_chunks_vector_index
```

Nếu chạy local hoàn toàn:

```env
RAG_MODE=local
LLM_PROVIDER=local
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=intfloat/multilingual-e5-base
VECTOR_DIR=output/chunks/retrieval/vector-local
```

Khi đổi embedding provider/model, cần build lại vector index tương ứng.

Vì lý do bảo mật, frontend không cho nhập hoặc thay đổi `OPENAI_API_KEY`. Admin UI chỉ hiển thị backend đã có key hay chưa. Muốn cấu hình key, hãy đặt `OPENAI_API_KEY` trong `.env`, biến môi trường của server, hoặc Docker Compose trước khi khởi động backend.

## Cấu hình Frontend

Tạo `law-rag-frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

## Chạy Dev

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-local.txt
uvicorn law_rag.api.server:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd law-rag-frontend
pnpm install
pnpm dev
```

URL:

- Frontend: `http://localhost:3000`
- Backend health: `http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`

## Docker

Chạy bằng Docker Compose từ thư mục gốc:

```powershell
docker compose -f docker/docker-compose.yml up -d
```

Nếu cổng mặc định bị chiếm:

```powershell
$env:BACKEND_PORT=8001
$env:FRONTEND_PORT=3001
docker compose -f docker/docker-compose.yml up -d
```

Dừng:

```powershell
docker compose -f docker/docker-compose.yml down
```

Build lại image:

```powershell
docker compose -f docker/docker-compose.yml build
```

Push Docker Hub:

```powershell
docker push maitung123/law-rag-backend:latest
docker push maitung123/law-rag-frontend:latest
```

Lưu ý Docker:

- Backend mount `../output:/app/output`, nên dữ liệu crawl/index/session/upload giữ trên máy host.
- Frontend image được build với `NEXT_PUBLIC_API_URL=http://localhost:${BACKEND_PORT:-8000}`.
- Nếu backend trong container cần gọi LLM local trên máy host, dùng `LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1`.

## Upload, OCR Và Embedding

Luồng upload:

1. `POST /api/uploads` lưu file vào `output/uploads`.
2. Backend OCR/trích text và lưu metadata upload.
3. Review text rồi gọi `PATCH /api/uploads/{upload_id}` với `embeddingTarget`.
4. Upload private được lưu tại:

```text
output/upload_documents/private/<upload_id>/
|- chunks.json
|- chunks.jsonl
|- embeddings/api/       # OpenAI embedding nếu chọn api
`- embeddings/local/     # local embedding nếu chọn local
```

Để kiểm tra embedding đã ghi:

```powershell
$uploadId="upload-..."
Get-Content "output\upload_documents\private\$uploadId\embeddings\local\vector_manifest.json" | ConvertFrom-Json
Test-Path "output\upload_documents\private\$uploadId\embeddings\local\faiss.index"
Test-Path "output\upload_documents\private\$uploadId\embeddings\local\vector_metadata.json"
```

`vector_manifest.json` hợp lệ sẽ có:

```json
{
  "built": true,
  "embedding_provider": "sentence-transformers",
  "embedding_model": "intfloat/multilingual-e5-base",
  "dimension": 768,
  "chunk_count": 1
}
```

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

Build FAISS:

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector-openai --backend faiss
```

Build Atlas:

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend atlas
```

## Test Và Kiểm Tra

Backend smoke test:

```powershell
python -m compileall law_rag
python -c "import law_rag.api.server; print('import ok')"
```

Frontend:

```powershell
cd law-rag-frontend
pnpm exec eslint .
.\node_modules\.bin\tsc.CMD --noEmit
pnpm run build
```

Docker runtime:

```powershell
$env:BACKEND_PORT=18000
$env:FRONTEND_PORT=13000
docker compose -f docker/docker-compose.yml up -d
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:18000/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:13000/
docker compose -f docker/docker-compose.yml down
```

## API Chính

- `GET /health`
- `GET /api/runtime/status`
- `POST /api/runtime/config`
- `POST /api/chat/ask`
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

- Không commit `.env` chứa secret thật.
- Nếu dùng OpenAI mode mà thiếu `OPENAI_API_KEY`, chat/embedding OpenAI sẽ lỗi nhưng health check vẫn chạy.
- Nếu dùng SentenceTransformers và gặp cảnh báo cache HuggingFace `Permission denied`, retrieval vẫn có thể chạy nếu model đã load được; để hết cảnh báo, đặt `HF_HOME` trỏ tới thư mục user có quyền ghi.
- Docker image backend chỉ nên đóng gói corpus/index nền. `.dockerignore` đang loại `output/uploads`, `output/upload_documents`, `output/sessions`, `output/eval` và `output/api_jobs.json` để tránh đưa dữ liệu runtime/private lên Docker Hub.
