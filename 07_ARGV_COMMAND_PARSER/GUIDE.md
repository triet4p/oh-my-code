# GUIDE — Argv command parser

## Bước 0 — Crate

```bash
cargo new ezcli --lib
cd ezcli
```

`Cargo.toml` chỉ cần `[package]` và `[dependencies]` rỗng. Viết trong `src/lib.rs`; test trong `#[cfg(test)] mod tests`.

## Bước 1 — Quyết định kiểu dữ liệu trước

Tách rõ:

- `Command`: kết quả đã hiểu.
- `ParseError`: lỗi cú pháp.
- `SplitStrategy`: enum nhỏ, `Copy`.

Không đưa `String` đã join trở lại vào `Command`. Mỗi trường có kiểu riêng; parser chịu trách nhiệm chuyển.

Tự hỏi: `ratio` nên là `f64` hay `f32`? Nguồn dùng `f32`; bài tập chọn `f64` để ít sai số khi so `0.7`. Ghi rõ lựa chọn.

## Bước 2 — Vòng lặp quét

Đừng viết `match command` với hàng chục `args.get(n)`. Viết một bộ quét chung:

```text
struct Parsed {
    positionals: Vec<String>,
    flags: BTreeMap<String, String>,   // cờ có giá trị
    switches: BTreeSet<String>,        // cờ boolean
}
```

Gợi ý thuật toán:

1. `i = 0`; `literal = false`.
2. Nếu `literal`: đẩy token vào positional.
3. Nếu token == `--`: bật `literal`.
4. Nếu token bắt đầu `--`:
   - Tách tại `=` đầu tiên nếu có → `(name, Some(value))`.
   - Nếu là cờ boolean của lệnh: có value → `UnexpectedValue`; chưa có → thêm; đã có → `DuplicateFlag`.
   - Nếu là cờ có giá trị: đã có → `DuplicateFlag`; có value từ `=` (kể cả rỗng) → kiểm tra rỗng; không có → lấy token kế tiếp nếu tồn tại và (không bắt đầu bằng `-` hoặc chính là `-`); nếu không → `MissingFlagValue`.
5. Nếu token bắt đầu `-` (một gạch) và không phải `-`: `UnknownFlag` (trừ khi lệnh chấp nhận).
6. Ngược lại: positional.

Vấn đề: bước 4 cần biết lệnh nào hỗ trợ cờ nào. Hãy xác định lệnh trước, rồi truyền một “schema cờ” vào bộ quét. Schema có thể là:

```text
enum FlagKind { Switch, Value }
fn flag_kind(command: &str, name: &str) -> Option<FlagKind>
```

Đây là chỗ dễ sai: nếu bạn coi mọi `--x` là cờ có giá trị, `--copy` sẽ nuốt `DST`.

## Bước 3 — Ánh xạ positional

Sau khi quét, mỗi lệnh có arity:

| Lệnh | Positional bắt buộc | Tối đa |
|---|---:|---:|
| tree | 0 | 1 |
| find | 1 | 2 |
| clean | 1 | 2 |
| split | 2 | 2 |
| env | 2 | 2 |
| help | 0 | 0 |

Viết helper `take(positionals, index, name)` trả `MissingArgument(name)`; sau khi lấy đủ, nếu còn → `UnexpectedArgument(positionals[max].clone())`.

Đừng dùng `positionals.get(n).unwrap()`; dù bạn đã kiểm tra độ dài, một helper trả lỗi rõ ràng dễ bảo trì hơn.

## Bước 4 — Danh sách

`split_list(value, flag)`:

- `value.is_empty()` → `EmptyList`.
- `value.split(',')`, `trim`, thu thập.
- Nếu gặp phần tử rỗng → `EmptyListItem { flag, index }`.
- Trả `Vec<String>`.

Giữ thứ tự người dùng nhập. Không dedupe — đó là quyết định của executor, không phải parser.

## Bước 5 — Ratio

