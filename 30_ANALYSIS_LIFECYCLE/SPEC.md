# SPEC 30 — Dịch vụ phân tích artifact

## 1. Mô hình

```text
PENDING ──analyze──> PROCESSING ──success──> COMPLETED
                         │
                         └──failure──> FAILED
```

- `PROCESSING` không nhận lần phân tích mới.
- `COMPLETED`/`FAILED` có thể phân tích lại.
- Không có chuyển trạng thái khác.

Artifact:

```json
{
  "id": 1,
  "type": "document",
  "local_path": "fixtures/docs/flood.md",
  "metadata": { "title": "Flood Risk", "extension": ".md" }
}
```

`type`: `document` hoặc `repository`. `metadata` là object; với repository có `repo_id`, `full_name`, `language`, `stars`, `readme_preview`, `tree_structure`, `default_branch`.

## 2. API

```python
service = AnalysisService(artifact_repo, analysis_repo, clock)
await service.analyze_artifact(artifact_id) -> AnalysisRead
await service.get_analysis(artifact_id) -> AnalysisRead | None
```

- `clock() -> datetime` trả datetime timezone-aware; test tiêm cố định.
- `artifact_repo.get(id)`, `.update(artifact)`.
- `analysis_repo.upsert_for_artifact(result)`, `.get_by_artifact(id)`.

## 3. Luồng `analyze_artifact`

1. `artifact = artifact_repo.get(id)`.
2. Nếu `None` → ném `ArtifactNotFound` (mã `ARTIFACT_NOT_FOUND`).
3. Nếu `status == PROCESSING` → ném `AnalysisInProgress` (mã `ANALYSIS_IN_PROGRESS`).
4. Đặt `status = PROCESSING`; `artifact_repo.update`.
5. Trong `try`:
   1. `payload = build_analysis(artifact)` (hàm thuần, có thể ném).
   2. Dựng `AnalysisResult` với `analyzed_at = clock()`.
   3. `stored = analysis_repo.upsert_for_artifact(result)`.
   4. `status = COMPLETED`; `update`.
   5. Trả DTO từ `stored`.
6. `except Exception`:
   1. Đặt `status = FAILED`; cố `update`.
   2. Nếu bước update này cũng lỗi, ghi log và vẫn ném lỗi phân tích gốc (không thay bằng lỗi lưu trạng thái).
   3. Ném lại lỗi gốc.

`get_analysis` trả `None` nếu chưa có; không đổi trạng thái.

## 4. Phân tích tài liệu

### 4.1. Đọc

- `.md`, `.txt`: đọc UTF-8, `errors="replace"`.
- File không tồn tại/không đọc được → `DocumentUnreadable` (`FILE_UNREADABLE`).
- Định dạng khác (kể cả `.pdf`) → `UnsupportedFormat` (`UNSUPPORTED_FORMAT`).

### 4.2. Chuẩn hóa

- `lines = text.splitlines()`.
- Bỏ dòng rỗng khi trích excerpt.
- Bỏ marker heading `#{1,6}\s+` ở đầu dòng khi tạo plain text.
- `plain = " ".join(collapse_whitespace(line) …)`.
- `words = len(plain.split())` (không tính dấu `#`).

### 4.3. TOC

Regex `^(#{1,6})\s+(.+?)\s*$`. Mỗi mục:

```json
{ "level": 1, "title": "Flood Risk", "anchor": "flood-risk" }
```

Slug: Unicode NFKD, bỏ combining mark, lower, thay mọi cụm không phải `[a-z0-9]+` bằng `-`, trim `-`; rỗng → `section`. Anchor trùng trong cùng tài liệu được thêm `-2`, `-3`, … theo thứ tự xuất hiện.

### 4.4. Content map

- Nếu text rỗng → `{}`.
- Nếu không có heading → `{"Document": excerpt(plain, 2400)}`.
- Ngược lại: mỗi heading sở hữu text từ sau dòng heading đến trước heading kế tiếp; bỏ dòng trống đầu/cuối; nối bằng `\n`.
- Khóa là **title**; title trùng được đổi thành `"<title> (2)"`, `"<title> (3)"` theo thứ tự.
- Section không có nội dung → giá trị `""` (vẫn có khóa).

