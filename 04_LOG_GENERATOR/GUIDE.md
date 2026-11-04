# GUIDE — Log generator

## Bước 0 — Môi trường

```bash
mkdir 04_LOG_GENERATOR/work && cd 04_LOG_GENERATOR/work
uv init . -p 3.12
uv add pyyaml faker
uv add --dev pytest
mkdir -p src/logsim tests out
```

`pyproject.toml` cần khai báo package `src/logsim`. Kiểm tra:

```bash
uv run python -c "import yaml, faker; print('ok')"
```

## Bước 1 — Tách ba trách nhiệm

Thiết kế trước khi viết:

1. **Config**: đọc YAML, áp override, validate, trả dataclass bất biến.
2. **Event factory**: nhận RNG đã seed và sinh một dict.
3. **Sink**: nhận dict, serialize, ghi một dòng, flush khi cần.

CLI chỉ lắp ba phần. Nhờ vậy test có thể gọi factory mà không đụng file, hoặc dùng sink giả để mô phỏng lỗi/ngắt.

Gợi ý kiểu:

```text
@dataclass(frozen=True)
class GeneratorConfig:
    rate: float
    count: int
    seed: int
    path: Path
    start_epoch: float | None
```

## Bước 2 — Đọc và validate cấu hình

Thứ tự:

1. Mở file; `FileNotFoundError` → lỗi cấu hình.
2. `yaml.safe_load`; bắt `yaml.YAMLError`.
3. Kiểm tra là mapping, có đúng hai khóa `generator`, `sink`.
4. Kiểm tra từng khóa con; từ chối khóa lạ.
5. Ép kiểu có kiểm soát: `count` phải là `int` thật (không `bool`, không `"3"`), `rate` là `int`/`float` và hữu hạn.
6. Áp override CLI sau cùng.

Một cái bẫy: YAML 1.1 đọc `on`, `off`, `yes`, `no` thành boolean. Nếu `action` nằm trong config, đừng dùng các chuỗi đó làm tên. Bài này action cố định nên không ảnh hưởng, nhưng hãy biết.

Một cái bẫy khác: `yaml.safe_load("")` trả `None`. Phải kiểm tra trước khi index.

## Bước 3 — Seed hai nguồn ngẫu nhiên

Faker dùng một `random.Random` nội bộ, nhưng một số hàm có thể dùng module `random`. Để chắc chắn:

```text
faker = Faker()
Faker.seed(seed)
random.seed(seed)
```

Gọi seed **một lần** trước vòng lặp, không seed lại mỗi sự kiện (seed lại sẽ lặp cùng giá trị).

Nếu bạn không muốn phụ thuộc Faker, có thể tự sinh:

- UUID từ 128 bit lấy từ `random.getrandbits`, đặt version/variant đúng chuẩn.
- `device`, `location` từ hai mảng cố định, chọn bằng `random.choice`.

Nhưng bài tập yêu cầu bám nguồn ở lược đồ, không bắt buộc bám thư viện; nếu tự sinh, ghi rõ trong README của bạn.

## Bước 4 — Vòng lặp và lịch

Tính `interval = 1.0 / rate` một lần. Với mỗi `i`:

1. `event = factory(i)`.
2. Ghi.
3. Nếu còn sự kiện: ngủ tới deadline.

Deadline tuyệt đối:

```text
start_mono = time.monotonic()
deadline = start_mono + (i + 1) / rate
delay = deadline - time.monotonic()
if delay > 0: time.sleep(delay)
```

Dùng `time.monotonic()`, không `time.time()`, cho khoảng nghỉ: đồng hồ hệ thống có thể bị chỉnh.

`event_time` phát ra dùng `start_epoch + i / rate`, với `start_epoch` lấy từ `--start-time` hoặc `time.time()` tại thời điểm bắt đầu. Đừng lấy `time.time()` mỗi vòng, vì như vậy mốc sẽ trôi theo thời gian thực thi và phá tất định.

## Bước 5 — Ghi NDJSON an toàn

Mở file một lần:

```text
with path.open("w", encoding="utf-8", newline="\n") as fh:
    ...
```

`newline="\n"` quan trọng trên Windows: nếu không, `\n` có thể thành `\r\n`, làm hỏng so sánh byte và một số parser.

Serialize:

```text
line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
fh.write(line + "\n")
```

