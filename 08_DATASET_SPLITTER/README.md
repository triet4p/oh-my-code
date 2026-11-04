# 08 — Dataset splitter: chia train/test an toàn, mặc định dry-run

## Mục tiêu

Tự viết công cụ chia một thư mục dữ liệu thành `train/` và `test/` theo tỉ lệ, với shuffle tất định theo seed, chiến lược copy/hardlink/move, và **mặc định chỉ lập kế hoạch** — không động vào file cho đến khi có `--apply`. Bài tập lấy thuật toán chia từ một lệnh CLI nhưng thay đổi mặc định phá hủy thành an toàn.

## Giá trị học được

- Vì sao công cụ di chuyển file phải có chế độ dry-run mặc định.
- Preflight toàn bộ đích trước khi ghi bất kỳ file nào; tránh trạng thái nửa vời.
- Shuffle tất định bằng PRNG tự cài, không phụ thuộc `rand`.
- Phân biệt copy, hardlink (có fallback), move (không fallback).
- Manifest là hợp đồng kiểm toán: cùng seed → cùng kế hoạch.
- Bẫy đường dẫn: đích nằm trong nguồn, symlink, tên trùng khi đệ quy.

## Ngôn ngữ và độ khó

- Ngôn ngữ: Rust 2021.
- Độ khó: **Trung bình**.
- Thời lượng gợi ý: 5–6 giờ.

## Điều kiện tiên quyết và runtime

- Rust stable, `cargo`.
- Không cần crate ngoài; PRNG và shuffle tự viết.
- Không cần mạng.

## Nguồn gốc

- Nguồn: `triet4p/ez_cli`, file `src/cmd/split.rs`.
- URL chính xác: <https://github.com/triet4p/ez_cli/blob/master/src/cmd/split.rs>

Hành vi quan sát được trong nguồn:

- `collect_files` chỉ đọc các entry trực tiếp trong thư mục, bỏ qua thư mục con, thu `PathBuf` của file.
- `run` kiểm tra thư mục nguồn tồn tại và là thư mục; từ chối `ratio <= 0.0 || ratio >= 1.0`.
- In “Reading files”, lấy `files.len()`, nếu 0 thì in cảnh báo và trả `Ok(())`.
- `files.shuffle(&mut rng)`; `split_idx = (total_files as f32 * ratio).round() as usize`; `split_at(split_idx)`.
- Tạo `dst/train`, `dst/test`, rồi `process_files` cho từng bên.
- `Copy` dùng `fs::copy`; `HardLink` thử `fs::hard_link`, lỗi thì in và `fs::copy`; `Move` dùng `fs::rename`.
- Cứ mỗi 10 file (và `i > 0`) in tiến độ kèm icon.
- `run` nhận `(src, dst, ratio, strategy)`, nhưng ở `Config::build`, `dst` và `ratio` cùng lấy từ `args[3]`, nên CLI thực tế không truyền được cả hai đúng.

## Phạm vi bài tập

Xây binary `dataset-split`:

- Mặc định **dry-run**: in kế hoạch, không tạo thư mục, không copy.
- `--apply` mới thực thi.
- Mặc định chiến lược `copy`; `--strategy move` và `--strategy hardlink` là lựa chọn rõ ràng.
- Seed bắt buộc tất định; danh sách file được sắp trước khi shuffle.
- Manifest JSON mô tả kế hoạch/kết quả.
- Preflight xung đột đích; không ghi một phần nếu có xung đột.
- Từ chối đích nằm trong nguồn.

Không nằm trong phạm vi: chia theo nhãn (stratified), nén, upload, xóa file nguồn ngoài chế độ `move`, xử lý file đang mở.

## Liên kết

- [SPEC.md](SPEC.md) — CLI, thuật toán, manifest, mã thoát.
- [GUIDE.md](GUIDE.md) — PRNG, shuffle, preflight, kiểm thử.

## Ghi chú về quan hệ nguồn — bài tập

Nguồn mặc định `Move` (phá hủy) và không có dry-run; bài tập đảo mặc định sang `copy` + dry-run. Nguồn dùng `rand`; bài tập yêu cầu PRNG tự viết để kế hoạch tái lập không phụ thuộc phiên bản crate. Nguồn có lỗi `dst`/`ratio`; bài tập định nghĩa CLI đúng. Đây là các khác biệt có chủ đích, không phải hành vi của nguồn.
