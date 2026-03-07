import os
import aiofiles
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from celery.result import AsyncResult

# Import the Celery app and task
from worker.celery_app import celery_app
from worker.tasks import process_pdf_task

app = FastAPI(title="Async PDF Processing API")

class TaskResponse(BaseModel):
    task_id: str
    message: str

@app.post("/upload-pdf/", response_model=TaskResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Endpoint to receive a PDF file, immediately assign a task ID,
    and process it asynchronously via Celery.
    """
    
    # Save the file to a temporary directory
    upload_dir = "temp_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    
    # Write the content locally without blocking
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
            
    # Trigger the Celery background task
    abs_path = os.path.abspath(file_path)
    task = process_pdf_task.delay(abs_path)
    
    # Return the genuine task ID immediately
    return {"task_id": task.id, "message": "File đã được xử lý nền"}

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
        filename=f"{task_id}_final.mp3"
    )

