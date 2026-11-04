# 30 — Vòng đời phân tích artifact

## Mục tiêu

Cài đặt dịch vụ phân tích artifact với trạng thái chuyển rõ ràng `PENDING → PROCESSING → COMPLETED | FAILED`, lưu kết quả qua upsert, giữ nguyên kết quả cũ khi lần phân tích mới thất bại, và tạo DTO ổn định từ tài liệu Markdown hoặc metadata repository.

## Giá trị

- Trạng thái là hợp đồng với UI và job runner; thiếu nhánh `FAILED` làm artifact kẹt vĩnh viễn.
- Học cách tách **build kết quả** khỏi **ghi trạng thái**, để lỗi không để lại dữ liệu nửa vời.
- Học phân tích nội dung có công thức rõ ràng: mục lục, content map, điểm cấu trúc/mật độ/độ sẵn sàng.
- Học kiểm thử bằng repository giả, không cần DB hay PDF.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.11+ (thư viện chuẩn) |
| Độ khó | Trung bình |
| Điều kiện | `dataclasses`, xử lý chuỗi, kiến thức repository pattern |
| Thời lượng gợi ý | 5–7 giờ |

## Nguồn gốc

- Repo: `triet4p/arch-lens-ai`
- File nguồn: <https://github.com/triet4p/arch-lens-ai/blob/main/python-sidecar/src/app/services/analysis.py>
- Hành vi quan sát được:
  - `analyze_artifact` lấy artifact; không có → `ValueError(f"Artifact {artifact_id} not found")`.
  - Đặt `artifact.status = ArtifactStatus.PROCESSING`, lưu; gọi `_build_analysis_result`; `upsert_for_artifact`; đặt `COMPLETED`; lưu; trả DTO.
  - `except Exception`: đặt `FAILED`, lưu, log `exc_info=True`, rồi `raise`.
  - `_build_analysis_result` phân nhánh `ArtifactType.REPO`, arXiv, tài liệu cục bộ.
  - Tài liệu: `_extract_toc` bằng regex `^(#{1,6})\s+(.+?)\s*$`; `_build_content_map`; `_word_count`; `_excerpt`; `_first_heading`.
  - Điểm tài liệu: `structure_score = min(100, 30 + headings * 12)`, `content_density = min(100, 10 + words // 20)`, `readiness_score = min(100, 20 + headings * 8 + words // 40)`.
  - Repository: `health_score = min(100, 20 + min(stars, 500) // 8 + (10 if readme else 0) + (10 if path_count else 0))`; `complexity_score = min(100, 15 + path_count // 4 + len(dependency_files) * 6)`; `integration_risk` theo công thức trong nguồn.
  - `analyzed_at=datetime.now()` (không tất định).
  - DTO dựng bằng `AnalysisRead.model_validate`.

**Phần là thiết kế của bài:** đồng hồ tiêm được, slug anchor và khử trùng anchor, định nghĩa `word_count`/`excerpt`, danh mục dependency/stack, lỗi có mã, và trạng thái `PROCESSING` không được phân tích lại. PDF/arXiv không nằm trong lõi bài.

## Hành vi bài tập yêu cầu

- Không tìm thấy artifact → lỗi `ARTIFACT_NOT_FOUND`, không đổi trạng thái.
- Artifact đang `PROCESSING` → `ANALYSIS_IN_PROGRESS`, không chạy song song.
- Mọi lỗi sau khi đặt `PROCESSING` (file thiếu, format lạ, build lỗi) → `FAILED`, rồi ném lỗi gốc.
- Kết quả cũ của lần trước **không bị xóa** khi lần mới thất bại; upsert chỉ xảy ra khi build thành công.
- Phân tích lại artifact `COMPLETED`/`FAILED` được phép; trạng thái về `PROCESSING` rồi kết thúc mới.
- Kết quả có `toc`, `content_map`, `scores`, `extracted_data`, `summary_markdown`, `analyzed_at`.
- `analyzed_at` lấy từ clock tiêm; cùng input + cùng clock → cùng output.

## Phạm vi

Trong phạm vi: document Markdown/`.txt`, repository metadata, state machine, repository in-memory, DTO, CLI.

Ngoài phạm vi: PDF, arXiv, gọi LLM, OCR, DB thật, job queue, song song nhiều artifact, UI.

## Fixture offline

- `fixtures/docs/flood.md` — tài liệu 30 từ, 4 heading.
- `fixtures/docs/empty.md`, `fixtures/docs/no-headings.md`, `fixtures/docs/duplicate-headings.md`.
- `fixtures/repos/repo-a.json` — metadata 20 path, 42 star, README, 3 dependency file.
- `fixtures/state.json` — artifact và analysis ban đầu.
- `fixtures/expected/*.json`.

Không PDF, không mạng, không LLM. Metadata repository là dữ liệu tổng hợp.

## Liên kết

- [SPEC.md](SPEC.md) — công thức, state machine, output, ví dụ.
- [GUIDE.md](GUIDE.md) — thiết kế repository/transaction và kiểm chứng.
