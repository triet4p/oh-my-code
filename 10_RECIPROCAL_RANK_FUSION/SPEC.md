# SPEC — Weighted Reciprocal Rank Fusion

## Mục tiêu hành vi

Hợp nhất `N` danh sách kết quả đã xếp hạng thành một danh sách duy nhất. Điểm của một tài liệu là tổng, trên mọi nguồn có tài liệu đó, của `weight(source) / (k + rank)`, với `rank` bắt đầu từ `1`. Kết quả sắp giảm dần theo điểm; hòa điểm được phân định bằng thứ tự xuất hiện đầu tiên.

## Kiểu

```python
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

@dataclass(frozen=True, slots=True)
class RetrievalResult:
    id: str
    score: float = 0.0
    payload: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class MergedCandidate:
    result: RetrievalResult       # kết quả của lần xuất hiện đầu tiên
    score: float
    rank: int                     # 1-based
    source_ranks: Mapping[str, int]
```

`RetrievalResult.score` **không** được dùng để tính RRF; nó chỉ được giữ lại trong `result` để người gọi tham khảo. Ghi rõ điều này trong docstring.

## API

```python
def fuse(
    result_lists: Sequence[Sequence[RetrievalResult]],
    *,
    source_names: Sequence[str] | None = None,
    source_weights: Mapping[str, float] | None = None,
    k: int = 60,
) -> list[MergedCandidate]:
    ...
```

## Quy tắc

### Tên nguồn

- `source_names is None` → `["semantic", "bm25", "graph", "temporal"]`.
- Nếu ít hơn số danh sách, dùng tên mặc định theo vị trí: `source_{idx}` cho các vị trí thiếu.
- Nếu nhiều hơn, bỏ qua phần dư.
- Mỗi tên phải là `str` không rỗng; tên trùng → `ValueError`.
- Không tự lower/trim tên.

### Trọng số

- `source_weights is None` → mọi nguồn `1.0`.
- Thiếu khóa → `1.0`.
- Khóa lạ (không có trong tên nguồn) bị bỏ qua.
- Giá trị phải là số thực hữu hạn; `bool` bị từ chối.
- Giá trị âm được **kẹp về 0** (giữ hành vi nguồn), không ném.
- Giá trị `NaN`/`inf` → `ValueError` (nguồn không xử lý; bài tập chọn an toàn).

### `k`

- Phải là `int` (không `bool`), `k >= 1`.
- Mặc định `60`.

### Xử lý danh sách

- Danh sách ngoài có thể rỗng → trả `[]`.
- Danh sách con rỗng được bỏ qua.
- Phần tử phải là `RetrievalResult`; `tuple`, `dict`, hay `None` → `TypeError`. Thông điệp nêu tên nguồn, rank và kiểu nhận được.
- Trong **cùng một danh sách**, nếu cùng `id` xuất hiện nhiều lần: chỉ lần đầu được tính; các lần sau bị bỏ qua hoàn toàn (không cộng điểm, không ghi đè `source_ranks`). Đây là khác biệt so với nguồn; nêu rõ.
- Rank dùng để tính là vị trí **sau khi khử trùng lặp**, bắt đầu từ 1.

### Cộng điểm và giữ kết quả

- `scores: dict[str, float]`; `first_seen: dict[str, int]` đánh số thứ tự xuất hiện toàn cục từ 0.
- `chosen: dict[str, RetrievalResult]` giữ kết quả lần đầu.
- Mỗi lần gặp tài liệu trong một nguồn hợp lệ:
  - Nếu chưa có trong `chosen`, lưu và gán `first_seen`.
  - Cộng `weight / (k + rank)`.
  - Ghi `source_ranks[f"{source_name}_rank"] = rank`.

### Sắp xếp

- Khóa chính: `score` giảm dần.
- Khóa phụ: `first_seen` tăng dần.
- Gán `rank` từ 1 theo thứ tự sau sắp.
- Không dùng `id` làm tie-break; thứ tự xuất hiện là hợp đồng.

## Công thức

$$ \text{score}(d) = \sum_{s \in \text{sources}(d)} \frac{w_s}{k + \text{rank}_s(d)} $$

Với `k` lớn, chênh lệch giữa các hạng gần nhau nhỏ; `k` nhỏ làm hạng đầu chiếm ưu thế.

