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

## Deploy Trên Vercel

Với kiến trúc hiện tại, cách deploy phù hợp là:

- Frontend Next.js deploy trên Vercel.
- Backend FastAPI deploy trên một dịch vụ chạy container hoặc Python server dài hạn như Railway, Render, Fly.io, VPS, hoặc Azure.

Không nên deploy toàn bộ backend hiện tại lên Vercel vì backend đang phụ thuộc vào các thành phần không hợp với môi trường serverless/ephemeral:

- Ghi dữ liệu vào thư mục local `output/`.
- OCR qua Tesseract.
- Index FAISS local.
- Job xử lý nền và upload tài liệu.

### 1. Deploy backend trước

Deploy backend ở nơi khác trước để có URL public, ví dụ `https://law-rag-api.onrender.com`.

Biến môi trường tối thiểu cho backend production:

```env
OPENAI_API_KEY=your_openai_api_key
RAG_MODE=openai
EMBEDDING_PROVIDER=openai
OPENAI_CHAT_MODEL=gpt-5.4-mini
OPENAI_MEMORY_MODEL=gpt-5.4-mini
OPENAI_QUERY_REWRITE_MODEL=gpt-5.4-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_MODEL=text-embedding-3-small
CORS_ALLOW_ORIGINS=https://your-vercel-app.vercel.app
```

Nếu dùng domain riêng cho frontend, thêm domain đó vào `CORS_ALLOW_ORIGINS`, ngăn cách bằng dấu phẩy:

```env
CORS_ALLOW_ORIGINS=https://your-vercel-app.vercel.app,https://chat.yourdomain.com
```

Lưu ý production:

- Nếu backend chạy container, có thể dùng [docker/Dockerfile.backend](docker/Dockerfile.backend).
- Nếu vẫn dùng FAISS local, thư mục chứa `output/` phải là persistent volume, không phải filesystem tạm.
- Nếu muốn scale ổn định hơn, nên chuyển vector store sang MongoDB Atlas Vector Search thay vì FAISS local.

### 2. Deploy frontend lên Vercel

Trong Vercel:

1. Import repository này.
2. Chọn Root Directory là `law-rag-frontend`.
3. Framework Preset chọn Next.js.
4. Thêm biến môi trường:

```env
NEXT_PUBLIC_API_URL=https://your-backend-domain.com
```

5. Deploy.

Vercel sẽ tự dùng các lệnh phù hợp từ `package.json`:

- Install: `pnpm install`
- Build: `pnpm build`

### 3. Cấu hình lại backend sau khi có URL Vercel

Sau khi frontend deploy xong, lấy URL thật của Vercel, ví dụ `https://law-rag-frontend.vercel.app`, rồi cập nhật lại backend:

```env
CORS_ALLOW_ORIGINS=https://law-rag-frontend.vercel.app
```

Nếu backend có health check, nên kiểm tra:

- `https://your-backend-domain.com/health`

### 4. Kiểm tra sau deploy

Kiểm tra các điểm sau:

- Frontend mở được trang chat/admin.
- Gọi API không bị lỗi CORS.
- API `/health` trả về 200.
- Chức năng upload/OCR hoạt động trên môi trường backend bạn chọn.

### 5. Cấu hình khuyến nghị cho production

Nếu mục tiêu là production thật, cấu hình bền hơn sẽ là:

- Vercel: frontend.
- Render/Railway/Fly.io/VPS: FastAPI backend.
- MongoDB Atlas: vector search + dữ liệu metadata.
- Object storage như S3/Cloudinary/R2: file upload thay vì lưu local vào `output/uploads`.

Nếu bạn muốn, có thể tiếp tục tách dự án này thành cấu hình deploy hoàn chỉnh cho Vercel + Render/Railway, bao gồm file `vercel.json`, env mẫu production và cấu hình backend persistent storage.

## Deploy Với Domain `lawrag.online`

Với domain bạn đã mua, cấu hình nên dùng là:

- `lawrag.online` hoặc `www.lawrag.online`: frontend Next.js trên Vercel.
- `api.lawrag.online`: backend FastAPI trên Render.

Đây là cách tách phù hợp nhất cho repo hiện tại vì frontend là web tĩnh/SSR chuẩn Next.js, còn backend cần môi trường chạy lâu dài, có storage bền và không phải serverless.

### Sơ đồ production nên dùng

```text
lawrag.online         -> Vercel project (frontend)
www.lawrag.online     -> alias sang frontend
api.lawrag.online     -> Render web service (backend)
```

