# Law RAG

Hệ thống RAG pháp luật Việt Nam gồm 2 phần chạy tách biệt:

- Backend Python với FastAPI, pipeline crawl/chunk/index và logic hỏi đáp dùng OpenAI.
- Frontend Next.js cho landing page, trang chat, dashboard quản trị dữ liệu và các thao tác debug.

README này phản ánh trạng thái hiện tại của repo sau khi frontend đã được cập nhật.

## 1. Tổng quan kiến trúc

```text
Law-RAG/
|- law_rag/                 # Backend Python
|  |- api/server.py         # FastAPI server
|  |- app/ask_law.py        # Logic hỏi đáp pháp luật
|  |- crawl/                # Crawl + phân loại + chunk dữ liệu
|  |- retrieval/            # BM25 / vector / hybrid retrieval
|  `- core/                 # Env loader, conversation state
|- law-rag-frontend/        # Frontend Next.js
|  |- app/                  # Landing, chat, admin
|  |- components/           # UI components
|  |- lib/api.ts            # API client gọi backend
|  `- .env.example          # Biến môi trường frontend
|- output/                  # Dữ liệu crawl, chunks, index, sessions, jobs
|- env.example              # Mẫu biến môi trường backend
|- env.txt                  # Biến môi trường backend thực tế
|- requirements.txt         # Python dependencies
`- README.md
```

## 2. Tính năng hiện có

- Chat hỏi đáp pháp luật bằng tiếng Việt tại `/chat`.
- Lưu lịch sử hội thoại nhiều lượt trong `output/sessions`.
- Hybrid retrieval: BM25 + vector search.
- Dashboard quản trị tại `/admin` để:
	- xem tình trạng corpus,
	- chạy crawl,
	- chạy chunk,
	- build BM25 index,
	- build vector index FAISS,
	- debug truy vấn retrieve.
- Upload tài liệu qua API để chuẩn bị cho luồng OCR/phân tích tài liệu.

## 2.1. Demo giao diện

### Landing page

![Landing page](docs/screenshots/landing-page.png)

Trang giới thiệu sản phẩm, mô tả giá trị của hệ thống Law RAG và điều hướng nhanh tới khu vực chat hoặc quản trị.

### Chat hỏi đáp pháp luật

![Màn hình chat hỏi đáp](docs/screenshots/chat-answer.png)

Màn hình hội thoại chính hỗ trợ hỏi đáp pháp luật tiếng Việt, lưu lịch sử chat và trả lời có trích dẫn căn cứ pháp lý.


### Khối tính năng nổi bật

![Phần tính năng nổi bật](docs/screenshots/features-section.png)

Phần giới thiệu các điểm mạnh của hệ thống như Hybrid Retrieval giúp tăng độ chính xác tìm kiếm, cơ chế trích dẫn minh bạch nguồn luật, hỗ trợ hội thoại liên tục theo ngữ cảnh và khả năng mở rộng tích hợp OCR trong tương lai.

### Dashboard quản trị

![Dashboard quản trị](docs/screenshots/admin-dashboard.png)

Trang quản trị theo dõi tình trạng dữ liệu, số lượng văn bản và điều khiển pipeline crawl, chunk, BM25, vector index.

## 3. Chạy bằng Docker

Repo hiện dùng [docker-compose.yml](c:/Users/Admin/Desktop/Law-RAG/docker-compose.yml) theo mode chạy từ image đã được push lên Docker Hub.

Ý nghĩa của mô hình này:

- Máy khác không cần source code để build lại.
- Chỉ cần file compose, Docker và quyền pull image từ Docker Hub.
- Compose sẽ kéo 2 image `maitung123/law-rag-backend:latest` và `maitung123/law-rag-frontend:latest` về để chạy.

### Chuẩn bị

1. Bảo đảm bạn có `OPENAI_API_KEY` dưới dạng biến môi trường shell hoặc file `.env` cho Docker Compose.
2. Đăng nhập Docker Hub nếu repository là private bằng `docker login`.

### Chạy

Từ thư mục gốc repo:

```powershell
docker compose up -d
```

Nếu máy bạn đã có service khác chiếm `3000` hoặc `8000`, có thể đổi cổng host ngay lúc chạy:

```powershell
$env:FRONTEND_PORT=3001
$env:BACKEND_PORT=8001
docker compose up -d
```

Sau khi chạy:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

Nếu đã đổi cổng host thì thay các URL trên theo giá trị `FRONTEND_PORT` và `BACKEND_PORT`.

### Chạy nền

```powershell
docker compose up -d
```

### Dừng container

```powershell
docker compose down
```

### Ghi chú Docker

- Backend dùng named volume `law_rag_output` để giữ dữ liệu crawl/index/session giữa các lần chạy.
- `luat.docx` và dữ liệu ban đầu trong `output/` đã được copy sẵn vào image backend trước khi push Docker Hub.
- Frontend được build theo chế độ `standalone` để image gọn hơn.
- `FRONTEND_PORT` và `BACKEND_PORT` chỉ đổi cổng host bind ra ngoài, không đổi cổng chạy bên trong container.
- `OPENAI_API_KEY` và các biến `MONGODB_ATLAS_*` được truyền trực tiếp vào container runtime, không còn phụ thuộc `env.txt` trên máy host.

### Máy khác cần gì để chạy

Máy khác chỉ cần:

- [docker-compose.yml](c:/Users/Admin/Desktop/Law-RAG/docker-compose.yml)
- Docker Desktop hoặc Docker Engine
- internet để pull image từ Docker Hub
- biến môi trường cần thiết như `OPENAI_API_KEY`

Sau đó trên máy đích chỉ cần:

```powershell
$env:OPENAI_API_KEY="your_openai_key"
docker compose up -d
```

Nếu repository trên Docker Hub là `private` thì thêm bước:

```powershell
docker login
```

Lưu ý: frontend image hiện tại đã được build với backend URL mặc định là `http://localhost:8000`. Nếu sau này backend cần chạy ở URL khác, bạn phải build lại và push lại frontend image.

