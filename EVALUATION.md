# Law RAG Evaluation

## Mục tiêu

File này định nghĩa cách đánh giá chất lượng hệ thống Law RAG. Mục tiêu không chỉ là câu trả lời nghe hợp lý, mà phải:

- Truy xuất đúng văn bản pháp luật liên quan.
- Trả lời đúng trọng tâm câu hỏi.
- Bám sát nguồn đã retrieve, không bịa thêm quy định.
- Trích dẫn đúng Điều/Khoản/Văn bản.
- Xử lý tốt câu hỏi thiếu dữ kiện và hội thoại nhiều lượt.

Khung đánh giá dựa trên workflow RAG evaluation: tạo dataset, chạy ứng dụng trên dataset, sau đó chấm bằng evaluator deterministic cho correctness, relevance, groundedness, citation accuracy và retrieval relevance. Hệ thống hiện không dùng LLM làm judge.

## Đơn vị đánh giá

Mỗi test case nên gồm:

```json
{
  "id": "criminal_injury_001",
  "category": "hinh_su",
  "inputs": {
    "question": "Tôi gây thương tích 18% cho người khác thì bị xử lý thế nào?"
  },
  "reference_outputs": {
    "answer_points": [
      "Cần xem xét tội cố ý gây thương tích hoặc gây tổn hại cho sức khỏe của người khác.",
      "Cần đối chiếu Điều 134 Bộ luật Hình sự.",
      "Tỷ lệ 18% là một tình tiết quan trọng nhưng vẫn cần xem thêm hung khí, tính chất hành vi, tình tiết tăng nặng."
    ],
    "expected_sources": [
      {
        "document_title_contains": "hinh su",
        "article_number": "134"
      }
    ],
    "required_terms": [
      "Điều 134",
      "tỷ lệ tổn thương"
    ],
    "forbidden_claims": [
      "chắc chắn bị đi tù",
      "không bị xử lý"
    ]
  }
}
```

Ý nghĩa các trường:

- `question`: câu hỏi đầu vào, nên có cả câu hỏi chuẩn pháp lý và câu hỏi đời thường.
- `answer_points`: các ý bắt buộc mà câu trả lời đúng nên bao phủ.
- `expected_sources`: văn bản/điều/khoản mong đợi phải được retrieve.
- `required_terms`: thuật ngữ hoặc số liệu quan trọng nên xuất hiện trong câu trả lời.
- `forbidden_claims`: các kết luận sai hoặc quá chắc chắn cần tránh.

## Bộ test nên có

Nên chia dataset thành các nhóm sau:

| Nhóm | Mục đích | Số lượng gợi ý |
|---|---|---:|
| Hình sự | Kiểm tra tội danh, điều kiện, mức phạt, tình tiết | 10-15 |
| Dân sự | Hợp đồng, thừa kế, bồi thường, quyền sở hữu | 10-15 |
| Lao động | Hợp đồng lao động, nghỉ việc, lương, BHXH | 8-12 |
| Doanh nghiệp | Thành lập, góp vốn, người đại diện, nghĩa vụ | 8-12 |
| Tố tụng | Thủ tục, thẩm quyền, thời hạn, quyền khiếu nại | 8-12 |
| Câu hỏi đời thường | Kiểm tra khả năng hiểu cách hỏi tự nhiên của người dùng | 10-20 |
| Câu hỏi thiếu dữ kiện | Kiểm tra khả năng nêu các khả năng và hỏi bổ sung | 10 |
| Hội thoại nhiều lượt | Kiểm tra memory và hợp nhất facts | 10 |
| Ngoài phạm vi corpus | Kiểm tra khả năng từ chối hoặc báo không đủ nguồn | 5-10 |

Tổng tối thiểu nên có 50 test cases. Nếu đánh giá nghiêm túc trước khi demo hoặc deploy, nên có 100+ test cases.

## Tiêu chí chấm điểm

Dùng thang 1-5 cho các tiêu chí có tính định tính.

