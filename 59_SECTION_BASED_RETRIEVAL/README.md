# 59 — Truy hồi theo mục lục thay vì vector

## Mục tiêu

Chọn **mục** của một tài liệu thay vì đoạn văn: bộ chọn trả về id mục, có kiểm tra hợp lệ, có đường dự phòng, rồi lắp ngữ cảnh theo ngân sách ký tự với dấu cắt tường minh.

1. Mô hình tài liệu `content_map` giữ thứ tự mục như trong nguồn.
2. `SectionSelector` là giao diện; cài `LexicalSelector` tất định và một cổng cho mô hình (không gọi mạng).
3. Id không tồn tại bị loại kèm cảnh báo; nếu không còn id hợp lệ ⇒ dự phòng **hai mục đầu**.
4. Lắp ngữ cảnh ≤ 40 000 ký tự, cắt giữa mục nếu cần, nối đúng dấu `\n...(truncated)...`.
5. `refs` phải bằng **đúng** các mục đã dùng.

## Giá trị

- Đây là phản ví dụ có chủ đích cho "RAG = vector search": với tài liệu có cấu trúc, chọn mục rẻ hơn, giải thích được, và không cần embedding.
- Bài tập luyện hai bất biến hay bị vi phạm: `refs` khớp ngữ cảnh thực dùng, và ngân sách ký tự không vượt (trừ đúng dấu cắt).
- Đường dự phòng buộc bạn phân biệt "bộ chọn trả rỗng" với "bộ chọn trả rác" — hai lỗi khác nhau, cùng một cách xử lý nhưng cảnh báo khác nhau.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn (`math`, `re`, `json`) |
| Độ khó | Trung bình |
| Điều kiện | Token hoá, IDF, sắp xếp ổn định, cắt chuỗi theo ngân sách |
| Runtime | Không mạng, không GPU, không `dspy`/`langchain` |
| Thời lượng gợi ý | 5–7 giờ |

## Nguồn gốc

- Repo: `triet4p/bridge-research` (nhánh `main`, repo đã archived 2026-10-23)
- File nguồn: <https://github.com/triet4p/bridge-research/blob/main/python-sidecar/src/services/paper_chat.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Hai signature DSPy: `SectionSelectorSignature` và `AnswerGeneratorSignature`; bộ chọn dựng bằng `self.selector = dspy.ChainOfThought(SectionSelectorSignature)`.
  - Dự phòng khi mô hình chọn sai: `if not valid_ids: valid_ids = list(doc.content_map.keys())[:2]`.
  - Chặn tràn ngữ cảnh: `if len(context_text) > 40000: context_text = context_text[:40000] + "\n...(truncated)..."`.
  - Lưu kèm tham chiếu: `refs=json.dumps(valid_ids)`.
- Giới hạn bằng chứng: đọc toàn bộ file; không quan sát được cách chấm điểm mục (mô hình tự chọn), định dạng `content_map`, hay cách dựng `context_text` từng mục.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: ý tưởng chọn theo mục lục; hai bước (chọn mục, sinh câu trả lời); dự phòng hai mục đầu khi danh sách hợp lệ rỗng; ngưỡng 40 000 và dấu cắt; lưu `refs`.

Phần **do bài tập định nghĩa**:

- Định dạng `content_map` (id → title/text) và thứ tự mục.
- Thuật toán chấm điểm từ vựng (IDF + tf), quy tắc hoà.
- Cách kiểm tra id hợp lệ và sinh cảnh báo.
- Cách lắp ngữ cảnh theo mục và cắt giữa mục (nguồn chỉ cắt chuỗi).
- Giao diện mô hình (`SectionSelector` inject) và bộ giả để test.
- Định dạng output, tên lỗi.

Nguồn **không** bao gồm: DSPy, mô hình thật, arXiv, hay cơ sở dữ liệu tài liệu.

## Phạm vi

Trong phạm vi:

- Tài liệu ≤ 30 mục, mỗi mục ≤ 50 000 ký tự.
- Hai bộ chọn: `LexicalSelector` (mặc định) và selector giả do test cấp.
- Lắp ngữ cảnh, cắt, tính `refs`, cảnh báo.
- CLI: `python -m src ask --fixture fixtures/doc.json --query "hệ thống"`.

Ngoài phạm vi:

- Không gọi mô hình, không embedding, không vector store.
- Không sinh câu trả lời (chỉ lắp ngữ cảnh); không đánh giá chất lượng câu trả lời.
- Không PDF/scan; đầu vào là JSON đã tách mục.

## Cảnh báo production

- Tài liệu thật thường có mục lồng nhau; bài này phẳng một cấp. Nếu mục quá lớn, ngân sách 40 000 sẽ cắt giữa nội dung — cần tách mục nhỏ hơn.
- Chấm điểm từ vựng yếu với từ đồng nghĩa; đây là lựa chọn để tất định, không phải để thay embedding.
- Dự phòng "hai mục đầu" có thể đưa ngữ cảnh không liên quan; sản phẩm thật nên trả "không tìm thấy" thay vì đoán.
- Dấu cắt phải được hiển thị cho người đọc biết ngữ cảnh không đầy đủ.

## Fixture offline

- `fixtures/doc_small.json` — 3 mục, dùng cho ví dụ số.
- `fixtures/doc_long.json` — hai mục lớn để kiểm tra cắt 40 000.
- `fixtures/doc_invalid_ids.json` — selector giả trả id không tồn tại.
- Không có URL ngoài; không gọi mạng.

## Liên kết

- [SPEC.md](SPEC.md) — công thức điểm, luật hợp lệ, ví dụ chuỗi chính xác, tiêu chí.
- [GUIDE.md](GUIDE.md) — thiết kế bộ chọn, bẫy `refs`/cắt, cách kiểm chứng.