### 4.5. Trích đoạn và tiêu đề

- `excerpt(text, limit)` gộp khoảng trắng, cắt `limit` ký tự; nếu cắt, thêm `"…"` (một ký tự U+2026).
- `title = metadata.title or metadata.original_name or first_heading or "Local document"`.
- `first_heading` là title của mục TOC cấp bất kỳ đầu tiên.

### 4.6. `extracted_data` và điểm

```json
{
  "title": "Flood Risk",
  "format": ".md",
  "word_count": 30,
  "headings_count": 4,
  "section_titles": ["Flood Risk", "Data", "Model", "Results"]
}
```

- `format = metadata.extension` nếu có, ngược lại suffix của `local_path`, lower.
- `section_titles` lấy tối đa 8 title đầu.
- `structure_score = min(100, 30 + headings_count * 12)`.
- `content_density = min(100, 10 + word_count // 20)`.
- `readiness_score = min(100, 20 + headings_count * 8 + word_count // 40)`.

### 4.7. `summary_markdown`

Đúng định dạng:

```text
Flood Risk

Converted into normalized markdown with 30 words and 4 detected sections.

Flood Risk Synthetic notes about river levels and rainfall. Data Daily rainfall totals and gauge readings. Model A simple threshold model. Results Accuracy is reported on a fixed validation split.
```

## 5. Phân tích repository

### 5.1. Dữ liệu

- `tree_structure`: chuỗi, mỗi dòng một đường dẫn; bỏ dòng rỗng; chuẩn hóa `/`.
- `path_count = len(paths)`.
- `readme_present = bool(readme_preview.strip())`.
- Dependency file nhận diện theo basename: `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `requirements.txt`, `pyproject.toml`, `poetry.lock`, `Pipfile`, `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, `build.gradle.kts`, `*.csproj`, `Dockerfile`, `docker-compose.yml`.
- Danh sách trả về **basename duy nhất**, sắp xếp Unicode tăng dần.

### 5.2. Stack

Ánh xạ có thứ tự cố định:

| Dấu hiệu | Stack |
|---|---|
| `package.json` | `Node` |
| `requirements.txt`/`pyproject.toml` | `Python` |
| `Cargo.toml` | `Rust` |
| `go.mod` | `Go` |
| `pom.xml`/`build.gradle*` | `Java` |
| `*.csproj` | `.NET` |
| `Dockerfile` | `Docker` |

Trả các nhãn duy nhất theo thứ tự bảng, không theo thứ tự file.

### 5.3. Điểm

- `health = min(100, 20 + min(stars,500)//8 + (10 if readme else 0) + (10 if path_count else 0))`.
- `complexity = min(100, 15 + path_count//4 + len(dependency_files)*6)`.
- `risk = max(5, min(100, 55 + (15 if not readme else 0) + (10 if not language else 0) + max(0, complexity-50)//2 - min(health,80)//6))`.

### 5.4. Nội dung cố định

TOC:

```json
[
  {"level": 1, "title": "Repository Overview", "anchor": "repository-overview"},
  {"level": 1, "title": "Dependency Signals", "anchor": "dependency-signals"},
  {"level": 1, "title": "README Excerpt", "anchor": "readme-excerpt"}
]
```

Content map khóa tương ứng; README excerpt 1200 ký tự; dependency rỗng → `"No common dependency manifest detected."`; README rỗng → `"README preview unavailable."`.

Summary:

```text
<full_name hoặc name hoặc "Repository">

Primary language: <language hoặc "unknown">.
Detected stack: <ds hoặc "none detected">.
Health score: <health>/100. Complexity score: <complexity>/100. Integration risk: <risk>/100.
```

## 6. Output DTO

```json
{
  "artifact_id": 1,
  "analysis_kind": "document",
  "summary_markdown": "…",
  "extracted_data": { … },
  "scores": { "structure_score": 78, "content_density": 11, "readiness_score": 52 },
  "toc": [ … ],
  "content_map": { … },
  "analyzed_at": "2026-01-01T00:00:00+00:00"
}
```