| Điểm | Ý nghĩa |
|---:|---|
| 1 | Sai nghiêm trọng hoặc không đúng câu hỏi |
| 2 | Có liên quan nhưng thiếu/sai phần quan trọng |
| 3 | Chấp nhận được, còn thiếu hoặc chưa chắc |
| 4 | Tốt, có sai sót nhỏ |
| 5 | Đúng, đầy đủ, rõ ràng, có căn cứ tốt |

## Metric retrieval

### 1. Retrieval relevance

Đo nguồn retrieve có liên quan đến câu hỏi không.

Chấm điểm:

- 5: Top sources đúng trọng tâm, có đúng văn bản và điều/khoản cần thiết.
- 4: Có nguồn đúng nhưng vẫn có một vài chunk nhiễu.
- 3: Có liên quan chung, nhưng thiếu điều/khoản quan trọng.
- 2: Đúng lĩnh vực pháp luật nhưng sai văn bản/điều trọng tâm.
- 1: Nguồn gần như không liên quan.

Metric bổ sung:

- `top_1_correct`: top 1 có đúng nguồn chính không.
- `top_3_contains_expected`: top 3 có chứa nguồn mong đợi không.
- `top_5_contains_expected`: top 5 có chứa nguồn mong đợi không.
- `precision_at_3`: tỷ lệ chunk đúng trong top 3.
- `precision_at_5`: tỷ lệ chunk đúng trong top 5.
- `recall_at_3`: tỷ lệ expected sources xuất hiện trong top 3.
- `recall_at_5`: tỷ lệ expected sources xuất hiện trong top 5.
- `mrr`: reciprocal rank của nguồn đúng đầu tiên.
- `ndcg_at_5`: chất lượng thứ tự ranking trong top 5.
- `duplicate_rate`: tỷ lệ chunk bị lặp theo cùng định danh văn bản/điều/khoản.

### 2. Citation accuracy

Đo trích dẫn có đúng Điều/Khoản/Văn bản không.

Chấm điểm:

- 5: Trích đúng văn bản, đúng điều, đúng khoản/điểm nếu cần.
- 4: Đúng văn bản và điều, thiếu khoản/điểm nhỏ.
- 3: Đúng văn bản, nhưng điều/khoản chưa chính xác hoặc quá chung.
- 2: Có trích dẫn nhưng sai phần quan trọng.
- 1: Bịa trích dẫn hoặc không có căn cứ.

Metric bổ sung:

- `has_citation`
- `correct_document`
- `correct_article`
- `correct_clause`
- `invented_citation`

## Metric answer

### 3. Groundedness

Đo câu trả lời có được chứng minh bởi context retrieve không.

Chấm điểm:

- 5: Mọi nhận định pháp lý quan trọng đều có cơ sở trong nguồn.
- 4: Hầu hết grounded, có một vài diễn giải nhẹ chưa rõ nguồn.
- 3: Có bám nguồn nhưng thêm nhận định chưa được chứng minh.
- 2: Nhiều phần suy diễn vượt quá context.
- 1: Bịa quy định, mức phạt, điều kiện hoặc nội dung không có trong nguồn.

Đây là tiêu chí bắt buộc với RAG pháp luật. Câu trả lời đúng về mặt ngôn ngữ nhưng không grounded vẫn phải chấm thấp.

Trong evaluator hiện tại, groundedness được kiểm tra bằng rule:

- Citation trong answer có nằm trong retrieved sources không.
- Số liệu/ngưỡng trong answer có xuất hiện trong context không.
- `required_terms` có được hỗ trợ bởi retrieved text không.
- Nếu không retrieve được nguồn nào thì groundedness rất thấp.

### 4. Answer correctness

Đo câu trả lời có đúng với đáp án chuẩn hoặc ý chính mong đợi không.

Chấm điểm:

- 5: Bao phủ đầy đủ các ý bắt buộc, không có nội dung mâu thuẫn.
- 4: Đúng phần lớn, thiếu chi tiết nhỏ.
- 3: Đúng ý chính nhưng thiếu điều kiện/ngoại lệ quan trọng.
- 2: Có một vài ý đúng nhưng kết luận dễ gây hiểu sai.
- 1: Sai bản chất pháp lý.

