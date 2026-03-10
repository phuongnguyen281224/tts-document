# Phân Tích Kiến Trúc Backend: Hệ Thống Text-to-Speech Phân Tán (Asynchronous TTS System)

Tài liệu này đóng vai trò là kim chỉ nam kỹ thuật cho Giai đoạn 1 của dự án. Hệ thống được thiết kế theo hướng Microservices siêu nhỏ, tách biệt hoàn toàn API giao tiếp (FastAPI) khỏi luồng tính toán AI nặng nề (Celery + Redis). Thiết kế này đảm bảo ứng dụng không bao giờ bị "treo" khi có nhiều người dùng sử dụng cùng lúc.

---

## 1. Cấu Trúc Thư Mục (Directory Structure)

```text
📦 tts-document
 ┣ 📂 app                  # Tầng Web API (FastAPI)
 ┃ ┣ 📜 main.py           # Entrypoint của toàn bộ API server, định nghĩa các routers
 ┃ ┣ 📜 database.py       # Cấu hình kết nối SQLAlchemy (SQLite)
 ┃ ┣ 📜 models.py         # Định nghĩa các ORM Models (VD: AudioJob)
 ┃ ┣ 📜 telemetry.py      # Cấu hình OpenTelemetry cho Distributed Tracing
 ┃ ┗ 📂 routers           # Chứa các API con (VD: health.py kiểm tra liveness/readiness)
 ┣ 📂 worker              # Tầng Xử Lý Nền (Celery)
 ┃ ┣ 📜 celery_app.py     # Khởi tạo Celery App & cấu hình Broker/Result Backend
 ┃ ┣ 📜 tasks.py          # Entrypoint của Worker, chứa @celery_app.task (VD: process_pdf_task)
 ┃ ┣ 📜 audio_processor.py# Chắp vá, crossfade và xuất file Audio MP3
 ┃ ┗ 📜 nlp_pipeline.py   # Xử lý ngôn ngữ tự nhiên (NLP), chuẩn hóa văn bản
 ┣ 📂 tts_engine          # Module AI Dịch Thuật & Sinh Âm Thanh (Core Engine)
 ┃ ┗ 📜 generator.py      # Chứa class VietnameseTTS để gọi mô hình Text-to-Speech
 ┣ 📂 pdf_parser          # Module Tiền Xử Lý Document
 ┃ ┣ 📜 extractor.py      # Trích xuất và dọn dẹp (clean) văn bản thô từ file PDF
 ┣ 📂 temp_uploads        # Thư mục tạm lưu PDF được push lên (Tự động xóa sau khi xử lý)
 ┣ 📂 temp_outputs        # Thư mục lưu Chunk JSON trung gian
 ┣ 📂 completed_audios    # Nơi lưu kết quả MP3/WAV cuối cùng để trả về cho người dùng
 ┣ 📜 docker-compose.yml  # File điều phối Container cho Redis & Flower
 ┗ 📜 tts_jobs.db         # Cơ sở dữ liệu SQLite theo dõi lộ trình và siêu dữ liệu của Task
```

---

## 2. Luồng Dữ Liệu Chốt Chặn (Data Flow)

Luồng đi của một Audio Job từ lúc khởi tạo đến lúc hoàn thiện diễn ra theo 6 bước:

1. **Upload File**: Người dùng gửi request `POST /upload-pdf/` đính kèm file.
2. **Metadata DB (SQLite)**: FastAPI ngay lập tức lưu một bản ghi vào `tts_jobs.db` với trạng thái `PENDING` và lấy ra `task_id` (UUID).
3. **Enqueue (Redis)**: FastAPI lưu file PDF vào `temp_uploads`, gọi lệnh `apply_async` để đẩy thông điệp công việc (gồm đường dẫn file và `task_id`) vào hàng đợi Redis Queue. Ngay lập tức API trả về HTTP 200 cho người dùng mà không cần chờ AI chạy xong.
4. **Processing (Celery Worker)**: Worker nhặt task từ Redis, tiến hành chuỗi hành động:
    - **PDF Parser**: Đọc và làm sạch text.
    - **NLP Pipeline**: Chuẩn hóa text tiếng Việt và cắt thành các Chunk ngữ nghĩa nhỏ.
    - **TTS Engine**: Render từng Chunk thành Audio (WAV) và lưu tạm.
    - **Audio Processor**: Ghép các audio lại bằng Crossfade và nén thành MP3.
