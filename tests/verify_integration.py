"""
verify_integration.py
End-to-end test for Phase 2 integration.
Requires: Redis running, Celery worker running, FastAPI server running.
"""
import os
import time
import requests

API_BASE = "http://127.0.0.1:8000"
SAMPLE_PDF_URL = "https://raw.githubusercontent.com/mozilla/pdf.js/master/test/pdfs/tracemonkey.pdf"
LOCAL_PDF = "temp_uploads/verify_sample.pdf"
POLL_INTERVAL = 2   # seconds between status checks
MAX_WAIT = 120      # seconds before giving up


def download_pdf(url: str, dest: str):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"[1] Downloading sample PDF from:\n    {url}")
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
    print(f"    Saved to: {dest} ({len(r.content):,} bytes)\n")


def upload_pdf(path: str) -> str:
    print(f"[2] POSTing PDF to {API_BASE}/upload-pdf/")
    with open(path, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/upload-pdf/",
            files={"file": (os.path.basename(path), f, "application/pdf")},
            timeout=30,
        )
    resp.raise_for_status()
    data = resp.json()
    task_id = data["task_id"]
    print(f"    Task ID: {task_id}\n")
    return task_id


def poll_task(task_id: str) -> dict:
    print(f"[3] Polling /task-status/{task_id} ...")
    elapsed = 0
    while elapsed < MAX_WAIT:
        resp = requests.get(f"{API_BASE}/task-status/{task_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        print(f"    [{elapsed:>3}s] status = {status}")
        if status == "SUCCESS":
            return data["result"]
        if status == "FAILURE":
            raise RuntimeError(f"Task failed: {data}")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    raise TimeoutError(f"Task did not complete within {MAX_WAIT}s")


def verify_output(result: dict):
    print(f"\n[4] Verifying output ...")
    print(f"    char_count_raw : {result.get('char_count_raw', '?')}")
    print(f"    chunk_count    : {result.get('chunk_count', '?')}")
    print(f"    chunks_file    : {result.get('chunks_file_path', '?')}")

    json_path = result.get("chunks_file_path")
    assert json_path and os.path.exists(json_path), \
        f"FAIL: Output .json file not found at: {json_path}"

    import json
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n    --- Preview first chunk ---")
    chunks = data.get("chunks", [])
    audio_files = data.get("audio_files", [])
    if chunks:
        print(chunks[0][:500])
        print(f"\n    --- Generated Audio Example ---")
        if audio_files:
            print(audio_files[0])
    print(f"    -----------------------------------------")
    print(f"\n[OK] Integration test PASSED.")


def main():
    try:
        download_pdf(SAMPLE_PDF_URL, LOCAL_PDF)
        task_id = upload_pdf(LOCAL_PDF)
        result = poll_task(task_id)
        verify_output(result)
    except Exception as e:
        print(f"\n[FAIL] Integration test FAILED: {e}")
        raise


if __name__ == "__main__":
    main()