Evaluator hiện tại so khớp answer với `answer_points` bằng keyword overlap.

### 5. Answer relevance

Đo câu trả lời có trả lời đúng câu hỏi người dùng không.

Chấm điểm:

- 5: Trả lời trực tiếp, đúng trọng tâm.
- 4: Đúng trọng tâm, hơi dài hoặc hơi thừa.
- 3: Có trả lời nhưng lan sang nội dung phụ.
- 2: Chỉ liên quan gián tiếp.
- 1: Không trả lời câu hỏi.

### 6. Completeness

Đo câu trả lời có đầy đủ điều kiện, nhánh khả năng, ngoại lệ quan trọng không.

Chấm điểm:

- 5: Nêu đủ các điều kiện, nhánh xử lý, thông tin cần bổ sung nếu có.
- 4: Gần đủ, thiếu một vài chi tiết ít ảnh hưởng.
- 3: Có ý chính nhưng thiếu nhánh khả năng quan trọng.
- 2: Quá ngắn, dễ gây kết luận sai.
- 1: Bỏ sót phần cốt lõi.

### 7. No overclaiming

Đo model có tránh kết luận chắc chắn khi thiếu dữ kiện không.

Chấm điểm:

- 5: Phân biệt rõ điều có thể khẳng định và điều cần xác minh.
- 4: Có cảnh báo thiếu dữ kiện, nhưng chưa thật rõ.
- 3: Đôi khi kết luận hơi nhanh.
- 2: Thường kết luận quá mức.
- 1: Khẳng định chắc chắn dù chưa đủ dữ kiện.

Evaluator hiện tại hỗ trợ trường `forbidden_claims` để phát hiện một số kết luận sai hoặc quá chắc chắn.

### 8. Clarification quality

Đánh giá khi câu hỏi thiếu dữ kiện.

Chấm điểm:

- 5: Vừa nêu được các khả năng pháp lý, vừa hỏi 1 câu bổ sung cụ thể nhất.
- 4: Câu hỏi bổ sung đúng nhưng chưa tối ưu.
- 3: Có hỏi bổ sung nhưng hơi chung.
- 2: Chỉ nói thiếu dữ kiện, không giúp người dùng tiếp tục.
- 1: Hỏi sai trọng tâm hoặc bỏ qua thông tin đã có.

### 9. Multi-turn memory

Đánh giá hội thoại nhiều lượt.

Chấm điểm:

- 5: Nhớ đúng facts, hợp nhất thông tin mới, không tự bịa.
- 4: Nhớ đúng phần lớn, sai sót nhỏ.
- 3: Nhớ được ý chính nhưng thiếu một vài facts.
- 2: Mất ngữ cảnh quan trọng.
- 1: Nhớ sai hoặc thêm facts không có.

## Evaluator tự động gợi ý

Vì không dùng LLM judge, evaluator nên ưu tiên các metric deterministic:

| Evaluator | So sánh | Cần reference answer |
|---|---|---|
| `answer_correctness` | answer vs answer points | Có |
| `answer_relevance` | answer vs question | Không |
| `groundedness` | answer vs retrieved sources | Không |
| `retrieval_relevance` | retrieved sources vs expected sources | Có |
| `citation_accuracy` | returned citations vs expected sources | Có |
| `no_overclaiming` | answer vs forbidden claims | Có nếu muốn chặt |
| `clarification_quality` | answer vs missing facts | Tùy case |
| `memory_quality` | final answer/session facts vs conversation history | Có với multi-turn |

## Output cần lưu mỗi lần chạy

Mỗi lần chạy evaluation nên lưu:

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
    "precision_at_3": 0.333,
    "recall_at_3": 1.0,
    "mrr": 1.0,
    "ndcg_at_5": 0.85,
    "retrieval_relevance": 5,
    "citation_accuracy": 5,
    "groundedness": 4,
    "answer_correctness": 4,
    "answer_relevance": 5,
    "completeness": 4,
    "no_overclaiming": 4,
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

## Cách hiểu và cách tính từng thông số

