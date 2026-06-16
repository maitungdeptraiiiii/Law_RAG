# Law RAG

Law RAG là hệ thống hỏi đáp pháp luật Việt Nam dùng FastAPI, Next.js và retrieval kết hợp BM25 + vector search. Dự án hiện dùng corpus văn bản pháp luật crawl trực tiếp từ VBPL, có hỗ trợ OpenAI API, local LLM OpenAI-compatible, OCR tài liệu upload, FAISS local và MongoDB Atlas Vector Search.

Backend có thể chạy theo hai chế độ:

- `openai`: dùng OpenAI cho LLM và embedding.
- `local`: dùng LLM local như Ollama/LM Studio/vLLM và embedding local bằng SentenceTransformers hoặc endpoint OpenAI-compatible.

Frontend có trang chat, quản lý phiên hỏi đáp, xem nguồn tham khảo, trang admin corpus/runtime/debug và upload tài liệu riêng.

## Kiến Trúc

```text
Law-RAG/
|- law_rag/                         # Backend Python/FastAPI
|  |- api/server.py                 # API server
|  |- app/ask_law.py                # Luồng hỏi đáp RAG
|  |- core/                         # Env loader, runtime config, LLM/embedding client
|  |- crawl/crawl_vbpl_laws.py      # Crawl, tiền xử lý, chunk corpus VBPL
|  |- retrieval/                    # BM25, FAISS, Atlas, hybrid retrieval
|  `- upload_pipeline.py            # Upload, OCR, chunk, embedding tài liệu riêng
|- law-rag-frontend/                # Frontend Next.js
|- docker/                          # Dockerfile backend/frontend và docker compose
|- output/vbpl_laws_active_partial/ # Corpus VBPL, chunks, BM25, vector index
|- requirements.txt                 # Dependency backend cơ bản
|- requirements-local.txt           # Dependency local embedding
`- .env                             # Cấu hình local, không commit lên Git
```

## Tính Năng Chính

- Chat hỏi đáp pháp luật bằng tiếng Việt, có trích dẫn nguồn.
- Hybrid retrieval: BM25 + vector FAISS.
- Hỗ trợ debug bằng BM25-only, vector-only hoặc hybrid.
- Corpus mới lấy từ `https://vbpl.vn/van-ban/trung-uong`, lọc Luật/Bộ luật theo trạng thái hiệu lực.
- Chunk theo cấu trúc văn bản pháp luật, ưu tiên điều/khoản/điểm và có báo cáo chất lượng chunk.
- Upload PDF/DOCX/image, OCR bằng Tesseract, review text rồi đưa vào retrieval riêng.
- Hỗ trợ OpenAI API, local LLM OpenAI-compatible và SentenceTransformers local embedding.
- Có Dockerfile và Docker Compose để chạy backend/frontend.

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

Ví dụ chạy mặc định bằng OpenAI:

```env
RAG_MODE=openai
LLM_PROVIDER=openai
CHAT_MODEL=gpt-5.4-mini
MEMORY_MODEL=gpt-5.4-mini
QUERY_REWRITE_MODEL=gpt-5.4-mini
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_CHAT_MODEL=gpt-5.4-mini
OPENAI_MEMORY_MODEL=gpt-5.4-mini
OPENAI_QUERY_REWRITE_MODEL=gpt-5.4-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
VECTOR_DIR=output/vbpl_laws_active_partial/retrieval/vector-openai
```

Ví dụ chạy local:

```env
RAG_MODE=local
LLM_PROVIDER=local
CHAT_MODEL=qwen2.5:7b-instruct
MEMORY_MODEL=qwen2.5:7b-instruct
QUERY_REWRITE_MODEL=qwen2.5:7b-instruct
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_API_KEY=local
LOCAL_CHAT_MODEL=qwen2.5:7b-instruct
LOCAL_MEMORY_MODEL=qwen2.5:7b-instruct
LOCAL_QUERY_REWRITE_MODEL=qwen2.5:7b-instruct
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=intfloat/multilingual-e5-base
LOCAL_EMBEDDING_PROVIDER=sentence-transformers
LOCAL_EMBEDDING_MODEL=intfloat/multilingual-e5-base
VECTOR_DIR=output/vbpl_laws_active_partial/retrieval/vector-local
```

