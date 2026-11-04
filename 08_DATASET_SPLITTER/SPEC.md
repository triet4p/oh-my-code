# SPEC — Dataset splitter an toàn

## Mục tiêu hành vi

Chia các file trong một thư mục nguồn thành hai tập `train` và `test` theo tỉ lệ, tất định theo seed, với ba chiến lược ghi. Mặc định chỉ in kế hoạch. Chỉ khi có `--apply` mới tạo thư mục và ghi file. Mọi xung đột đích được phát hiện trước khi ghi file đầu tiên.

## CLI

```text
dataset-split --src DIR --dst DIR [--ratio R] [--seed N] [--recursive]
              [--strategy copy|hardlink|move] [--apply] [--overwrite]
              [--manifest PATH]
```

| Tùy chọn | Mặc định | Ý nghĩa |
|---|---|---|
| `--src` | bắt buộc | thư mục nguồn |
| `--dst` | bắt buộc | thư mục đích; `train/`, `test/` được tạo bên trong |
| `--ratio` | `0.8` | tỉ lệ train, `0 < R < 1`, hữu hạn |
| `--seed` | `42` | số nguyên không dấu 64-bit |
| `--recursive` | tắt | lấy file trong thư mục con |
| `--strategy` | `copy` | `copy`, `hardlink`, `move` |
| `--apply` | tắt | thực thi; không có thì dry-run |
| `--overwrite` | tắt | cho phép ghi đè file đích đã tồn tại |
| `--manifest` | không | ghi manifest JSON vào đường dẫn |

`--apply` là điều kiện duy nhất để thay đổi filesystem. `--overwrite` không có hiệu lực khi không có `--apply`.

## Thu thập file

- `--src` phải tồn tại và là thư mục; nếu không → exit 3.
- Không đệ quy: chỉ các entry là file thường trực tiếp trong `src`.
- Đệ quy: duyệt cây, chỉ file thường.
- Bỏ qua symlink (cả file và thư mục) và ghi cảnh báo đếm được vào manifest (`skipped_symlinks`).
- Bỏ qua file ẩn? Không; mọi file thường đều được lấy. Ghi rõ để tránh bất ngờ.
- Khóa sắp xếp: đường dẫn tương đối dùng `/`, sắp theo thứ tự byte tăng dần. Sắp **trước** khi shuffle.

## Chia

```text
N = files.len()
train_count = floor(N * ratio + 0.5)     // làm tròn nửa lên (half away from zero)
train = shuffled[0..train_count]
test  = shuffled[train_count..N]
```

- `train_count` được kẹp vào `[0, N]` (không cần thiết nếu ratio hợp lệ nhưng vẫn làm).
- `N = 0`: hợp lệ; manifest có `total: 0`; `--apply` không tạo thư mục; exit 0.
- `N = 1`: toàn bộ vào train nếu `ratio >= 0.5`, ngược lại vào test, theo công thức.
- Không đảm bảo tập test khác rỗng; người dùng chọn ratio.

## Shuffle tất định

Dùng SplitMix64 và Fisher–Yates:

```text
state = seed
next_u64():
    state = state + 0x9E3779B97F4A7C15            (wrapping 64-bit)
    z = state
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9      (wrapping)
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB      (wrapping)
    return z ^ (z >> 31)

shuffle(v):
    for i from len(v)-1 down to 1:
        j = next_u64() % (i + 1)
        swap(v[i], v[j])
```

- Dùng modulo; thiên lệch không đáng kể với mục đích chia file và được chấp nhận. Ghi rõ nếu muốn loại bỏ bằng rejection sampling.
- Không seed lại giữa chừng.
- Cùng seed + cùng danh sách đã sắp → cùng hoán vị trên mọi nền tảng (số học 64-bit xác định).

## Preflight

Trước khi tạo thư mục hoặc ghi file, kiểm tra:

1. `dst` không trùng `src` và không nằm trong `src` sau khi canonicalize (nếu `dst` chưa tồn tại, canonicalize tổ tiên gần nhất tồn tại).
2. Với mỗi file, đích `dst/train/<rel>` hoặc `dst/test/<rel>`:
   - Nếu tồn tại và là thư mục → lỗi.
   - Nếu tồn tại và không có `--overwrite` → lỗi.
3. Nếu `--manifest` trỏ vào bên trong `src` → lỗi (tránh tự ghi vào dữ liệu nguồn).

Chỉ khi tất cả đạt mới bắt đầu ghi. Nếu có lỗi preflight, **không file nào bị thay đổi** và exit 4.

## Chiến lược ghi

| Chiến lược | Hành vi |
|---|---|
| `copy` | `std::fs::copy`; giữ nguyên nội dung; không giữ metadata thời gian (tùy nền tảng) |
| `hardlink` | thử `std::fs::hard_link`; nếu lỗi (khác ổ đĩa, FS không hỗ trợ) → fallback `copy`, ghi `fallback: true` |
| `move` | `std::fs::rename`; **không** fallback; lỗi xuyên ổ đĩa → exit 4 với thông điệp rõ |

Với `--recursive`, giữ cấu trúc thư mục con dưới `train/`/`test/`; tạo thư mục cha trước khi ghi.

## Manifest

JSON, UTF-8, khóa theo thứ tự cố định:

