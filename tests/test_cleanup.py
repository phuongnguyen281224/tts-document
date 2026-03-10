import requests
import time
import os
import base64

BASE_URL = "http://localhost:8000"

# Minimal valid PDF with 1 empty page
MINIMAL_PDF_B64 = "JVBERi0xLgoxIDAgb2JqPDwvUGFnZXMgMiAwIFI+PmVuZG9iagoyIDAgb2JqPDwvVHlwZSAvUGFnZXMvS2lkc1szIDAgUl0vQ291bnQgMT4+ZW5kb2JqCjMgMCBvYmo8PC9UeXBlIC9QYWdlL1BhcmVudCAyIDAgUi9NZWRpYUJveFswIDAgNTk1IDg0Ml0vQ29udGVudHMgNCAwIFI+PmVuZG9iago0IDAgb2JqPDwvTGVuZ3RoIDIyPj5zdHJlYW0KMTAwIDEwMCBtCjIwMCAyMDAgbApTCmVuZHN0cmVhbQplbmRvYmoKeHJlZgowIDUKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDEwIDAwMDAwIG4gCjAwMDAwMDAwNTMgMDAwMDAgbiAKMDAwMDAwMDEwMiAwMDAwMCBuIAowMDAwMDAwMTkyIDAwMDAwIG4gCnRyYWlsZXI8PC9TaXplIDUvUm9vdCAxIDAgUj4+CnN0YXJ0eHJlZgoyNjUKJSVFT0YK"

def wait_for_task(task_id, max_wait=30):
    for _ in range(max_wait):
        r = requests.get(f"{BASE_URL}/task-status/{task_id}").json()
        print(f"Status: {r['status']}")
        if r['status'] in ['SUCCESS', 'FAILURE']:
            return r
        time.sleep(2)
    return None

def test_cleanup_success():
    print("\n--- Testing Cleanup on SUCCESS ---")
    valid_pdf_bytes = base64.b64decode(MINIMAL_PDF_B64)
    files = {'file': ('success_test.pdf', valid_pdf_bytes, 'application/pdf')}
    response = requests.post(f"{BASE_URL}/upload-pdf/", files=files).json()
    task_id = response['task_id']
    print(f"Task ID: {task_id}")
    
    # Wait for the task to finish
    result = wait_for_task(task_id)
    print(f"Final Task Status: {result['status']}")
    
    # Find the file in temp_uploads matching the task UUID
    temp_dir = "temp_uploads"
    found_files = [f for f in os.listdir(temp_dir) if task_id in f]
    if len(found_files) == 0:
        print("[SUCCESS] File was correctly deleted.")
    else:
        print(f"[ERROR] Files still exist: {found_files}")

def test_cleanup_failure():
    print("\n--- Testing Cleanup on FAILURE (Invalid PDF) ---")
    # Sending a completely invalid non-PDF stream to force PyMuPDF failure
    files = {'file': ('fake_pdf.pdf', b'this is not a valid pdf file', 'application/pdf')}
    response = requests.post(f"{BASE_URL}/upload-pdf/", files=files).json()
    task_id = response['task_id']
    print(f"Task ID: {task_id}")
    
    # This task will fail, retry 3 times, then hit FAILURE. Wait longer.
    print("Wait for retries to exhaust (approx 15-20s)...")
    result = wait_for_task(task_id, max_wait=40)
    print(f"Final Task Status: {result['status']}")
    
    temp_dir = "temp_uploads"
    found_files = [f for f in os.listdir(temp_dir) if task_id in f]
    if len(found_files) == 0:
        print("[SUCCESS] File was correctly deleted even after FAILURE.")
    else:
        print(f"[ERROR] Files still exist: {found_files}")

if __name__ == "__main__":
    test_cleanup_success()
    test_cleanup_failure()
    print("\nTests complete!")
