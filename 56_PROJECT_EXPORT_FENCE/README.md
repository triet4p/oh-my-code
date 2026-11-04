# 56 — Hàng rào ghi cho xuất/nhập dự án

## Mục tiêu

Cài một **hàng rào ghi** (write fence) bất đồng bộ cho một tài nguyên dùng chung: nhiều reader chạy song song, writer độc quyền, và một **epoch xuất** chặn mọi ghi trong suốt thời gian xuất — kèm phát hiện sổ sách không nhất quán.

1. `enter_read/exit_read`, `enter_write/exit_write` với `asyncio.Condition`.
2. `export_epoch()` là context manager: chỉ một epoch tại một thời điểm; epoch đang mở chặn writer mới và làm writer đang chờ thất bại.
3. Đếm và kiểm tra: `active_readers`, `active_writers`, `exporting`; lệch sổ ⇒ `FenceAccountingError`.
4. Phân loại request theo `(method, path)` bằng ba biểu thức chính quy thành `EXPORT`, `IMPORT_APPLY`, `DELETION`, `MUTATION`, `READ`.

## Giá trị

- Đây là bài toán đồng bộ thật: "reader đồng thời, writer độc quyền, và một chế độ đặc biệt chặn tất cả" xuất hiện ở backup, export, migration.
- Sổ sách (counter) là nơi lỗi ẩn lâu nhất: một `exit` bị bỏ qua làm fence kẹt vĩnh viễn, nhưng test đơn giản không thấy. Bài tập bắt bạn kiểm tra **tại chỗ**.
- Bạn học cách viết test bất đồng bộ tất định bằng `asyncio.Event` thay vì `sleep`.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn (`asyncio`, `contextlib`, `re`) |
| Độ khó | Khó |
| Điều kiện | `asyncio.Condition`, `async with`, context manager, thứ tự wake-up |
| Runtime | Không mạng, không GPU, không cơ sở dữ liệu |
| Thời lượng gợi ý | 8–10 giờ |

## Nguồn gốc

- Repo: `triet4p/projecta` (nhánh `main`)
- File nguồn: <https://github.com/triet4p/projecta/blob/main/apps/api/src/projecta_api/export_fence.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - `ProjectWriteFence` dùng `asyncio.Condition` với các bộ đếm `_active_writers / _active_readers / _exporting / _maintenance_kind / _write_attempted / _recovery_required`.
  - `enter_write/exit_write/enter_read/exit_read` có kiểm tra lỗi *"project write fence accounting is inconsistent"*.
  - `export_epoch()` là context manager và ném `ExportAlreadyRunning`.
  - Ba biểu thức chính quy phân loại đường dẫn: `_EXPORT_PATH = ^/v1/projects/[^/]+/exports$`, `_IMPORT_APPLY_PATH`, `_DELETION_PATH`, cộng `_MUTATING_METHODS`.
- Giới hạn bằng chứng: đọc 80 dòng đầu; không quan sát được chính sách uỷ quyền writer (độc quyền tuyệt đối hay ưu tiên writer), hay cách `_recovery_required` được dùng.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: dùng `asyncio.Condition`; bốn hàm enter/exit; kiểm tra sổ sách không nhất quán; `export_epoch()` ném `ExportAlreadyRunning`; ba regex đường dẫn và tập method ghi.

Phần **do bài tập định nghĩa**:

- Chính sách: reader đồng thời; writer **độc quyền tuyệt đối** với reader và writer khác (không ưu tiên writer).
- Epoch xuất: đang mở thì **writer đang chờ phải thất bại** với `FenceClosedForExport`, không phải chờ tiếp.
- `recovery_required` bật khi một writer thoát bằng ngoại lệ giữa chừng; fence vẫn mở nhưng yêu cầu phục hồi được báo qua thuộc tính.
- Phân loại request và thứ tự ưu tiên regex.
- Định dạng fixture/CLI, tên lỗi.

Nguồn **không** bao gồm: FastAPI, cơ sở dữ liệu, hay tầng HTTP thật.

## Phạm vi

Trong phạm vi:

- Một fence trong bộ nhớ; test với `asyncio.Event` để điều khiển thứ tự.
- Bốn thao tác enter/exit; một context manager export; một hàm phân loại.
- Test: reader song song, writer chờ, export chặn, sổ sách, recovery.

Ngoài phạm vi:

- Không HTTP server, không DB, không nhiều tiến trình.
- Không timeout tự động cho reader/writer bị treo (có thể là mở rộng).
- Không công bằng (fairness) giữa các writer.

## Cảnh báo production

- Fence trong bộ nhớ chỉ đúng trong một tiến trình. Nhiều worker ⇒ cần khoá phân tán (DB advisory lock, Redis, hoặc lease).
- `asyncio.Condition` không công bằng; writer có thể đói nếu reader đến liên tục. Bài tập cố ý không ưu tiên writer để bạn thấy vấn đề.
- Export dài làm chặn ghi; sản phẩm thật cần cửa sổ bảo trì hoặc copy-on-write.
- `recovery_required` là tín hiệu, không phải tự phục hồi. Đừng coi cờ này là "đã sửa".

## Fixture offline

- `fixtures/paths.json` — danh sách `(method, path)` với kỳ vọng phân loại.
- `fixtures/scenario_export.json` — mô tả thứ tự thao tác cho CLI mô phỏng.
- Không có URL ngoài; không cần DB.

## Liên kết

- [SPEC.md](SPEC.md) — chính sách, bảng phân loại, ví dụ, tiêu chí chấp nhận.
- [GUIDE.md](GUIDE.md) — thiết kế condition, bẫy đếm và wake-up, cách kiểm chứng.
