from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from law_rag.retrieval.sqlite_retrieval_store import SQLiteRetrievalStore


STORE_PATH = ROOT_DIR / "output" / "vbpl_merged_reuse_openai" / "retrieval" / "retrieval_store.sqlite"
OUTPUT_PATH = ROOT_DIR / "evaluation" / "law_rag_eval_dataset.json"


CASES: list[dict[str, str]] = [
    # Hinh su - doi thuong, chung chung
    {"id": "criminal_injury_general", "category": "hinh_su", "question": "Đánh người gây thương tích 18% thì bị tội gì?", "doc_hint": "Bộ luật Hình sự", "title_contains": "hinh su", "article": "134"},
    {"id": "criminal_injury_weapon", "category": "hinh_su", "question": "Dùng dao đánh người gây thương tích thì bị xử lý thế nào?", "doc_hint": "Bộ luật Hình sự", "title_contains": "hinh su", "article": "134"},
    {"id": "criminal_theft_phone", "category": "hinh_su", "question": "Lén lấy trộm điện thoại của người khác thì phạm tội gì?", "doc_hint": "Bộ luật Hình sự", "title_contains": "hinh su", "article": "173"},
    {"id": "criminal_fraud_transfer", "category": "hinh_su", "question": "Lừa người khác chuyển tiền rồi chiếm đoạt thì bị xử lý theo tội gì?", "doc_hint": "Bộ luật Hình sự", "title_contains": "hinh su", "article": "174"},
    {"id": "criminal_trust_abuse_motorbike", "category": "hinh_su", "question": "Mượn xe rồi mang đi bán không trả thì bị tội gì?", "doc_hint": "Bộ luật Hình sự", "title_contains": "hinh su", "article": "175"},
    {"id": "criminal_insult_online", "category": "hinh_su", "question": "Chửi bới xúc phạm nghiêm trọng danh dự người khác trên mạng có bị truy cứu hình sự không?", "doc_hint": "Bộ luật Hình sự", "title_contains": "hinh su", "article": "155"},
    {"id": "criminal_slander_fake_post", "category": "hinh_su", "question": "Bịa chuyện sai sự thật để vu khống người khác thì bị xử lý thế nào?", "doc_hint": "Bộ luật Hình sự", "title_contains": "hinh su", "article": "156"},
    {"id": "criminal_gambling_online", "category": "hinh_su", "question": "Đánh bạc ăn tiền qua mạng có thể bị tội gì?", "doc_hint": "Bộ luật Hình sự", "title_contains": "hinh su", "article": "321"},
    {"id": "criminal_traffic_death", "category": "hinh_su", "question": "Gây tai nạn giao thông làm chết người thì có thể bị truy cứu tội gì?", "doc_hint": "Bộ luật Hình sự", "title_contains": "hinh su", "article": "260"},
    {"id": "criminal_murder", "category": "hinh_su", "question": "Cố ý tước đoạt tính mạng người khác bị xử lý theo tội gì?", "doc_hint": "Bộ luật Hình sự", "title_contains": "hinh su", "article": "123"},

    # Dan su
    {"id": "civil_transaction_valid", "category": "dan_su", "question": "Giao dịch dân sự có hiệu lực khi đáp ứng điều kiện nào?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "117"},
    {"id": "civil_contract_form", "category": "dan_su", "question": "Hợp đồng dân sự có bắt buộc phải lập thành văn bản không?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "119"},
    {"id": "civil_invalid_form", "category": "dan_su", "question": "Hợp đồng vi phạm quy định về hình thức thì có vô hiệu không?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "129"},
    {"id": "civil_late_obligation", "category": "dan_su", "question": "Chậm thực hiện nghĩa vụ dân sự thì phải chịu trách nhiệm gì?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "357"},
    {"id": "civil_loan_contract", "category": "dan_su", "question": "Cho vay tiền bằng miệng có được coi là hợp đồng vay tài sản không?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "463"},
    {"id": "civil_repay_loan", "category": "dan_su", "question": "Vay tiền đến hạn không trả thì nghĩa vụ trả nợ được quy định thế nào?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "466"},
    {"id": "civil_interest_rate", "category": "dan_su", "question": "Lãi suất cho vay dân sự tối đa là bao nhiêu?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "468"},
    {"id": "civil_compensation_basis", "category": "dan_su", "question": "Làm hư tài sản của người khác thì phải bồi thường theo căn cứ nào?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "584"},
    {"id": "civil_health_damage", "category": "dan_su", "question": "Gây thương tích cho người khác thì bồi thường thiệt hại sức khỏe gồm những khoản nào?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "590"},
    {"id": "civil_adopted_child_inheritance", "category": "dan_su", "question": "Con nuôi có được hưởng thừa kế như con đẻ không?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "651"},
    {"id": "civil_valid_will", "category": "dan_su", "question": "Di chúc hợp pháp cần điều kiện gì?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "630"},
    {"id": "civil_inheritance_time_limit", "category": "dan_su", "question": "Thời hiệu yêu cầu chia di sản thừa kế là bao lâu?", "doc_hint": "Bộ luật Dân sự", "title_contains": "dan su", "article": "623"},

    # Lao dong
    {"id": "labor_quit_without_notice", "category": "lao_dong", "question": "Tôi nghỉ việc không báo trước có sao không?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "35"},
    {"id": "labor_quit_illegal_damages", "category": "lao_dong", "question": "Người lao động tự ý nghỉ ngang trái luật phải bồi thường gì?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "40"},
    {"id": "labor_employer_unilateral", "category": "lao_dong", "question": "Công ty được đơn phương chấm dứt hợp đồng lao động khi nào?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "36"},
    {"id": "labor_wrongful_termination", "category": "lao_dong", "question": "Công ty cho nghỉ việc trái luật thì phải bồi thường thế nào?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "41"},
    {"id": "labor_contract_types", "category": "lao_dong", "question": "Hợp đồng lao động có những loại nào?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "20"},
    {"id": "labor_contract_content", "category": "lao_dong", "question": "Hợp đồng lao động bắt buộc phải có nội dung gì?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "21"},
    {"id": "labor_termination_cases", "category": "lao_dong", "question": "Hợp đồng lao động chấm dứt trong những trường hợp nào?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "34"},
    {"id": "labor_severance_allowance", "category": "lao_dong", "question": "Nghỉ việc thì khi nào được trợ cấp thôi việc?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "46"},
    {"id": "labor_job_loss_allowance", "category": "lao_dong", "question": "Mất việc do thay đổi cơ cấu thì được trợ cấp mất việc không?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "47"},
    {"id": "labor_final_payment", "category": "lao_dong", "question": "Sau khi nghỉ việc công ty phải thanh toán lương trong bao lâu?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "48"},
    {"id": "labor_overtime_pay", "category": "lao_dong", "question": "Làm thêm giờ được trả lương như thế nào?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "98"},
    {"id": "labor_working_hours", "category": "lao_dong", "question": "Thời giờ làm việc bình thường tối đa là bao nhiêu?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "105"},
    {"id": "labor_overtime_limit", "category": "lao_dong", "question": "Công ty được yêu cầu làm thêm giờ tối đa bao nhiêu?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "107"},
    {"id": "labor_annual_leave", "category": "lao_dong", "question": "Một năm người lao động được nghỉ phép bao nhiêu ngày?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "113"},
    {"id": "labor_pregnant_worker", "category": "lao_dong", "question": "Lao động nữ mang thai có được bảo vệ khi công ty muốn chấm dứt hợp đồng không?", "doc_hint": "Bộ luật Lao động", "title_contains": "lao dong", "article": "137"},

    # Hon nhan gia dinh
    {"id": "marriage_conditions", "category": "hon_nhan", "question": "Muốn đăng ký kết hôn thì nam nữ phải đáp ứng điều kiện gì?", "doc_hint": "Luật Hôn nhân và gia đình", "title_contains": "hon nhan", "article": "8"},
    {"id": "marriage_registration", "category": "hon_nhan", "question": "Không đăng ký kết hôn thì hôn nhân có được pháp luật công nhận không?", "doc_hint": "Luật Hôn nhân và gia đình", "title_contains": "hon nhan", "article": "9"},
    {"id": "marriage_divorce_right", "category": "hon_nhan", "question": "Ai có quyền yêu cầu ly hôn?", "doc_hint": "Luật Hôn nhân và gia đình", "title_contains": "hon nhan", "article": "51"},
    {"id": "marriage_unilateral_divorce", "category": "hon_nhan", "question": "Một bên muốn ly hôn nhưng bên kia không đồng ý thì tòa án giải quyết thế nào?", "doc_hint": "Luật Hôn nhân và gia đình", "title_contains": "hon nhan", "article": "56"},
    {"id": "marriage_child_custody", "category": "hon_nhan", "question": "Ly hôn thì con dưới 36 tháng tuổi thường giao cho ai nuôi?", "doc_hint": "Luật Hôn nhân và gia đình", "title_contains": "hon nhan", "article": "81"},
    {"id": "marriage_child_support", "category": "hon_nhan", "question": "Người không trực tiếp nuôi con sau ly hôn có nghĩa vụ gì?", "doc_hint": "Luật Hôn nhân và gia đình", "title_contains": "hon nhan", "article": "82"},

    # Doanh nghiep
    {"id": "enterprise_banned_founder", "category": "doanh_nghiep", "question": "Những ai không được quyền thành lập và quản lý doanh nghiệp?", "doc_hint": "Luật Doanh nghiệp", "title_contains": "doanh nghiep", "article": "17"},
    {"id": "enterprise_charter_content", "category": "doanh_nghiep", "question": "Điều lệ công ty cần có những nội dung chủ yếu nào?", "doc_hint": "Luật Doanh nghiệp", "title_contains": "doanh nghiep", "article": "24"},
    {"id": "enterprise_two_member_llc", "category": "doanh_nghiep", "question": "Công ty trách nhiệm hữu hạn hai thành viên có đặc điểm gì?", "doc_hint": "Luật Doanh nghiệp", "title_contains": "doanh nghiep", "article": "46"},
    {"id": "enterprise_single_member_llc", "category": "doanh_nghiep", "question": "Công ty trách nhiệm hữu hạn một thành viên là gì?", "doc_hint": "Luật Doanh nghiệp", "title_contains": "doanh nghiep", "article": "74"},
    {"id": "enterprise_joint_stock", "category": "doanh_nghiep", "question": "Công ty cổ phần có đặc điểm pháp lý cơ bản nào?", "doc_hint": "Luật Doanh nghiệp", "title_contains": "doanh nghiep", "article": "111"},
    {"id": "enterprise_private_liability", "category": "doanh_nghiep", "question": "Doanh nghiệp tư nhân chịu trách nhiệm tài sản như thế nào?", "doc_hint": "Luật Doanh nghiệp", "title_contains": "doanh nghiep", "article": "188"},

    # Linh vuc khac
    {"id": "residence_permanent_registration", "category": "cu_tru", "question": "Đăng ký thường trú cần điều kiện gì?", "doc_hint": "Luật Cư trú", "title_contains": "cu tru", "article": "20"},
    {"id": "residence_temporary_registration", "category": "cu_tru", "question": "Đăng ký tạm trú được quy định như thế nào?", "doc_hint": "Luật Cư trú", "title_contains": "cu tru", "article": "27"},
    {"id": "social_insurance_maternity", "category": "bao_hiem_xa_hoi", "question": "Điều kiện hưởng chế độ thai sản là gì?", "doc_hint": "Luật Bảo hiểm xã hội", "title_contains": "bao hiem xa hoi", "article": "31"},
    {"id": "social_insurance_lump_sum", "category": "bao_hiem_xa_hoi", "question": "Khi nào được nhận bảo hiểm xã hội một lần?", "doc_hint": "Luật Bảo hiểm xã hội", "title_contains": "bao hiem xa hoi", "article": "60"},
    {"id": "health_insurance_benefit", "category": "bao_hiem_y_te", "question": "Mức hưởng bảo hiểm y tế khi đi khám chữa bệnh đúng tuyến là bao nhiêu?", "doc_hint": "Luật Bảo hiểm y tế", "title_contains": "bao hiem y te", "article": "22"},
    {"id": "traffic_prohibited_acts", "category": "giao_thong", "question": "Những hành vi nào bị nghiêm cấm khi tham gia giao thông đường bộ?", "doc_hint": "Luật Giao thông đường bộ", "title_contains": "giao thong duong bo", "article": "8"},
    {"id": "traffic_driver_conditions", "category": "giao_thong", "question": "Người lái xe tham gia giao thông cần điều kiện gì?", "doc_hint": "Luật Giao thông đường bộ", "title_contains": "giao thong duong bo", "article": "58"},
    {"id": "cyber_prohibited_acts", "category": "an_ninh_mang", "question": "Các hành vi nào bị nghiêm cấm trên không gian mạng?", "doc_hint": "Luật An ninh mạng", "title_contains": "an ninh mang", "article": "8"},
    {"id": "cyber_user_info", "category": "an_ninh_mang", "question": "Doanh nghiệp cung cấp dịch vụ trên mạng phải bảo đảm thông tin người dùng thế nào?", "doc_hint": "Luật An ninh mạng", "title_contains": "an ninh mang", "article": "26"},
    {"id": "ip_right_basis", "category": "so_huu_tri_tue", "question": "Quyền tác giả và quyền sở hữu công nghiệp phát sinh dựa trên căn cứ nào?", "doc_hint": "Luật Sở hữu trí tuệ", "title_contains": "so huu tri tue", "article": "6"},
    {"id": "ip_copyright_infringement", "category": "so_huu_tri_tue", "question": "Sao chép tác phẩm của người khác khi chưa được phép có phải xâm phạm quyền tác giả không?", "doc_hint": "Luật Sở hữu trí tuệ", "title_contains": "so huu tri tue", "article": "28"},
    {"id": "commerce_contract_form", "category": "thuong_mai", "question": "Hợp đồng mua bán hàng hóa có bắt buộc lập thành văn bản không?", "doc_hint": "Luật Thương mại", "title_contains": "thuong mai", "article": "24"},
    {"id": "commerce_contract_remedies", "category": "thuong_mai", "question": "Khi vi phạm hợp đồng thương mại thì có những chế tài nào?", "doc_hint": "Luật Thương mại", "title_contains": "thuong mai", "article": "292"},
]


def normalize(value: Any) -> str:
    text = str(value or "").casefold()
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.replace("đ", "d")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def matches_source(item: dict[str, Any], *, title_contains: str, article: str) -> bool:
    identity = normalize(
        " ".join(
            str(item.get(key) or "")
            for key in ("source_file", "document_title", "documentTitle", "documentId", "doc_number")
        )
    )
    return normalize(title_contains) in identity and normalize(item.get("article_number")) == normalize(article)


def first_sentences(text: str, *, limit: int = 3) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", clean)
    points: list[str] = []
    for part in parts:
        part = part.strip(" -")
        if len(part) < 25:
            continue
        points.append(part[:240].strip())
        if len(points) >= limit:
            break
    return points


def find_expected_source(store: SQLiteRetrievalStore, case: dict[str, str]) -> tuple[dict[str, Any], int | None]:
    anchor_query = f"Điều {case['article']} {case['doc_hint']}"
    anchor_results = store.query_bm25(anchor_query, 50)
    for item in anchor_results:
        if matches_source(item, title_contains=case["doc_hint"], article=case["article"]):
            question_rank = None
            for rank, candidate in enumerate(store.query_bm25(case["question"], 30), start=1):
                if matches_source(candidate, title_contains=case["doc_hint"], article=case["article"]):
                    question_rank = rank
                    break
            return item, question_rank
    raise RuntimeError(f"Cannot find expected source for {case['id']} with anchor query: {anchor_query}")


def build_dataset() -> list[dict[str, Any]]:
    store = SQLiteRetrievalStore(STORE_PATH)
    dataset: list[dict[str, Any]] = []
    failures: list[str] = []
    try:
        for case in CASES:
            try:
                source, question_rank = find_expected_source(store, case)
            except Exception as exc:
                failures.append(f"{case['id']}: {exc}")
                continue

            text = str(source.get("text") or source.get("preview") or "")
            heading = text.splitlines()[0].strip() if text.splitlines() else f"Điều {case['article']}"
            answer_points = [
                f"Cần đối chiếu {heading} trong {source.get('document_title')}.",
                *first_sentences(text, limit=3),
            ]
            dataset.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "inputs": {"question": case["question"]},
                    "reference_outputs": {
                        "answer_points": answer_points[:4],
                        "expected_sources": [
                            {
                                "document_title_contains": case["doc_hint"],
                                "article_number": case["article"],
                            }
                        ],
                        "required_terms": [f"Điều {case['article']}", case["doc_hint"]],
                        "forbidden_claims": [
                            "chắc chắn không bị xử lý",
                            "không cần căn cứ pháp luật",
                            "luôn luôn",
                        ],
                        "notes": (
                            f"Generated from corpus chunk_id={source.get('chunk_id')}, "
                            f"doc_number={source.get('doc_number')}, "
                            f"question_bm25_rank={question_rank if question_rank is not None else 'not_in_top_30'}."
                        ),
                    },
                }
            )
    finally:
        store.close()

    if failures:
        print("Skipped cases:")
        for failure in failures:
            print(f"- {failure}")
    return dataset


def main() -> int:
    dataset = build_dataset()
    if len(dataset) < 50:
        raise SystemExit(f"Only generated {len(dataset)} validated cases; need at least 50.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(dataset)} cases to {OUTPUT_PATH}")
    ranks = [
        item["reference_outputs"]["notes"].split("question_bm25_rank=", 1)[1].rstrip(".")
        for item in dataset
    ]
    in_top_30 = sum(rank != "not_in_top_30" for rank in ranks)
    print(f"Question BM25 hit in top 30: {in_top_30}/{len(dataset)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