## 4. Yêu cầu môi trường

### Backend

- Python 3.11 khuyến nghị
- OpenAI API key
- Tùy chọn: MongoDB Atlas nếu muốn dùng vector backend là `atlas`

### Frontend

- Node.js 20 trở lên khuyến nghị
- `pnpm` khuyến nghị vì repo đang có `pnpm-lock.yaml`

## 5. Cài đặt backend

Từ thư mục gốc của repo:

### Cách 1: dùng `venv`

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Cách 2: dùng Conda

```powershell
conda create -n law_rag python=3.11 -y
conda activate law_rag
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 6. Cấu hình biến môi trường backend

Tạo hoặc cập nhật file `env.txt` ở thư mục gốc dựa trên `env.example`:

```env
OPENAI_API_KEY=your_openai_api_key_here

RAG_MODE=openai
OPENAI_CHAT_MODEL=gpt-5.4-mini
OPENAI_MEMORY_MODEL=gpt-5.4-mini
OPENAI_QUERY_REWRITE_MODEL=gpt-5.4-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Optional: chỉ cần khi dùng MongoDB Atlas làm vector backend.
MONGODB_ATLAS_URI=mongodb+srv://username:password@cluster.mongodb.net/?appName=Cluster0
MONGODB_ATLAS_DB=law_rag
MONGODB_ATLAS_COLLECTION=legal_chunks
MONGODB_ATLAS_VECTOR_INDEX=legal_chunks_vector_index
```

Lưu ý:

- `env.txt` được backend tự nạp khi chạy.
- Nếu dùng OpenAI cho chat/embedding thì cần `OPENAI_API_KEY`; nếu chuyển cả chat và embedding sang local thì có thể không cần.
- Không commit `env.txt` chứa secret lên Git.

### Chế độ OpenAI API

```env
RAG_MODE=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_CHAT_MODEL=gpt-5.4-mini
OPENAI_MEMORY_MODEL=gpt-5.4-mini
OPENAI_QUERY_REWRITE_MODEL=gpt-5.4-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Build FAISS index cho OpenAI mode:

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector-openai --backend faiss
```

### Chế độ local

```env
RAG_MODE=local
LOCAL_LLM_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_LLM_API_KEY=local
LOCAL_CHAT_MODEL=qwen2.5:7b-instruct
LOCAL_MEMORY_MODEL=qwen2.5:7b-instruct
LOCAL_QUERY_REWRITE_MODEL=qwen2.5:7b-instruct
LOCAL_EMBEDDING_PROVIDER=sentence-transformers
LOCAL_EMBEDDING_MODEL=intfloat/multilingual-e5-base
```

Build FAISS index cho local mode:

```powershell
python -m pip install -r requirements-local.txt
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector-local --backend faiss
```

Biến `LLM_PROVIDER`, `CHAT_MODEL`, `MEMORY_MODEL`, `QUERY_REWRITE_MODEL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` vẫn có thể dùng khi cần override thủ công, nhưng thường chỉ cần đổi `RAG_MODE`.

### Dùng model local cho answer, memory và query rewrite

Backend có 3 phần dùng chat LLM:

- `CHAT_MODEL`: sinh câu trả lời cuối cùng từ retrieved context.
- `MEMORY_MODEL`: cập nhật bộ nhớ hội thoại và tạo retrieval query theo ngữ cảnh nhiều lượt.
- `QUERY_REWRITE_MODEL`: rewrite/mở rộng câu hỏi trước retrieval.

Mặc định các phần này dùng OpenAI. Nếu muốn dùng model local như Qwen/HuggingFace qua server tương thích OpenAI API, cấu hình:

```env
LLM_PROVIDER=local
LOCAL_LLM_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_LLM_API_KEY=local
CHAT_MODEL=qwen2.5:7b-instruct
MEMORY_MODEL=qwen2.5:7b-instruct
QUERY_REWRITE_MODEL=qwen2.5:7b-instruct
```

Sau đó chạy backend như bình thường. Với vLLM hoặc LM Studio, chỉ cần thay `LOCAL_LLM_BASE_URL` và tên model theo server đang chạy.

Nếu backend chạy trong Docker nhưng server local chạy trên máy host, thường dùng:

```env
LOCAL_LLM_BASE_URL=http://host.docker.internal:8000/v1
```

Lưu ý: cấu hình chat LLM ở trên chỉ áp dụng cho answer, memory và rewrite query. Vector embedding có cấu hình riêng bên dưới.

### Dùng embedding local cho vector search

Vector search có 2 giai đoạn đều phải dùng cùng embedding provider/model:

- Build index: biến từng chunk luật thành vector và lưu vào FAISS hoặc Atlas.
- Query runtime: biến câu hỏi/retrieval query thành vector để search.

Các provider hỗ trợ:

```env
# OpenAI, mặc định
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small

