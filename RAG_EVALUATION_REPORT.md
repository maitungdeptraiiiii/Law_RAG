# Báo cáo đánh giá kết quả Law RAG

## Nguồn số liệu

Báo cáo này dựa trên lần chạy evaluation gần nhất:

- File kết quả: `output/eval/runs/eval-1778645257.json`
- Số test case: `48`
- Bao gồm cả câu hỏi chuẩn pháp lý và câu hỏi đời thường như `tôi lỡ đánh người ta...`, `tôi muốn nghỉ việc...`, `mua hàng bị lỗi...`
- Evaluator: deterministic, không dùng LLM judge

## Tóm tắt kết quả

| Metric | Kết quả | Đánh giá |
|---|---:|---|
| `overall` | `4.45 / 5` | Tốt |
| `recall_at_3` | `0.90` | Tốt |
| `recall_at_5` | `0.93` | Tốt |
| `top_3_contains_expected_rate` | `0.917` | Tốt |
| `mrr` | `0.81` | Khá tốt |
| `ndcg_at_5` | `0.73` | Khá |
| `precision_at_3` | `0.45` | Trung bình |
| `precision_at_5` | `0.34` | Thấp |
| `citation_accuracy` | `4.71 / 5` | Rất tốt |
| `groundedness` | `3.21 / 5` | Trung bình |
| `answer_correctness` | `4.98 / 5` | Rất tốt |
| `completeness` | `4.98 / 5` | Rất tốt |
| `latency_ms_avg` | `13.95s` | Hơi cao |
| `latency_ms_max` | `28.78s` | Cao |

## Nhận định tổng quan

Hệ thống hiện tại có chất lượng retrieval tương đối tốt. Với `recall_at_5 = 0.93`, trong đa số trường hợp top 5 kết quả đã chứa nguồn luật mong đợi. `top_3_contains_expected_rate = 0.917` cũng cho thấy nguồn đúng thường xuất hiện rất sớm, phù hợp với yêu cầu của một hệ thống RAG pháp luật.

Tuy nhiên, `precision_at_3 = 0.45` và `precision_at_5 = 0.34` cho thấy top-k vẫn còn nhiều chunk nhiễu. Điều này chưa phải lỗi nghiêm trọng nếu nguồn đúng vẫn xuất hiện trong top-k, nhưng trong thực tế có thể làm prompt dài hơn, tăng latency và tăng nguy cơ câu trả lời bị kéo theo nội dung phụ.

Điểm mạnh nhất là `answer_correctness = 4.98` và `completeness = 4.98`. Khi hệ thống retrieve được đúng nguồn, câu trả lời cuối thường bao phủ gần đủ các ý chính trong goldset.

Điểm yếu chính là `groundedness = 3.21`. Mức này chưa đủ tốt cho bài toán pháp luật nếu triển khai nghiêm túc, vì legal RAG cần câu trả lời phải bám rất chặt vào văn bản được retrieve. Một phần có thể đến từ evaluator deterministic còn nghiêm với số liệu/citation, nhưng vẫn nên xem đây là tín hiệu cần cải thiện.

## Đánh giá so với thực tế sử dụng

### Có ổn để demo không?

Có. Với `overall = 4.45`, `recall_at_5 = 0.93` và `citation_accuracy = 4.71`, hệ thống đủ ổn để demo luồng hỏi đáp pháp luật, đặc biệt khi cần chứng minh khả năng:

- Tìm đúng văn bản/điều luật liên quan.
- Trả lời có trích dẫn.
- Xử lý được cả câu hỏi đời thường.
- Có bộ evaluation đo được chất lượng thay vì chỉ đánh giá cảm tính.

### Có ổn để dùng production chưa?

Chưa nên coi là production-ready cho tư vấn pháp lý nghiêm túc. Lý do chính:

- `groundedness = 3.21` còn thấp so với kỳ vọng của legal RAG.
- `precision_at_5 = 0.34` nghĩa là nhiều context không thật sự liên quan vẫn được đưa vào prompt.
- Latency trung bình gần `14s`, max gần `29s`, có thể gây chậm trong UI chat.
- Dataset mới có `48` case, chưa đủ rộng để bao phủ nhiều tình huống pháp luật thực tế.

