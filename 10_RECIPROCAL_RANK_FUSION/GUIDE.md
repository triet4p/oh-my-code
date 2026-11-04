# GUIDE — Weighted Reciprocal Rank Fusion

## Bước 0 — Môi trường

```bash
mkdir 10_RECIPROCAL_RANK_FUSION/work && cd 10_RECIPROCAL_RANK_FUSION/work
uv init . -p 3.12 --lib
uv add --dev pytest
mkdir -p src/rrf tests
```

## Bước 1 — Mô hình hóa kết quả

Bắt đầu bằng dataclass bất biến. Tại sao bất biến? Vì `fuse` phải không sửa đầu vào, và người gọi có thể dùng cùng một kết quả cho nhiều lần trộn.

`payload: Mapping[str, Any]` với `field(default_factory=dict)` để tránh mutable default. Trong `__post_init__`:

- Kiểm tra `id`.
- Kiểm tra `score` hữu hạn.
- Chuyển `payload` thành `dict` nếu cần (nhưng dataclass frozen vẫn cho phép `object.__setattr__`; hoặc dùng `MappingProxyType`).

Đừng dùng `list` cho payload; mapping phù hợp hơn với metadata.

## Bước 2 — Chuẩn bị tên và trọng số

Viết helper:

```text
def _resolve_name(index, source_names):
    if source_names is not None and index < len(source_names):
        return source_names[index]
    return f"source_{index}"
```

Trước vòng lặp, kiểm tra toàn bộ `source_names` (nếu có): mỗi phần tử là `str` không rỗng, không trùng. Làm sớm để lỗi không phụ thuộc dữ liệu.

Trọng số:

```text
def _weight(name, weights):
    if weights is None or name not in weights:
        return 1.0
    value = weights[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(...)
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(...)
    return max(value, 0.0)
```

Tại sao `bool` bị từ chối? `True` là `1`; một trọng số boolean gần như chắc chắn là lỗi lập trình.

## Bước 3 — Vòng lặp chính

Cấu trúc dữ liệu:

```text
chosen: dict[str, RetrievalResult] = {}
scores: dict[str, float] = {}
first_seen: dict[str, int] = {}
ranks: dict[str, dict[str, int]] = {}
next_seen = 0
```

Với mỗi `(source_idx, results)`:

- Tính `name`, `weight`.
- Duyệt `results` với `position` bắt đầu 1.
- Kiểm tra kiểu phần tử **trước** khi đọc `.id`; nếu sai, ném `TypeError` có ngữ cảnh.
- Khử trùng trong danh sách: dùng `seen_in_source: set[str]`. Nếu `id` đã thấy, `continue` — nhưng lưu ý rank đã dùng để tính là vị trí sau khử trùng, nên hãy dùng một biến `effective_rank` tăng khi gặp id mới, không dùng `position` trực tiếp.

Gợi ý:

```text
effective_rank = 0
for result in results:
    validate(result)
    if result.id in seen_in_source:
        continue
    seen_in_source.add(result.id)
    effective_rank += 1
    if result.id not in chosen:
        chosen[result.id] = result
        first_seen[result.id] = next_seen
        next_seen += 1
    scores[result.id] = scores.get(result.id, 0.0) + weight / (k + effective_rank)
    ranks.setdefault(result.id, {})[f"{name}_rank"] = effective_rank
```

Đây là điểm khác nguồn: nguồn dùng `enumerate(results, start=1)` nên bản trùng vẫn tăng rank của các phần tử sau. Bài tập đổi để rank phản ánh danh sách đã khử trùng; ghi rõ trong docstring.

## Bước 4 — Sắp xếp

```text
ordered = sorted(scores.items(), key=lambda kv: (-kv[1], first_seen[kv[0]]))
```

Không dùng `reverse=True` rồi tie-break `-first_seen`; công thức trên rõ hơn.