Frontend local đọc `law-rag-frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

## Chạy Local

Tạo và cài môi trường Python nếu chưa có:

```powershell
cd C:\Users\Admin\Desktop\Law-RAG
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Nếu cần local embedding:

```powershell
python -m pip install -r requirements-local.txt
```

Chạy backend:

```powershell
cd C:\Users\Admin\Desktop\Law-RAG
.\.venv\Scripts\Activate.ps1
python -m uvicorn law_rag.api.server:app --reload --host 127.0.0.1 --port 8000
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
docker compose --env-file .env -f docker/docker-compose.yml up --build
```

Chạy nền:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up --build -d
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
docker compose --env-file .env -f docker/docker-compose.yml down
```

Xem log:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml logs -f
```

Build lại sạch:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml build --no-cache
```

Lưu ý Docker:

- `docker-compose.yml` mount `../output:/app/output`, nên dữ liệu runtime vẫn nằm trên máy host.
- Nếu muốn image chạy được chỉ bằng compose mà không cần copy `output`, phải bake `output` vào image backend. Cách này làm image nặng hơn.
- Nếu backend trong container cần gọi Ollama/LM Studio trên máy host, dùng `LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1`.
- Không đưa `.env`, API key, uploads hoặc sessions vào image public.

## Push Docker Hub

Đăng nhập:

```powershell
docker login
```

Build image:

```powershell
cd C:\Users\Admin\Desktop\Law-RAG
docker compose --env-file .env -f docker/docker-compose.yml build
```

Push từng image:

```powershell
docker push maitung123/law-rag-backend:latest
docker push maitung123/law-rag-frontend:latest
```

Hoặc push bằng compose:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml push
```

Nếu muốn tách tag:

```powershell
docker tag maitung123/law-rag-backend:latest maitung123/law-rag-backend:openai
docker tag maitung123/law-rag-backend:latest maitung123/law-rag-backend:full
docker push maitung123/law-rag-backend:openai
docker push maitung123/law-rag-backend:full
```

Khuyến nghị:

- `openai`: image nhẹ, chỉ cần OpenAI API và vector OpenAI.
- `full`: image nặng hơn, có dependency local embedding như `sentence-transformers`, `torch`, `transformers`.

## Pipeline Dữ Liệu VBPL

Crawl lại corpus VBPL:

```powershell
cd C:\Users\Admin\Desktop\Law-RAG
.\.venv\Scripts\Activate.ps1
python -m law_rag.crawl.crawl_vbpl_laws `
  --output output/vbpl_laws_active_partial `
  --page-size 100 `
  --zip
```

Crawler sẽ tạo các file chính:

```text
output/vbpl_laws_active_partial/documents.json
output/vbpl_laws_active_partial/all_chunks.jsonl
output/vbpl_laws_active_partial/chunk_report.json
output/vbpl_laws_active_partial/manifest.json
```

Build BM25:

```powershell
python -m law_rag.retrieval.retrieve_chunks build `
  --chunks output/vbpl_laws_active_partial/all_chunks.jsonl `
  --output output/vbpl_laws_active_partial/retrieval/bm25_index.json
```

Build vector OpenAI:

```powershell
$env:EMBEDDING_PROVIDER="openai"
$env:EMBEDDING_MODEL="text-embedding-3-small"

python -m law_rag.retrieval.build_vector_index `
  --chunks output/vbpl_laws_active_partial/all_chunks.jsonl `
  --output-dir output/vbpl_laws_active_partial/retrieval/vector-openai `
  --backend faiss
```

Build vector local:

```powershell
$env:EMBEDDING_PROVIDER="sentence-transformers"
$env:EMBEDDING_MODEL="intfloat/multilingual-e5-base"

python -m law_rag.retrieval.build_vector_index `
  --chunks output/vbpl_laws_active_partial/all_chunks.jsonl `
  --output-dir output/vbpl_laws_active_partial/retrieval/vector-local `
  --backend faiss `
  --batch-size 50
```

