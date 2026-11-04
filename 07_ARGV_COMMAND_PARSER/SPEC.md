# SPEC — Argv command parser

## Grammar

```text
args      := command-token*
command   := "tree"  tree-args
           | "find"  PATTERN [ROOT]
           | "clean" PATTERN [ROOT]
           | "split" SRC DST [split-opts]
           | "env"   KEY VALUE [env-opts]
           | "help" | "--help" | "-h"
tree-args := [PATH] ["--include" LIST] ["--exclude" LIST]
split-opts:= ["--ratio" R] ["--copy" | "--hard-link"]
env-opts  := ["--group" GROUP]
```

Quy tắc chung:

- Đối số truyền vào `parse` **không** gồm tên chương trình.
- Không có đối số → `Command::Help`.
- `--` kết thúc vùng cờ: mọi token sau đó là positional, kể cả bắt đầu bằng `-`.
- Cờ có thể đứng trước, giữa hoặc sau positional.
- `--flag=value` tương đương `--flag value`; dạng `=` thắng nếu cả hai xuất hiện? Không — mỗi cờ chỉ được xuất hiện một lần; lặp → `DuplicateFlag`.
- Cờ boolean (`--copy`, `--hard-link`) không nhận giá trị; `--copy=true` → `UnexpectedValue`.
- Giá trị của cờ có thể bắt đầu bằng `-` nếu dùng dạng `--flag=-x`; dạng khoảng trắng từ chối token bắt đầu bằng `-` (trừ `-` đơn lẻ) để tránh nuốt cờ kế tiếp.
- Tên cờ lạ → `UnknownFlag`.
- Token không phải cờ được gom vào positional theo thứ tự.

## Kiểu

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SplitStrategy { Move, Copy, HardLink }

