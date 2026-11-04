# GUIDE 52 — Bộ truy hồi đồ thị cắm được

## 1. Điều đang được kiểm tra

Không phải "BFS có đúng không" hay "PPR có hội tụ không" — hai thuật toán đó đã quen. Điều đáng làm là **chứng minh trừu tượng không rò**:

- Pipeline không biết tên cụ thể.
- Thay retriever chỉ đổi thứ hạng, không đổi mã hậu xử lý.
- Mọi retriever nhận cùng một "gói" tham số, kể cả tham số nó không dùng.

Ba tiêu chí này tạo ra thiết kế khác hẳn "viết hai hàm rồi if/else".

## 2. Cấu trúc

```text
src/
├── model.py       # Fact, GraphPool, RetrievalResult, MPFPTimings
├── base.py        # GraphRetriever (ABC) + filter helper
├── bfs.py         # BFSRetriever
├── ppr.py         # PPRRetriever
├── registry.py    # RETRIEVERS, get_retriever
├── pipeline.py    # recall()
└── __main__.py
```

`base.py` chứa **hàm lọc duy nhất** `is_allowed(fact, filters)`. Cả hai retriever gọi nó. Nếu mỗi retriever tự lọc, chúng sẽ trôi khỏi nhau và test "đổi retriever không đổi bộ lọc" sẽ vô nghĩa.

## 3. Thứ tự cài đặt

### Bước 1 — Mô hình và bộ lọc

Viết `Fact`, `GraphPool`, `RetrievalResult`, `MPFPTimings` trước. `MPFPTimings` nên có mặc định `truncated=False` để retriever không phải nhớ.

Bộ lọc: viết `is_allowed(fact, fact_type, allowed_fact_types, tags, tags_match, tag_groups)` và test riêng với 6 tổ hợp. Đây là phần dễ sai nhất về ngữ nghĩa (`any`/`all`, AND giữa nhóm).

### Bước 2 — BFS

Dùng `heapq` với khóa `(hop, fact_id)` để thứ tự không phụ thuộc thứ tự chèn. Nếu bạn dùng `deque` FIFO, kết quả vẫn đúng nhưng khi trùng `hop` thứ tự sẽ phụ thuộc `adjacency` — test 3.2 có thể fail.

Điểm: `score = 1 / (1 + hop)`. Ở `hop = 2`, `score = 1/3`, không phải `0.5`.

Ngân sách: kiểm tra **trước** khi mở rộng:

```text
if expansions >= budget: truncated = True; break
expansions += 1
```

Nếu kiểm tra sau, bạn vượt ngân sách đúng một đơn vị — lỗi kinh điển.

### Bước 3 — PPR

Lặp công suất với `p0` là phân bố đều trên seed. Ba chi tiết:

1. **Nút treo** (không có cạnh ra) làm mất khối lượng; phải phân phối lại đều cho seed, nếu không tổng `p` giảm và test "tổng ≈ 1" fail.
2. **Hội tụ**: dừng khi `Σ|p_new - p| < 1e-9` hoặc 50 vòng. Ghi `iterations` thực tế.
3. **Chuẩn hoá điểm**: nhân với số nút đã xét để điểm không phụ thuộc kích thước đồ thị — hoặc bỏ hẳn và ghi rõ. SPEC chọn nhân.

Nghiệm tay: hai nút đối xứng, `d = 0.5` ⇒ `p_A = 2/3`. Nếu bạn ra `0.5`, có thể bạn quên số hạng `(1-d)` hoặc dùng `d = 1`.

### Bước 4 — Registry

```python
RETRIEVERS = {"bfs": BFSRetriever, "ppr": PPRRetriever}
def get_retriever(name):
    try: return RETRIEVERS[name]()
    except KeyError: raise UnknownRetriever(name, sorted(RETRIEVERS))
```

Đừng dùng `globals()[name]` hay `eval`. Registry tường minh là ranh giới an toàn.

### Bước 5 — Pipeline

```text
def recall(pool, query_embedding_str, retriever_name, config):
    r = get_retriever(retriever_name)
    results, timings = asyncio.run(r.retrieve(pool, query_embedding_str, ...))
    dedup by fact_id (max score)
    sort (-score, fact_id)
    cut top_k
    return {...}
```

`asyncio.run` chỉ nên ở biên (CLI). Nếu pipeline được gọi từ ngữ cảnh async, cung cấp `async def recall_async` và để `recall` bọc lại — tránh lỗi "event loop already running".

