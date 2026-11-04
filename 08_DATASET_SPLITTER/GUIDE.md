# GUIDE — Dataset splitter an toàn

## Bước 0 — Crate

```bash
cargo new dataset-split
cd dataset-split
```

Không cần dependency. Chia module:

```text
src/main.rs        CLI, exit code
src/config.rs      parse args
src/collect.rs     thu thập + sắp xếp
src/plan.rs        SplitMix64, shuffle, chia
src/apply.rs       preflight + ghi + manifest
```

Bạn có thể gộp nếu muốn, nhưng tách `plan` khỏi `apply` là cách tốt nhất để chứng minh dry-run không ghi.

## Bước 1 — An toàn trước tiên

Trước khi viết logic chia, viết hai hàm:

- `plan_only(config) -> Vec<Assignment>`: thuần, không I/O ghi.
- `execute(assignments, config) -> Result<Report, ApplyError>`: mọi thứ chạm filesystem.

`main` chỉ gọi `execute` khi `--apply`. Dry-run in kế hoạch từ `plan_only`. Nhờ vậy, test dry-run chỉ cần kiểm tra `plan_only` và một snapshot thư mục.

## Bước 2 — Parse CLI

Dùng thủ công như bài 07 hoặc một crate nhỏ; bài tập khuyến khích thủ công để hiểu.

Các bẫy:

- `--strategy` nhận ba giá trị; giá trị lạ → exit 2.
- `--ratio` parse `f64`, kiểm tra `is_finite` và `0 < r < 1`.
- `--seed` parse `u64`; `-1` phải lỗi, không wrap.
- Cờ lặp → exit 2.
- `--src`/`--dst` thiếu → exit 2 (usage), không phải 3.

Không tự tạo `dst` trong lúc parse. Parse thuần.

## Bước 3 — Thu thập và sắp xếp

`collect(src, recursive)`:

- Nếu không recursive: `read_dir`, lấy entry có `file_type()?.is_file()`, bỏ symlink (kiểm tra `is_symlink()` trước `is_file()`).
- Nếu recursive: duyệt bằng stack; mỗi entry:
  - symlink → tăng `skipped_symlinks`, không đi vào.
  - thư mục → đẩy vào stack.
  - file → lấy.
- Tính đường dẫn tương đối bằng `strip_prefix(src)`, chuyển separator thành `/` để manifest ổn định trên Windows.
- Sắp xếp theo chuỗi tương đối.

Tại sao sắp trước shuffle? Vì `read_dir` không đảm bảo thứ tự; nếu không sắp, cùng seed vẫn có thể ra kế hoạch khác giữa các lần chạy.

Một cái bẫy: trên Windows, `Path` so sánh không phân biệt hoa thường ở filesystem nhưng chuỗi thì có. Dùng chuỗi tương đối đã chuẩn hóa `/` và sắp theo byte; ghi rõ quy ước.

## Bước 4 — SplitMix64

Cài đặt đúng số học wrapping:

```text
fn next_u64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}
```

Không dùng `+=` thường (panic debug khi tràn) và không dùng số học dấu.

Kiểm tra bằng một vector test cố định: với seed 0, ba giá trị đầu phải khớp một implementation tham chiếu bạn tự tính hoặc lấy từ tài liệu SplitMix64. Đừng chỉ tin “chạy được”.

## Bước 5 — Fisher–Yates

```text
for i in (1..v.len()).rev() {
    let j = (next_u64(&mut state) % (i as u64 + 1)) as usize;
    v.swap(i, j);
}
```

Kiểm tra:

- Với vector 1 phần tử, không đổi.
- Với vector 2 phần tử, seed cố định → hoán vị cố định.
- Chạy hai lần cùng seed → giống.
- Mọi phần tử vẫn xuất hiện đúng một lần (đa tập).

Không dùng `sort_by_key(|_| rng)` — không phải shuffle đều và có thể không ổn định.