#[derive(Debug, Clone, PartialEq)]
pub enum Command {
    Tree { path: String, include: Vec<String>, exclude: Vec<String> },
    Find { pattern: String, root_dir: String },
    Clean { pattern: String, root_dir: String },
    Split { src: String, dst: String, ratio: f64, strategy: SplitStrategy },
    Env { key: String, val: String, group: String },
    Help,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ParseError {
    UnknownCommand(String),
    UnknownFlag(String),
    MissingArgument(&'static str),
    UnexpectedArgument(String),
    MissingFlagValue(String),
    UnexpectedValue(String),
    DuplicateFlag(String),
    EmptyList(String),
    EmptyListItem { flag: String, index: usize },
    InvalidRatio(String),
    ConflictingFlags(&'static str, &'static str),
}
```

`ParseError` implement `Display`; thông điệp chỉ cần chứa thông tin, test so khớp **biến thể** và payload, không so chuỗi hiển thị (trừ một test smoke).

## Mặc định

| Lệnh | Mặc định |
|---|---|
| `tree` không có positional | `path = "."` |
| `tree` không có `--include` | `include = []` |
| `tree` không có `--exclude` | `exclude = []` |
| `find`, `clean` không có root | `root_dir = "."` |
| `split` không có `--ratio` | `0.8` |
| `split` không có cờ chiến lược | `SplitStrategy::Move` |
| `env` không có `--group` | `group = "default"` |

## Ràng buộc giá trị

- `PATH`, `ROOT`, `SRC`, `DST`, `PATTERN`, `KEY`, `VALUE`, `GROUP` là chuỗi không rỗng; token rỗng `""` → `MissingArgument` hoặc `UnexpectedArgument` tùy vị trí.
- `LIST` tách theo `,`, trim từng phần tử. Chuỗi rỗng → `EmptyList(flag)`. Phần tử rỗng sau trim (ví dụ `"a,,b"`) → `EmptyListItem { flag, index }` với `index` là vị trí trong danh sách tách (bắt đầu 0).
- `R`: parse `f64`; từ chối NaN, vô cực, `<= 0`, `>= 1` → `InvalidRatio(text)`.
- `--copy` và `--hard-link` cùng xuất hiện → `ConflictingFlags("--copy", "--hard-link")`.
- Số positional vượt mức → `UnexpectedArgument(token đầu tiên dư)`.

## Thứ tự kiểm tra

1. Xác định lệnh từ token đầu tiên. Token rỗng hoặc không khớp → `UnknownCommand`.
2. Với `help`/`--help`/`-h`: nếu còn token → `UnexpectedArgument`; ngược lại `Help`.
3. Quét phần còn lại, tách flag và positional.
4. Kiểm tra cờ lạ/trùng/thiếu giá trị trong lúc quét.
5. Ánh xạ positional vào lệnh; thiếu → `MissingArgument` với tên trường.
6. Kiểm tra giá trị phụ thuộc (ratio, danh sách, xung đột cờ).
7. Trả `Command`.

## Ví dụ

| `args` | Kết quả |
|---|---|
| `[]` | `Help` |
| `["help"]` | `Help` |
| `["tree"]` | `Tree { path: ".", include: [], exclude: [] }` |
| `["tree", "src"]` | path `src` |
| `["tree", "--include", "rs,toml"]` | path `.`, include `["rs","toml"]` |
| `["tree", "src", "--exclude", "target", "--include=rs"]` | path `src`, include `["rs"]`, exclude `["target"]` |
| `["find", "*.pyc"]` | `Find { pattern: "*.pyc", root_dir: "." }` |
| `["find", "*.pyc", "src"]` | root `src` |
| `["clean", "*.tmp", "--", "-weird"]` | `Clean { pattern: "*.tmp", root_dir: "-weird" }` |
| `["split", "data", "out"]` | ratio `0.8`, `Move` |
| `["split", "data", "out", "--ratio", "0.7", "--copy"]` | ratio `0.7`, `Copy` |
| `["split", "data", "out", "--hard-link"]` | `HardLink` |
| `["env", "TOKEN", "abc", "--group", "prod"]` | `Env { key: "TOKEN", val: "abc", group: "prod" }` |
| `["env", "A=B", "--group=dev", "x=y"]` | `Env { key: "A=B", val: "x=y", group: "dev" }` |
| `["bogus"]` | `UnknownCommand("bogus")` |
| `["tree", "--include", ""]` | `EmptyList("--include")` |
| `["tree", "--include", "a,,b"]` | `EmptyListItem { flag: "--include", index: 1 }` |
| `["find"]` | `MissingArgument("pattern")` |
| `["find", "x", "y", "z"]` | `UnexpectedArgument("z")` |
| `["split", "data", "out", "--ratio", "1.2"]` | `InvalidRatio("1.2")` |
| `["split", "data", "out", "--ratio", "NaN"]` | `InvalidRatio("NaN")` |
| `["split", "data", "out", "--copy", "--hard-link"]` | `ConflictingFlags("--copy", "--hard-link")` |
| `["tree", "--include"]` | `MissingFlagValue("--include")` |
| `["tree", "--include=a", "--include=b"]` | `DuplicateFlag("--include")` |
| `["tree", "--copy"]` | `UnknownFlag("--copy")` |
| `["help", "x"]` | `UnexpectedArgument("x")` |

## Tính xác định

- Parser thuần: cùng `args` → cùng kết quả, không đọc môi trường hay filesystem.
- Không phụ thuộc thứ tự duyệt của `HashMap`; dùng `match` tĩnh hoặc `Vec` cố định.
- Thông điệp lỗi không chứa thời gian hay đường dẫn tuyệt đối.

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| Token rỗng ở vị trí lệnh | `UnknownCommand("")` |
| `--` không còn token | hợp lệ, không positional thêm |
| `--` trước lệnh (`["--", "tree"]`) | `UnknownCommand("--")` |
| `--ratio=0` | `InvalidRatio("0")` |
| `--ratio` theo sau bởi `--copy` | `MissingFlagValue("--ratio")` |
| `--group=` | `MissingFlagValue("--group")` (giá trị rỗng) |
| `--include= a` (khoảng trắng) | phần tử `a` sau trim; không rỗng |
| Tên lệnh viết hoa `Tree` | `UnknownCommand` |
| `-h` không phải lệnh đầu | cờ lạ nếu lệnh không hỗ trợ |
| Giá trị positional trùng tên cờ (`--copy` là DST) | chỉ dùng `--` mới biểu diễn được |

## Tiêu chí nghiệm thu

1. Toàn bộ bảng ví dụ là test, so khớp `Result` bằng `assert_eq!`.
2. Không có `unwrap()` trên đầu vào người dùng trong đường parse.
3. Có test `--` cho phép positional bắt đầu bằng `-`.
4. Có test `--flag=value` và `--flag value` cho cùng kết quả.
5. Có test split với đủ `src`, `dst`, ratio và cờ; xác nhận `dst` đúng (không bị dùng làm ratio).
6. `cargo test` xanh; `cargo clippy -- -D warnings` sạch nếu có cài clippy.

## Non-goals

- Thực thi lệnh, in cây thư mục, tìm/xóa file.
- Hỗ trợ `-abc` gộp cờ ngắn.
- Hỗ trợ subcommand lồng nhau.
- Đọc biến môi trường hoặc file cấu hình.
- Hoàn thiện `Display` cho mọi lỗi theo chuẩn i18n.