## 4. Cạm bẫy

- **`if name == "ppr"` trong pipeline**: phá mục đích. Test bằng cách đếm số lần một hàm hậu xử lý được gọi — phải giống nhau cho cả hai.
- **Mỗi retriever tự lọc**: trôi ngữ nghĩa. Dùng chung `is_allowed`.
- **Seed trùng**: `semantic_seeds + temporal_seeds` có thể lặp; phải dedupe **giữ thứ tự** trước khi đếm `1/|seeds|`.
- **Seed lạ**: có trong `semantic_seeds` nhưng không có trong `pool` ⇒ bỏ, không `KeyError`.
- **Điểm BFS không chuẩn hoá**: so sánh với PPR vô nghĩa; đó là lý do pipeline nên ghi rõ `score_kind` nếu trộn nguồn.
- **PPR `iterations = 0` khi seed rỗng**: trả `([], timings)` chứ không `None`; nhất quán kiểu.
- **Chữ ký bị "cải tiến"**: thêm `**kwargs` làm test `inspect.signature` fail — đó là chủ đích của bài.
- **`inspect.signature` trên class**: `GraphRetriever.retrieve` chưa bind sẽ có `self`; nhớ loại nó khi so.

## 5. Kiểm thử

| Test | Nội dung |
|---|---|
| `signature_fidelity` | 14 tên, đúng thứ tự |
| `bfs_small` | bảng 3.2, đúng thứ tự `f1, f3, f2, f4` |
| `ppr_two_nodes` | `2/3`, `1/3` trong `1e-6`; tổng ≈ 1 |
| `budget` | `expansions <= budget`; `truncated` đúng |
| `filters_any_all` | hai tập khác nhau trên `graph_tagged` |
| `seed_unknown` | không lỗi, không kết quả |
| `unknown_retriever` | danh sách đã sắp |
| `pipeline_no_branch` | spy cho thấy cùng đường đi |
| `determinism` | hai lần chạy giống hệt |
| `hop_scores` | `1/(1+hop)` cho hop 0..2 |

## 6. Kiểm chứng độc lập

```bash
python --version
python -m unittest discover -s tests -v
python -m src recall --retriever bfs --fixture fixtures/graph_small.json
python -m src recall --retriever ppr --fixture fixtures/graph_two_nodes.json --damping 0.5
```

Lệnh thứ ba phải in `A ≈ 0.666667`, `B ≈ 0.333333` (sau khi chia chuẩn hoá; xem SPEC 4.1 để biết điểm đã nhân chuẩn hoá — khi đó so tỉ lệ, không so giá trị tuyệt đối).

Kiểm tra chữ ký:

```bash
python -c "import inspect, src.base as b; print([p for p in inspect.signature(b.GraphRetriever.retrieve).parameters])"
```

Danh sách phải bắt đầu `self` rồi đúng 14 tên.

## 7. Gợi ý

- Viết `spy_pipeline(name)` trong test: một `list` ghi tên hàm hậu xử lý; so hai danh sách từ hai retriever. Nếu khác nhau, trừu tượng đã rò.
- Viết `assert_scores_sorted(results)` và gọi ở cuối cả hai retriever.
- Với PPR, in `iterations` trong test để thấy ảnh hưởng của damping: `d = 0.5` hội tụ nhanh hơn `0.95`.
- Đừng tối ưu bằng cache toàn cục; nó làm test phụ thuộc thứ tự.

## 8. Mở rộng

- **Gói tham số**: thêm `RetrievalRequest` dataclass và một adapter giữ chữ ký cũ; so sánh độ dễ đọc.
- **Trọng số cạnh**: đổi `adjacency` thành `dict[str, list[(str, float)]]`; BFS dùng ngưỡng trọng số, PPR chia theo trọng số.
- **RRF nhiều nguồn**: chạy cả BFS và PPR rồi hợp nhất bằng RRF (bài 10) — pipeline vẫn không rẽ nhánh.
- **Đo thời gian**: thêm `elapsed_ms` vào timings bằng `time.perf_counter` **chỉ** khi cờ `--timing` bật, để test vẫn tất định.
- **Retriever thứ ba**: thêm "temporal" chỉ theo cạnh thời gian; chứng minh registry mở rộng mà pipeline không đổi.