## Bước 6 — Chia

```text
let n = files.len();
let train_count = ((n as f64) * ratio + 0.5).floor() as usize;
let train_count = train_count.min(n);
let (train, test) = files.split_at(train_count);
```

Chú ý `floor` sau khi cộng 0.5 là “round half up” cho số dương, khớp `f64::round` của nguồn. Không dùng `as usize` trên số âm (không xảy ra vì ratio dương).

Tạo `Assignment { rel_path, split }` cho từng file. Giữ danh sách theo thứ tự đã sắp để manifest ổn định; việc chia dùng vector đã shuffle riêng.

## Bước 7 — Preflight

Viết `preflight(assignments, dst, overwrite) -> Result<(), Conflict>`:

1. Chuẩn hóa `src`, `dst`:
   - `src.canonicalize()`.
   - Nếu `dst` tồn tại, `dst.canonicalize()`.
   - Nếu chưa, lấy tổ tiên gần nhất tồn tại, canonicalize, rồi nối phần còn lại; hoặc đơn giản: `dst.canonicalize()` lỗi thì dùng `dst.parent().canonicalize()` + file name. Ghi rõ cách bạn chọn.
2. Kiểm tra `dst_canon.starts_with(&src_canon)` → `DstInsideSrc`.
3. Với từng đích:
   - Nếu `symlink_metadata` thành công:
     - là dir → `DestinationIsDirectory`.
     - là file và `!overwrite` → `DestinationExists`.
   - Nếu lỗi `NotFound` → ổn.
   - Lỗi khác → `Io`.
4. Kiểm tra manifest path không nằm trong `src` (canonicalize cha).

Chỉ gọi `create_dir_all` sau preflight.

Một cái bẫy: kiểm tra `dst` nằm trong `src` bằng so chuỗi thô sẽ sai với `..`, symlink, hay đường dẫn tương đối. Luôn canonicalize.

## Bước 8 — Apply

Thứ tự:

1. Preflight.
2. `create_dir_all(dst/train)` và `dst/test` (chỉ khi N > 0).
3. Với từng assignment:
   - Tạo thư mục cha của đích.
   - Theo strategy:
     - `copy`: `fs::copy`.
     - `hardlink`: `fs::hard_link`; nếu lỗi → `fs::copy`, đánh dấu fallback.
     - `move`: `fs::rename`; lỗi → dừng với `MoveFailed`.
   - Cập nhật tiến độ mỗi 10 file ra stderr.
4. Ghi manifest (nếu có) sau khi tất cả thành công.
5. In tóm tắt.

Về “không ghi một phần”: preflight loại xung đột đã biết, nhưng lỗi I/O giữa chừng vẫn có thể để lại file đã ghi. Đừng hứa rollback nếu chưa cài. Manifest không ghi khi lỗi, để không tuyên bố thành công giả.

Với `move`, preflight không thể biết `rename` sẽ lỗi xuyên ổ đĩa. Có hai lựa chọn:

- Thử `rename` từng file; nếu lỗi, dừng và báo rõ file nào đã move.
- Kiểm tra `src` và `dst` cùng `st_dev` trước (Unix) nhưng không portable.

Bài tập chọn cách đầu và ghi rõ giới hạn.

## Bước 9 — Manifest