```json
{
  "schema_version": 1,
  "dry_run": true,
  "src": "data",
  "dst": "out",
  "ratio": 0.8,
  "seed": 42,
  "strategy": "copy",
  "recursive": false,
  "counts": { "total": 5, "train": 4, "test": 1, "skipped_symlinks": 0 },
  "files": [
    { "path": "a.txt", "split": "train", "method": "copy", "fallback": false }
  ]
}
```

- `files` sắp theo `path` tăng dần, không theo thứ tự shuffle.
- Dry-run: `method` là chiến lược dự kiến, `fallback` luôn `false` (chưa biết).
- Khi `--manifest` không có: in manifest ra `stdout` (cả dry-run và apply).
- Khi có `--manifest`: ghi file; không in manifest ra stdout, chỉ in tóm tắt.
- Ghi manifest nguyên tử: ghi file tạm cùng thư mục rồi `rename`. Với apply, chỉ ghi sau khi mọi file thành công.
- `src`, `dst` giữ đúng chuỗi người dùng nhập, không canonicalize, để manifest ổn định.

## Output và mã thoát

Stdout (dry-run):

```text
DRY RUN: 5 files -> train=4 test=1 (ratio=0.800, seed=42, strategy=copy)
```

Apply:

```text
APPLIED: 5 files -> train=4 test=1 (ratio=0.800, seed=42, strategy=copy)
```

Tiến độ mỗi 10 file ra `stderr` khi apply.

| Tình huống | Mã |
|---|---:|
| Thành công (kể cả N=0) | 0 |
| Thiếu `--src`/`--dst`, giá trị lạ, trùng cờ | 2 |
| `src` không hợp lệ, ratio ngoài khoảng, đích nằm trong nguồn | 3 |
| Xung đột đích, lỗi I/O, move xuyên ổ đĩa | 4 |

## Ví dụ

Nguồn có `a.txt b.txt c.txt d.txt e.txt`; lệnh:

```bash
dataset-split --src data --dst out --ratio 0.8 --seed 42
```

Kết quả: chỉ in dòng `DRY RUN` và manifest; `out/` không được tạo. Kiểm tra:

```bash
test ! -e out && echo "no writes"
```

Thêm `--apply`:

```bash
dataset-split --src data --dst out --ratio 0.8 --seed 42 --apply
```

Tạo `out/train` (4 file) và `out/test` (1 file). Chạy lại cùng lệnh vào `out2` cho cùng phân bổ thành viên:

```bash
dataset-split --src data --dst out2 --ratio 0.8 --seed 42 --apply
diff <(cd out && find . -type f | sort) <(cd out2 && find . -type f | sort) && echo SAME_PLAN
```

(So sánh đường dẫn tương đối; nội dung file giống nếu nguồn không đổi.)

Xung đột: chạy lại `--apply` vào `out` không có `--overwrite` → exit 4, không file nào bị sửa (preflight chặn trước).

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| `src` rỗng | manifest total 0, exit 0, không tạo thư mục |
| `src` chỉ có thư mục con, không `--recursive` | total 0 |
| `src` chỉ có symlink | total 0, `skipped_symlinks > 0` |
| `dst` nằm trong `src` | exit 3 trước mọi ghi |
| `dst == src` | exit 3 |
| `ratio = 0.0` / `1.0` / NaN / inf | exit 3 |
| `N = 1`, ratio 0.8 | 1 train, 0 test |
| `N = 2`, ratio 0.01 | 0 train, 2 test (theo công thức) |
| Tên file trùng ở hai thư mục con, `--recursive` | không xung đột vì giữ đường dẫn tương đối |
| File đích đã tồn tại, không `--overwrite` | exit 4, không ghi file nào |
| `--overwrite` với đích là thư mục | exit 4 |
| Hardlink xuyên ổ đĩa | fallback copy, `fallback: true` |
| Move xuyên ổ đĩa | exit 4, có thể đã move một phần? Preflight không phát hiện được; xem GUIDE |
| Ctrl+C giữa apply | có thể đã ghi một phần; manifest không được ghi; exit 130 nếu bắt |

## Tiêu chí nghiệm thu

1. Dry-run không thay đổi filesystem: so snapshot cây trước/sau.
2. `--apply` tạo đúng số file train/test theo công thức.
3. Cùng seed và cùng danh sách nguồn → cùng tập thành viên; chạy hai đích khác nhau rồi so đường dẫn tương đối.
4. Seed khác → kế hoạch có thể khác; test không khẳng định “phải khác” với N nhỏ.
5. Preflight xung đột: tạo sẵn một file đích, chạy apply không `--overwrite`, khẳng định exit 4 và **không** file mới nào được tạo.
6. `dst` trong `src` bị từ chối.
7. Manifest parse được, có đủ khóa, `files` sắp theo path.
8. `src` rỗng exit 0, không tạo `train/test`.
9. Test hardlink (trên cùng ổ đĩa) cho `method: hardlink`, `fallback: false`.
10. `cargo test` xanh.

## Non-goals

- Chia stratified theo nhãn hoặc theo nhóm.
- Chống trùng nội dung (hash).
- Nén, mã hóa, upload.
- Sao chép metadata (quyền, mtime) một cách đầy đủ.
- Rollback tự động khi lỗi giữa chừng.
- Theo dõi file thay đổi trong lúc chạy.