Mức mục tiêu hợp lý trước khi triển khai nghiêm túc:

| Metric | Hiện tại | Mục tiêu |
|---|---:|---:|
| `recall_at_5` | `0.93` | `>= 0.95` |
| `mrr` | `0.81` | `>= 0.88` |
| `ndcg_at_5` | `0.73` | `>= 0.85` |
| `precision_at_5` | `0.34` | `>= 0.50` |
| `citation_accuracy` | `4.71` | `>= 4.5` |
| `groundedness` | `3.21` | `>= 4.2` |
| `overall` | `4.45` | `>= 4.5` |
| Avg latency | `13.95s` | `<= 10s` |

## Giải thích các thông số chính

### `recall_at_k`

Đo trong top-k kết quả retrieve có chứa nguồn đúng không.

Kết quả hiện tại:

- `recall_at_3 = 0.90`
- `recall_at_5 = 0.93`

Đây là điểm tốt. Trong legal RAG, recall thường quan trọng hơn precision ở bước đầu, vì nếu không retrieve được điều luật đúng thì model rất khó trả lời grounded.

### `precision_at_k`

Đo tỷ lệ chunk đúng trong top-k.

Kết quả hiện tại:

- `precision_at_3 = 0.45`
- `precision_at_5 = 0.34`

Mức này còn thấp. Nghĩa là hệ thống thường lấy được nguồn đúng, nhưng cũng lấy kèm nhiều chunk chưa cần thiết. Nên cải thiện bằng reranking, lọc trùng điều luật, hoặc giảm top-k trong một số chế độ.

### `mrr`

Đo nguồn đúng đầu tiên nằm cao hay thấp trong ranking. `mrr = 0.81` là khá tốt, cho thấy nguồn đúng thường nằm gần đầu.

Nếu cải thiện ranking tốt, chỉ số này nên tăng lên khoảng `0.88+`.

### `ndcg_at_5`

Đo chất lượng thứ tự trong top 5, có tính đến mức liên quan. `ndcg_at_5 = 0.73` là khá nhưng chưa mạnh. Điều này khớp với tình trạng precision thấp: nguồn đúng có xuất hiện nhưng ranking vẫn có thể chưa tối ưu.

### `citation_accuracy`

Đo mức độ retrieve/trích dẫn đúng văn bản, điều, khoản theo goldset. `citation_accuracy = 4.71` là rất tốt, cho thấy hệ thống đang xác định nguồn pháp lý khá chính xác.

### `groundedness`

Đo câu trả lời có bám vào retrieved sources không. `groundedness = 3.21` là phần yếu nhất hiện tại.

Với bài toán pháp luật, groundedness nên được ưu tiên cao hơn answer nghe có vẻ đúng. Một câu trả lời đúng về mặt ngôn ngữ nhưng không được chứng minh bằng nguồn retrieve vẫn là rủi ro.

### `answer_correctness` và `completeness`

Hai metric này đều đạt `4.98`, rất cao. Điều đó cho thấy answer thường chứa đủ các ý trong `answer_points`. Tuy nhiên cần đọc cùng với groundedness: answer đúng theo goldset nhưng vẫn cần đảm bảo từng ý có căn cứ trong context retrieve.

## Các case cần xem lại

Một số case có điểm thấp hoặc retrieval chưa đạt:

| Case | Category | Overall | Groundedness | Recall@5 | MRR | Nhận xét |
|---|---|---:|---:|---:|---:|---|
| `social_insurance_pension_condition_001` | `bao_hiem_xa_hoi` | `3.15` | `2` | `0.0` | `0.0` | Không retrieve được expected source |
| `colloquial_domestic_violence_001` | `gia_dinh_colloquial` | `3.65` | `2` | `0.5` | `0.333` | Câu đời thường, cần cải thiện retrieval/rerank |
| `enterprise_board_authority_001` | `doanh_nghiep` | `3.75` | `5` | `0.0` | `0.0` | Answer có thể đúng nhưng expected source không được retrieve |
| `colloquial_consumer_bad_product_001` | `bao_ve_nguoi_tieu_dung_colloquial` | `3.75` | `5` | `0.0` | `0.0` | Query đời thường chưa kéo đúng Điều 4 |
| `enterprise_capital_contribution_001` | `doanh_nghiep` | `4.15` | `2` | `1.0` | `0.5` | Có nguồn đúng nhưng groundedness thấp |
| `consumer_rights_001` | `bao_ve_nguoi_tieu_dung` | `4.15` | `2` | `1.0` | `0.25` | Nguồn đúng xếp thấp, groundedness thấp |
| `social_insurance_contribution_rate_001` | `bao_hiem_xa_hoi` | `4.15` | `2` | `1.0` | `0.5` | Cần kiểm tra số liệu trong answer/context |
| `colloquial_borrow_money_interest_001` | `dan_su_colloquial` | `4.15` | `2` | `1.0` | `0.5` | Cần kiểm tra rule groundedness hoặc context có đủ Điều 468 |

## Khuyến nghị cải thiện

### 1. Cải thiện ranking

Đã có bước rerank deterministic sau RRF. Nên tiếp tục đo lại sau thay đổi này và so với report cũ:

- `mrr` có tăng không
- `ndcg_at_5` có tăng không
- nhóm `*_colloquial` có cải thiện không

Nếu chưa đủ, nên thêm:

- Boost mạnh hơn khi query expansion có số điều và chunk có đúng `article_number`.
- Penalize các chunk cùng văn bản nhưng sai điều.
- Giới hạn số chunk mỗi điều luật để giảm nhiễu.
- Dùng cross-encoder reranker nếu chấp nhận thêm model rerank riêng.

### 2. Giảm nhiễu context

Precision thấp cho thấy top-k còn nhiễu. Có thể thử:

```powershell
python evaluate_law_rag.py --top-k 3
```

Sau đó so với `--top-k 5`. Nếu recall không giảm nhiều nhưng groundedness/latency tốt hơn, có thể dùng top-k 3 cho UI.

### 3. Tăng groundedness

Nên inspect các case `groundedness <= 3`:

- Answer có nêu số liệu không nằm trong source không.
- Citation trong answer có khớp retrieved source không.
- Retrieved chunk có đúng điều nhưng thiếu khoản/nội dung cần thiết không.
- Evaluator có đang phạt quá gắt với cách diễn đạt số liệu không.

Với legal RAG, nên đặt target `groundedness >= 4.2`.

### 4. Mở rộng dataset

Dataset hiện có `48` case, dùng để demo evaluation là ổn. Nhưng để đánh giá nghiêm túc hơn nên tăng lên:

- Ít nhất `100` case.
- Có nhiều câu đời thường hơn.
- Có case thiếu dữ kiện.
- Có case ngoài phạm vi corpus.
- Có case multi-turn.
- Có case dễ nhầm giữa các luật/điều gần nhau.

### 5. Tối ưu latency

Latency trung bình gần `14s`, max gần `29s`. Có thể giảm bằng:

- Tắt query rewrite ở một số câu rõ ràng.
- Cache embedding query hoặc cache retrieval.
- Giảm `top_k`.
- Giảm số query rewrite.
- Tách retrieval-only eval để debug retriever không cần gọi chat model.

## Kết luận

Hệ thống Law RAG hiện tại đạt mức tốt cho demo và nghiên cứu. Retrieval có recall cao, citation khá chính xác, answer bao phủ tốt goldset. Tuy nhiên để dùng nghiêm túc trong ngữ cảnh pháp luật, cần ưu tiên cải thiện groundedness, ranking và latency.

Trạng thái hiện tại:

- Demo: đạt
- Internal testing: đạt
- Production pháp lý nghiêm túc: chưa đạt

Ưu tiên kỹ thuật tiếp theo:

1. Chạy lại evaluation sau thay đổi rerank.
2. So sánh `top-k 3` và `top-k 5`.
3. Debug các case `groundedness <= 3`.
4. Mở rộng goldset lên 100+ case.
5. Theo dõi riêng nhóm câu hỏi đời thường.
