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

## 3. Yêu cầu môi trường

### Backend

- Python 3.11 khuyến nghị
- OpenAI API key
- Tùy chọn: MongoDB Atlas nếu muốn dùng vector backend là `atlas`

### Frontend

- Node.js 20 trở lên khuyến nghị
- `pnpm` khuyến nghị vì repo đang có `pnpm-lock.yaml`

## 4. Cài đặt backend

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

## 5. Cấu hình biến môi trường backend

Tạo hoặc cập nhật file `env.txt` ở thư mục gốc dựa trên `env.example`:

```env
OPENAI_API_KEY=your_openai_api_key_here

# Optional: chỉ cần khi dùng MongoDB Atlas làm vector backend.
MONGODB_ATLAS_URI=mongodb+srv://username:password@cluster.mongodb.net/?appName=Cluster0
MONGODB_ATLAS_DB=law_rag
MONGODB_ATLAS_COLLECTION=legal_chunks
MONGODB_ATLAS_VECTOR_INDEX=legal_chunks_vector_index
```

Lưu ý:

- `env.txt` được backend tự nạp khi chạy.
- Nếu chỉ dùng FAISS thì chỉ cần `OPENAI_API_KEY`.
- Không commit `env.txt` chứa secret lên Git.

## 6. Cài đặt frontend

Từ thư mục [law-rag-frontend](c:/Users/Admin/Desktop/Law-RAG/law-rag-frontend):

```powershell
cd law-rag-frontend
pnpm install
```

Nếu máy chưa có `pnpm`:

```powershell
npm install -g pnpm
```

## 7. Cấu hình biến môi trường frontend

Tạo file `.env.local` trong thư mục frontend dựa trên [law-rag-frontend/.env.example](c:/Users/Admin/Desktop/Law-RAG/law-rag-frontend/.env.example):

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Nếu backend chạy ở host hoặc port khác thì cập nhật lại biến này.

## 8. Chạy dự án ở môi trường dev

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

## 9. Chạy nhanh nếu đã có dữ liệu/index sẵn

Repo hiện đã có dữ liệu trong `output/`. Nếu các file sau đã tồn tại thì bạn có thể mở chat ngay sau khi chạy backend + frontend:

- `output/chunks/all_chunks.jsonl`
- `output/chunks/retrieval/bm25_index.json`
- `output/chunks/retrieval/vector/faiss.index` hoặc manifest Atlas

Nếu chưa đủ dữ liệu/index, hãy vào trang `/admin` để chạy lần lượt:

1. Thu thập văn bản
2. Chia chunks
3. Xây dựng BM25
4. Xây dựng Vector

## 10. Build frontend cho production

Từ thư mục [law-rag-frontend](c:/Users/Admin/Desktop/Law-RAG/law-rag-frontend):

```powershell
pnpm build
pnpm start
```

## 10.1. Chạy bằng Docker

Repo đã có sẵn cấu hình Docker cho cả backend và frontend.

### Chuẩn bị

1. Tạo `env.txt` ở thư mục gốc từ `env.example` và điền `OPENAI_API_KEY`.
2. Nếu muốn frontend gọi API khác `http://localhost:8000`, đặt biến môi trường `NEXT_PUBLIC_API_URL` trước khi build hoặc sửa trực tiếp trong `docker-compose.yml`.

### Build và chạy

Từ thư mục gốc repo:

```powershell
docker compose up --build
```

Nếu máy bạn đã có service khác chiếm `3000` hoặc `8000`, có thể đổi cổng host ngay lúc chạy:

```powershell
$env:FRONTEND_PORT=3001
$env:BACKEND_PORT=8001
$env:NEXT_PUBLIC_API_URL=http://localhost:8001
docker compose up --build
```

Sau khi chạy:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

Nếu đã đổi cổng host thì thay các URL trên theo giá trị `FRONTEND_PORT` và `BACKEND_PORT`.

### Chạy nền

```powershell
docker compose up --build -d
```

### Dừng container

```powershell
docker compose down
```

### Ghi chú Docker

- Backend mount `output/`, `env.txt` và `luat.docx` từ máy host để dữ liệu crawl/index và session vẫn được giữ lại ngoài container.
- Frontend được build theo chế độ `standalone` để image gọn hơn.
- `NEXT_PUBLIC_API_URL` là biến được dùng lúc build frontend. Nếu đổi URL API, cần build lại frontend image.
- `FRONTEND_PORT` và `BACKEND_PORT` chỉ đổi cổng host bind ra ngoài, không đổi cổng chạy bên trong container.

## 11. Luồng xử lý dữ liệu backend

Backend hỗ trợ cả chạy qua dashboard admin lẫn chạy CLI trực tiếp.

### 11.1. Crawl văn bản luật

```powershell
python -m law_rag.crawl.crawl_laws --docx luat.docx --output output/laws --clean
```

Ví dụ giới hạn số lượng văn bản:

```powershell
python -m law_rag.crawl.crawl_laws --docx luat.docx --output output/laws --limit 5 --clean
```

### 11.2. Kiểm tra framework chunking

```powershell
python -m law_rag.crawl.chunk_framework_check --input output/laws --json-out output/chunk_framework_report.json
```

### 11.3. Chunk corpus

```powershell
python -m law_rag.crawl.chunk_laws --input output/laws --output-dir output/chunks --max-chars 1800
```

Output chính:

- `output/chunks/all_chunks.jsonl`
- `output/chunks/chunk_report.json`
- `output/chunks/*.chunks.json`

### 11.4. Build BM25 index

```powershell
python -m law_rag.retrieval.retrieve_chunks build --chunks output/chunks/all_chunks.jsonl --output output/chunks/retrieval/bm25_index.json
```

### 11.5. Build vector index

#### FAISS

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend faiss
```

#### MongoDB Atlas

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend atlas
```

## 12. Chạy hỏi đáp từ CLI

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

## 13. Một số API đáng chú ý

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

## 14. Các file/thư mục đầu ra quan trọng

- `output/laws`: dữ liệu văn bản đã crawl.
- `output/chunks`: dữ liệu chunk.
- `output/chunks/retrieval`: BM25 index và vector assets.
- `output/sessions`: lịch sử chat nhiều lượt.
- `output/api_jobs.json`: trạng thái job chạy từ dashboard admin.

## 15. Lệnh trợ giúp nhanh

```powershell
python -m law_rag.app.ask_law --help
python -m law_rag.retrieval.retrieve_chunks --help
python -m law_rag.retrieval.build_vector_index --help
python -m law_rag.retrieval.hybrid_retrieve --help
python -m law_rag.crawl.crawl_laws --help
python -m law_rag.crawl.chunk_framework_check --help
python -m law_rag.crawl.chunk_laws --help
```

## 16. Ghi chú triển khai

- Frontend mặc định gọi backend qua `NEXT_PUBLIC_API_URL`.
- Backend đã mở CORS cho `localhost:3000`, `127.0.0.1:3000`, `localhost:3001`, `127.0.0.1:3001`.
- Muốn dùng MongoDB Atlas thì cần cấu hình đầy đủ biến `MONGODB_ATLAS_*` ở backend.
- Dashboard admin hiện tại build vector theo backend `faiss`; nếu muốn build Atlas từ UI thì cần mở rộng thêm API/admin flow.