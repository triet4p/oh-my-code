# 03 — Plugin registry: đăng ký symptom và scorer bằng decorator

## Mục tiêu

Tự viết một registry dùng Strategy Pattern: các lớp “symptom” và “pattern scorer” tự đăng ký tên bằng decorator, registry tra cứu lớp theo tên, và mọi lỗi biên (tên trùng, tên chưa đăng ký, schema sai) được xử lý tường minh. Đây là bài học về cách một bảng tra toàn cục trở thành API ổn định thay vì một `dict` công khai.

## Giá trị học được

- Decorator trong Python thực chất là hàm nhận lớp và trả lớp; registry chỉ là closure ghi vào dict.
- Trạng thái cấp lớp (class-level state) tồn tại xuyên test — cần thiết kế cô lập.
- “Đăng ký hai bảng phải nguyên tử”: nếu ghi `SYMPTOMS` xong mới phát hiện `SYMPTOMS_CONFIGS` lỗi, registry đã hỏng.
- Phân biệt **đăng ký** (ghi) và **tra cứu** (đọc); lỗi của mỗi bên khác nhau.
- Vì sao API “tự phát hiện plugin” cần quy ước tên và kiểm tra kiểu ở biên.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Python 3.12+.
- Độ khó: **Dễ – Trung bình**.
- Thời lượng gợi ý: 3–4 giờ.

## Điều kiện tiên quyết và runtime

- Python 3.12+, `uv`, `pytest`.
- Không cần thư viện ngoài, không cần mạng.

## Nguồn gốc

- Repo: `triet4p/CTC-East` — **repo riêng tư**.
- File: `src/anomaly_detection_dl/forensic_analyzer/core/registry.py`.
- URL chính xác: <https://github.com/triet4p/CTC-East/blob/master/src/anomaly_detection_dl/forensic_analyzer/core/registry.py>
- Truy cập: liên kết chỉ mở được khi tài khoản GitHub có quyền đọc repo `triet4p/CTC-East`; truy cập ẩn danh trả 404 vì repo private. Nội dung dưới đây được đọc từ nguồn qua phiên có quyền.

Hành vi quan sát được trong nguồn:

- Lớp `ForensicRegistry` có ba dict cấp lớp: `SYMPTOMS: Dict[str, Type]`, `SYMPTOMS_CONFIGS: Dict[str, Type]`, `PATTERN_SCORERS: Dict[str, Type]`.
- `register_symptom(cls, name, config_schema)` là `classmethod` trả về một decorator; decorator ghi `SYMPTOMS[name] = symptom_cls` và `SYMPTOMS_CONFIGS[name] = config_schema`, rồi trả lại chính lớp đó.
- `register_pattern_scorer(cls, name)` tương tự, chỉ ghi `PATTERN_SCORERS[name] = scorer_cls`.
- Nguồn **không** kiểm tra tên trùng, không kiểm tra tên rỗng, không có hàm tra cứu, và không có cơ chế cô lập trạng thái cho test.

## Phạm vi bài tập

Xây module `forensic_registry` với:

- Ba dict ở cấp lớp, nhưng nên truy cập qua API (không khuyến khích sửa trực tiếp).
- Decorator đăng ký có kiểm tra tên và schema.
- Tra cứu có lỗi riêng cho tên chưa đăng ký.
- Ngữ nghĩa rõ cho đăng ký trùng.
- `snapshot()` / `restore()` để test không rò rỉ trạng thái.

Không nằm trong phạm vi: import động theo entry point, thread safety, đa hình thực thi symptom, đọc file cấu hình.

## Liên kết

- [SPEC.md](SPEC.md) — hợp đồng đăng ký/tra cứu, lỗi, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế closure, kiểm tra nguyên tử, cách test.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn chỉ là bảng ghi; bài tập **bổ sung** chính sách trùng tên, kiểm tra tên, tra cứu có lỗi và snapshot. Những chính sách này là thiết kế của bài tập, không phải hành vi của nguồn. Bài tập cũng không sao chép bất kỳ hành vi bảo mật nào của nguồn.
