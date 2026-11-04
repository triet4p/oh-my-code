# SETUP — Môi trường cho 60 mini-project

Tài liệu này hướng dẫn cài **công cụ dùng chung** và chọn dependency theo từng bài. Các lệnh mặc định chạy trong **PowerShell trên Windows 10/11 x64**; chỉ khối có ghi MSYS2 UCRT64 chạy trong terminal MSYS2. macOS/Linux có liên kết cài đặt chính thức ở từng mục.

Không cần cài tất cả ngay. Bắt đầu bằng Python + uv, rồi cài thêm khi gặp bài dùng ngôn ngữ khác. Các folder hiện chứa tài liệu, **chưa có sẵn implementation, project, test hay fixtures**: bạn tự tạo chúng theo `GUIDE.md` của từng bài. Cài tool và package ban đầu cần Internet; các bài được thiết kế để thực hành offline sau khi đã có dependencies.

## 1. Bản đồ môi trường theo bài

Mở [lộ trình](docs/CURRICULUM.md) để tới README/SPEC/GUIDE theo ID. Các phiên bản dưới đây là lựa chọn chung thỏa yêu cầu đã ghi trong bài; xem README/GUIDE của bài để biết chi tiết và các lựa chọn thay thế.

| ID | Môi trường và dependency cho bài |
|---|---|
| 01, 03, 10, 12, 19 | Python 3.12+, uv, pytest; code bài dùng thư viện chuẩn |
| 02, 13 | Node.js 22+, npm, TypeScript, Vitest, `@types/node` |
| 04 | Python 3.12+, uv, pytest, PyYAML; Faker theo hướng dẫn bài hoặc tự sinh dữ liệu theo SPEC |
| 05, 09 | Node.js 22+; chỉ thư viện chuẩn Node |
| 06 | Trình biên dịch C++17: MSVC, GCC/g++ hoặc Clang |
| 07, 08 | Rust stable, Cargo; không cần crate ngoài |
| 11 | Node.js 22+, npm, TypeScript, tsx, Vitest, `@types/node`, Zod, YAML, gray-matter |
| 14 | Python 3.12+, uv, httpx, pytest; server SSE giả tự viết ở máy local |
| 15 | Như 14, thêm pytest-asyncio hoặc AnyIO theo cách viết test |
| 16 | Python 3.12+, uv, pytest; RDFLib tùy chọn để kiểm tra cú pháp |
| 17 | Python 3.12+, uv, openpyxl, pytest; không cần Microsoft Excel |
| 18 | JDK 21, Kotlin 2.x, Gradle, JUnit 5; không cần Android SDK |
| 20 | Python 3.12+, uv, NumPy, pytest |
| 21 | Trình duyệt hiện đại; Node.js 18+ **hoặc** Python 3.11+ để chạy static server local |
| 22–30 | Python 3.11+; thư viện chuẩn, không cần service thật |
| 31 | Node.js 20+, TypeScript 5; dùng Node 22+ để thống nhất với các bài TypeScript khác |
| 32 | JDK 17+ (`java`, `javac`); không cần MySQL hay JDBC driver |
| 33–37 | Python 3.11+; thư viện chuẩn |
| 38 | Rust 1.75+, Cargo; chỉ `std` |
| 39–40 | .NET SDK 8 với C# 12; không cần database |
| 41–44 | Python 3.12, thư viện chuẩn; bài 42 chỉ cần PyTorch nếu tự làm adapter thật tùy chọn |
| 45 | Rust 1.70+, Cargo; chỉ `std` |
| 46–52 | Python 3.12, thư viện chuẩn |
| 53 | JDK 17+, Kotlin compiler `kotlinc` 1.9+; không bắt buộc Gradle |
| 54–60 | Python 3.12, thư viện chuẩn |

Python 3.12 là baseline thuận tiện cho các bài Python; nếu một bài ghi `3.11+`, 3.12 cũng đáp ứng. Trong bảng, pytest là **package bên ngoài**, không thuộc thư viện chuẩn. JDK 21 đáp ứng cả yêu cầu JDK 17 của bài 32 và 53. Với bài 18, Gradle tải Kotlin plugin và JUnit khi thiết lập lần đầu; không cần cài Android SDK.

## 2. Công cụ chung

### 2.1 Git và trình soạn thảo

