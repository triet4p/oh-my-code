# SPEC 52 — Bộ truy hồi đồ thị cắm được

## 1. Giao diện

```python
class GraphRetriever(ABC):
    name: str

    @abstractmethod
    async def retrieve(
        self,
        pool,
        query_embedding_str,
        bank_id,
        fact_type,
        budget,
        query_text,
        semantic_seeds,
        temporal_seeds,
        adjacency,
        tags,
        tags_match,
        tag_groups,
        allowed_fact_types,
    ) -> tuple[list[RetrievalResult], MPFPTimings | None]: ...
```

Tên và **thứ tự** 14 tham số phải đúng như trên (sau `self`). Test dùng `inspect.signature` để khẳng định; đây là hợp đồng thay thế được.

### 1.1 Ý nghĩa tham số

| Tham số | Kiểu | Ý nghĩa trong bài |
|---|---|---|
| `pool` | `GraphPool` | Nguồn fact; có `.facts: dict[str, Fact]` |
| `query_embedding_str` | `str` | Vector dạng `"0.1,0.0,0.5"`; chỉ dùng để **phá hoà** |
| `bank_id` | `str` | Nhãn không gian; chép vào `RetrievalResult.bank_id` |
| `fact_type` | `str \| None` | Lọc chính xác theo `Fact.type`; `None` = không lọc |
| `budget` | `int >= 1` | Số nút tối đa được **mở rộng** (không tính seed) |
| `query_text` | `str` | Không dùng trong hai retriever mẫu; giữ chỗ cho retriever khác |
| `semantic_seeds` | `list[str]` | Seed từ nhánh ngữ nghĩa |
| `temporal_seeds` | `list[str]` | Seed từ nhánh thời gian |
| `adjacency` | `dict[str, list[str]]` | Danh sách kề; nút đích lạ bị bỏ qua |
| `tags` | `list[str]` | Nhãn cần khớp |
| `tags_match` | `"any" \| "all"` | Cách khớp `tags` |
| `tag_groups` | `list[list[str]]` | Mỗi nhóm phải có ít nhất một nhãn khớp (AND giữa nhóm) |
| `allowed_fact_types` | `list[str] \| None` | Nếu có, chỉ giữ fact thuộc danh sách |

### 1.2 Kiểu dữ liệu

```text
Fact:
    id: str
    type: str
    embedding: list[float]
    tags: list[str]

RetrievalResult:
    fact_id: str
    score: float
    hop: int                  # 0 cho seed; PPR dùng -1 (không theo bước)
    bank_id: str

MPFPTimings:
    expansions: int
    max_frontier: int
    iterations: int           # BFS: số lớp; PPR: số vòng lặp
    truncated: bool
```

## 2. Bộ lọc dùng chung

Một fact `f` **được phép** khi thoả tất cả:

1. `fact_type is None` hoặc `f.type == fact_type`.
2. `allowed_fact_types is None` hoặc `f.type in allowed_fact_types`.
3. Nếu `tags` không rỗng:
   - `tags_match == "any"`: `set(tags) & set(f.tags)` khác rỗng.
   - `tags_match == "all"`: `set(tags) <= set(f.tags)`.
4. Với mỗi nhóm trong `tag_groups`: `set(nhóm) & set(f.tags)` khác rỗng.

Seed cũng phải qua bộ lọc; seed bị lọc ⇒ bỏ (không phải lỗi).

## 3. `BFSRetriever`

### 3.1 Thuật toán

```text
seeds = (semantic_seeds + temporal_seeds), giữ thứ tự, bỏ trùng, chỉ giữ nút có trong pool và qua lọc
hàng đợi: (hop, fact_id) ưu tiên hop tăng, rồi fact_id tăng
kết quả: mỗi seed hop=0, score = 1.0
expansions = 0; max_frontier = 0
while hàng đợi không rỗng:
    (hop, u) = pop
    nếu hop >= 2: bỏ qua việc mở rộng (vẫn giữ kết quả)
    nếu expansions >= budget: truncated = true; dừng
    expansions += 1
    với v trong adjacency.get(u, []) đã sắp tăng:
        nếu v không có trong pool hoặc không qua lọc: bỏ
        nếu v chưa có kết quả:
            score = 1 / (1 + hop + 1); hop_v = hop + 1
            thêm kết quả; đẩy (hop_v, v)
    max_frontier = max(max_frontier, len(hàng đợi))
```

- Độ sâu tối đa: `hop <= 1` được mở rộng, tức kết quả tối đa ở `hop = 2`.
- `budget` chỉ đếm lần **mở rộng** một nút, không đếm seed.

### 3.2 Ví dụ

`fixtures/graph_small.json`: `f1` → `[f2, f3]`, `f2` → `[f4]`, `f3` → `[f4]`, `f4` → `[]`.
Embedding: `f1=[1,0]`, `f2=[0,1]`, `f3=[0.7071,0.7071]`, `f4=[1,0]`.
Seed: `["f1"]`; `query_embedding_str = "1,0"`; `budget = 10`.

