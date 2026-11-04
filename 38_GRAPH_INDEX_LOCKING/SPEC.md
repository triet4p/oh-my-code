# SPEC 38 — Đồ thị hai khóa

## 1. Kiểu dữ liệu

```rust
pub type NodeId = u64;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MemoryNode {
    pub id: NodeId,
    pub label: String,
}

#[derive(Clone, Debug, PartialEq)]
pub struct EdgeData {
    pub weight: i64,
}

#[derive(Debug)]
pub enum GraphError {
    DuplicateNode(NodeId),
    MissingNode(NodeId),
    InvalidNode(String),   // label rỗng
}
```

`NodeId` dùng `u64` thay UUID để test dễ; thiết kế không phụ thuộc kiểu ID.

## 2. Cấu trúc

```rust
pub struct CognitiveGraph {
    indices: RwLock<HashMap<NodeId, usize>>,
    graph: RwLock<GraphData>,
}

struct GraphData {
    nodes: Vec<MemoryNode>,
    edges: Vec<EdgeRecord>,
}

struct EdgeRecord {
    source: usize,
    target: usize,
    data: EdgeData,
}
```

Hai khóa tách biệt. `graph` chứa cả node và cạnh; `indices` chỉ là bảng tra.

## 3. API

```rust
impl CognitiveGraph {
    pub fn new() -> Self;
    pub fn add_node(&self, node: MemoryNode) -> Result<(), GraphError>;
    pub fn add_edge(&self, source: NodeId, target: NodeId, data: EdgeData) -> Result<(), GraphError>;
    pub fn get_node(&self, id: NodeId) -> Result<MemoryNode, GraphError>;
    pub fn node_count(&self) -> usize;
    pub fn edge_count(&self) -> usize;
}
```

- `label` rỗng/toàn khoảng trắng → `InvalidNode`.
- `weight` mọi `i64` hợp lệ.

## 4. Thứ tự khóa (bắt buộc)

Thứ tự toàn cục: **indices trước, graph sau**.

### 4.1. `add_node`

1. `let mut indices = self.indices.write()`.
2. Nếu `indices.contains_key(&id)` → trả `DuplicateNode`; guard tự thả.
3. `let mut graph = self.graph.write()`.
4. `let idx = graph.nodes.len()`; `graph.nodes.push(node)`.
5. `indices.insert(id, idx)`.
6. Thả graph, rồi indices.

Nếu bước 5 không thể thất bại (HashMap insert), bất biến giữ.

### 4.2. `add_edge`

1. `let (src_idx, tgt_idx) = { let indices = self.indices.read(); ... }` — copy `usize`, **guard thả ở cuối block**.
2. Nếu thiếu source → `MissingNode(source)`; thiếu target → `MissingNode(target)`. Kiểm tra source trước.
3. `let mut graph = self.graph.write()`.
4. Kiểm tra lại `src_idx < graph.nodes.len()` và `tgt_idx < ...`; nếu không → `MissingNode` (phòng thủ; không xảy ra nếu không có remove).
5. Push `EdgeRecord`.
6. Thả graph.

Không được giữ `indices` guard khi bước 3. Nếu không, luồng A giữ read indices chờ write graph, luồng B giữ write indices chờ write graph? Thực ra deadlock cần hai khóa ngược thứ tự; nhưng quy tắc chung: không lồng read indices với write graph.

### 4.3. `get_node`

1. Block đọc indices, copy `usize`, thả.
2. Đọc graph.
3. `nodes.get(idx)` → clone hoặc `MissingNode`.

### 4.4. Đếm

`node_count`: read graph, `nodes.len()`.
`edge_count`: read graph, `edges.len()`.

## 5. Bất biến

1. Mọi `(id, idx)` trong `indices` có `idx < graph.nodes.len()`.
2. `graph.nodes[idx].id == id`.
3. Không có hai node cùng id.
4. `edges` chỉ chứa index hợp lệ tại thời điểm thêm.
5. Sau khi `add_node` trả `Ok`, node quan sát được qua `get_node` và đếm.
6. Sau khi `add_edge` trả `Ok`, `edge_count` tăng đúng 1.

Không có removal nên index ổn định vĩnh viễn. Nếu thêm removal, phải có generation hoặc tombstone; ghi vào mở rộng.

## 6. Ví dụ cụ thể

```rust
let g = CognitiveGraph::new();
g.add_node(MemoryNode { id: 1, label: "A".into() })?;
g.add_node(MemoryNode { id: 2, label: "B".into() })?;
g.add_edge(1, 2, EdgeData { weight: 5 })?;

assert_eq!(g.node_count(), 2);
assert_eq!(g.edge_count(), 1);
assert_eq!(g.get_node(1)?.label, "A");

assert!(matches!(g.add_node(MemoryNode { id: 1, label: "dup".into() }), Err(GraphError::DuplicateNode(1))));
assert!(matches!(g.add_edge(1, 99, EdgeData { weight: 1 }), Err(GraphError::MissingNode(99))));
assert_eq!(g.edge_count(), 1);
```

## 7. Stress test

8 luồng, mỗi luồng:

- id gốc `t*1000`, thêm 100 node `id = base + i`, label `t-i`.
- thêm 100 cạnh nối vòng `base+i → base+(i+1)%100`.

Sau khi join:

- `node_count == 800`.
- `edge_count == 800`.
- Mọi node `get_node` thành công.
- Không panic, không deadlock.

Dùng `mpsc::channel` + `recv_timeout(Duration::from_secs(5))` cho mỗi luồng hoặc một kênh chung; nếu timeout → panic test. Không assert thứ tự.

## 8. Trường hợp biên

| # | Tình huống | Kết quả |
|---|---|---|
| 1 | Label rỗng | `InvalidNode` |
| 2 | Label toàn space | `InvalidNode` |
| 3 | Hai node cùng id tuần tự | lần hai `DuplicateNode` |
| 4 | Hai node cùng id song song | đúng một `Ok`, một `DuplicateNode` |
| 5 | Edge source thiếu | `MissingNode(source)` |
| 6 | Edge target thiếu | `MissingNode(target)` |
| 7 | Cả hai thiếu | báo source |
| 8 | Self-loop | hợp lệ |
| 9 | Cạnh trùng | hợp lệ, edge_count tăng |
| 10 | `get_node` id lạ | `MissingNode` |
| 11 | Đồ thị rỗng | count 0 |
| 12 | 800 node/edge song song | đúng count |
| 13 | Poisoned lock (panic trong thread) | panic có thông điệp, không UB |
| 14 | `weight = i64::MIN/MAX` | hợp lệ |

## 9. Tiêu chí chấp nhận

- [ ] Ví dụ mục 6 chạy đúng.
- [ ] `add_edge` không giữ read guard khi lấy write graph (kiểm tra bằng code review; có thể thêm instrumentation tạm).
- [ ] Stress 8×100 hoàn tất <5 giây, count 800/800.
- [ ] Không `unsafe`.
- [ ] Không crate ngoài.
- [ ] `cargo test` không cần mạng sau khi có toolchain.
- [ ] Thứ tự lỗi source trước target.
- [ ] `get_node` trả clone, sửa clone không ảnh hưởng graph.

## 10. Non-goals

- Không xóa node/cạnh, không cập nhật.
- Không duyệt đồ thị, không thuật toán lan truyền.
- Không async/tokio, không persistence.
- Không tối ưu lock-free.