Viết struct serialize bằng tay (không cần serde) hoặc thêm `serde`/`serde_json` nếu muốn học. Với JSON thủ công, phải escape chuỗi đường dẫn (dấu `"`, `\`, ký tự điều khiển).

Gợi ý: dùng `serde` để tránh tự viết JSON encoder; bài học chính không nằm ở JSON. Nếu thêm, ghi dependency và pin phiên bản.

Ghi nguyên tử:

```text
let tmp = manifest_path.with_extension("json.tmp");
write tmp
rename tmp -> manifest_path
```

Trên Windows, `rename` ghi đè file tồn tại có thể lỗi; xử lý bằng xóa đích trước hoặc dùng `fs::rename` sau khi kiểm tra. Ghi rõ hành vi.

## Bước 10 — Test

Dùng `tempfile` crate (dev-dependency) hoặc tự tạo thư mục dưới `target/tmp` và dọn. Các ca:

1. Dry-run: tạo 5 file, chạy `plan_only`, khẳng định `dst` không tồn tại.
2. Apply copy: đếm file, nội dung giống.
3. Cùng seed → cùng tập; so đường dẫn.
4. Seed khác → chỉ khẳng định tổng số file, không khẳng định khác.
5. Preflight xung đột: tạo `dst/train/a.txt`, chạy apply, khẳng định exit 4 và không có file mới.
6. `dst` trong `src` → lỗi.
7. Rỗng → exit 0, không tạo thư mục.
8. Hardlink → `method == "hardlink"` (Unix/Windows NTFS cùng ổ).
9. Manifest: parse, `files` sorted, `counts` đúng.
10. `ratio` biên.

Không test thời gian hay thứ tự tiến trình.

## Bước 11 — Kiểm chứng độc lập

```bash
cargo test
mkdir -p /tmp/ds-src && printf '1' > /tmp/ds-src/a.txt
printf '2' > /tmp/ds-src/b.txt
cargo run -- --src /tmp/ds-src --dst /tmp/ds-out --seed 7
test ! -e /tmp/ds-out && echo "dry-run made no dir"
cargo run -- --src /tmp/ds-src --dst /tmp/ds-out --seed 7 --apply
find /tmp/ds-out -type f | sort
```

Kỳ vọng: dry-run không tạo `/tmp/ds-out`; apply tạo `train/a.txt` hoặc `train/b.txt` tùy hoán vị seed 7, và phần còn lại ở `test/`.

Kiểm tra tất định:

```bash
cargo run -- --src /tmp/ds-src --dst /tmp/ds-out2 --seed 7 --apply
diff <(cd /tmp/ds-out && find . -type f | sort) <(cd /tmp/ds-out2 && find . -type f | sort)
```

Không có output → cùng kế hoạch.

## Bước 12 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Dry-run vẫn tạo thư mục | Gọi `create_dir_all` trước khi kiểm tra `--apply`. |
| Cùng seed ra khác | Chưa sắp danh sách trước shuffle, hoặc PRNG không wrapping. |
| `dst` trong `src` lọt | So sánh chuỗi thay vì canonicalize. |
| Ghi đè ngoài ý muốn | Preflight bỏ qua file tồn tại. |
| Hardlink luôn fallback | `dst` khác ổ đĩa hoặc FS không hỗ trợ; kiểm tra `st_dev`. |
| Move mất file một phần | Không có rollback; ghi rõ hoặc preflight chặt hơn. |
| Manifest lệch thứ tự | Ghi theo thứ tự shuffle thay vì sắp theo path. |
| Windows `\` trong manifest | Chưa chuẩn hóa separator. |
| Ratio 0.5 với N=3 ra 1 thay vì 2 | Dùng `floor` không cộng 0.5; `1.5` phải thành `2`. |

## Bước 13 — Mở rộng

- Thêm `--stratify-by <field>` cho file JSON.
- Thêm `--limit` và `--min-test`.
- Thêm chế độ `--verify` đọc manifest và kiểm tra filesystem khớp.
- Thêm hash SHA-256 vào manifest để kiểm tra toàn vẹn.
- Thêm rollback bằng cách ghi danh sách file đã tạo và xóa khi lỗi (cẩn thận với `--strategy move`, không thể phục hồi nếu nguồn đã mất).

## Tự đánh giá

1. Vì sao phải sắp danh sách trước khi shuffle?
2. Vì sao preflight phải chạy trước `create_dir_all`?
3. Khi nào `hardlink` fallback là chấp nhận được, khi nào không?
4. Vì sao manifest không nên ghi khi apply thất bại giữa chừng?
