# SPEC — Forensic plugin registry

## Mục tiêu hành vi

Cung cấp một registry toàn cục có kiểm soát cho hai loại plugin: symptom (kèm schema cấu hình) và pattern scorer. Đăng ký qua decorator, tra cứu theo tên, lỗi rõ ràng, và trạng thái có thể chụp/khôi phục để test độc lập.

## API

```python
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T", bound=type)

class RegistryError(Exception): ...
class InvalidNameError(RegistryError): ...
class InvalidSchemaError(RegistryError): ...
class DuplicatePluginError(RegistryError): ...
class UnknownPluginError(RegistryError): ...

class ForensicRegistry:
    SYMPTOMS: dict[str, type] = {}
    SYMPTOMS_CONFIGS: dict[str, type] = {}
    PATTERN_SCORERS: dict[str, type] = {}

    @classmethod
    def register_symptom(cls, name: str, config_schema: type) -> Callable[[T], T]: ...

    @classmethod
    def register_pattern_scorer(cls, name: str) -> Callable[[T], T]: ...

    @classmethod
    def get_symptom(cls, name: str) -> tuple[type, type]: ...

    @classmethod
    def get_pattern_scorer(cls, name: str) -> type: ...

    @classmethod
    def snapshot(cls) -> dict[str, dict[str, type]]: ...

    @classmethod
    def restore(cls, state: dict[str, dict[str, type]]) -> None: ...

    @classmethod
    def clear(cls) -> None: ...
```

## Quy tắc tên

- Tên phải là `str`, khớp `^[a-z][a-z0-9_]{1,63}$`: bắt đầu bằng chữ thường, chỉ chữ thường/số/gạch dưới, dài 2–64 ký tự.
- Không tự chuẩn hóa (không `lower()`, không `strip()`) — làm vậy sẽ khiến hai tên khác nhau âm thầm va chạm.
- Tên vi phạm → `InvalidNameError(name)`; `str(error)` chứa tên gốc.

## Đăng ký symptom

`register_symptom(name, config_schema)`:

1. Kiểm tra tên.
2. Kiểm tra `config_schema` là **lớp** (không phải instance), không phải `None`. Không bắt buộc kế thừa lớp cụ thể nào; registry không biết cách validate cấu hình.
3. Kiểm tra trùng **trước khi ghi bất kỳ dict nào**.
4. Trả decorator; decorator nhận `symptom_cls`, kiểm tra đó là lớp, ghi cả hai dict, trả lại `symptom_cls`.

Ngữ nghĩa trùng:

- Cùng tên, cùng `symptom_cls`, cùng `config_schema`: **idempotent**, không ném, không ghi lại (hữu ích khi module bị import hai lần).
- Cùng tên nhưng khác lớp hoặc khác schema: `DuplicatePluginError(name)`; **không dict nào bị thay đổi**.
- Tên đã có trong `PATTERN_SCORERS` nhưng đăng ký symptom: cho phép; hai không gian tên độc lập.

## Đăng ký pattern scorer

`register_pattern_scorer(name)`:

1. Kiểm tra tên.
2. Trả decorator kiểm tra lớp, ghi `PATTERN_SCORERS[name]`.
3. Trùng cùng lớp: idempotent. Trùng khác lớp: `DuplicatePluginError`.

## Tra cứu

- `get_symptom(name)` trả `(symptom_cls, config_schema)`.
- `get_pattern_scorer(name)` trả `scorer_cls`.
- Tên chưa đăng ký → `UnknownPluginError(name)`, không trả `None`, không `KeyError` trần.
- Tên không hợp lệ → `InvalidNameError` trước khi tra dict (cùng quy tắc với đăng ký).

## Snapshot và cô lập

- `snapshot()` trả ba **bản sao nông** của dict, khóa là `"symptoms"`, `"configs"`, `"scorers"`.
- `restore(state)` thay nội dung ba dict bằng bản sao của state; state thiếu khóa → `ValueError`.
- `clear()` làm rỗng cả ba dict.
- `restore` và `clear` không được giữ tham chiếu tới dict cũ của người gọi.