Phần này mô tả các thông số đang được sinh bởi `evaluate_law_rag.py`. Các metric dạng `*_at_k`, `mrr`, `ndcg_at_5`, `duplicate_rate`, `required_term_coverage`, `best_reference_token_iou` nằm trong thang `0.0-1.0`. Các metric như `retrieval_relevance`, `citation_accuracy`, `groundedness`, `answer_correctness`, `answer_relevance`, `completeness`, `no_overclaiming`, `overall` nằm trong thang `1-5`. Nếu dataset không khai báo dữ liệu chuẩn cần thiết, một số metric sẽ là `None` và không được tính vào trung bình.

### Quy tắc xác định một source đúng

Một retrieved source được xem là khớp với một `expected_sources` khi thỏa tất cả điều kiện mà expected source khai báo:

- Nếu có `source_file_contains`, chuỗi này phải xuất hiện trong định danh file/source sau khi normalize.
- Nếu có `document_title_contains`, chuỗi này phải xuất hiện trong tiêu đề hoặc định danh tài liệu sau khi normalize.
- Nếu có `article_number`, số điều của source phải bằng số điều mong đợi.
- Nếu có `clause_number`, số khoản của source phải bằng số khoản mong đợi.

Evaluator normalize text trước khi so khớp: chuyển về chữ thường, bỏ dấu tiếng Việt, bỏ ký tự đặc biệt và gom khoảng trắng. Vì vậy `Điều 134`, `dieu 134` và các biến thể viết hoa/thường được xem là cùng một khóa.

### `top_1_correct`

Cho biết kết quả retrieve đầu tiên có khớp với ít nhất một source mong đợi không.

```text
top_1_correct = true nếu retrieved[0] khớp expected_sources
top_1_correct = false nếu top 1 không khớp hoặc không có retrieved source
top_1_correct = None nếu test case không có expected_sources
```

Metric này quan trọng vì source top 1 thường có ảnh hưởng lớn nhất tới prompt và câu trả lời cuối.

### `top_3_contains_expected` và `top_5_contains_expected`

Cho biết trong top 3 hoặc top 5 retrieved sources có ít nhất một source mong đợi hay không.

```text
top_k_contains_expected = true nếu tồn tại source trong retrieved[:k] khớp expected_sources
```

Metric này không đo đủ hay thiếu toàn bộ nguồn mong đợi, chỉ đo việc top-k có chứa ít nhất một nguồn đúng.

### `precision_at_3` và `precision_at_5`

Đo độ sạch của top-k, tức trong các chunk được đưa vào context có bao nhiêu chunk thật sự đúng với source mong đợi.

```text
precision_at_k = số retrieved source đúng trong top k / số retrieved source thực tế trong top k
```

Ví dụ top 5 trả về 5 chunk, trong đó 2 chunk khớp `expected_sources`:

```text
precision_at_5 = 2 / 5 = 0.4
```

Precision thấp nghĩa là context có nhiều nhiễu. Trong RAG pháp luật, precision thấp có thể làm prompt dài hơn, tăng latency và tăng nguy cơ model dựa vào đoạn luật phụ không đúng trọng tâm.

### `recall_at_3` và `recall_at_5`

Đo độ phủ của retrieval, tức hệ thống có tìm được bao nhiêu source mong đợi trong top-k.

```text
recall_at_k = số expected source xuất hiện trong top k / tổng số expected source
```

Ví dụ một test case có 2 source mong đợi, top 5 tìm được 1 source:

```text
recall_at_5 = 1 / 2 = 0.5
```

Trong legal RAG, recall thường rất quan trọng: nếu điều luật đúng không được retrieve, model khó trả lời có căn cứ dù phần generation tốt.

### `mrr`

`mrr` là Mean Reciprocal Rank cho từng case, đo source đúng đầu tiên xuất hiện sớm đến đâu trong danh sách retrieve.

```text
mrr = 1 / rank_của_source_đúng_đầu_tiên
```

Ví dụ:

- Source đúng nằm ở hạng 1: `mrr = 1.0`
- Source đúng nằm ở hạng 2: `mrr = 0.5`
- Source đúng nằm ở hạng 5: `mrr = 0.2`
- Không có source đúng: `mrr = 0.0`