# OpenAI-compatible local endpoint, ví dụ vLLM/LM Studio nếu server có /v1/embeddings
EMBEDDING_PROVIDER=local-openai
LOCAL_EMBEDDING_BASE_URL=http://127.0.0.1:8001/v1
LOCAL_EMBEDDING_API_KEY=local
EMBEDDING_MODEL=your-local-embedding-model

# HuggingFace SentenceTransformers chạy local trong process Python
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=intfloat/multilingual-e5-base
```

Ví dụ với SentenceTransformers:

```powershell
python -m pip install -r requirements-local.txt
$env:EMBEDDING_PROVIDER="sentence-transformers"
$env:EMBEDDING_MODEL="intfloat/multilingual-e5-base"
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend faiss --model intfloat/multilingual-e5-base
```

Quan trọng: khi đổi `EMBEDDING_PROVIDER` hoặc `EMBEDDING_MODEL`, phải build lại vector index. FAISS manifest sẽ lưu `embedding_provider` và `embedding_model`, sau đó query runtime tự dùng lại đúng cấu hình đó.

## 7. Cài đặt frontend

Từ thư mục [law-rag-frontend](c:/Users/Admin/Desktop/Law-RAG/law-rag-frontend):

```powershell
cd law-rag-frontend
pnpm install
```

Nếu máy chưa có `pnpm`:

```powershell
npm install -g pnpm
```

## 8. Cấu hình biến môi trường frontend

Tạo file `.env.local` trong thư mục frontend dựa trên [law-rag-frontend/.env.example](c:/Users/Admin/Desktop/Law-RAG/law-rag-frontend/.env.example):

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Nếu backend chạy ở host hoặc port khác thì cập nhật lại biến này.

## 9. Chạy dự án ở môi trường dev

Bạn cần chạy 2 tiến trình riêng.

### Terminal 1: chạy backend FastAPI

Từ thư mục gốc repo:

```powershell
uvicorn law_rag.api.server:app --reload --host 127.0.0.1 --port 8000
```

Kiểm tra nhanh:

- Health check: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`

### Terminal 2: chạy frontend Next.js

Từ thư mục [law-rag-frontend](c:/Users/Admin/Desktop/Law-RAG/law-rag-frontend):

```powershell
pnpm dev
```

Mặc định frontend chạy tại:

- `http://localhost:3000`

Các trang chính:

- Landing page: `http://localhost:3000/`
- Chat: `http://localhost:3000/chat`
- Admin dashboard: `http://localhost:3000/admin`

## 10. Chạy nhanh nếu đã có dữ liệu/index sẵn

Repo hiện đã có dữ liệu trong `output/`. Nếu các file sau đã tồn tại thì bạn có thể mở chat ngay sau khi chạy backend + frontend:

- `output/chunks/all_chunks.jsonl`
- `output/chunks/retrieval/bm25_index.json`
- `output/chunks/retrieval/vector/faiss.index` hoặc manifest Atlas

Nếu chưa đủ dữ liệu/index, hãy vào trang `/admin` để chạy lần lượt:

1. Thu thập văn bản
2. Chia chunks
3. Xây dựng BM25
4. Xây dựng Vector

