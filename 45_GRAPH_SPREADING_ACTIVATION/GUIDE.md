# GUIDE 45 — Lan truyền kích hoạt trên đồ thị có kiểu cạnh

## 1. Đọc nguồn: ba cơ chế chống bùng nổ

Nguồn có ba thứ khác nhau, đừng gộp:

| Cơ chế | Câu hỏi nó trả lời | Hệ quả khi thiếu |
|---|---|---|
| `a_max` | "Một nút có thể mạnh đến đâu?" | Năng lượng tăng vô hạn trong chu trình |
| `epsilon` | "Nút yếu đến mức nào thì thôi?" | Lan truyền lan sang nút gần 0, tốn vô ích |
| `max_fires` + trơ | "Một nút được phát bao nhiêu lần?" | Chu trình tự kích hoạt mãi mãi |

Bài tập yêu cầu **cả ba** cùng tồn tại và cùng được test riêng, vì mỗi cái che một loại lỗi khác nhau.

## 2. Kiến trúc Rust không crate

```text
src/
├── main.rs      # đọc args, gọi parse + run + print, map lỗi -> exit code
├── graph.rs     # Graph { names, index, out_edges }
├── params.rs    # ActivationParams + parse từ dòng "param"
├── activation.rs# run(graph, params) -> ActivationOutcome
└── lib.rs       # re-export cho cargo test
```

Gợi ý kiểu:

- `struct Edge { to: usize, weight: f64, kind: EdgeKind }`
- `struct Graph { names: Vec<String>, index: HashMap<String, usize>, out: Vec<Vec<Edge>> }`
- `struct ActivationOutcome { activation: Vec<f64>, fires: Vec<u32>, steps_run: u32 }`

Giữ `lib.rs` + `main.rs` để `cargo test` import được. Nếu bạn chỉ có `main.rs`, test vẫn chạy nhưng khó tách.

## 3. Thứ tự cài đặt

### Bước 1 — Parser

Parse **trước**, chạy sau. Mọi lỗi cú pháp phải xuất hiện trước khi bắt đầu lan truyền; nếu không, fixture lỗi sẽ để lại trạng thái dở.

- Bỏ dòng trống và dòng bắt đầu bằng `#`.
- `split_whitespace()` — không dùng `split(' ')`, vì TAB và nhiều dấu cách sẽ tạo trường rỗng.
- `edge` có thể nhắc nút chưa tồn tại: tạo nút mới với `A = 0`, `fires = 0`.
- Kiểm tra `a_max > 0`, `delta >= 0`, `epsilon >= 0`, `max_steps >= 0`, `max_fires >= 0`.

### Bước 2 — Đăng ký nút theo thứ tự từ điển

Sắp `names` **một lần** sau khi parse, rồi xây lại `index` và `out` theo thứ tự đó. Vì sao: thứ tự duyệt nút ảnh hưởng tới thứ tự cộng vào `buf`; dù phép cộng `f64` gần như giao hoán, sai số làm tròn vẫn có thể lệch ở chữ số cuối. Cố định thứ tự giúp output ổn định.

Lưu ý: sắp lại `names` phải ánh xạ lại chỉ số cạnh — dễ sai. Cách an toàn hơn: giữ `names` theo thứ tự xuất hiện, nhưng khi lặp bước, tạo `order: Vec<usize>` đã sắp theo `names` và lặp theo `order`. Ít lỗi hơn nhiều.

### Bước 3 — Vòng bước

Cấu trúc gợi ý:

```text
let mut buf = vec![0.0; n];
let mut fired_this_step = Vec::new();
for u in &order {
    if a[*u] + 1e-15 < eps { continue; }        // so sánh có dung sai? xem 4.1
    if fires[*u] >= max_fires { continue; }
    if refractory.contains(u) { continue; }
    fired_this_step.push(*u);
    fires[*u] += 1;
    for e in &out[*u] {
        buf[e.to] += a[*u] * e.weight * e.kind.multiplier() * delta;
    }
}
for v in 0..n { a[v] = (a[v] + buf[v]).min(a_max); }
refractory = fired_this_step.iter().copied().collect();
steps_run += 1;
```

Hai lỗi kinh điển ở đây:

1. Cập nhật `a[v]` **bên trong** vòng `u` — sai, vì nút sau sẽ đọc giá trị mới.
2. Quên reset `buf` mỗi bước — năng lượng cộng dồn vĩnh viễn.

### Bước 4 — Điều kiện dừng

```text
for _ in 0..max_steps {
    ...một bước...
    if fired_this_step.is_empty() && !co_the_phat_tiep() { break; }
}
```

`co_the_phat_tiep()` = tồn tại `v` với `A[v] >= epsilon` và `fires[v] < max_fires` (bỏ qua trơ).

Vì sao cần vế thứ hai: trơ chỉ chặn một bước. Nếu bạn dừng ngay khi bước rỗng, ví dụ 5.3 của SPEC sẽ dừng ở bước 2 với `fires = 1` thay vì đi tiếp tới bước 4 với `fires = 2`. Đây là lỗi tôi đã mắc khi soạn ví dụ; script đối chứng bắt được.

`steps_run` tăng **trước** khi kiểm tra, nên bước rỗng cuối cùng vẫn được đếm.