Kết quả:

| fact | hop | score |
|---|---|---|
| `f1` | 0 | 1.0 |
| `f3` | 1 | 0.5 |
| `f2` | 1 | 0.5 |
| `f4` | 2 | 0.333333 |

Thứ tự: `score` giảm; hoà thì cosine với query giảm; hoà nữa thì `fact_id` tăng.
`cos(f2, q) = 0`, `cos(f3, q) = 0.7071` ⇒ `f3` trước `f2`.

## 4. `PPRRetriever`

### 4.1 Thuật toán

```text
seeds = như BFS; nếu rỗng: trả ([], timings với iterations=0, truncated=false)
p0 = 1/|seeds| cho mỗi seed, 0 cho nút khác
p = p0
với iteration = 1..50:
    p_new[v] = (1 - d) * p0[v] + d * Σ_{u -> v} p[u] / outdeg(u)
    nút treo (outdeg = 0) phân phối khối lượng của nó đều cho seeds
    nếu Σ|p_new - p| < 1e-9: dừng
    p = p_new
điểm = p[v] * (số nút đã xét)      # chuẩn hoá để không phụ thuộc kích thước
hop = -1
```

`d = 0.85` mặc định, cấu hình được (`configs.json`). `expansions` = số lần duyệt cạnh; nếu vượt `budget`, dừng và `truncated = true` (kết quả dùng `p` hiện tại, chuẩn hoá lại).

### 4.2 Ví dụ có nghiệm giải tích

`fixtures/graph_two_nodes.json`: `A -> [B]`, `B -> [A]`; seed `["A"]`; **`d = 0.5`**.

Phương trình điểm bất động:

```text
p_A = 0.5 * p_B + 0.5
p_B = 0.5 * p_A
⇒ p_A = 0.5 * 0.5 * p_A + 0.5 ⇒ 0.75 p_A = 0.5 ⇒ p_A = 2/3, p_B = 1/3
```

Test phải khẳng định `|p_A - 0.6666667| < 1e-6` và tổng xấp xỉ 1.

## 5. Registry và pipeline

```text
RETRIEVERS = {"bfs": BFSRetriever, "ppr": PPRRetriever}
get_retriever(name) -> GraphRetriever
```

- Tên lạ ⇒ `UnknownRetriever(name, available=["bfs", "ppr"])` (đã sắp).
- Pipeline `recall(...)`:
  1. `get_retriever(name)`
  2. gọi `retrieve(...)`
  3. bỏ kết quả trùng `fact_id` (giữ điểm cao nhất)
  4. sắp `(-score, fact_id)`
  5. cắt `top_k`
  6. trả `{"results": [...], "timings": {...}, "retriever": name}`

Pipeline **không** được chứa `if name == ...`. Test dò bằng cách theo dõi các hàm được gọi: cùng input, đổi `name` chỉ đổi giá trị `results`/`retriever`, không đổi nhánh thực thi.

## 6. Kiểm tra hợp lệ

| Điều kiện | Lỗi |
|---|---|
| `budget < 1` | `InvalidBudget` |
| `tags_match` khác `any`/`all` | `InvalidTagsMatch` |
| `query_embedding_str` không parse được | `InvalidEmbedding` |
| `semantic_seeds`/`temporal_seeds` không phải list[str] | `InvalidSeeds` |
| tên retriever lạ | `UnknownRetriever` |
| `top_k < 1` | `InvalidTopK` |

`query_embedding_str` chỉ cần hợp lệ khi thực sự dùng để phá hoà; validation vẫn chạy trước để lỗi nhất quán.

## 7. Tiêu chí chấp nhận

1. `inspect.signature(GraphRetriever.retrieve).parameters` cho đúng 14 tên theo thứ tự ở mục 1, cộng `self` ở phương thức chưa bind.
2. BFS trên `graph_small` cho bảng ở 3.2, đúng cả thứ tự.
3. PPR trên `graph_two_nodes` với `d = 0.5` cho `2/3`, `1/3` trong `1e-6`.
4. Với mọi fixture: `expansions <= budget`; nếu dừng sớm thì `truncated == true`.
5. Bộ lọc: `tags_match="any"` vs `"all"` cho tập khác nhau trên `graph_tagged`; `fact_type` và `allowed_fact_types` áp đúng.
6. Seed bị lọc không sinh kết quả và không gây lỗi; seed lạ (không có trong pool) cũng vậy.
7. `UnknownRetriever` nêu danh sách đã sắp.
8. Cùng input ⇒ cùng output; hai retriever đều tất định.
9. Pipeline không rẽ nhánh theo tên (test theo dõi call).
10. `python -m src recall --retriever bfs --fixture fixtures/graph_small.json` in JSON khớp 3.2.

## 8. Non-goals

- Không DB/SQL/vector index; không kết nối mạng.
- Không học tham số; không tối ưu tốc độ.
- Không hợp nhất nhiều nguồn điểm (RRF thuộc bài 10).
- Không hỗ trợ đồ thị có trọng số cạnh (đó là phần mở rộng).
