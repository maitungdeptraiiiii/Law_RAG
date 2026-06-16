# Bao cao cai thien chunking cho Law RAG

## Tom tat quyet dinh

Ban dau em chunk theo Dieu vi van ban phap luat co cau truc ro. Sau khi eval, em thay article-level qua dai lam retrieval bi nhieu, nen chuyen sang semantic chunking theo Dieu/khoan/diem. Trade-off la chunk nho hon thi chinh xac hon nhung de mat ngu canh toan Dieu. Vi vay em bo sung parent metadata, merge chunk qua ngan va dung parent context trong retrieval de can bang giua precision va groundedness.

## Van de cua chunking cu

Chunking cu chu yeu cat theo Dieu hoac cat theo size lon. Cach nay co uu diem la giu du ngu canh cua ca Dieu, nhung voi cac Dieu dai, embedding bi loang vi mot vector phai dai dien cho qua nhieu y phap ly.

Ket qua quan sat:

- Nhieu chunk dai hon 3500 ky tu, co chunk gan 10000 ky tu.
- Query cu the ve mot khoan/diem co the bi match sang van ban lien quan nhung khong dung Dieu can tra.
- Citation accuracy va MRR bi anh huong vi source dung khong luon nam o top dau.

## Huong chunking moi

Chunking moi van giu nen tang theo cau truc phap luat:

- Neu Dieu ngan: giu nguyen mot chunk.
- Neu Dieu dai: tach theo khoan.
- Neu khoan van dai: tach tiep theo diem.
- Neu van qua dai: fallback sang split theo kich thuoc co overlap.

Cach nay phu hop voi bai toan phap luat vi nguon du lieu co cau truc tu nhien: van ban, Dieu, khoan, diem.

## Thay doi da thuc hien

### 1. Bo sung parent metadata/context

Moi chunk duoc bo sung `parent_context_text`, gom cac thong tin nhu:

- Ten van ban.
- So hieu van ban.
- Loai van ban.
- Phan/chuong/muc neu co.
- Tieu de Dieu.
- So Dieu.

Muc dich la de chunk con, vi du mot khoan ngan, van mang du dau hieu cho embedding va BM25 biet no thuoc Dieu nao, van ban nao.

Trade-off:

- Tang kha nang retrieve dung Dieu/van ban.
- Embedding input dai hon mot chut.
- Co them trung lap metadata giua cac chunk cung parent, nhung chap nhan duoc vi doi lai retrieval on dinh hon.

### 2. Merge chunk qua ngan cung parent

Nhung chunk qua ngan duoi 120 ky tu se duoc merge voi chunk truoc hoac sau neu:

- Cung `parent_chunk_id`.
- Cung van ban / source / article.
- Sau khi merge khong vuot 2500 ky tu.

Muc dich la giam cac chunk qua mong, it y nghia khi embedding rieng le.

Trade-off:

- Giam nhieu chunk ngan gay nhieu.
- Tang groundedness vi context cua chunk day du hon.
- Co the giam do min cua retrieval trong mot so cau hoi rat chi tiet, nen gioi han merge toi da 2500 ky tu thay vi merge qua dai.

### 3. Dua parent context vao searchable text

`build_searchable_text()` da them `parent_context_text` vao input cho BM25/vector index.

Dieu nay co nghia la khi build lai BM25/FAISS, retrieval khong chi nhin noi dung chunk ma con nhin them ngu canh phap ly cua chunk.

Trade-off:

- BM25 va vector search de match dung van ban/Dieu hon.
- Searchable text co them metadata lap lai, co the uu tien document title/article title manh hon. Day la chu dich co loi cho bai toan citation phap luat.

## Ket qua eval truoc khi sua tiep

So sanh giua corpus cu va chunking moi truoc lan tinh chinh nay:

| Metric | Chunking cu | Chunking moi |
|---|---:|---:|
| Recall@3 | 0.43 | 0.55 |
| Recall@5 | 0.54 | 0.61 |
| MRR | 0.36 | 0.46 |
| nDCG@5 | 0.36 | 0.45 |
| Citation accuracy | 3.14 | 3.43 |
| Overall | 3.84 | 3.92 |

Dieu nay cho thay huong semantic chunking la dung, nhung van can tinh chinh de cai thien groundedness.

## Luu y khi build lai

Sau thay doi nay, can tao lai chunk file va build lai index. Neu chi build lai vector tren file `all_chunks.jsonl` cu thi se chua co `parent_context_text` va merge chunk ngan.

Thu tu nen lam:

1. Chay lai pipeline tao `all_chunks.jsonl` cho corpus moi.
2. Build lai SQLite/BM25.
3. Build lai FAISS vector.
4. Chay lai evaluation tren bo 56 cau hoi.

Lenh build index sau khi da co `output/vbpl_combined/all_chunks.jsonl` moi:

```powershell
python -m law_rag.retrieval.sqlite_retrieval_store `
  --chunks output/vbpl_combined/all_chunks.jsonl `
  --output output/vbpl_combined/retrieval/retrieval_store.sqlite

python -m law_rag.retrieval.retrieve_chunks build `
  --chunks output/vbpl_combined/all_chunks.jsonl `
  --output output/vbpl_combined/retrieval/bm25_index.json

$env:EMBEDDING_PROVIDER="openai"
$env:EMBEDDING_MODEL="text-embedding-3-small"

python -m law_rag.retrieval.build_vector_index `
  --chunks output/vbpl_combined/all_chunks.jsonl `
  --output-dir output/vbpl_combined/retrieval/vector-openai `
  --model text-embedding-3-small `
  --batch-size 100 `
  --backend faiss
```

## Cau tra loi phong van ngan gon

Em khong chon chunking mot cach cam tinh. Ban dau em chunk theo Dieu vi van ban phap luat co cau truc ro rang va Dieu la don vi tham chieu tu nhien khi citation. Sau khi chay evaluation, em thay nhieu Dieu qua dai lam embedding bi nhieu, nen em chuyen sang semantic chunking theo Dieu/khoan/diem.

Trade-off la chunk nho hon giup retrieval chinh xac hon, nhung co nguy co mat ngu canh cua toan Dieu. De can bang, em bo sung parent metadata vao searchable text, merge cac chunk qua ngan voi chunk lan can cung parent, va giu gioi han kich thuoc de tranh quay lai van de chunk qua dai.

Huong nay giup tang Recall@5, MRR va citation accuracy, trong khi van kiem soat duoc context cho cau tra loi.
