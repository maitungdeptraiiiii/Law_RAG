# Law RAG

A Vietnamese legal RAG (Retrieval-Augmented Generation) system with four main components:

- Crawl Vietnamese legal documents from URLs listed in a DOCX file
- Chunk legal corpora into retrieval-friendly segments
- Build BM25 and vector indexes using FAISS or MongoDB Atlas
- Answer legal questions using retrieval + OpenAI

All Python source code has been organized into the `law_rag` package so the repository stays cleaner and all modules can be executed consistently using `python -m ...`.

## Project Structure

```text
Law-RAG/
├─ law_rag/
│  ├─ app/
│  │  └─ ask_law.py
│  ├─ core/
│  │  ├─ conversation_state.py
│  │  └─ env_loader.py
│  ├─ retrieval/
│  │  ├─ atlas_vector_store.py
│  │  ├─ build_vector_index.py
│  │  ├─ hybrid_retrieve.py
│  │  └─ retrieve_chunks.py
│  └─ crawl/
│     ├─ crawl_laws.py
│     ├─ chunk_framework_check.py
│     └─ chunk_laws.py
├─ env.example
├─ requirements.txt
├─ luat.docx
├─ output/
└─ README.md
```

## Requirements

- Python 3.11 recommended
- OpenAI API key
- Optional: MongoDB Atlas if using `atlas` as the vector backend

## Installation

### Option 1: Using venv

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Option 2: Using Conda

```powershell
conda create -n law_rag python=3.11 -y
conda activate law_rag
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Environment Configuration

Create an `env.txt` file in the repository root based on `env.example`:

```env
OPENAI_API_KEY=your_openai_api_key_here

# Optional when using MongoDB Atlas
MONGODB_ATLAS_URI=mongodb+srv://username:password@cluster.mongodb.net/?appName=Cluster0
MONGODB_ATLAS_DB=law_rag
MONGODB_ATLAS_COLLECTION=legal_chunks
MONGODB_ATLAS_VECTOR_INDEX=legal_chunks_vector_index
```

Notes:

- `env.txt` is ignored by Git and should never be pushed to the repository.
- If you only use FAISS, you only need `OPENAI_API_KEY`.

## Full Pipeline Workflow

### 1. Crawl Legal Documents

By default, the system reads URLs from `luat.docx` and saves crawled files into `output/laws`.

```powershell
python -m law_rag.crawl.crawl_laws --docx luat.docx --output output/laws --clean
```

Useful optional arguments:

```powershell
python -m law_rag.crawl.crawl_laws --docx luat.docx --output output/laws --limit 5 --clean
python -m law_rag.crawl.crawl_laws --docx luat.docx --output output/laws --delay 1.0 --timeout 60
```

### 2. Check Chunking Framework

Used to determine which files fit `normal_mode` and which require `amendment_mode`.

```powershell
python -m law_rag.crawl.chunk_framework_check --input output/laws
```

To export a JSON report:

```powershell
python -m law_rag.crawl.chunk_framework_check --input output/laws --json-out output/chunk_framework_report.json
```

### 3. Chunk the Corpus

```powershell
python -m law_rag.crawl.chunk_laws --input output/laws --output-dir output/chunks --max-chars 1800
```

Main outputs:

- `output/chunks/all_chunks.jsonl`
- `output/chunks/chunk_report.json`
- `output/chunks/*.chunks.json`

### 4. Build BM25 Index

```powershell
python -m law_rag.retrieval.retrieve_chunks build --chunks output/chunks/all_chunks.jsonl --output output/chunks/retrieval/bm25_index.json
```

### 5. Build Vector Index

#### FAISS

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend faiss
```

#### MongoDB Atlas

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend atlas
```

#### Build Both

```powershell
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend both
```

## Running Individual Modules

### 1. Legal Question Answering

#### One-shot Example

```powershell
python -m law_rag.app.ask_law "I caused 18% bodily injury to someone. What legal consequences could I face?"
```

#### Hybrid Retrieval + Query Rewrite

```powershell
python -m law_rag.app.ask_law "I caused 18% bodily injury to someone. What legal consequences could I face?" --retrieval-mode hybrid --query-rewrite-mode llm --top-k 5
```

#### Multi-turn Conversation with Session Memory

```powershell
python -m law_rag.app.ask_law "I broke someone's arm. What could happen legally?" --session-id vu_001
python -m law_rag.app.ask_law "The injury assessment rate is 18%" --session-id vu_001
python -m law_rag.app.ask_law "No weapon was used" --session-id vu_001
```

#### Print Full JSON Output

```powershell
python -m law_rag.app.ask_law "I caused 18% bodily injury to someone. What legal consequences could I face?" --json
```

### 2. Query BM25 Index Directly

```powershell
python -m law_rag.retrieval.retrieve_chunks query "intentional bodily injury 18 percent" --index output/chunks/retrieval/bm25_index.json --top-k 5
```

### 3. Query Hybrid / Vector / BM25 Retrieval Directly

```powershell
python -m law_rag.retrieval.hybrid_retrieve "intentional bodily injury 18 percent" --retrieval-mode hybrid --vector-backend faiss --top-k 5
```

Atlas example:

```powershell
python -m law_rag.retrieval.hybrid_retrieve "intentional bodily injury 18 percent" --retrieval-mode vector --vector-backend atlas --top-k 5
```

## Recommended End-to-End Workflow

If you clone the repository and want to rebuild the entire pipeline from scratch:

```powershell
python -m law_rag.crawl.crawl_laws --docx luat.docx --output output/laws --clean
python -m law_rag.crawl.chunk_framework_check --input output/laws --json-out output/chunk_framework_report.json
python -m law_rag.crawl.chunk_laws --input output/laws --output-dir output/chunks --max-chars 1800
python -m law_rag.retrieval.retrieve_chunks build --chunks output/chunks/all_chunks.jsonl --output output/chunks/retrieval/bm25_index.json
python -m law_rag.retrieval.build_vector_index --chunks output/chunks/all_chunks.jsonl --output-dir output/chunks/retrieval/vector --backend faiss
python -m law_rag.app.ask_law "What are the legal consequences of causing 18% bodily injury?"
```

## Notes About Data and Outputs

- `luat.docx`: input file containing legal document URLs
- `output/laws`: crawled legal documents in JSON/TXT format
- `output/chunks`: chunked legal corpus
- `output/chunks/retrieval`: BM25 indexes and vector assets
- `output/sessions`: multi-turn conversation memory

## Quick Help Commands

```powershell
python -m law_rag.app.ask_law --help
python -m law_rag.retrieval.retrieve_chunks --help
python -m law_rag.retrieval.build_vector_index --help
python -m law_rag.retrieval.hybrid_retrieve --help
python -m law_rag.crawl.crawl_laws --help
python -m law_rag.crawl.chunk_framework_check --help
python -m law_rag.crawl.chunk_laws --help
```