- [Git for Windows](https://git-scm.com/downloads/win), hoặc chọn bản phù hợp OS trên trang Git.
- Editor tùy chọn: [Visual Studio Code](https://code.visualstudio.com/). Có thể cài extension Python, Rust, C/C++, Kotlin, C# khi cần; extension không thay thế compiler/SDK.

Kiểm tra trong terminal mới:

```powershell
git --version
```

### 2.2 Python 3.12 và uv

1. Cài [uv theo hướng dẫn chính thức](https://docs.astral.sh/uv/getting-started/installation/). Trên Windows có thể dùng WinGet:

   ```powershell
   winget install --id=astral-sh.uv -e
   ```

   Nếu không có WinGet, dùng installer ở trang chính thức. Trên macOS/Linux trang đó có lệnh tương ứng.
2. Đóng và mở lại PowerShell để cập nhật `PATH`, rồi để uv tải Python 3.12:

   ```powershell
   uv --version
   uv python install 3.12
   uv python list --only-installed
   ```

   `uv` quản lý được bản Python riêng; bạn không bắt buộc phải cài Python toàn cục. Nếu muốn Python hệ thống, tải từ [python.org](https://www.python.org/downloads/) và kiểm tra bằng `py -3.12 --version`.
3. Tại **một folder bài**, tạo project riêng trong `work/` khi bắt đầu thực hành. Ví dụ từ root repo:

   ```powershell
   New-Item -ItemType Directory -Force 01_SIMPLE_RECT_GEOMETRY/work | Out-Null
   Set-Location 01_SIMPLE_RECT_GEOMETRY/work
   uv init . -p 3.12
   uv add --dev pytest
   uv run python --version
   uv run python -m pytest --version
   ```

   `uv init` tạo `pyproject.toml`; `uv add` ghi dependencies vào project và tạo/cập nhật lockfile. Lệnh này là **thiết lập ban đầu**, không chạy lại `uv init` trên project đã khởi tạo. Có thể dùng `uv run ...` thay vì activate `.venv`; nếu muốn activate trong PowerShell dùng `.\.venv\Scripts\Activate.ps1`. Nếu policy chặn, xem [PowerShell execution policies](https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_execution_policies); không cần thay policy nếu dùng `uv run`.

Với bài 22–30, 33–37, 41–44, 46–52, 54–60, bản cơ bản chỉ dùng thư viện chuẩn: có thể tạo môi trường tương tự và chỉ thêm pytest nếu chọn pytest; không cần cài lại các package của bài khác. Bài có thể dùng `unittest` hoặc công cụ tự kiểm tra như GUIDE mô tả.

### 2.3 Node.js, npm và TypeScript

1. Tải Node.js LTS từ [nodejs.org/download](https://nodejs.org/en/download); chọn bản **22 trở lên**. npm đi cùng bộ cài Node. Mở terminal mới:

   ```powershell
   node --version
   npm --version
   ```

2. Với bài TypeScript, khởi tạo **riêng từng `work/`**, ví dụ từ root repo:

   ```powershell
   New-Item -ItemType Directory -Force 02_PLAN_SORT_COMPARATOR/work | Out-Null
   Set-Location 02_PLAN_SORT_COMPARATOR/work
   npm init -y
   npm install -D typescript vitest @types/node
   npx tsc --version
   npx vitest --version
   ```

   Tiếp tục cấu hình `tsconfig.json`, `package.json` và tạo file theo GUIDE của bài. Package được cài local trong `work/node_modules`, không bắt buộc cài TypeScript/Vitest toàn cục. Lưu `package-lock.json` nếu muốn tái lập phiên bản. Bài 31 chỉ bắt buộc TypeScript; cài test runner theo GUIDE hoặc cách bạn chọn.
3. Bài 05/09 chỉ cần Node; bài 21 có thể dùng trình duyệt cùng `python -m http.server` thay Node. Không cần `npm install` cho các bài Node thuần này.

### 2.4 C++17: GCC/g++ hoặc MSVC

**Windows, chọn một trong hai:**

- **GCC/g++:** cài [MSYS2](https://www.msys2.org/), mở terminal **MSYS2 UCRT64** và làm theo hướng dẫn cập nhật hệ thống của MSYS2, sau đó:

  ```bash
  pacman -S mingw-w64-ucrt-x86_64-gcc
  gcc --version
  g++ --version
  ```

  Dùng `g++` để biên dịch C++ cho bài 06. Các lệnh `pacman` chạy trong MSYS2, không phải PowerShell thường. Nếu muốn dùng `g++` trong PowerShell, thêm thư mục `ucrt64/bin` của bản MSYS2 vào `PATH` rồi mở terminal mới; không trộn lẫn các bộ toolchain một cách tùy tiện.
- **MSVC:** tải [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/), chọn workload **Desktop development with C++** và Windows SDK. Mở **x64 Native Tools Command Prompt for Visual Studio** rồi chạy `cl` để kiểm tra. Lệnh `cl` chỉ có sẵn trong môi trường đã nạp build tools; dùng `/std:c++17` khi biên dịch.

Trên Linux dùng package compiler C++ của distro; trên macOS cài Xcode Command Line Tools (`xcode-select --install`). Xem [hướng dẫn MSYS2](https://www.msys2.org/) và [MSVC](https://learn.microsoft.com/cpp/build/building-on-the-command-line). CMake không bắt buộc cho bài 06.

### 2.5 Rust và Cargo

1. Trên Windows tải [rustup-init.exe](https://www.rust-lang.org/tools/install/) đúng kiến trúc, chạy installer và chọn stable. Cấu hình MSVC mặc định cần Visual Studio C++ Build Tools và Windows SDK như mục 2.4; GCC cài qua MSYS2 **không tự thay thế** linker MSVC của toolchain mặc định.
2. Mở terminal mới:

   ```powershell
   rustup --version
   rustc --version
   cargo --version
   rustup show active-toolchain
   ```

   Nếu lệnh không tìm thấy, kiểm tra `%USERPROFILE%\.cargo\bin` có trong `PATH`. Trên macOS/Linux làm theo [rustup](https://www.rust-lang.org/tools/install/) và cài C compiler/linker của OS.
3. Tạo crate ở `work/` theo GUIDE của bài, rồi `cargo test`. Bài 07, 08, 38, 45 dùng `std`; không cần thêm crate ngoài cho phạm vi cơ bản.

### 2.6 JDK, Kotlin và Gradle

1. Cài **JDK 21** từ [Eclipse Temurin](https://adoptium.net/temurin/releases/) hoặc nhà cung cấp OpenJDK tin cậy. Chọn JDK, không chỉ JRE. Trong PowerShell mới:

   ```powershell
   java -version
   javac -version
   ```

   Nếu Gradle/compiler chọn nhầm Java, đặt `JAVA_HOME` đến **thư mục JDK** và bảo đảm `%JAVA_HOME%\bin` trong `PATH`, rồi mở lại terminal.
2. **Bài 18:** cài [Gradle](https://docs.gradle.org/current/userguide/installation.html) để bootstrap nếu chưa có `gradle`, kiểm tra `gradle --version`, sau đó khởi tạo project Kotlin/JVM theo GUIDE bài 18. Dùng Gradle Wrapper (`.\gradlew.bat` trên Windows) sau khi wrapper được tạo; lần đầu wrapper, Kotlin plugin và JUnit cần tải từ mạng. Kotlin Gradle plugin 2.x quản lý compiler của bài, không bắt buộc `kotlinc` toàn cục.
3. **Bài 53:** tải `kotlin-compiler-*.zip` từ [Kotlin releases](https://github.com/JetBrains/kotlin/releases), giải nén và thêm `kotlinc/bin` vào `PATH` theo [hướng dẫn Kotlin](https://kotlinlang.org/docs/command-line.html). Mở terminal mới rồi kiểm tra:

   ```powershell
   kotlinc -version
   java -version
   ```

   Làm theo GUIDE bài 53 để biên dịch các file bạn tự viết bằng `kotlinc` và chạy bằng `java`. Bài 32 dùng `javac`/`java`, không cần Kotlin hay Gradle.

### 2.7 .NET SDK cho C#

Tải **.NET SDK 8** từ [dotnet.microsoft.com/download/dotnet/8.0](https://dotnet.microsoft.com/download/dotnet/8.0); chọn SDK, không chỉ runtime. Mở terminal mới:

```powershell
dotnet --list-sdks
dotnet --version
```

Bài 39–40 dùng C# 12/.NET 8. Tạo project trong `work/` và chạy các lệnh build/test **sau khi tự viết code** theo GUIDE từng bài. Nếu có nhiều SDK, bảo đảm `dotnet --list-sdks` liệt kê bản 8.x; có thể chọn SDK qua `global.json` nếu cần ghim phiên bản cho project.

## 3. Dependency riêng từng bài

Thực hiện sau khi tạo project `work/` của **chính bài đó**. Không cài vào root repo hoặc cùng một môi trường chung cho toàn bộ bài. Các lệnh `uv add` cần `pyproject.toml` đã tạo bằng `uv init`; các lệnh `npm install` cần project npm đã khởi tạo.

| Bài | Chạy trong `work/` | Ghi chú |
|---|---|---|
| 01, 03, 10, 12, 16, 19 | `uv add --dev pytest` | Bài 16: `uv add rdflib` chỉ khi muốn dùng RDFLib. |
| 04 | `uv add pyyaml faker` rồi `uv add --dev pytest` | Faker có thể thay bằng cách tự sinh phù hợp SPEC. |
| 14 | `uv add httpx` rồi `uv add --dev pytest` | Server local do người học tự viết. |
| 15 | `uv add httpx` rồi `uv add --dev pytest pytest-asyncio` | Có thể dùng AnyIO thay thế theo cách viết test. |
| 17 | `uv add openpyxl` rồi `uv add --dev pytest` | Workbook test do người học tạo. |
| 20 | `uv add numpy` rồi `uv add --dev pytest` | Không cần GPU. |
| 02, 13 | `npm install -D typescript vitest @types/node` | Thêm cấu hình TypeScript, ESM và script theo GUIDE. |
| 11 | `npm install zod yaml gray-matter` rồi `npm install -D typescript tsx vitest @types/node` | GUIDE có thể cho phép tự tách frontmatter thay `gray-matter`. |
| 31 | `npm install -D typescript @types/node` | Đọc GUIDE để chọn cấu hình compile/chạy test. |
| 18 | Kotlin Gradle plugin 2.x và JUnit 5 trong `build.gradle.kts` | Khai báo theo GUIDE; Gradle tải khi chạy lần đầu. |
| 42 | Không cần package cho bài cơ bản | `torch` chỉ dành cho adapter thật tùy chọn; xem [PyTorch Start Locally](https://pytorch.org/get-started/locally/) để chọn bản phù hợp CPU/GPU. |

Các bài còn lại dùng compiler/runtime và thư viện chuẩn trong bảng mục 1. Nếu tự thêm package cho phiên bản mở rộng, ghi dependency và phiên bản trong project của bài; không biến nó thành yêu cầu bắt buộc của bài gốc.

## 4. Kiểm tra trước khi bắt đầu một bài

1. Chọn ID trong [lộ trình](docs/CURRICULUM.md); đối chiếu mục 1 và README của bài.
2. Kiểm tra version công cụ cần thiết bằng các lệnh ở mục 2. Không bắt buộc mọi lệnh cho mọi bài đều phải thành công.
3. Tạo `work/` riêng theo GUIDE, cài dependency tương ứng trong mục 3. Cài một lần; giữ manifest/lockfile nếu cần tái lập.
4. Tự tạo source, test và fixtures theo SPEC/GUIDE; sau đó mới chạy lệnh kiểm chứng của bài.
5. Bài 14/15/21/50 sử dụng kết nối **local** trong quá trình thực hành; không cần public endpoint hoặc API key thật cho phạm vi cơ bản.

Nếu terminal không nhận lệnh sau khi cài: mở terminal mới, kiểm tra `PATH` bằng `Get-Command <tên-lệnh>` trong PowerShell. Kiểm tra đúng terminal: `pacman` chỉ trong MSYS2, `cl` trong terminal đã nạp MSVC. Nếu tải package lỗi, kiểm tra kết nối, proxy và nguồn cài chính thức trước khi đổi cấu hình hệ thống.

## 5. Nguồn cài đặt và lưu ý an toàn

Các link ở trên dẫn đến tài liệu/nhà phát hành chính thức. Đọc hướng dẫn trước khi chạy installer hoặc script tải từ Internet; không cần chạy PowerShell với quyền administrator trừ khi installer cụ thể yêu cầu. Các bài tập không yêu cầu cấu hình Kafka, Spark, HDFS, Fuseki, Android SDK, tài khoản LLM hay GPU cho phạm vi cơ bản — đừng cài chúng chỉ vì repo nguồn ban đầu sử dụng.
