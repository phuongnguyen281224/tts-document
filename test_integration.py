import requests
import time
import os

BASE_URL = "http://localhost:8000"

def create_dummy_pdf():
    """Creates a dummy PDF file for testing."""
    filename = "dummy.pdf"
    with open(filename, "wb") as f:
        f.write(b"%PDF-1.4\n%EOF\n")
    return filename

def test_async_workflow():
    print("Testing asynchronous API workflow...")
    
    # Ensure a test file exists
    dummy_pdf_path = create_dummy_pdf()
    
    # 1. Upload a dummy PDF
    print("\n--- 1. Uploading PDF ---")
    with open(dummy_pdf_path, 'rb') as f:
        files = {'file': (dummy_pdf_path, f, 'application/pdf')}
        response = requests.post(f"{BASE_URL}/upload", files=files)
        
    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()
    task_id = data.get("task_id")
    status = data.get("status")
    
    print(f"Task ID received: {task_id}")
    print(f"Initial Status: {status}")
    
    assert task_id is not None
    assert status == "processing"
    
    # 2. Check task status until it completes
    print("\n--- 2. Checking Task Status ---")
    max_retries = 10
    sleep_delay = 2
    
    for i in range(max_retries):
        resp = requests.get(f"{BASE_URL}/task/{task_id}")
        assert resp.status_code == 200, f"Failed to get task status: {resp.text}"
        
        task_info = resp.json()
        current_status = task_info.get("status")
        
        print(f"[{i+1}/{max_retries}] Status: {current_status}")
        
        if current_status == "SUCCESS":
            print(f"Task result: {task_info.get('result')}")
            print("\nWorkflow completed successfully!")
            break
        elif current_status == "FAILURE":
            print(f"Task failed: {task_info}")
            break
            
        time.sleep(sleep_delay)
    else:
        print("\nTimeout: Task took too long to complete.")
        
    # Clean up
    if os.path.exists(dummy_pdf_path):
        os.remove(dummy_pdf_path)

if __name__ == "__main__":
    try:
        test_async_workflow()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to FastAPI server. Ensure it is running on port 8000.")
