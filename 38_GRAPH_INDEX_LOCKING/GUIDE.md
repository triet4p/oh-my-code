# GUIDE 38 — Thiết kế khóa và stress test

## 1. Kiến trúc

```
src/
├─ lib.rs      # CognitiveGraph, types, errors
└─ tests/
   └─ graph.rs
Cargo.toml
fixtures/      # tùy chọn
```

Không cần crate; `Cargo.toml` chỉ khai báo package.

## 2. Tại sao hai khóa

Nếu chỉ một khóa, mọi thao tác tuần tự; đơn giản nhưng bài học về lồng khóa biến mất. Nếu hai khóa, phải có thứ tự. Bài giữ hai khóa như nguồn:

- `indices`: bảng tra nhanh.
- `graph`: dữ liệu thật.

## 3. Mẫu add_edge

```rust
let (src_idx, tgt_idx) = {
    let indices = self.indices.read().expect("indices poisoned");
    let s = *indices.get(&source).ok_or(GraphError::MissingNode(source))?;
    let t = *indices.get(&target).ok_or(GraphError::MissingNode(target))?;
    (s, t)
}; // guard drop ở đây
let mut graph = self.graph.write().expect("graph poisoned");
```

Đây là **khung**, không phải lời giải. Điểm mấu chốt là block `{}` và `*` copy.

Nếu viết:

```rust
let indices = self.indices.read()?;
let mut graph = self.graph.write()?;   // giữ read guard
```

bạn đang lồng khóa. Với `std::sync::RwLock`, điều này có thể tự deadlock nếu writer đang chờ giữa hai bước (writer preference), hoặc tạo điều kiện cho luồng khác đảo thứ tự. Đừng làm.

## 4. Mẫu add_node

Giữ write indices suốt quá trình để không ai thấy trạng thái nửa vời:

```
write indices
  if dup: return
  write graph
    push node
    insert index
  drop graph
drop indices
```

Nếu thả indices trước khi insert, luồng khác có thể thấy graph có node nhưng map chưa có; `get_node` sẽ báo missing dù node tồn tại. Giữ đến sau insert.

## 5. Poisoning

`RwLock` bị poison nếu thread panic khi giữ guard. Bài chọn `expect("... poisoned")` để fail fast; không cố phục hồi dữ liệu có thể không nhất quán. Ghi rõ.

## 6. Borrow checker

- Không trả `&MemoryNode` từ trong guard; trả clone.
- Không lưu `usize` index ra ngoài khi chưa kiểm tra graph.
- `HashMap::get` trả `&usize`; dùng `*` để copy.
- `graph.nodes[idx]` sau khi có write guard; kiểm tra bounds trước.

## 7. Stress test

```rust
let (tx, rx) = mpsc::channel();
for t in 0..8 {
    let g = Arc::clone(&graph);
    let tx = tx.clone();
    thread::spawn(move || {
        for i in 0..100 { g.add_node(...).unwrap(); }
        for i in 0..100 { g.add_edge(..., ...).unwrap(); }
        tx.send(t).unwrap();
    });
}
drop(tx);
for _ in 0..8 {
    rx.recv_timeout(Duration::from_secs(5)).expect("deadlock?");
}
```

**Bẫy:** nếu panic trong thread, kênh không gửi; `recv_timeout` báo lỗi nhưng không in panic của thread. Dùng `JoinHandle` sau timeout hoặc `thread::Builder` + hook; đơn giản: kiểm tra count sau khi nhận đủ.

Không assert thứ tự node; chỉ count và `get_node`.

## 8. Bẫy thường gặp

- **Lồng read indices + write graph**: deadlock tiềm ẩn.
- **Thả indices quá sớm trong add_node**: vi phạm bất biến quan sát.
- **Dùng `indices.get` rồi lấy graph trong cùng biểu thức**: guard sống đến cuối statement, có thể lồng ngoài ý muốn.
- **Clone node thay vì copy index**: tốn kém; index là `Copy`.
- **Không kiểm tra bounds lại**: nếu sau này thêm remove, index cũ treo.
- **Dùng `Mutex` thay `RwLock`**: đúng nhưng mất song song đọc; bài yêu cầu RwLock.
- **Trả tham chiếu nội bộ**: borrow checker chặn, nhưng đừng cố `unsafe`.
- **Stress test không timeout**: treo CI.
- **Assert thứ tự node**: không tất định.
- **Bỏ qua label rỗng**: dữ liệu xấu vào graph.

## 9. Kiểm chứng

```bash
cd 38_GRAPH_INDEX_LOCKING
cargo test
cargo test --release
```

Nếu có `clippy`:

```bash
cargo clippy -- -D warnings
```

Kiểm tra deadlock thủ công: chạy test 20 lần:

```bash
for i in $(seq 1 20); do cargo test --quiet || break; done
```

Windows PowerShell:

```powershell
1..20 | ForEach-Object { cargo test --quiet; if ($LASTEXITCODE -ne 0) { break } }
```

## 10. Gợi ý

- Viết tuần tự trước: add/get/dup/missing.
- Thêm test `get_node` trả clone: sửa clone, đọc lại.
- Viết stress với 2 luồng trước, rồi 8.
- Dùng `Arc<CognitiveGraph>`; graph không cần `Clone`.
- Có thể thêm `#[cfg(test)]` instrumentation đếm số lần acquire để kiểm tra thứ tự, nhưng đừng đưa vào production.

## 11. Mở rộng

1. Port sang `tokio::sync::RwLock`, giữ nguyên thứ tự.
2. Thêm xóa node với tombstone/generation.
3. Thêm `get_edge`/duyệt BFS.
4. Thêm petgraph backend sau interface.
5. Thêm test property-based cho bất biến.
