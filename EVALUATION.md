# Law RAG Evaluation

## Muc tieu

File nay dinh nghia cach danh gia chat luong he thong Law RAG. Muc tieu khong chi la cau tra loi nghe hop ly, ma phai:

- Truy xuat dung van ban phap luat lien quan.
- Tra loi dung trong tam cau hoi.
- Bam sat nguon da retrieve, khong bia them quy dinh.
- Trich dan dung Dieu/Khoan/Van ban.
- Xu ly tot cau hoi thieu du kien va hoi thoai nhieu luot.

Khung danh gia dua tren workflow RAG evaluation cua LangSmith: tao dataset, chay ung dung tren dataset, sau do cham bang evaluator cho correctness, relevance, groundedness va retrieval relevance.

## Don vi danh gia

Moi test case nen gom:

```json
{
  "id": "criminal_injury_001",
  "category": "hinh_su",
  "inputs": {
    "question": "Toi gay thuong tich 18% cho nguoi khac thi bi xu ly the nao?"
  },
  "reference_outputs": {
    "answer_points": [
      "Can xem xet toi co y gay thuong tich hoac gay ton hai cho suc khoe nguoi khac.",
      "Can doi chieu Dieu 134 Bo luat Hinh su.",
      "Ty le 18% la mot tinh tiet quan trong nhung van can xem them hung khi, tinh chat hanh vi, tinh tiet tang nang."
    ],
    "expected_sources": [
      {
        "document_title": "Bo luat Hinh su 2015",
        "article_number": "134"
      }
    ]
  }
}
```

## Bo test nen co

Nen chia dataset thanh cac nhom sau:

| Nhom | Muc dich | So luong goi y |
|---|---|---:|
| Hinh su | Kiem tra toi danh, dieu kien, muc phat, tinh tiet | 10-15 |
| Dan su | Hop dong, thua ke, boi thuong, quyen so huu | 10-15 |
| Lao dong | Hop dong lao dong, nghi viec, luong, BHXH | 8-12 |
| Doanh nghiep | Thanh lap, gop von, nguoi dai dien, nghia vu | 8-12 |
| To tung | Thu tuc, tham quyen, thoi han, quyen khieu nai | 8-12 |
| Cau hoi thieu du kien | Kiem tra kha nang neu nhanh kha nang va hoi bo sung | 10 |
| Hoi thoai nhieu luot | Kiem tra memory va hop nhat facts | 10 |
| Ngoai pham vi corpus | Kiem tra kha nang tu choi/bao khong du nguon | 5-10 |

Tong toi thieu nen co 50 test cases. Neu danh gia nghiem tuc truoc khi demo hoac deploy, nen co 100+ test cases.

## Tieu chi cham diem

Dung thang 1-5 cho cac tieu chi co tinh dinh tinh.

| Diem | Y nghia |
|---:|---|
| 1 | Sai nghiem trong hoac khong dung cau hoi |
| 2 | Co lien quan nhung thieu/sai phan quan trong |
| 3 | Chap nhan duoc, con thieu hoac chua chac |
| 4 | Tot, co sai sot nho |
| 5 | Dung, day du, ro rang, co can cu tot |

### 1. Retrieval relevance

Do nguon retrieve co lien quan den cau hoi khong.

Cham diem:

- 5: Top sources dung trong tam, co dung van ban va dieu/khoan can thiet.
- 4: Co nguon dung nhung van co mot vai chunk nhieu.
- 3: Co lien quan chung, nhung thieu dieu/khoan quan trong.
- 2: Dung linh vuc phap luat nhung sai van ban/dieu trong tam.
- 1: Nguon gan nhu khong lien quan.

Metric bo sung:

- `top_1_correct`: top 1 co dung nguon chinh khong.
- `top_3_contains_expected`: top 3 co chua nguon mong doi khong.
- `top_5_contains_expected`: top 5 co chua nguon mong doi khong.
- `retrieval_noise_count`: so chunk khong lien quan trong top K.

### 2. Citation accuracy

Do trich dan co dung Dieu/Khoan/Van ban khong.

Cham diem:

- 5: Trich dung van ban, dung dieu, dung khoan/diem neu can.
- 4: Dung van ban va dieu, thieu khoan/diem nho.
- 3: Dung van ban, nhung dieu/khoan chua chinh xac hoac qua chung.
- 2: Co trich dan nhung sai phan quan trong.
- 1: Bia trich dan hoac khong co can cu.

Metric bo sung:

- `has_citation`
- `correct_document`
- `correct_article`
- `correct_clause`
- `invented_citation`

### 3. Groundedness

Do cau tra loi co duoc chung minh boi context retrieve khong.

Cham diem:

- 5: Moi nhan dinh phap ly quan trong deu co co so trong nguon.
- 4: Hau het grounded, co mot vai dien giai nhe chua ro nguon.
- 3: Co bam nguon nhung them nhan dinh chua duoc chung minh.
- 2: Nhieu phan suy dien vuot qua context.
- 1: Bia quy dinh, muc phat, dieu kien hoac noi dung khong co trong nguon.

Day la tieu chi bat buoc voi RAG phap luat. Cau tra loi dung ve mat ngon ngu nhung khong grounded van phai cham thap.

### 4. Answer correctness

Do cau tra loi co dung voi dap an chuan hoac y chinh mong doi khong.

Cham diem:

- 5: Bao phu day du cac y bat buoc, khong co noi dung mau thuan.
- 4: Dung phan lon, thieu chi tiet nho.
- 3: Dung y chinh nhung thieu dieu kien/ngoai le quan trong.
- 2: Co mot vai y dung nhung ket luan de gay hieu sai.
- 1: Sai ban chat phap ly.

### 5. Answer relevance

Do cau tra loi co tra loi dung cau hoi nguoi dung khong.

Cham diem:

- 5: Tra loi truc tiep, dung trong tam.
- 4: Dung trong tam, hoi dai hoac hoi thua.
- 3: Co tra loi nhung lan sang noi dung phu.
- 2: Chi lien quan gian tiep.
- 1: Khong tra loi cau hoi.

### 6. Completeness

Do cau tra loi co day du dieu kien, nhanh kha nang, ngoai le quan trong khong.

Cham diem:

- 5: Neu du cac dieu kien, nhanh xu ly, thong tin can bo sung neu co.
- 4: Gan du, thieu mot vai chi tiet it anh huong.
- 3: Co y chinh nhung thieu nhanh kha nang quan trong.
- 2: Qua ngan, de gay ket luan sai.
- 1: Bo sot phan cot loi.

### 7. No overclaiming

Do model co tranh ket luan chac chan khi thieu du kien khong.

Cham diem:

- 5: Phan biet ro dieu co the khang dinh va dieu can xac minh.
- 4: Co canh bao thieu du kien, nhung chua that ro.
- 3: Doi khi ket luan hoi nhanh.
- 2: Thuong ket luan qua muc.
- 1: Khang dinh chac chan du chua du du kien.

### 8. Clarification quality

Danh gia khi cau hoi thieu du kien.

Cham diem:

- 5: Vua neu duoc cac kha nang phap ly, vua hoi 1 cau bo sung cu the nhat.
- 4: Cau hoi bo sung dung nhung chua toi uu.
- 3: Co hoi bo sung nhung hoi hoi chung.
- 2: Chi noi thieu du kien, khong giup nguoi dung tiep tuc.
- 1: Hoi sai trong tam hoac bo qua thong tin da co.

### 9. Multi-turn memory

Danh gia hoi thoai nhieu luot.

Cham diem:

- 5: Nho dung facts, hop nhat thong tin moi, khong tu bia.
- 4: Nho dung phan lon, sai sot nho.
- 3: Nho duoc y chinh nhung thieu mot vai facts.
- 2: Mat ngu canh quan trong.
- 1: Nho sai hoac them facts khong co.

## Evaluator tu dong goi y

Neu dung LangSmith hoac script rieng, nen co cac evaluator sau:

| Evaluator | So sanh | Can reference answer |
|---|---|---|
| `answer_correctness` | answer vs reference answer/answer points | Co |
| `answer_relevance` | answer vs question | Khong |
| `groundedness` | answer vs retrieved sources | Khong |
| `retrieval_relevance` | retrieved sources vs question | Khong |
| `citation_accuracy` | returned citations vs expected sources | Co |
| `no_overclaiming` | answer vs question + retrieved sources | Khong |
| `clarification_quality` | answer vs missing facts | Tuy case |
| `memory_quality` | final answer/session facts vs conversation history | Co voi multi-turn |