## 11. Build frontend cho production

Từ thư mục [law-rag-frontend](c:/Users/Admin/Desktop/Law-RAG/law-rag-frontend):

```powershell
pnpm build
pnpm start
```

## 12. Luồng xử lý dữ liệu backend

Backend hỗ trợ cả chạy qua dashboard admin lẫn chạy CLI trực tiếp.

### 12.1. Crawl văn bản luật

```powershell
python -m law_rag.crawl.crawl_laws --docx luat.docx --output output/laws --clean
```

Ví dụ giới hạn số lượng văn bản:

```powershell
python -m law_rag.crawl.crawl_laws --docx luat.docx --output output/laws --limit 5 --clean
```

### 12.2. Kiểm tra framework chunking

```powershell
python -m law_rag.crawl.chunk_framework_check --input output/laws --json-out output/chunk_framework_report.json
```

### 12.3. Chunk corpus

```powershell
python -m law_rag.crawl.chunk_laws --input output/laws --output-dir output/chunks --max-chars 1800
```

Output chính:

- `output/chunks/all_chunks.jsonl`
- `output/chunks/chunk_report.json`
- `output/chunks/*.chunks.json`

### 12.4. Build BM25 index

```powershell
python -m law_rag.retrieval.retrieve_chunks build --chunks output/chunks/all_chunks.jsonl --output output/chunks/retrieval/bm25_index.json
```

### 12.5. Build vector index

#### FAISS

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend faiss
```

#### MongoDB Atlas

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend atlas
```

## 13. Chạy hỏi đáp từ CLI

### One-shot

```powershell
python -m law_rag.app.ask_law "Tôi gây thương tích 18% cho người khác thì có thể bị xử lý thế nào?"
```

### Hybrid retrieval + query rewrite

```powershell
python -m law_rag.app.ask_law "Tôi gây thương tích 18% cho người khác thì có thể bị xử lý thế nào?" --retrieval-mode hybrid --query-rewrite-mode llm --top-k 5
```

### Hội thoại nhiều lượt

```powershell
python -m law_rag.app.ask_law "Tôi làm gãy tay người khác thì có sao không?" --session-id vu_001
python -m law_rag.app.ask_law "Tỷ lệ thương tật là 18%" --session-id vu_001
python -m law_rag.app.ask_law "Không dùng hung khí" --session-id vu_001
```

### In JSON output đầy đủ

```powershell
python -m law_rag.app.ask_law "Tôi gây thương tích 18% cho người khác thì có thể bị xử lý thế nào?" --json
```

## 14. Một số API đáng chú ý

- `GET /health`: kiểm tra backend sống.
- `POST /api/chat/ask`: gửi câu hỏi pháp luật.
- `GET /api/sessions`: danh sách phiên chat.
- `GET /api/documents`: danh sách văn bản đã crawl/chunk/index.
- `GET /api/admin/corpus-status`: trạng thái corpus và index.
- `POST /api/admin/jobs/crawl`: chạy crawl.
- `POST /api/admin/jobs/chunk`: chạy chunk.
- `POST /api/admin/jobs/index-bm25`: build BM25.
- `POST /api/admin/jobs/index-vector`: build vector FAISS.
- `POST /api/admin/debug/query`: debug retrieval.
- `POST /api/uploads`: upload tài liệu.

## 15. Các file/thư mục đầu ra quan trọng

- `output/laws`: dữ liệu văn bản đã crawl.
- `output/chunks`: dữ liệu chunk.
- `output/chunks/retrieval`: BM25 index và vector assets.
- `output/sessions`: lịch sử chat nhiều lượt.
- `output/api_jobs.json`: trạng thái job chạy từ dashboard admin.

## 16. Lệnh trợ giúp nhanh

```powershell
python -m law_rag.app.ask_law --help
python -m law_rag.retrieval.retrieve_chunks --help
python -m law_rag.retrieval.build_vector_index --help
python -m law_rag.retrieval.hybrid_retrieve --help
python -m law_rag.crawl.crawl_laws --help
python -m law_rag.crawl.chunk_framework_check --help
python -m law_rag.crawl.chunk_laws --help
```

## 17. Ghi chú triển khai

- Frontend mặc định gọi backend qua `NEXT_PUBLIC_API_URL`.
- Backend đã mở CORS cho `localhost:3000`, `127.0.0.1:3000`, `localhost:3001`, `127.0.0.1:3001`.
- Muốn dùng MongoDB Atlas thì cần cấu hình đầy đủ biến `MONGODB_ATLAS_*` ở backend.
- Dashboard admin hiện tại build vector theo backend `faiss`; nếu muốn build Atlas từ UI thì cần mở rộng thêm API/admin flow.