Không dùng `print(..., file=fh)` nếu muốn kiểm soát newline tuyệt đối.

Flush mỗi dòng hay mỗi N dòng? Với bài học, flush mỗi dòng để `Ctrl+C` không mất dữ liệu; đổi lại tốc độ thấp hơn. Ghi rõ lựa chọn.

## Bước 6 — Ngắt sạch

Bọc vòng lặp:

```text
try:
    run(...)
except KeyboardInterrupt:
    print(f"interrupted after {written} events", file=sys.stderr)
    return 130
```

`with` sẽ đóng file. Điều cần tránh: bắt `KeyboardInterrupt` bên trong lúc đang `write` rồi cố ghi tiếp. Hãy để nó thoát ra ngoài.

Nếu muốn chắc chắn không có dòng cụt, ghi theo kiểu “tất cả hoặc không”: serialize vào chuỗi trước, rồi một lần `write`. Python buffering có thể vẫn chia nhỏ ở tầng OS, nhưng với file thường và dòng ngắn, rủi ro thực tế thấp; đó là giới hạn cần ghi rõ.

## Bước 7 — Kiểm thử

Test cấu hình:

- Thiếu `sink`, thiếu `log-rate`, khóa lạ, rate 0/âm/NaN, count âm, seed âm.
- Override CLI thắng YAML.

Test sinh:

- Dùng `start_epoch` cố định và seed cố định, sinh 3 sự kiện vào `io.StringIO`, parse từng dòng.
- Khẳng định 5 khóa, thứ tự khóa (Python dict giữ thứ tự chèn), action thuộc enum, UUID parse được bằng `uuid.UUID`.
- Khẳng định `event_time` chênh `0.2` với rate 5.

Test file:

- `tmp_path` tạo file, chạy, đọc lại, đếm dòng.
- Chạy hai lần, so bytes.
- `count=0` → file tồn tại, kích thước 0.

Test ngắt: dùng sink giả ném `KeyboardInterrupt` sau 2 lần ghi; kiểm tra exit code và số dòng.

## Bước 8 — Kiểm chứng độc lập

```bash
uv run pytest -q
uv run python -m logsim --config examples/config.yaml --start-time 1767225600 --out /tmp/a.ndjson
uv run python -m logsim --config examples/config.yaml --start-time 1767225600 --out /tmp/b.ndjson
cmp /tmp/a.ndjson /tmp/b.ndjson && echo IDENTICAL
uv run python - <<'PY'
import json
rows = [json.loads(line) for line in open('/tmp/a.ndjson', encoding='utf-8')]
print(len(rows), rows[0].keys(), rows[-1]['event_time'] - rows[0]['event_time'])
PY
```

Kỳ vọng: `IDENTICAL`, `3 dict_keys([...]) 0.4`.

## Bước 9 — Gỡ vướng

| Triệu chứng | Nguyên nhân |
|---|---|
| Hai lần chạy khác nhau dù cùng seed | Seed sau khi tạo Faker nhưng trước khi sinh? Có gọi `uuid.uuid4()`? Có dùng `time.time()` mỗi vòng? |
| Khoảng cách thời gian trôi | Dùng `sleep(interval)` tích lũy thay vì deadline. |
| File có `\r\n` | Thiếu `newline="\n"`. |
| Dòng cuối không có newline | Ghi `line` thay vì `line + "\n"`. |
| Ctrl+C để lại dòng cụt | Serialize và ghi không nguyên tử; hoặc bắt interrupt trong lúc ghi. |
| `count=0` vẫn ghi dòng | Vòng lặp `while` thay vì `for range(count)`. |
| Rate âm gây sleep lỗi | Validate trước khi tính interval. |

## Bước 10 — Mở rộng

- Thêm sink `stdout` và sink “đếm” để test throughput.
- Thêm `--format jsonl|csv`.
- Thêm phân phối action có trọng số, vẫn tất định theo seed.
- Thêm giới hạn kích thước file và xoay vòng.
- Thêm chế độ replay từ file đã sinh để so sánh downstream.

## Tự đánh giá

1. Vì sao phải tách `event_time` khỏi thời điểm ghi thực tế?
2. Vì sao deadline tuyệt đối tốt hơn `sleep(interval)`?
3. Phần nào của đầu ra là tất định, phần nào không?
4. Nếu Faker đổi cách sinh user agent, điều gì trong hợp đồng bị ảnh hưởng?