### Bước 1. Deploy backend lên Render

Repo đã có sẵn file [render.yaml](render.yaml) để bạn import trực tiếp vào Render.

Trên Render:

1. Chọn `New +`.
2. Chọn `Blueprint`.
3. Kết nối GitHub repo này.
4. Render sẽ đọc [render.yaml](render.yaml) và tạo service `law-rag-backend`.
5. Trong phần environment variables, nhập thêm secret `OPENAI_API_KEY`.
6. Deploy và chờ Render cấp URL dạng `https://law-rag-backend.onrender.com`.

File [render.yaml](render.yaml) đã cấu hình sẵn:

- chạy bằng Dockerfile backend;
- health check tại `/health`;
- mount persistent disk vào `/app/output` để giữ dữ liệu `output/`;
- CORS mặc định cho `https://lawrag.online` và `https://www.lawrag.online`.

Sau khi service chạy, vào Render và add custom domain:

- `api.lawrag.online`

### Bước 2. Cấu hình DNS cho backend domain

Trong nơi quản lý DNS của domain `lawrag.online`, tạo record theo hướng dẫn Render cung cấp cho custom domain `api.lawrag.online`.

Thông thường sẽ là:

- Type `CNAME`
- Name `api`
- Target: hostname do Render cấp

Sau khi DNS cập nhật, kiểm tra:

- `https://api.lawrag.online/health`

Nếu trả về `200`, backend domain đã hoạt động.

### Bước 3. Deploy frontend lên Vercel

Frontend đã có file [law-rag-frontend/vercel.json](law-rag-frontend/vercel.json) để cố định build command.

Trong Vercel:

1. Import chính repo này.
2. Chọn `Root Directory` là `law-rag-frontend`.
3. Framework Preset: `Next.js`.
4. Thêm environment variable:

```env
NEXT_PUBLIC_API_URL=https://api.lawrag.online
```

5. Deploy.

### Bước 4. Gắn domain `lawrag.online` vào Vercel

Trong project frontend trên Vercel:

1. Vào `Settings`.
2. Mở `Domains`.
3. Add các domain:

- `lawrag.online`
- `www.lawrag.online`

Vercel sẽ hiển thị DNS records cần tạo. Thường là một trong hai kiểu sau:

- Apex/root domain `lawrag.online`: thêm `A record` trỏ đến IP Vercel.
- `www`: thêm `CNAME` trỏ đến hostname Vercel cung cấp.

Sau đó đặt:

- Primary domain: `lawrag.online`
- Redirect `www.lawrag.online` về `lawrag.online`

### Bước 5. Cập nhật backend CORS nếu cần

Backend hiện đọc CORS từ biến môi trường `CORS_ALLOW_ORIGINS` trong [law_rag/api/server.py](law_rag/api/server.py#L125).

Nếu cần thêm domain preview hoặc domain mới, cập nhật trên Render:

```env
CORS_ALLOW_ORIGINS=https://lawrag.online,https://www.lawrag.online
```

Nếu bạn muốn cho cả preview deployments của Vercel gọi vào backend, có thể tạm nới thêm preview domain tương ứng, nhưng production nên chỉ giữ domain chính thức.

### Bước 6. Checklist production

Kiểm tra lần lượt:

- `https://api.lawrag.online/health` hoạt động.
- `https://lawrag.online` mở được frontend.
- Chat gọi API không bị lỗi CORS.
- Upload tài liệu lưu được vào backend production.
- Nếu dùng FAISS local, dữ liệu vẫn còn sau khi Render redeploy.

### Ghi chú quan trọng

- Vercel chỉ nên host frontend của repo này.
- Backend không nên đưa lên Vercel Functions vì có OCR, ghi file local, upload pipeline và FAISS.
- Nếu sau này muốn production bền hơn nữa, nên chuyển file upload sang S3/R2 và vector store sang MongoDB Atlas.

### Lệnh/env bạn sẽ dùng thực tế

Backend trên Render:

```env
OPENAI_API_KEY=...
RAG_MODE=openai
EMBEDDING_PROVIDER=openai
OPENAI_CHAT_MODEL=gpt-5.4-mini
OPENAI_MEMORY_MODEL=gpt-5.4-mini
OPENAI_QUERY_REWRITE_MODEL=gpt-5.4-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_MODEL=text-embedding-3-small
CORS_ALLOW_ORIGINS=https://lawrag.online,https://www.lawrag.online
```

Frontend trên Vercel:

```env
NEXT_PUBLIC_API_URL=https://api.lawrag.online
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