Thiết kế này không bảo vệ khỏi truy cập trực tiếp `ForensicRegistry.SYMPTOMS[...] = ...`; đó là lý do API công khai nên được dùng và test nên snapshot/restore trong fixture.

## Kiểm tra kiểu và lỗi

| Tình huống | Lỗi |
|---|---|
| Tên không phải `str` | `InvalidNameError` |
| Tên rỗng, hoa, bắt đầu bằng số, quá dài, chứa `-` | `InvalidNameError` |
| `config_schema` không phải lớp | `InvalidSchemaError` |
| Decorator nhận không phải lớp | `InvalidSchemaError` (thông điệp nêu loại nhận được) |
| Trùng tên khác đối tượng | `DuplicatePluginError` |
| Tra cứu tên chưa có | `UnknownPluginError` |
| `restore` thiếu khóa | `ValueError` |

Tất cả lỗi registry kế thừa `RegistryError`, để người gọi có thể bắt một loại.

## Tính xác định

- Thứ tự đăng ký không ảnh hưởng kết quả tra cứu.
- `snapshot()` trả dict mới mỗi lần; sửa bản snapshot không ảnh hưởng registry.
- Không đọc thời gian, môi trường, hay thứ tự import ngoài việc module tự đăng ký.

## Ví dụ

```python
@ForensicRegistry.register_symptom("burst", BurstConfig)
class BurstSymptom:
    ...

@ForensicRegistry.register_pattern_scorer("transition_entropy")
class TransitionEntropyScorer:
    ...

assert ForensicRegistry.get_symptom("burst") == (BurstSymptom, BurstConfig)
assert ForensicRegistry.get_pattern_scorer("transition_entropy") is TransitionEntropyScorer
```

Đăng ký trùng:

```python
try:
    ForensicRegistry.register_symptom("burst", OtherConfig)(OtherSymptom)
except DuplicatePluginError as exc:
    assert str(exc) == "burst"
# BurstSymptom và BurstConfig vẫn còn nguyên
```

Tra cứu thiếu:

```python
try:
    ForensicRegistry.get_symptom("missing")
except UnknownPluginError:
    ...
```

Nguyên tử:

```python
before = ForensicRegistry.snapshot()
try:
    ForensicRegistry.register_symptom("ok_name", object())(SomeSymptom)
except InvalidSchemaError:
    pass
assert ForensicRegistry.snapshot() == before
```

## Trường hợp biên

| Trường hợp | Kết quả |
|---|---|
| Đăng ký cùng lớp hai lần | không lỗi, một mục |
| Đăng ký cùng tên, lớp khác | lỗi, state không đổi |
| `config_schema` là instance | `InvalidSchemaError`, state không đổi |
| Tên 1 ký tự (`"a"`) | `InvalidNameError` (tối thiểu 2) |
| Tên 64 ký tự | hợp lệ |
| Tên 65 ký tự | `InvalidNameError` |
| Tên `"Burst"` | `InvalidNameError` (không tự lower) |
| Symptom và scorer cùng tên | cả hai tồn tại độc lập |
| Snapshot sửa tay | registry không đổi |
| Restore snapshot cũ | state quay lại đúng |

## Tiêu chí nghiệm thu

1. Có test cho từng lỗi ở bảng trên, so khớp kiểu lỗi và `str(exc)`.
2. Có test chứng minh đăng ký trùng khác lớp không làm thay đổi bất kỳ dict nào (so snapshot trước/sau).
3. Có test đăng ký idempotent với cùng lớp/schema.
4. Có test symptom và scorer cùng tên không ghi đè nhau.
5. Có test `snapshot`/`restore`/`clear`.
6. `pytest -q` xanh.
7. Không có test nào phụ thuộc thứ tự chạy (chạy riêng từng test và chạy cả file đều xanh).

## Non-goals

- Tự import module plugin từ thư mục.
- Kiểm tra schema bằng Pydantic hoặc validate giá trị cấu hình.
- Khởi tạo symptom từ `(name, config_dict)`.
- Thread safety hoặc đa tiến trình.
- Ghi log, metrics, hay cơ chế ưu tiên khi trùng.