MRR cao nghĩa là ranking tốt, source đúng được đặt sớm.

### `ndcg_at_5`

`ndcg_at_5` đo chất lượng thứ tự ranking trong top 5, có tính đến mức độ khớp một phần. Evaluator gán gain cho mỗi source:

- `3`: khớp đầy đủ expected source.
- `2`: đúng document và đúng article.
- `1`: đúng document hoặc đúng phần clause/document ở mức yếu.
- `0`: không liên quan.

Công thức:

```text
DCG@5 = tổng((2^gain - 1) / log2(vị_trí + 1))
NDCG@5 = DCG@5 / DCG_lý_tưởng@5
```

Giá trị càng gần `1.0` thì thứ tự retrieve càng tốt. NDCG khác recall ở chỗ nó phạt trường hợp source đúng xuất hiện quá thấp trong top-k.

### `matched_expected_sources` và `expected_source_count`

Hai thông số này cho biết số source chuẩn đã được retrieve ở bất kỳ vị trí nào trong danh sách kết quả.

```text
matched_expected_sources = số expected source có ít nhất một retrieved source khớp
expected_source_count = tổng số expected source trong test case
```

Chúng giúp đọc nhanh lý do vì sao `recall_at_k` hoặc `citation_accuracy` cao/thấp.

### `citation_accuracy`

Trong evaluator hiện tại, metric này được suy ra từ việc retrieved sources có bao phủ `expected_sources` hay không:

```text
citation_accuracy = 5 nếu matched_expected_sources == expected_source_count
citation_accuracy = 3 nếu matched_expected_sources > 0 nhưng chưa đủ
citation_accuracy = 1 nếu không khớp expected source nào
citation_accuracy = None nếu không có expected_sources
```

Lưu ý: đây là heuristic ở tầng retrieval/citation source, chưa phải kiểm chứng pháp lý sâu từng câu trích dẫn trong answer. Khi đọc kết quả cần kết hợp với `groundedness`, `unsupported_citations` và kiểm tra thủ công các case rủi ro.

### `retrieval_relevance`

Đây là điểm 1-5 tổng hợp chất lượng retrieval của một case:

```text
5 nếu recall_at_5 == 1 và mrr == 1
4 nếu recall_at_5 >= 0.8
3 nếu top_5_contains_expected == true
2 nếu có retrieved source nhưng không chứa expected source trong top 5
1 nếu không retrieve được source nào
```

Metric này dễ đọc hơn các tỷ lệ top-k riêng lẻ, nên được dùng trong `overall`.

### `matched_answer_points`, `answer_point_count`, `missing_answer_points`

Các thông số này đo câu trả lời có bao phủ các ý chuẩn trong `answer_points` không.

Với mỗi answer point, evaluator:

- Normalize answer và answer point.
- Tách các token có độ dài từ 4 ký tự trở lên.
- Tính tỷ lệ token của answer point xuất hiện trong answer.
- Xem answer point là đã khớp nếu tỷ lệ token khớp `>= 0.35`.

```text
matched_answer_points = số answer_points được match
answer_point_count = tổng số answer_points
missing_answer_points = danh sách answer_points chưa match
```

Đây là keyword-overlap heuristic, nên có thể bỏ sót trường hợp model diễn đạt đúng nhưng dùng từ khác.

### `answer_correctness`

`answer_correctness` được lấy từ `answer_correctness_heuristic`, dựa trên tỷ lệ answer point được bao phủ:

```text
coverage = matched_answer_points / answer_point_count

5 nếu coverage >= 0.90
4 nếu coverage >= 0.70
3 nếu coverage >= 0.45
2 nếu coverage > 0
1 nếu coverage == 0
None nếu không có answer_points
```

Metric này đo đúng/sai theo goldset, không tự chứng minh câu trả lời có bám context hay không. Vì vậy cần đọc cùng `groundedness`.

### `completeness`

Trong evaluator hiện tại, `completeness` dùng cùng giá trị với `answer_correctness_heuristic`.

```text
completeness = answer_correctness
```