## Output can luu moi lan chay

Moi lan chay evaluation nen luu:

```json
{
  "case_id": "criminal_injury_001",
  "question": "...",
  "answer": "...",
  "sources": [
    {
      "documentTitle": "...",
      "articleNumber": "...",
      "clauseNumber": "...",
      "chunkText": "...",
      "relevanceScore": 0.031,
      "retrievalOrigin": "hybrid"
    }
  ],
  "scores": {
    "retrieval_relevance": 5,
    "citation_accuracy": 5,
    "groundedness": 4,
    "answer_correctness": 4,
    "answer_relevance": 5,
    "completeness": 4,
    "no_overclaiming": 5,
    "clarification_quality": null,
    "memory_quality": null,
    "overall": 4.6
  },
  "metadata": {
    "retrieval_mode": "hybrid",
    "vector_backend": "faiss",
    "top_k": 5,
    "query_rewrite": true,
    "chat_model": "gpt-5.4-mini",
    "embedding_model": "text-embedding-3-small",
    "latency_ms": 12345
  }
}
```

## Cach tinh overall score

Goi y trong giai do dau:

```text
overall =
  0.20 * retrieval_relevance +
  0.15 * citation_accuracy +
  0.20 * groundedness +
  0.20 * answer_correctness +
  0.10 * answer_relevance +
  0.10 * completeness +
  0.05 * no_overclaiming
```

Voi test case hoi thoai nhieu luot, them `memory_quality`:

```text
overall_multi_turn =
  0.15 * retrieval_relevance +
  0.15 * citation_accuracy +
  0.20 * groundedness +
  0.15 * answer_correctness +
  0.10 * completeness +
  0.10 * no_overclaiming +
  0.15 * memory_quality
```

## Cac experiment nen so sanh

Chay cung mot dataset voi cac cau hinh sau:

| Experiment | Retrieval mode | Query rewrite | Top K | Muc dich |
|---|---|---:|---:|---|
| `bm25_no_rewrite_k5` | bm25 | false | 5 | Baseline keyword |
| `vector_no_rewrite_k5` | vector | false | 5 | Baseline semantic |
| `hybrid_no_rewrite_k5` | hybrid | false | 5 | So sanh hybrid khong rewrite |
| `hybrid_rewrite_k5` | hybrid | true | 5 | Cau hinh mac dinh hien tai |
| `hybrid_rewrite_k3` | hybrid | true | 3 | Giam nhieu context |
| `hybrid_rewrite_k10` | hybrid | true | 10 | Tang do phu context |

Nen chon cau hinh tot nhat dua tren:

- `groundedness >= 4.0`
- `citation_accuracy >= 4.0`
- `retrieval_relevance >= 4.0`
- latency chap nhan duoc
- chi phi moi cau hoi chap nhan duoc

## Mau bang bao cao

| Metric | Target | Ket qua | Dat |
|---|---:|---:|---|
| Retrieval relevance avg | >= 4.0 | TBD | TBD |
| Citation accuracy avg | >= 4.0 | TBD | TBD |
| Groundedness avg | >= 4.2 | TBD | TBD |
| Answer correctness avg | >= 4.0 | TBD | TBD |
| Top-3 contains expected source | >= 80% | TBD | TBD |
| Hallucination rate | <= 5% | TBD | TBD |
| Avg latency | <= 15s | TBD | TBD |
| Error rate | <= 2% | TBD | TBD |

## Checklist truoc khi demo/deploy

- Dataset co it nhat 50 test cases.
- Co test case cho cau hoi thieu du kien.
- Co test case multi-turn.
- Co test case ngoai pham vi corpus.
- Da so sanh BM25, vector va hybrid.
- Da so sanh query rewrite bat/tat.
- Da kiem tra citation khong bia Dieu/Khoan.
- Da kiem tra answer khong vuot qua context.
- Da luu ket qua evaluation theo tung experiment.
