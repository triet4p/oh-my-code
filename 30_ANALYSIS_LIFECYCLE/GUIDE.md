# GUIDE 30 — Thiết kế state machine và phân tích

## 1. Kiến trúc

```
analysis_service/
├─ models.py      # Artifact, AnalysisResult, DTO
├─ state.py       # chuyển trạng thái hợp lệ
├─ document.py    # toc, content_map, scores
├─ repository.py  # metadata repo
├─ service.py     # analyze_artifact
├─ store.py       # in-memory repositories
└─ cli.py
fixtures/
```

`document.py` và `repository.py` là hàm thuần; `service.py` chỉ điều phối và trạng thái.

## 2. State machine

```python
ALLOWED = {
    "PENDING": {"PROCESSING"},
    "PROCESSING": {"COMPLETED", "FAILED"},
    "COMPLETED": {"PROCESSING"},
    "FAILED": {"PROCESSING"},
}
```

`transition(artifact, new)` kiểm tra; ném `IllegalTransition` nếu sai. Đừng gán trực tiếp `artifact.status = ...` rải rác.

Lưu ý: bước đặt `PROCESSING` phải được lưu **trước** khi build để UI thấy trạng thái; bước `FAILED` phải được lưu ngay cả khi build ném.

## 3. Transaction logic

Source dùng một `try` bao cả build và upsert, nên lỗi upsert cũng làm FAILED. Bài giữ semantics đó.

Pseudo:

```
if not artifact: raise NotFound
if artifact.status == PROCESSING: raise InProgress
set PROCESSING; save
try:
    result = build(artifact)
    result.analyzed_at = clock()
    stored = upsert(result)
    set COMPLETED; save
    return dto(stored)
except Exception as exc:
    set FAILED
    try: save
    except Exception: log
    raise exc
```

Không đặt `COMPLETED` trước upsert: nếu upsert lỗi, UI thấy completed nhưng không có dữ liệu.

## 4. TOC và content map

Parse heading bằng regex trên **từng dòng**, không dùng `re.MULTILINE` trên cả chuỗi nếu dễ nhầm.

Vị trí dòng:

```
headings = [(line_index, level, title), ...]
for i, h in enumerate(headings):
    body_start = h.line + 1
    body_end = headings[i+1].line if i+1 < len else len(lines)
    body = "\n".join(lines[body_start:body_end]).strip()
```

Nếu body chứa heading con, nó vẫn thuộc section cha theo cách này; đó là content map thô, chấp nhận được. Nếu muốn map theo cấp, phải xây cây — ngoài phạm vi.

Anchor slug: dùng `unicodedata.normalize("NFKD", title)`, `encode("ascii","ignore").decode()`, lower, regex `[^a-z0-9]+` → `-`. Tiếng Việt sẽ mất dấu; ổn định và dễ link.

## 5. Điểm

Giữ đúng công thức; đừng “cải tiến” thành phần trăm logic. Test biên:

- `words=0, headings=0` → 30/10/20.
- `words=1000, headings=10` → structure 100, density 60, readiness 100? 20+80+25=125 → 100.
- `words=19` → density 10; `words=20` → 11.

## 6. Repository

`tree_structure` có thể là chuỗi nhiều dòng hoặc rỗng. Chuẩn hóa:

```
paths = [p.strip().replace("\\","/") for p in tree.splitlines() if p.strip()]
```

Dependency: so basename với tập; với `*.csproj`, dùng `fnmatch`. Stack: xét sự hiện diện của basename, không xét phần mở rộng.

Risk: chú ý `max(0, complexity-50)//2` — nếu complexity < 50 thì 0; không dùng phép chia âm.

## 7. Bẫy thường gặp

- **Quên lưu PROCESSING**: nếu build ném ngay, artifact vẫn PENDING; test không thấy FAILED.
- **Đặt FAILED trong `finally`**: sẽ đè COMPLETED. Chỉ trong `except`.
- **Nuốt exception sau khi set FAILED**: phải `raise`.
- **Xóa analysis cũ trước khi build**: mất dữ liệu khi lỗi. Upsert sau build.
- **Dùng `datetime.now()`**: output đổi giữa các lần. Tiêm clock.
- **Tính word count trên markdown thô**: đếm cả `#`, lệch ví dụ. Dùng plain text.
- **Content map dùng heading level để cắt**: dễ sai với heading nhảy cấp; dùng vị trí dòng.
- **Slug trùng**: anchor HTML trùng; thêm hậu tố.
- **`scores` bị `json.dumps`**: DTO phải là object.
- **PDF**: không cài `pymupdf4llm`; trả `UNSUPPORTED_FORMAT` rõ ràng.

## 8. Kiểm chứng

```bash
cd 30_ANALYSIS_LIFECYCLE
python -m analysis_service --state fixtures/state.json --artifact 1 \
  --now 2026-01-01T00:00:00+00:00 --out /tmp/a.json
python - <<'PY'
import json
d=json.load(open('/tmp/a.json'))
assert d['scores']=={'structure_score':78,'content_density':11,'readiness_score':52}, d['scores']
assert [t['anchor'] for t in d['toc']]==['flood-risk','data','model','results']
assert d['analyzed_at']=='2026-01-01T00:00:00+00:00'
print(d['extracted_data'])
PY
```

Test lỗi:

```bash
python -m analysis_service --state fixtures/state.json --artifact 999 --out /tmp/e.json; echo $?
```

Kiểm tra analysis cũ còn sau lỗi: chạy artifact 2 với file bị xóa, đọc state.

## 9. Gợi ý

- Viết `document.build(markdown, metadata)` trước; test bằng chuỗi, không cần file.
- Viết `FakeArtifactRepo`/`FakeAnalysisRepo` ghi lại lịch sử update.
- Test state machine bằng bảng chuyển hợp lệ/không hợp lệ.
- Dùng `dataclasses.asdict` cẩn thận: datetime cần serialize ISO.
- Đừng đưa `clock` vào hàm build; chỉ service cần.

## 10. Mở rộng

1. Thêm phân tích arXiv với metadata có sẵn (không gọi mạng).
2. Thêm PDF qua converter injectable.
3. Thêm khóa theo artifact để chống chạy song song.
4. Thêm retry có backoff cho lỗi tạm thời.
5. Thêm lịch sử phiên bản analysis thay vì upsert.
