# 07 — Argv parser: biến chuỗi dòng lệnh thành enum an toàn

## Mục tiêu

Tự viết một parser `argv` không dùng thư viện: nhận các đối số sau tên chương trình, phân tích lệnh con, positional, cờ boolean và cờ có giá trị, rồi trả về một `enum Command` đã kiểm tra kiểu. Mọi lỗi cú pháp trả về biến thể lỗi có cấu trúc thay vì chuỗi tự do.

## Giá trị học được

- Ranh giới giữa **cú pháp** (parser) và **ngữ nghĩa** (executor): parser không đọc filesystem, không xóa file.
- Vị trí positional và flag có thể xen kẽ; cần một vòng lặp trạng thái rõ ràng.
- `--flag=value` và `--flag value` là hai cú pháp; xử lý cả hai mà không mơ hồ.
- `--` kết thúc vùng cờ, cho phép giá trị bắt đầu bằng `-`.
- Enum lỗi giúp test so khớp chính xác và giúp caller quyết định mã thoát.
- Một lỗi thật trong nguồn: cùng `args[3]` được dùng cho cả `dst` và `ratio`.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Rust 2021.
- Độ khó: **Trung bình**.
- Thời lượng gợi ý: 4–5 giờ.

## Điều kiện tiên quyết và runtime

- Rust stable (1.75+), `cargo`.
- Không cần crate ngoài.
- Không cần mạng sau khi cài toolchain.

## Nguồn gốc

- Nguồn: `triet4p/ez_cli`, file `src/lib.rs`.
- URL chính xác: <https://github.com/triet4p/ez_cli/blob/master/src/lib.rs>

Hành vi quan sát được trong nguồn:

- `enum SplitStrategy { Move, Copy, HardLink }` với `Move` là mặc định.
- `enum Command` gồm `Tree { path, include, exclude }`, `Find { pattern, root_dir }`, `Clean { pattern, root_dir }`, `Split { src, dst, ratio, strategy }`, `Env { key, val, group }`, `Help`.
- `Config::build(args: &[String])` coi `args[1]` là tên lệnh; `args.len() < 2` trả `Help`; `tree` mặc định path `"."`; `find`/`clean` lấy pattern ở `args[2]` và root mặc định `"."`; `--group` mặc định `"default"`.
- `find_flag_value` tìm vị trí flag rồi lấy phần tử `index + 1`, không kiểm tra đó có phải flag khác không.
- `convert_list_patterns` tách theo `","`, trim từng phần tử; không có flag thì trả vector rỗng.
- `split` lấy `dst` từ `args[3]` (mặc định `"."`) và **cũng** parse `ratio` từ `args[3]` (mặc định `0.8`), nên hai giá trị dùng chung một vị trí; help lại ghi `split <src> [ratio]`, không có `dst`.
- Chọn cả `--hard-link` và `--copy` trả lỗi chuỗi; ngược lại chọn theo cờ, không cờ thì `Move`.

## Phạm vi bài tập

Xây crate `ezcli`:

- `Command` và `ParseError` có cấu trúc.
- `parse(args: &[String]) -> Result<Command, ParseError>` (không tính tên chương trình).
- Hỗ trợ `--flag value`, `--flag=value`, `--`.
- Sửa cú pháp `split <src> <dst> [--ratio R]`.
- Test toàn bộ bảng ví dụ và lỗi.

Không nằm trong phạm vi: thực thi `tree`/`find`/`clean`/`split`, đọc filesystem, biến môi trường, in màu.

## Liên kết

- [SPEC.md](SPEC.md) — grammar, mặc định, lỗi, bảng argv.
- [GUIDE.md](GUIDE.md) — vòng lặp parser, bẫy, test.

## Ghi chú về quan hệ nguồn — bài tập

Bài tập **sửa** lỗi vị trí `split` và thay lỗi chuỗi bằng enum. Nguồn không có `--flag=value` hay `--`; đây là mở rộng có chủ đích. Không tuyên bố nguồn xử lý các cú pháp đó.