Ý nghĩa thực tế là mức độ câu trả lời bao phủ đủ các ý bắt buộc trong `answer_points`. Nếu muốn tách riêng correctness và completeness về sau, cần thêm rubric hoặc field reference riêng cho lỗi sai pháp lý và ý còn thiếu.

### `matched_required_terms`, `required_term_count`, `missing_required_terms`, `required_term_coverage`

Các metric này kiểm tra thuật ngữ bắt buộc trong `required_terms`.

```text
matched_required_terms = số required_terms xuất hiện trong answer
required_term_count = tổng số required_terms
missing_required_terms = danh sách thuật ngữ chưa xuất hiện
required_term_coverage = matched_required_terms / required_term_count
```

Nếu không khai báo `required_terms`, `required_term_coverage = None`.

### `forbidden_claim_hits`, `forbidden_claim_count`, `no_forbidden_claims`

Các metric này phát hiện những kết luận sai hoặc quá chắc chắn được khai báo trong `forbidden_claims`.

```text
forbidden_claim_hits = danh sách forbidden claims xuất hiện trong answer
forbidden_claim_count = số forbidden claims bị hit
no_forbidden_claims = true nếu không có claim cấm nào xuất hiện
```

So khớp cũng dùng normalize text. Đây là blacklist heuristic, chỉ bắt được các lỗi đã biết trước.

### `no_overclaiming`

Trong evaluator hiện tại:

```text
no_overclaiming = 1 nếu forbidden_claim_hits không rỗng
no_overclaiming = 4 nếu không hit forbidden_claims
```

Điểm tối đa hiện là `4`, không phải `5`, vì evaluator deterministic chỉ xác nhận không thấy claim cấm đã khai báo; nó chưa đủ mạnh để khẳng định câu trả lời hoàn toàn không overclaim.

### `groundedness`

`groundedness` đo câu trả lời có bám retrieved context không. Evaluator kiểm tra ba nhóm tín hiệu:

- Citation trong answer, ví dụ `Điều 134`, `Khoản 1`, có xuất hiện trong metadata của retrieved sources không.
- Số liệu trong answer, ví dụ `18%`, `30 ngày`, có xuất hiện trong retrieved text không.
- `required_terms` có được hỗ trợ bởi retrieved text không.

Cách tính hiện tại:

```text
1 nếu không có retrieved source
2 nếu answer có citation không xuất hiện trong retrieved sources
2 nếu retrieved text không chứa required_terms nào
3 nếu answer có số liệu không xuất hiện trong retrieved text
5 nếu citation/required_terms được hỗ trợ và không có lỗi trên
4 nếu không có citation/required_terms nhưng retrieved source có metadata điều/khoản
3 nếu không có citation/required_terms và retrieved source cũng thiếu metadata điều/khoản
```

Evaluator cũng lưu thêm:

```text
unsupported_citations = các citation trong answer không thấy ở retrieved sources
unsupported_numbers = các số liệu trong answer không thấy ở retrieved text
retrieved_required_term_coverage = tỷ lệ required_terms xuất hiện trong retrieved text
```

Với bài toán pháp luật, nên ưu tiên debug các case `groundedness <= 3`.

### `answer_relevance`

Trong evaluator hiện tại, `answer_relevance` là heuristic rất đơn giản dựa trên độ dài answer:

```text
5 nếu answer có ít nhất 80 ký tự sau khi strip
3 nếu answer có nội dung nhưng dưới 80 ký tự
1 nếu answer rỗng
```

Metric này chưa hiểu ngữ nghĩa câu hỏi. Nó chủ yếu phát hiện answer rỗng hoặc quá ngắn, không thay thế được đánh giá thủ công về việc trả lời đúng trọng tâm.

### `best_reference_token_iou`

Metric này đo overlap token tốt nhất giữa các retrieved source và các reference text gồm `answer_points` cộng `required_terms`.

```text
IoU = số token giao nhau / số token hợp nhất
best_reference_token_iou = IoU cao nhất giữa mọi cặp retrieved source và reference text
```

Giá trị cao gợi ý context retrieve có nhiều từ vựng trùng với goldset. Đây là tín hiệu phụ, không được đưa vào `overall`.