## Ví dụ tính tay

`k = 60`; hai nguồn:

- `semantic` (weight 1.0): `[A, B]`
- `bm25` (weight 2.0): `[B, C]`

| Tài liệu | Điểm | Tính |
|---|---:|---|
| A | 0.01639344262295082 | `1 / 61` |
| B | 0.04891591750396616 | `1 / 62 + 2 / 61` |
| C | 0.03225806451612903 | `2 / 62` |

Thứ tự: **B, C, A**. `rank` lần lượt 1, 2, 3.

`source_ranks`:

| Tài liệu | Giá trị |
|---|---|
| A | `{"semantic_rank": 1}` |
| B | `{"semantic_rank": 2, "bm25_rank": 1}` |
| C | `{"bm25_rank": 2}` |

Nếu `A` cũng xuất hiện ở `bm25` rank 3, điểm A thành `1/61 + 2/63` và `source_ranks` có thêm `bm25_rank: 3`.

Hòa điểm: `semantic=[A]`, `bm25=[D]`, cùng weight 1, k=60 → cả hai `1/61`. A xuất hiện trước → A rank 1, D rank 2.

Trùng trong một danh sách: `semantic=[A, A, B]` → A tính một lần với rank 1; B có rank 2 (không phải 3).

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| `result_lists=[]` | `[]` |
| `result_lists=[[]]` | `[]` |
| Một danh sách một phần tử | một candidate, `score = 1/(k+1)` |
| Danh sách có id trùng | chỉ lần đầu |
| Cùng id ở nhiều nguồn | cộng điểm, giữ result đầu |
| Trọng số 0 | tài liệu vẫn xuất hiện, điểm có thể 0; `source_ranks` vẫn ghi |
| Mọi trọng số 0 | mọi điểm 0, sắp theo lần xuất hiện |
| `source_names` ngắn hơn | phần thiếu dùng `source_{idx}` |
| `source_names` dài hơn | bỏ phần dư |
| Tên nguồn trùng | `ValueError` |
| Tên rỗng | `ValueError` |
| `k=0`, `k<0`, `k=True` | `ValueError`/`TypeError` (bool) |
| Phần tử là tuple | `TypeError` |
| `source_weights` có NaN | `ValueError` |
| `source_weights` âm | kẹp 0 |
| `id` rỗng | cho phép? **Không**: `ValueError` khi tạo `RetrievalResult` (xem dưới) |

## Kiểm tra `RetrievalResult`

- `id` phải là `str` không rỗng; nếu không → `ValueError`.
- `score` phải là số thực hữu hạn (không dùng để tính, nhưng giữ hợp đồng).
- `payload` phải là mapping; copy nông khi tạo để tránh thay đổi ngoài? Bắt buộc: lưu `dict(payload)`.

## Tính xác định

- Cùng đầu vào → cùng thứ tự và cùng điểm (trừ sai số dấu phẩy động).
- Không phụ thuộc thứ tự duyệt dict; dùng list/`enumerate` cho nguồn.
- Không phụ thuộc hash randomization của Python: không lặp trên `set`.
- So sánh điểm bằng `math.isclose(..., rel_tol=1e-12, abs_tol=1e-15)` trong test.

## Tiêu chí nghiệm thu

1. Ví dụ ba tài liệu cho đúng thứ tự và điểm trong sai số `1e-12`.
2. `source_ranks` đúng cho từng tài liệu.
3. Test trùng trong một danh sách: A tính một lần, B rank 2.
4. Test hòa điểm theo thứ tự xuất hiện.
5. Test trọng số 0 và trọng số âm.
6. Test `k` không hợp lệ và phần tử sai kiểu.
7. Test `source_names` ngắn/dài/trùng.
8. Không sửa `result_lists` và không sửa `RetrievalResult` đầu vào.
9. `pytest -q` xanh.

## Non-goals

- Tính điểm semantic/BM25/graph.
- Chuẩn hóa điểm giữa các nguồn.
- Lọc theo ngưỡng, phân trang, dedupe theo nội dung.
- Hợp nhất metadata xung đột (bài tập chỉ giữ bản đầu).
- Tối ưu cho hàng triệu ứng viên.
