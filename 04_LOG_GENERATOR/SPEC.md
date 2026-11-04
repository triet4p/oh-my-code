# SPEC — Log generator

## Mục tiêu hành vi

Sinh `count` sự kiện JSON theo một tần suất cấu hình, ghi mỗi sự kiện thành một dòng vào file NDJSON, với mốc thời gian và chuỗi ngẫu nhiên tái lập được khi cung cấp seed và `--start-time`. Không gửi dữ liệu qua mạng.

## Lược đồ sự kiện

Mỗi dòng là một JSON object với **đúng năm khóa**, theo thứ tự chèn cố định:

| Khóa | Kiểu | Giá trị |
|---|---|---|
| `event_time` | number | epoch giây, `start_epoch + i / rate` |
| `user_id` | string | UUID v4 dạng chuẩn 36 ký tự |
| `action` | string | một trong `click`, `view`, `purchase`, `login`, `logout` |
| `device` | string | user agent không rỗng |
| `location` | string | tên thành phố không rỗng |

Serialize bằng `json.dumps(event, ensure_ascii=False, separators=(",", ":"))`, ghi UTF-8, kết thúc mỗi dòng bằng `\n` (kể cả dòng cuối). Không có BOM, không có dòng trống.

## Cấu hình

File YAML:

```yaml
generator:
  log-rate: 5.0
  count: 10
  seed: 42
sink:
  path: events.ndjson
```

| Khóa | Bắt buộc | Mặc định | Ràng buộc |
|---|---|---|---|
| `generator.log-rate` | có | — | số thực hữu hạn, `> 0`, `<= 10000` |
| `generator.count` | không | `10` | số nguyên `>= 0`, `<= 1_000_000` |
| `generator.seed` | không | `0` | số nguyên `>= 0`, `< 2**63` |
| `sink.path` | có | — | chuỗi không rỗng; thư mục cha phải tồn tại |

Khóa lạ trong YAML bị từ chối (`extra keys are not allowed`) để phát hiện lỗi gõ. Thiếu khóa bắt buộc → lỗi cấu hình.

## CLI

```text
logsim --config CONFIG [--out PATH] [--count N] [--rate R] [--seed S] [--start-time T]
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `--config` | đường dẫn YAML; bắt buộc |
| `--out` | ghi đè `sink.path` |
| `--count` | ghi đè `generator.count` |
| `--rate` | ghi đè `generator.log-rate` |
| `--seed` | ghi đè `generator.seed` |
| `--start-time` | epoch giây (số thực) hoặc `YYYY-MM-DDTHH:MM:SSZ`; mặc định lấy `time.time()` |

Thứ tự ưu tiên: CLI > YAML > mặc định. `--count 0` hợp lệ: tạo file rỗng (0 byte) và thoát 0.

## Hành vi thời gian

- Nếu có `--start-time`, `event_time[i] = start_epoch + i / rate` cho `i = 0..count-1`. Giá trị này **không** phụ thuộc thời gian thực thi.
- Nếu không, `start_epoch` là thời điểm bắt đầu chạy; các mốc vẫn cộng đều theo `i / rate`.
- Việc ngủ dùng deadline tuyệt đối: `deadline_i = start_monotonic + i / rate`; ngủ `max(0, deadline_i - now)`. Không cộng dồn `sleep(interval)` sau mỗi lần ghi, vì sai số sẽ trôi.
- Nếu máy chậm khiến deadline đã qua, không ngủ và ghi tiếp; không “bù” bằng cách nhảy mốc thời gian phát ra.

## Tất định

- Cùng YAML, cùng seed, cùng `--start-time`, cùng phiên bản Faker trong lockfile → file đầu ra **byte-identical** giữa các lần chạy.
- Seed phải được đặt cho cả `random` và `Faker` trước khi sinh sự kiện đầu tiên.
- Không dùng `uuid.uuid4()` trực tiếp (nó đọc entropy hệ thống); dùng `faker.uuid4()` sau khi seed, hoặc nguồn ngẫu nhiên đã seed.
- Không có `--start-time` thì `event_time` khác nhau giữa các lần chạy; đó là phần không tất định duy nhất.

## Kiểm tra và lỗi

| Tình huống | Mã thoát | Thông điệp (chứa) |
|---|---|---|
| Thiếu `--config` | 2 | `--config is required` |
| File cấu hình không tồn tại | 2 | `config not found` |
| YAML sai cú pháp | 2 | `invalid YAML` |
| Thiếu khóa bắt buộc | 2 | `missing key` + tên khóa |
| Khóa lạ | 2 | `extra keys` |
| `log-rate <= 0`, NaN, inf | 2 | `log-rate must be` |
| `count < 0` hoặc không nguyên | 2 | `count must be` |
| `seed` âm | 2 | `seed must be` |
| `--start-time` sai định dạng | 2 | `invalid start time` |
| Không mở/ghi được file | 1 | `cannot open output` |
| `KeyboardInterrupt` | 130 | in `interrupted after N events` ra stderr |

Mọi thông điệp lỗi ra `stderr`; không ghi lẫn vào file NDJSON.

## Ngắt giữa chừng

Khi nhận `SIGINT`:

1. Ngừng vòng lặp.
2. `flush()` và `close()` file.
3. In số sự kiện đã ghi ra `stderr`.
4. Thoát 130.

File còn lại phải là NDJSON hợp lệ: mỗi dòng hoàn chỉnh, không có dòng cụt. Cách đơn giản để đảm bảo: serialize cả dòng vào một biến trước khi `write`, và không bắt `KeyboardInterrupt` ở giữa `write` — chấp nhận rằng lần ghi cuối có thể mất, miễn file không có nửa dòng.

## Ví dụ

Cấu hình:

```yaml
generator:
  log-rate: 5
  count: 3
  seed: 7
