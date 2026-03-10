import os
import time
import requests

API_BASE = "http://localhost:8000"
POLL_INTERVAL = 3
MAX_WAIT = 1800 # 30 mins for 121+ chunks

def main():
    print("--- [Verification] Project Verification with Sample PDF ---")
    
    # 1. Path to sample PDF in test_data
    pdf_path = r"e:\Document\New folder\tts-document\test_data\sample.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"[LỖI] Không tìm thấy file PDF tại: {pdf_path}")
        return

    # 2. Upload PDF
    print(f"\n[1] Uploading Sample PDF file to API...")
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            response = requests.post(f"{API_BASE}/upload-pdf/", files=files)
        
        if response.status_code != 200:
            print(f"[ERROR] Upload failed: {response.status_code} - {response.text}")
            return
            
        task_data = response.json()
        task_id = task_data.get("task_id")
        print(f"    -> Received Task ID: {task_id}")
    except Exception as e:
        print(f"[ERROR] Connection error: {e}. Check Uvicorn!")
        return
    
    # 3. Poll for status
    print("\n[2] Waiting for Celery (ext -> nlp -> tts -> merge mp3)...")
    elapsed = 0
    while elapsed < MAX_WAIT:
        try:
            status_resp = requests.get(f"{API_BASE}/task-status/{task_id}")
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                state = status_data.get("status")
                if state == "SUCCESS":
                    result = status_data.get("result", {})
                    print("\n[OK] Task completed successfully!")
                    mp3_path_internal = result.get("final_mp3_path")
                    print(f"     -> MP3 created on server: {mp3_path_internal}")
                    
                    # 4. Download MP3
                    print("\n[3] Downloading MP3...")
                    download_resp = requests.get(f"{API_BASE}/download-audio/{task_id}")
                    if download_resp.status_code == 200:
                        local_mp3 = f"sample_result_{task_id}.mp3"
                        with open(local_mp3, "wb") as mf:
                            mf.write(download_resp.content)
                        print(f"[OK] Downloaded successfully: {local_mp3}")
                    else:
                        print(f"[ERROR] Failed to download. Status: {download_resp.status_code}")
                    return
                elif state == "FAILURE":
                    print(f"\n[FAIL] Task failed. Result: {status_data.get('result')}")
                    return
                else:
                    print(f"    [{elapsed:>3}s] Task status: {state}...")
            else:
                print(f"    [{elapsed:>3}s] Fetch status error: {status_resp.status_code}")
        except Exception as e:
            print(f"    [{elapsed:>3}s] Connection error while polling: {e}")
            
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        
    print(f"\n[FAIL] Timeout sau {MAX_WAIT} giây.")

if __name__ == "__main__":
    main()
