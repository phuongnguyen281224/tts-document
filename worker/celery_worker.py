from celery import Celery
import os
from pdf_extractor import extract_pdf_text

# Configure Celery application to use Redis as broker and backend
celery_app = Celery(
    "pdf_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="process_pdf")
def process_pdf_task(file_path: str, original_file_name: str, file_size: int):
    """
    Task to process PDF using the pdf_extractor module.
    """
    print(f"Received task to process PDF: {original_file_name} (Size: {file_size} bytes)")
    
    try:
        # Extract text using the new PyMuPDF/OCR module
        extracted_text = extract_pdf_text(file_path)
        
        # Clean up the file after processing
        if os.path.exists(file_path):
            os.remove(file_path)
            
        print(f"Successfully processed PDF: {original_file_name}")
        return {
            "status": "success", 
            "file_name": original_file_name, 
            "message": "PDF processed successfully",
            "extracted_text": extracted_text[:1000] + ("..." if len(extracted_text) > 1000 else "") # Returning preview
        }
    except Exception as e:
        print(f"Failed to process PDF: {str(e)}")
        # Attempt to clean up even if it fails
        if os.path.exists(file_path):
            os.remove(file_path)
        return {"status": "error", "message": str(e)}