Sau khi build xong, thư mục vector phải có:

```text
faiss.index
vector_metadata.json
vector_manifest.json
```

## Chạy Evaluation Theo 2 Pipeline

Có thể dùng biến môi trường `LAW_RAG_GRAPH_PIPELINE` để chuyển giữa hai pipeline retrieval:

- `LAW_RAG_GRAPH_PIPELINE=off`: pipeline 1, chạy RAG hiện tại với BM25 + vector + rerank.
- `LAW_RAG_GRAPH_PIPELINE=on`: pipeline 2, chạy Graph RAG với Neo4j legal issue map + BM25 + vector + rerank.

`GRAPH_RETRIEVAL_ENABLED` vẫn dùng được như biến override trực tiếp. Nếu biến này được set, backend sẽ ưu tiên nó hơn `LAW_RAG_GRAPH_PIPELINE`.

Các lệnh dưới đây dùng corpus/vector hiện tại:

```text
chunks: output\vbpl_merged_reuse_openai\all_chunks.jsonl
bm25:   output\vbpl_merged_reuse_openai\retrieval\bm25_index.json
vector: output\vbpl_merged_reuse_openai\retrieval\vector-openai
dataset: evaluation\law_rag_eval_dataset.json
```

### Pipeline 1: baseline, không dùng Neo4j

```powershell
cd C:\Users\Admin\Desktop\Law-RAG

$env:LAW_RAG_GRAPH_PIPELINE="off"
Remove-Item Env:\GRAPH_RETRIEVAL_ENABLED -ErrorAction SilentlyContinue
$env:MAX_ACTIVE_RETRIEVAL_QUERIES="3"

$report="output\eval\runs\pipeline1-baseline.json"

.\.venv\Scripts\python.exe evaluation\evaluate_law_rag.py `
  --dataset evaluation\law_rag_eval_dataset.json `
  --retrieval-mode hybrid `
  --top-k 5 `
  --query-rewrite `
  --output $report

.\.venv\Scripts\python.exe evaluation\run_ragas_semantic_judge.py `
  --report $report `
  --dataset evaluation\law_rag_eval_dataset.json
```

### Pipeline 2: Graph RAG với Neo4j

Khởi động Neo4j nếu chưa chạy:

```powershell
docker compose -f docker\neo4j-compose.yml up -d
```

Build graph từ chunk mới có Điều/Khoản/Điểm. Có thể dùng `--skip-references` để build nhanh phần cần cho legal issue map:

```powershell
$env:NEO4J_URI="bolt://127.0.0.1:7687"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="lawrag-password"
$env:NEO4J_DATABASE="neo4j"

.\.venv\Scripts\python.exe scripts\build_neo4j_legal_graph.py `
  --chunks output\vbpl_combined_chunking_v3\all_chunks.jsonl `
  --issue-rules law_rag\retrieval\legal_issues_full_all_added.json `
  --skip-references `
  --wait-seconds 180
```

Chạy eval với Graph RAG:

```powershell
cd C:\Users\Admin\Desktop\Law-RAG

$env:LAW_RAG_GRAPH_PIPELINE="on"
Remove-Item Env:\GRAPH_RETRIEVAL_ENABLED -ErrorAction SilentlyContinue
$env:GRAPH_MAX_PINNED="1"
$env:GRAPH_PIN_DISTINGUISH="false"
$env:GRAPH_PIN_MIN_RERANK_SCORE="0"
$env:MAX_ACTIVE_RETRIEVAL_QUERIES="3"

$env:NEO4J_URI="bolt://127.0.0.1:7687"
$env:NEO4J_USER="neo4j"
$env:NEO4J_PASSWORD="lawrag-password"
$env:NEO4J_DATABASE="neo4j"

$report="output\eval\runs\pipeline2-graph-rag.json"

.\.venv\Scripts\python.exe evaluation\evaluate_law_rag.py `
  --dataset evaluation\law_rag_eval_dataset.json `
  --retrieval-mode hybrid `
  --top-k 5 `
  --query-rewrite `
  --output $report

.\.venv\Scripts\python.exe evaluation\run_ragas_semantic_judge.py `
  --report $report `
  --dataset evaluation\law_rag_eval_dataset.json
```