```text
let ratio: f64 = text.parse().map_err(|_| InvalidRatio(text.to_string()))?;
if !ratio.is_finite() || ratio <= 0.0 || ratio >= 1.0 { return Err(InvalidRatio(...)); }
```

`"NaN".parse::<f64>()` **thành công** trong Rust (trả NaN), nên phải kiểm tra `is_finite`. `"inf"` cũng parse được.

Không dùng `partial_cmp` mà bỏ `None`; `is_finite` xử lý trước.

## Bước 6 — Xung đột cờ

Kiểm tra sau khi quét:

- Nếu cả `--copy` và `--hard-link` → `ConflictingFlags`.
- Chọn chiến lược: `--hard-link` → `HardLink`, `--copy` → `Copy`, không có → `Move`.

Thứ tự kiểm tra xung đột trước khi chọn để không phụ thuộc thứ tự `if`.

## Bước 7 — Test

Tổ chức:

1. `parse_ok(args) -> Command` helper.
2. `parse_err(args) -> ParseError` helper.
3. Bảng ví dụ SPEC.
4. Test `--` và `--flag=value`.
5. Test split `dst` không bị nhầm với ratio.

Một cái bẫy test: `assert_eq!` trên `f64` với `0.7` ổn vì cùng literal; nhưng nếu bạn tính `7.0/10.0`, có thể lệch. Dùng `0.7` trực tiếp trong kỳ vọng.

Test lỗi nên so biến thể, ví dụ:

```text
assert!(matches!(parse_err(&["find"]), ParseError::MissingArgument("pattern")));
```

## Bước 8 — Kiểm chứng độc lập

```bash
cargo test
cargo build
```

Chạy thử một binary nhỏ (tùy chọn): thêm `src/bin/ezcli.rs` gọi `parse(&env::args().skip(1).collect::<Vec<_>>())` và in `{:#?}`. Đây là công cụ học tập, không phải executor.

Kiểm tra lỗi gốc của nguồn: với `split data out 0.7`, parser **phải** hiểu `out` là `dst` và `0.7` là positional dư → `UnexpectedArgument("0.7")`, trừ khi bạn hỗ trợ ratio positional (bài tập không hỗ trợ). Đây là điểm khác nguồn có chủ đích.

## Bước 9 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| `--copy` nuốt `out` | Coi mọi cờ là có giá trị. |
| `--flag=` bị coi là thiếu giá trị | Bạn dùng `unwrap_or` thay vì phân biệt `None` và `Some("")`. |
| `--` không hoạt động | Quên trạng thái literal hoặc reset sau một token. |
| `-5` bị coi là positional | Nếu lệnh không hỗ trợ số âm, từ chối là đúng; muốn nhận thì dùng `--`. |
| Ratio `"NaN"` lọt qua | Thiếu `is_finite`. |
| Lỗi “dư đối số” chỉ ra sai token | Dùng `len()` thay vì token thực. |
| `help x` không lỗi | Bạn trả Help trước khi kiểm tra positional. |
| Test split nhầm dst/ratio | Bạn giữ nguyên bug nguồn. |

## Bước 10 — Mở rộng

- Thêm `--version`.
- Thêm alias lệnh (`ls` cho `tree`).
- Thêm parser cho `--include` lặp nhiều lần, cộng dồn thay vì lỗi.
- Thêm `Command::validate()` tách khỏi parse, kiểm tra đường dẫn tồn tại (nhưng khi đó không còn thuần).
- Thêm derive `Eq` cho `f64` bằng wrapper `Ratio`, hoặc dùng `rust_decimal`.

## Tự đánh giá

1. Vì sao parser không nên kiểm tra filesystem?
2. Vì sao `--` cần thiết?
3. `--flag=` khác `--flag` ở đâu, và tại sao phân biệt?
4. Lỗi nào nên là `UnknownFlag` và lỗi nào là `UnexpectedArgument`?