### Bước 5 — In

Sắp theo `(-activation, name)`; dùng `sort_by` với `partial_cmp` trên `f64` (mọi giá trị đều hữu hạn nên an toàn), rồi in `{:.6}`.

Cảnh báo: `{:.6}` làm tròn; hai giá trị khác nhau ở chữ số thứ 7 in ra giống nhau. Nếu muốn phân biệt, in thêm `{:e}` trong chế độ debug.

## 4. Cạm bẫy

### 4.1 So sánh với `epsilon`

`A[u] >= epsilon` theo SPEC là so sánh trực tiếp, **không** dung sai. Thêm `1e-15` sẽ làm một fixture biên cho kết quả khác — hãy chọn một cách và ghi rõ. SPEC chọn so sánh trực tiếp.

### 4.2 Cộng dồn rồi kẹp

Đã giải thích ở SPEC 5.2. Nếu bạn kẹp sau từng cạnh và sau này thêm trọng số âm (ngoài phạm vi bài), kết quả sẽ khác. Giữ đúng thứ tự: `buf` → `a + buf` → `min`.

### 4.3 Trơ "một bước" không phải "vĩnh viễn"

Nhiều cài đặt nhầm `just_fired` thành tập cấm vĩnh viễn. Hệ quả: nút chỉ phát một lần, `max_fires` trở nên vô nghĩa. Test 5.3 phân biệt rõ: `a` phát ở bước 1 và 3.

### 4.4 `min` với NaN

Nếu ai đó nhập `delta = NaN`, `f64::min` trả về giá trị còn lại (không lan NaN), che mất lỗi. Parser phải từ chối `NaN`/`inf` trước khi vào vòng lặp — `is_finite()`.

### 4.5 Chuỗi byte và Unicode

Sắp theo "so sánh chuỗi byte" (mặc định `str::cmp`) khác sắp theo locale. Với tên ASCII không sao; với tên có dấu, output có thể khác máy khác. Ghi rõ hoặc giới hạn tên nút là ASCII.

### 4.6 Tràn chỉ số

`edge` tạo nút mới: nếu bạn push vào `out` nhưng quên push `names`, chỉ số lệch và panic ở chỗ khác. Viết hàm `intern(name) -> usize` duy nhất.

## 5. Kiểm thử

`cargo test` cần tối thiểu:

| Test | Nội dung |
|---|---|
| `chain_single_fire` | 5.1, so từng giá trị với dung sai `1e-12` |
| `saturation_guard` | 5.2, `A[b] == 2.0` chính xác |
| `quota_and_refractory` | 5.3, `fires == 2`, `steps_run == 4` |
| `cycle_terminates` | 5.4, `steps_run == 7` |
| `max_steps_cap` | 5.5, `steps_run == 3` |
| `unknown_kind` | lỗi đúng biến thể |
| `order_independence` | đảo thứ tự dòng `edge`, cùng output |

Dùng `approx` tự viết (không crate): `assert!((x - y).abs() < 1e-12)`.

## 6. Kiểm chứng độc lập

```bash
rustc --version          # >= 1.70
cargo test
cargo run --quiet -- fixtures/chain.txt
cargo run --quiet -- fixtures/cycle.txt
```

So `chain.txt` với khối ở SPEC mục 3. Kiểm tra bất biến bằng mắt hoặc bằng script:

```bash
cargo run --quiet -- fixtures/saturate.txt | awk -F'\t' 'NF==3 && $1!="steps" {if ($2+0 > 2.0) print "VUOT", $0}'
```

Không được in dòng `VUOT`. Kiểm tra mã thoát:

```bash
cargo run --quiet -- fixtures/bad_kind.txt; echo "exit=$?"
```

Kỳ vọng `exit=2`.

## 7. Gợi ý

- Viết `fn step(...) -> Vec<usize>` trả danh sách nút đã phát; vòng ngoài chỉ lo đếm và dừng. Test hàm `step` riêng — dễ hơn test cả vòng.
- Viết `EdgeKind::multiplier()` bằng `match` với nhánh `_ => Err(...)` ở parser, đừng để `_ => 0.0`.
- Nếu output lệch ở chữ số thứ 6, in thêm `{:?}` (full precision) ở chế độ `--debug` thay vì sửa hằng số.
- Giữ `order` như một `Vec<usize>` đã sắp; đừng sắp lại mỗi bước.

## 8. Mở rộng

- **Truy vết nguồn**: mỗi nút lưu top-3 cạnh đóng góp nhiều nhất trong bước cuối; in kèm để giải thích "vì sao nút này mạnh".
- **Suy giảm theo thời gian**: `A[v] *= (1 - decay)` sau mỗi bước; so hành vi với bản không suy giảm.
- **Đa nguồn**: nhiều `seed` với giá trị khác nhau; kiểm tra tuyến tính khi không chạm trần.
- **Đồ thị lớn**: đọc từ file CSV cạnh và đo thời gian mỗi bước; thêm early-exit khi `buf` toàn 0.
- **So sánh với PPR**: cài PageRank cá nhân hoá trên cùng fixture để thấy hai cách "lan" khác nhau (bài 52 cũng làm việc này ở dạng retriever).