5. **Database Sync**: Thông qua hook `after_return`, worker kết nối lại vào SQLite để cập nhật trạng thái `SUCCESS` (hoặc `FAILURE`) và neo nhãn thời gian `finished_at`.
6. **Garbage Collection (Dọn dẹp)**: Hook `after_return` tiếp tục kiểm tra và ra lệnh `os.remove()` thủ tiêu file PDF gốc trong `temp_uploads` để chống rác ổ cứng.

---

## 3. Các Quy Ước Bảo Mật & An Toàn Vận Hành

- **Màng Lọc Dữ Liệu**: API upload luôn kiểm tra khắt khe `content_type == "application/pdf"` và sử dụng kích thước trần `50MB` mặc định để chống tấn công DDoS phình to đĩa.
- **Cách Ly Tên Tệp (Sanitization)**: Không bao giờ lưu tên file gốc của người dùng. Mọi file được lưu tại backend đều bị ép đổi tên theo chuỗi `UUID` vô danh để tránh Path Traversal và ghi đè trái phép.
- **Giới Hạn Nút Thắt (Prefetch Limit)**: Celery worker được cấu hình `worker_prefetch_multiplier = 1` và `task_acks_late = True`. Điều này cấm Worker đầu cơ tích trữ task vào RAM, giúp tiết kiệm bộ nhớ và chống tình trạng OOM (Out Of Memory) Crash.
- **Thu Hồi Quyền Lực (Aggressive Cancellation)**: Endpoint `DELETE /tasks/{task_id}` cho phép triệu hồi cờ `SIGTERM` đâm thẳng vào OS để ép buộc hủy diệt process của Worker nếu task đó bị kẹt vòng lặp hoặc chạy quá thời gian (chuyển state sang `REVOKED`).
- **Distributed Tracing (OpenTelemetry)**: Luồng tín hiệu được đồng bộ hóa `Trace ID` từ FastAPI xuyên qua Redis tới tận Celery nhờ OpenTelemetry, giúp dễ dàng rà soát log đa luồng.

---

## 4. Dependencies & Broker Configuration

- **Message Broker & Result Backend**: Sử dụng `Redis` (Image Docker: `redis:alpine`) làm trạm trung chuyển trung tâm, chạy ở port `6379`.
- **Worker Monitor**: Sử dụng `Flower` (Image: `mher/flower`) đọc trực tiếp Redis để vẽ biểu đồ giám sát luồng Celery, phơi bày WebUI ở port `5555`.
- **Database**: Sử dụng `SQLite` thông qua bộ ORM `SQLAlchemy` để lưu trữ dữ liệu task vượt quá vòng đời tắt mở máy.
- **Core Library & ML**:
  - `FastAPI`, `Uvicorn`: Khung sườn Web API bất đồng bộ.
  - `Celery`, `Redis`: Chịu trách nhiệm xử lý nền.
  - `PyMuPDF` (fitz), `tesseract`: Trích xuất và OCR văn bản.
  - `PyTorch`, `Transformers`, `Huggingface Hub`: Thư viện lõi cho AI.
  - `Pydub`: Cố định và hợp nhất Audio Format.

---

## 5. Hướng Dẫn Khởi Động Nhanh (Setup & Execution)

### Bước 1: Kích Hoạt Nền Tảng Phụ Trợ (Docker)
Đảm bảo Redis Broker và UI Flower đã sẵn sàng:
```bash
docker-compose up -d
```
Trang Dashboard Celery: Mở trình duyệt vào http://localhost:5555

### Bước 2: Kích Hoạt Tầng AI (Celery Worker)
Mở một terminal chuyên biệt dành riêng cho Engine nền:
```bash
# Đối với Windows
.\venv\Scripts\celery -A worker.celery_app worker --loglevel=info --pool=solo
```

### Bước 3: Kích Hoạt Tầng Giao Tiếp (FastAPI)
Mở một terminal khác và khởi chạy Uvicorn Server:
```bash
.\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Tài liệu Swagger API: http://localhost:8000/docs