Nếu muốn thử pin có điều kiện sau BGE rerank, đặt:

```powershell
$env:GRAPH_PIN_MIN_RERANK_SCORE="0.45"
```

Kết quả gần đây cho thấy cấu hình retrieval tốt nhất đang là soft pin:

```powershell
$env:LAW_RAG_GRAPH_PIPELINE="on"
Remove-Item Env:\GRAPH_RETRIEVAL_ENABLED -ErrorAction SilentlyContinue
$env:GRAPH_MAX_PINNED="1"
$env:GRAPH_PIN_DISTINGUISH="false"
$env:GRAPH_PIN_MIN_RERANK_SCORE="0"
$env:MAX_ACTIVE_RETRIEVAL_QUERIES="3"
```

## Upload, OCR Và Embedding Tài Liệu Riêng

Luồng upload:

1. `POST /api/uploads` lưu file vào `output/uploads`.
2. Backend OCR/trích text và lưu metadata upload.
3. Người dùng review text.
4. `PATCH /api/uploads/{upload_id}` lưu tài liệu đã xử lý.
5. `POST /api/uploads/{upload_id}/embed` build embedding riêng.

Upload private được lưu tại:

```text
output/uploads/private/
```

Các thư mục upload, session và private runtime data không nên commit lên Git.

## Runtime Và API Key

Kiểm tra runtime:

```powershell
curl http://127.0.0.1:8000/api/runtime/status
```

Trong trang Admin có thể chuyển runtime giữa `Local` và `OpenAI API`.

Khi chọn OpenAI API, backend cần `OPENAI_API_KEY` trong `.env`. Không commit key lên GitHub hoặc bake vào Docker image public.

Khi chọn local, backend cần:

```env
LLM_PROVIDER=local
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
EMBEDDING_PROVIDER=sentence-transformers
VECTOR_DIR=output/vbpl_laws_active_partial/retrieval/vector-local
```

Nếu chạy local qua Docker và Ollama nằm trên máy host:

```env
LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1
```

## API Chính

```text
GET  /health
GET  /api/runtime/status
POST /api/chat/ask
POST /api/chat/ask/stream
GET  /api/sessions
GET  /api/sessions/{session_id}/conversation
POST /api/debug/search
GET  /api/admin/documents
GET  /api/uploads
POST /api/uploads
PATCH /api/uploads/{upload_id}
POST /api/uploads/{upload_id}/embed
```

## Chạy Web Public Với Domain `lawrag.online`

Sơ đồ hiện tại:

```text
https://www.lawrag.online/chat  -> frontend trên Vercel
https://api.lawrag.online       -> Cloudflare Tunnel
Cloudflare Tunnel               -> backend FastAPI trên máy cá nhân
```

Khởi động backend:

```powershell
cd C:\Users\Admin\Desktop\Law-RAG
.\.venv\Scripts\python.exe -m uvicorn law_rag.api.server:app --host 127.0.0.1 --port 8000
```

Khởi động Cloudflare Tunnel:

```powershell
cloudflared tunnel run lawrag-api
```

Kiểm tra:

```powershell
curl http://127.0.0.1:8000/health
curl https://api.lawrag.online/health
```

Nếu tắt máy hoặc dừng tunnel, frontend vẫn mở được nhưng chat sẽ không gọi được API.

## Ghi Chú Vận Hành

- Không commit `.env`, uploads, sessions hoặc private upload data.
- Nếu API key đã từng lộ, hãy rotate key trên OpenAI dashboard và cập nhật lại `.env`.
- Nếu dùng OpenAI mode mà thiếu `OPENAI_API_KEY`, chat/embedding OpenAI sẽ lỗi nhưng health check vẫn chạy.
- Nếu dùng local mode, cần chạy Ollama/LM Studio/vLLM hoặc endpoint OpenAI-compatible tương ứng.
- Nếu dùng SentenceTransformers lần đầu, model local embedding có thể mất thời gian tải từ Hugging Face.
- Backend đang dùng corpus mặc định tại `output/vbpl_laws_active_partial`.