### `duplicate_rate`

Đo tỷ lệ source bị lặp trong danh sách retrieved. Identity của source được tạo từ các trường `source_file`, `document_title`, `documentTitle`, `article_number`, `clause_number`.

```text
duplicate_rate = (số retrieved source - số identity duy nhất) / số retrieved source
```

Ví dụ retrieve 5 chunk nhưng chỉ có 4 identity duy nhất:

```text
duplicate_rate = (5 - 4) / 5 = 0.2
```

Duplicate rate cao nghĩa là context bị chiếm bởi các đoạn quá giống nhau, có thể làm giảm độ phủ.

### `overall`

`overall` là trung bình có trọng số của các metric chính. Các metric có giá trị `None` bị loại khỏi mẫu số, sau đó điểm được làm tròn 2 chữ số thập phân.

```text
overall = tổng(score_i * weight_i) / tổng(weight_i của các score không None)
```

Trọng số mặc định được mô tả ở mục tiếp theo.

### `latency_ms`

`latency_ms` là thời gian chạy end-to-end cho một test case, tính từ ngay trước khi gọi `answer_question(...)` đến khi nhận kết quả.

```text
latency_ms = int((time.perf_counter() - started) * 1000)
```

Metric này bao gồm thời gian rewrite query, retrieval, gọi model, xử lý memory và format answer nếu các bước đó nằm trong `answer_question`.

## Cách tính overall score

Gợi ý trong giai đoạn đầu:

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

Với test case hội thoại nhiều lượt, có thể thêm `memory_quality`:

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

## Các experiment nên so sánh

Chạy cùng một dataset với các cấu hình sau:

| Experiment | Retrieval mode | Query rewrite | Top K | Mục đích |
|---|---|---:|---:|---|
| `bm25_no_rewrite_k5` | bm25 | false | 5 | Baseline keyword |
| `vector_no_rewrite_k5` | vector | false | 5 | Baseline semantic |
| `hybrid_no_rewrite_k5` | hybrid | false | 5 | So sánh hybrid không rewrite |
| `hybrid_rewrite_k5` | hybrid | true | 5 | Cấu hình mặc định hiện tại |
| `hybrid_rewrite_k3` | hybrid | true | 3 | Giảm nhiễu context |
| `hybrid_rewrite_k10` | hybrid | true | 10 | Tăng độ phủ context |

Nên chọn cấu hình tốt nhất dựa trên:

- `groundedness >= 4.0`
- `citation_accuracy >= 4.0`
- `retrieval_relevance >= 4.0`
- `recall_at_5 >= 0.9`
- `mrr >= 0.8`
- latency chấp nhận được
- chi phí mỗi câu hỏi chấp nhận được

## Mẫu bảng báo cáo

| Metric | Target | Kết quả | Đạt |
|---|---:|---:|---|
| Retrieval relevance avg | >= 4.0 | TBD | TBD |
| Citation accuracy avg | >= 4.0 | TBD | TBD |
| Groundedness avg | >= 4.2 | TBD | TBD |
| Answer correctness avg | >= 4.0 | TBD | TBD |
| Top-3 contains expected source | >= 80% | TBD | TBD |
| Recall@5 | >= 90% | TBD | TBD |
| MRR | >= 0.8 | TBD | TBD |
| Hallucination rate | <= 5% | TBD | TBD |
| Avg latency | <= 15s | TBD | TBD |
| Error rate | <= 2% | TBD | TBD |

## Checklist trước khi demo/deploy

- Dataset có ít nhất 50 test cases.
- Có test case cho câu hỏi đời thường.
- Có test case cho câu hỏi thiếu dữ kiện.
- Có test case multi-turn.
- Có test case ngoài phạm vi corpus.
- Đã so sánh BM25, vector và hybrid.
- Đã so sánh query rewrite bật/tắt.
- Đã kiểm tra citation không bịa Điều/Khoản.
- Đã kiểm tra answer không vượt quá context.
- Đã lưu kết quả evaluation theo từng experiment.
- Đã xem các biểu đồ trong `evaluate_law_rag.ipynb`.