- `scores` là object, không phải chuỗi JSON.
- `toc`/`content_map` là cấu trúc, không phải chuỗi.
- `analyzed_at` ISO-8601 với offset.

## 7. Ví dụ cụ thể — `flood.md`

Nội dung:

```markdown
# Flood Risk

Synthetic notes about river levels and rainfall.

## Data

Daily rainfall totals and gauge readings.

### Model

A simple threshold model.

## Results

Accuracy is reported on a fixed validation split.
```

Kết quả:

- `words=30`, `headings=4`.
- `toc`: `Flood Risk` (1), `Data` (2), `Model` (3), `Results` (2).
- `scores`: `structure_score=78`, `content_density=11`, `readiness_score=52`.
- `section_titles`: 4 title trên.
- `content_map`: bốn khóa; `Flood Risk` → `Synthetic notes about river levels and rainfall.`; `Data` → `Daily rainfall totals and gauge readings.`; `Model` → `A simple threshold model.`; `Results` → `Accuracy is reported on a fixed validation split.`
- `analyzed_at = 2026-01-01T00:00:00+00:00` khi clock tiêm giá trị đó.

Repository `repo-a`:

- 20 path, 42 star, readme có, language `Python`, dependency `Dockerfile`, `pyproject.toml`, `requirements.txt`.
- `health=45`, `complexity=38`, `risk=48`.
- stack `["Python", "Docker"]`.

## 8. Lỗi

| Mã | Khi nào | Trạng thái sau |
|---|---|---|
| `ARTIFACT_NOT_FOUND` | id không tồn tại | không đổi |
| `ANALYSIS_IN_PROGRESS` | đang PROCESSING | PROCESSING |
| `FILE_UNREADABLE` | thiếu/không đọc được | FAILED |
| `UNSUPPORTED_FORMAT` | đuôi khác `.md/.txt` | FAILED |
| `BUILD_FAILED` | lỗi logic | FAILED |
| `STORAGE_FAILED` | upsert lỗi | FAILED |

## 9. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | File rỗng | `words=0`, `headings=0`, `toc=[]`, `content_map={}`, `structure=30`, `density=10`, `readiness=20` |
| 2 | Không heading nhưng có text | content map `{"Document": …}` |
| 3 | Heading trùng tên | content map `Title`, `Title (2)` |
| 4 | Heading trùng anchor | anchor `-2` |
| 5 | Heading cấp 6 | level 6 |
| 6 | Dòng `#######` | không phải heading |
| 7 | Heading có `#` trong text | giữ trong title |
| 8 | Title rỗng | fallback `Local document` |
| 9 | `.PDF` | `UNSUPPORTED_FORMAT` (so lower) |
| 10 | File sai encoding | đọc với `errors=replace` |
| 11 | Phân tích lại COMPLETED | chạy lại, upsert thay |
| 12 | Lần mới thất bại | analysis cũ vẫn còn, artifact FAILED |
| 13 | `PROCESSING` | `ANALYSIS_IN_PROGRESS` |
| 14 | Upsert ném lỗi | artifact FAILED, lỗi gốc lan truyền |
| 15 | Repo không readme/language | risk tăng theo công thức |
| 16 | `stars` âm | coi `min(stars,500)` âm; công thức vẫn chạy; validate metadata nên chặn `stars < 0` |

## 10. Tiêu chí chấp nhận

- [ ] Ví dụ `flood.md` khớp chính xác các điểm và content map.
- [ ] Ví dụ `repo-a` khớp 45/38/48 và stack.
- [ ] Lỗi build để artifact `FAILED` và ném lại đúng exception.
- [ ] Analysis cũ không bị xóa khi lần mới lỗi.
- [ ] Không có trạng thái nào khác ngoài bốn giá trị.
- [ ] `analyzed_at` lấy từ clock, không gọi `datetime.now()`.
- [ ] Output không chứa chuỗi JSON lồng cho `toc`/`scores`.
- [ ] Chạy hai lần cùng clock cho cùng output.

## 11. Non-goals

- Không cần PDF, arXiv, OCR, LLM.
- Không cần DB thật; repository trong bộ nhớ là đủ.
- Không cần job queue/retry.
- Không cần phân tích song song nhiều artifact.