sink:
  path: out/events.ndjson
```

Lệnh:

```bash
uv run python -m logsim --config config.yaml --start-time 1767225600
```

Ba dòng có dạng (giá trị `user_id`, `device`, `location` phụ thuộc Faker đã seed):

```json
{"event_time":1767225600.0,"user_id":"…","action":"view","device":"…","location":"…"}
{"event_time":1767225600.2,"user_id":"…","action":"login","device":"…","location":"…"}
{"event_time":1767225600.4,"user_id":"…","action":"click","device":"…","location":"…"}
```

Kiểm tra:

```bash
wc -l out/events.ndjson          # 3
python -c "import json;[json.loads(l) for l in open('out/events.ndjson',encoding='utf-8')]"
```

Chạy lại cùng lệnh vào file khác rồi so:

```bash
cmp out/events.ndjson out/events-2.ndjson && echo identical
```

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| `count = 0` | file rỗng, thoát 0 |
| `rate` rất lớn (10000) | không ngủ âm; 3 sự kiện gần như tức thời |
| `count = 1` | một dòng, không có sleep sau dòng cuối (hoặc sleep không quan sát được) |
| Đường dẫn cha không tồn tại | lỗi cấu hình/IO, không tự tạo thư mục |
| `--out` trùng file đang tồn tại | ghi đè (mode `w`), không nối thêm |
| `--start-time` ở tương lai | vẫn ghi mốc tương lai; không chờ |
| Seed trùng nhưng khác count | `count` dòng đầu giống nhau |
| Ctrl+C sau 2 dòng | 2 dòng hợp lệ, exit 130, stderr báo 2 |
| Action không nằm trong enum | không thể xảy ra nếu generator đúng; test phải khẳng định |

## Tiêu chí nghiệm thu

1. Hai lần chạy với cùng seed/start-time cho file giống nhau từng byte (`cmp` không in gì).
2. Mỗi dòng parse được bằng `json.loads`; đúng 5 khóa; `event_time` tăng dần với chênh lệch `1/rate` (sai số `1e-9`).
3. `action` luôn thuộc enum 5 giá trị, không có `purcharse`.
4. `count = 0` tạo file 0 byte và exit 0.
5. Cấu hình thiếu khóa, khóa lạ, rate âm, seed âm đều exit 2 và không tạo file đầu ra.
6. Test ngắt mô phỏng (gọi generator với sink ném `KeyboardInterrupt` sau 2 dòng) để lại 2 dòng hợp lệ và exit 130.
7. Không có import `kafka`, không mở socket.

## Non-goals

- Kafka producer, consumer, topic, partition, offset.
- Ghi Parquet/HDFS, Spark structured streaming.
- Xoay vòng file theo dung lượng, nén, upload.
- Đo backpressure hay throughput thực của sink.
- Đảm bảo tất định qua các phiên bản Faker khác nhau.