Tạo `MergedCandidate(result=chosen[doc_id], score=score, rank=i, source_ranks=ranks[doc_id])`.

`source_ranks` nên là mapping chỉ đọc hoặc bản sao; nếu để dict nội bộ, người gọi sửa được. Dùng `dict(ranks[doc_id])`.

## Bước 5 — Kiểm tra `k`

```text
if isinstance(k, bool) or not isinstance(k, int):
    raise TypeError("k must be an int, not bool")
if k < 1:
    raise ValueError("k must be >= 1")
```

Sai thứ tự sẽ khiến `True` lọt qua `k < 1`.

## Bước 6 — Test

Viết một helper tính điểm kỳ vọng bằng công thức, để test không lặp số học.

Các nhóm:

1. **Cơ bản**: ví dụ SPEC, so điểm với `pytest.approx`.
2. **Trùng trong list**: `[A,A,B]`; A rank 1, B rank 2.
3. **Trùng giữa list**: giữ payload của lần đầu; kiểm tra `candidate.result is first`.
4. **Tie**: hai tài liệu điểm bằng, thứ tự xuất hiện.
5. **Trọng số**: 0, âm, NaN, thiếu key, key lạ.
6. **k**: 0, -1, 1.5, True.
7. **Tên nguồn**: ngắn, dài, trùng, rỗng.
8. **Rỗng**: `[]`, `[[]]`.
9. **Không sửa đầu vào**: so sánh list và object trước/sau.

Một cái bẫy: `pytest.approx` mặc định `rel=1e-6`; với các giá trị nhỏ như `1/61`, sai số tuyệt đối có thể che lỗi. Đặt `rel=1e-12, abs=1e-15`.

## Bước 7 — Kiểm chứng độc lập

```bash
uv run pytest -q
uv run python - <<'PY'
from rrf import RetrievalResult, fuse
sem = [RetrievalResult("A"), RetrievalResult("B")]
bm = [RetrievalResult("B"), RetrievalResult("C")]
out = fuse([sem, bm], source_weights={"semantic": 1, "bm25": 2}, k=60)
for c in out:
    print(c.result.id, round(c.score, 12), c.rank, dict(c.source_ranks))
PY
```

Kỳ vọng:

```text
B 0.048915917504 1 {'semantic_rank': 2, 'bm25_rank': 1}
C 0.032258064516 2 {'bm25_rank': 2}
A 0.016393442623 3 {'semantic_rank': 1}
```

## Bước 8 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Điểm gấp đôi | Cộng cả bản trùng trong cùng list. |
| Thứ tự hòa không ổn định | Dùng `set` hoặc sort không có tie-break. |
| `source_ranks` mất khóa | Ghi đè dict thay vì cập nhật. |
| Trọng số âm làm điểm âm | Quên `max(..., 0)`. |
| `k=True` lọt | Kiểm tra `bool` sau `int`. |
| `NaN` lan ra | Không kiểm tra `isfinite` ở weight. |
| Kết quả thay đổi giữa lần chạy | Lặp trên set/dict không xác định. |
| Sửa payload của input | Dùng chung dict thay vì copy. |

## Bước 9 — Mở rộng

- Thêm `fuse_with_scores` cho nguồn đã chuẩn hóa.
- Thêm giới hạn `top_k` nhưng vẫn tính đủ điểm.
- Thêm trọng số theo loại truy vấn.
- Thêm chuẩn hóa điểm bằng min-max trước khi trộn (khác RRF thuần).
- So sánh RRF với CombSUM/CombMNZ trên cùng dữ liệu.

## Tự đánh giá

1. Vì sao RRF không cần điểm gốc?
2. Vì sao `k` lớn làm giảm ảnh hưởng của thứ hạng?
3. Vì sao khử trùng trong một danh sách lại thay đổi rank của các phần tử sau?
4. Tie-break theo thứ tự xuất hiện có nhược điểm gì so với tie-break theo `id`?
