# 51 — Sinh lược đồ công cụ động từ registry

## Mục tiêu

Từ một registry mô tả công cụ (JSON cục bộ), sinh ra **mọi thứ cần để gọi**: JSON Schema cho tham số, bộ xác thực, bộ phân tích `argv`, và đối tượng request `{method, url, query, json}` — tất cả không cần mạng.

1. Nạp registry theo "provider" với tên được kiểm tra bằng biểu thức chính quy (không `import` chuỗi tùy ý).
2. Sinh JSON Schema tất định từ mô tả tham số, kể cả `enum` và `default`.
3. Sinh hàm xác thực: thiếu, thừa, sai kiểu, sai enum, sai `in`.
4. Tách tham số path/query/body và dựng request; kiểm tra placeholder trong endpoint.
5. Phân tích `argv` kiểu CLI cho cùng bộ tham số.

## Giá trị

- Đây là bài toán "dữ liệu điều khiển code": registry là dữ liệu, nhưng sinh ra hợp đồng (schema) mà mọi tầng khác phải tuân. Sai một khóa là lỗi runtime ở tận đâu đó.
- Nguồn dùng `importlib.import_module(f"app.mcp_schemas.{provider}")` — một chuỗi từ dữ liệu đi vào `import`. Bài tập buộc bạn thấy rủi ro đó và thay bằng whitelist; đây là ví dụ về "không sao chép điểm yếu".
- Bạn học cách giữ **một nguồn sự thật**: schema, validator, CLI và request builder đều dẫn xuất từ cùng mô tả, nên không thể lệch nhau.

## Ngôn ngữ, độ khó, điều kiện

| Mục | Giá trị |
|---|---|
| Ngôn ngữ | Python 3.12, chỉ thư viện chuẩn |
| Độ khó | Trung bình–Khó |
| Điều kiện | `json`, `re`, `argparse` (hoặc tự viết), hiểu JSON Schema mức cơ bản |
| Runtime | Không mạng, không GPU, không `pydantic`/`langchain` |
| Thời lượng gợi ý | 6–8 giờ |

## Nguồn gốc

- Repo: `triet4p/mcp-fin-test` (nhánh `main`, repo đã archived 2026-10-23)
- File nguồn: <https://github.com/triet4p/mcp-fin-test/blob/main/mcp_hosts/app/clients/tools_discovery.py>
- Hành vi quan sát được (nguyên văn có lược bớt bằng `…`):
  - Sinh model động: `ArgsModel = create_model(f"{name.title().replace('_', '')}Input", **fields_for_model)`.
  - Nhánh enum: `py_type = Literal[tuple(details['enum'])]`.
  - Nạp schema động theo provider: `importlib.import_module(f"app.mcp_schemas.{provider}")`.
  - Tách tham số khi gọi: `request_body = all_args.pop(body_param_name).model_dump()`; `formatted_endpoint = endpoint_template.format(**all_args)`.
  - Lấy spec từ registry qua HTTP: `requests.get(f"{cfg.MCP_SERVERS_REGISTRY_URL}/tools")`.
- Giới hạn bằng chứng: đọc toàn bộ file (~185 dòng theo ghi nhận của scout); không quan sát được định dạng registry phía server hay cách xử lý lỗi HTTP.

## Hành vi bài tập yêu cầu (thiết kế của bài)

Phần **có trong nguồn**: sinh tên model theo `title().replace('_','')`; nhánh `enum`; nạp schema theo tên provider; tách path/query/body với một tham số body; lấy spec từ registry.

Phần **do bài tập định nghĩa**:

- Registry là **file cục bộ** thay vì HTTP; không có `requests`.
- Tên provider bị giới hạn bằng `^[a-z][a-z0-9_]*$` và tra trong thư mục whitelist — thay cho `importlib` với chuỗi tùy ý.
- Định dạng mô tả tham số (bảng 1.1), quy tắc áp `default`, thứ tự query.
- JSON Schema đầu ra (tập con), tên lỗi, định dạng CLI.
- Một tham số `in: "body"` kiểu object có `properties` lồng; xác thực đệ quy.

Nguồn **không** bao gồm: `pydantic`, `langchain`, HTTP client, hay gọi công cụ thật.

## Phạm vi

Trong phạm vi:

- Ba provider mẫu, mỗi provider vài công cụ; tổng ≤ 20 công cụ.
- Bốn hàm công khai: `load_provider`, `json_schema`, `validate_args`, `build_request`, cộng `parse_argv`.
- CLI: `schema`, `validate`, `request`, `argv` cho một công cụ.

Ngoài phạm vi:

- Không gọi HTTP thật; không sinh client code; không hỗ trợ `$ref`, `oneOf`, `allOf`.
- Không hỗ trợ file upload, header tùy biến, auth.
- Không dùng `pydantic`; mọi xác thực viết tay.

## Cảnh báo production

- Registry là **dữ liệu không tin cậy** nếu đến từ mạng. Bài này đọc file cục bộ; nếu chuyển sang HTTP, phải kiểm tra kích thước, timeout, và không bao giờ `eval`/`import` tên từ registry.
- `importlib.import_module` với chuỗi từ dữ liệu là lỗ hổng thật (đọc/ghi module tùy ý). Bài tập loại bỏ nó; đừng "khôi phục" để cho giống nguồn.
- Sinh schema không thay thế xác thực phía server: client luôn có thể gửi dữ liệu sai.
- `endpoint.format(**path_params)` có thể bị injection nếu giá trị chứa `/` hoặc `..`; bài tập yêu cầu từ chối ký tự không an toàn trong path.

## Fixture offline

- `fixtures/registry_finance.json` — 4 công cụ: GET có path+query, POST có body, DELETE có path, GET có enum.
- `fixtures/registry_weather.json` — provider thứ hai để kiểm tra nạp theo tên.
- `fixtures/args_*.json` — bộ tham số hợp lệ/không hợp lệ.
- `fixtures/expected_schema_*.json` — golden schema cho hai công cụ.
- Không có URL ngoài; không biến môi trường.

## Liên kết

- [SPEC.md](SPEC.md) — mô tả registry, quy tắc sinh schema, ví dụ request, tiêu chí.
- [GUIDE.md](GUIDE.md) — thiết kế bốn lớp dẫn xuất, bẫy path injection, kiểm chứng.
