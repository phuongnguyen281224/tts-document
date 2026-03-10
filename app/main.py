import os
import uuid
import aiofiles
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from celery.result import AsyncResult

# Import the Celery app and task
from worker.celery_app import celery_app
from worker.tasks import process_pdf_task

# Import routers and DB components
from app.routers import health
from app import models, database
from sqlalchemy.orm import Session

# Initialize database tables
models.Base.metadata.create_all(bind=database.engine)

# OpenTelemetry Instrumentation
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from app.telemetry import setup_telemetry

# Khởi tạo Global Tracer Provider cho toàn bộ ứng dụng API
setup_telemetry("fastapi-server")

app = FastAPI(title="Async PDF Processing API")
app.include_router(health.router)

# Tự động bắt mọi request vào FastAPI và tạo Span. 
# Từ đây, Trace ID sẽ tự sinh hoặc lấy từ request header nếu client có cấp.
FastAPIInstrumentor.instrument_app(app)

class TaskResponse(BaseModel):
    task_id: str
    message: str

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@app.post("/upload-pdf/", response_model=TaskResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Endpoint to receive a PDF file, validate security requirements,
    and process it asynchronously via Celery.
    """
    # 1. Validate Content-Type
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Chỉ chấp nhận tệp định dạng PDF (application/pdf)."
        )

    # 2. Check File Size
    # FastAPI's UploadFile attempts to get size automatically
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Tệp quá lớn. Giới hạn tối đa là {MAX_FILE_SIZE // (1024*1024)}MB."
        )

    # 3. Sanitize filename and generate UUID
    upload_dir = "temp_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Secure filename: uuid_originalName
    clean_filename = os.path.basename(file.filename)
    task_id = str(uuid.uuid4())
    unique_filename = f"{task_id}_{clean_filename}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    # 4. Save the file locally without blocking
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        # Double check size if file.size was None
        if len(content) > MAX_FILE_SIZE:
             # Cleanup if metadata check failed but actual content is huge
             # Ensure the file is closed before attempting to remove it
             await out_file.close()
             os.remove(file_path) 
             raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Tệp quá lớn. Giới hạn tối đa là {MAX_FILE_SIZE // (1024*1024)}MB."
            )
        await out_file.write(content)
            
    # 5. Create a database record for this job
    db: Session = database.SessionLocal()
    try:
        new_job = models.AudioJob(
            task_id=task_id,
            filename=clean_filename,
            status="PENDING"
        )
        db.add(new_job)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Failed to create DB record: {e}")
    finally:
        db.close()

    # 6. Trigger the Celery background task
    abs_path = os.path.abspath(file_path)
    # Pass the generated task_id to Celery's apply_async for explicit task ID
    process_pdf_task.apply_async(args=[abs_path], task_id=task_id)
    
    return {"task_id": task_id, "message": "File đã được xử lý nền"}

@app.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """
    Endpoint to check the status of a specific task.
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    # Expected statuses: PENDING, STARTED, SUCCESS, FAILURE
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None
    }

@app.get("/download-audio/{task_id}")
async def download_audio(task_id: str):
    """
    Lấy file audio hoàn chỉnh (mp3) theo task ID.
    Kiểm tra AsyncResult trước khi cho phép tải, chỉ SUCCESS mới cho tải.
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    if task_result.status != "SUCCESS":
        raise HTTPException(
            status_code=400, 
            detail=f"Task is currently {task_result.status}. You can only download when it's SUCCESS."
        )
        
    result_data = task_result.result
    if not result_data or "final_mp3_path" not in result_data:
        raise HTTPException(status_code=404, detail="Không tìm thấy đường dẫn MP3 trong metadata của task.")
        
    file_path = result_data["final_mp3_path"]
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File âm thanh không tồn tại trên hệ thống.")
        
    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=os.path.basename(file_path)
    )

@app.delete("/tasks/{task_id}", response_model=TaskResponse)
async def cancel_task(task_id: str):
    """
    Hủy ngang một tác vụ đang chạy trên Celery.
    - Gọi lệnh thu hồi (revoke) kèm theo tín hiệu ép buộc dừng (terminate=True).
    - Lệnh này sẽ tiêu diệt process của worker nếu nó đang kẹt tính toán AI.
    """
    try:
        # Request celery to revoke the task. terminate=True kills the process executing it.
        celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
        return TaskResponse(
            task_id=task_id, 
            message="Yêu cầu hủy tác vụ đã được gửi thành công. Trạng thái task sẽ chuyển sang REVOKED."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Lỗi khi gửi lệnh hủy tác vụ: {str(e)}"
        )
