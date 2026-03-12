import os
import sys
import argparse
import subprocess
import time
import requests
import re
import shutil

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

API_BASE = "http://localhost:8000"
POLL_INTERVAL = 3
MAX_WAIT = 1800 # 30 mins max to wait for large PDFs

def kill_port_8000():
    try:
        output = subprocess.check_output(["netstat", "-ano"], text=True)
        for line in output.splitlines():
            if ":8000" in line and "LISTENING" in line:
                parts = re.split(r'\s+', line.strip())
                if len(parts) >= 5:
                    pid = parts[4]
                    print(f"[*] Killing process {pid} on port 8000...")
                    subprocess.run(["taskkill", "/F", "/PID", pid, "/T"], capture_output=True)
    except Exception as e:
        print(f"Error checking port 8000: {e}")

def kill_celery():
    try:
        output = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq celery.exe", "/FO", "CSV", "/NH"], text=True)
        for line in output.splitlines():
            if not line.strip(): continue
            parts = line.split('","')
            pid = parts[1].strip('"')
            print(f"[*] Killing celery {pid}...")
            subprocess.run(["taskkill", "/F", "/PID", pid, "/T"], capture_output=True)
    except:
        pass

def check_redis():
    try:
        print("[*] Ensuring Redis is running via docker-compose (if applicable)...")
        subprocess.run(["docker-compose", "up", "-d", "redis"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        # Ignore errors if docker or docker-compose is not installed or not running
        pass

def start_services():
    print("[*] Cleaning up old instances of FastAPI & Celery...")
    kill_port_8000()
    kill_celery()
    time.sleep(2)

    check_redis()

    print("[*] Starting backend services (FastAPI & Celery)...")
    venv_python = r".\venv\Scripts\python.exe"
    venv_celery = r".\venv\Scripts\celery.exe"

    if not os.path.exists(venv_python):
        print(f"[!] Virtual environment not found at {venv_python}. Please ensure you are in the project root.")
        return False
        
    out_fastapi = open("fastapi_server.log", "w", encoding='utf-8')
    err_fastapi = open("fastapi_server_error.log", "w", encoding='utf-8')
    subprocess.Popen([venv_python, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
                     stdout=out_fastapi, stderr=err_fastapi)
    
    out_celery = open("celery_worker.log", "w", encoding='utf-8')
    err_celery = open("celery_worker_error.log", "w", encoding='utf-8')
    subprocess.Popen([venv_celery, "-A", "worker.celery_app", "worker", "--loglevel=info", "--pool=solo"],
                     stdout=out_celery, stderr=err_celery)

    print("[*] Waiting for FastAPI to be ready on port 8000...")
    for i in range(20):
        try:
            resp = requests.get("http://localhost:8000/docs", timeout=1)
            if resp.status_code == 200:
                print("[+] Services are running!")
                return True
        except:
            pass
        time.sleep(1)
        sys.stdout.write(f"\r    Waiting... ({i+1}/20s)")
        sys.stdout.flush()
    print()
    return False

def process_pdf(pdf_path, output_dir=None):
    if not os.path.exists(pdf_path):
        print(f"[!] PDF not found: {pdf_path}")
        return

    print(f"\n[*] Uploading PDF: {pdf_path}")
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            response = requests.post(f"{API_BASE}/upload-pdf/", files=files)
        
        if response.status_code != 200:
            print(f"[!] Upload failed. Status {response.status_code}: {response.text}")
            return
            
        task_data = response.json()
        task_id = task_data.get("task_id")
        print(f"[+] PDF accepted. Task ID: {task_id}")
    except Exception as e:
        print(f"[!] Connection error: {e}. Are the services running?")
        return

    print(f"\n[*] Processing PDF... (This can take a while for large files)")
    print(f"[*] Task progress is monitored in celery_worker.log and fastapi_server.log")
    elapsed = 0
    sys.stdout.write("    [")
    while elapsed < MAX_WAIT:
        try:
            status_resp = requests.get(f"{API_BASE}/task-status/{task_id}")
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                state = status_data.get("status")
                if state == "SUCCESS":
                    sys.stdout.write("]\n")
                    result = status_data.get("result", {})
                    print("\n[+] Task completed successfully!")
                    
                    print("[*] Downloading output MP3...")
                    download_resp = requests.get(f"{API_BASE}/download-audio/{task_id}")
                    if download_resp.status_code == 200:
                        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
                        local_mp3 = f"{pdf_name}_output.mp3"
                        
                        if output_dir:
                            # If the output_dir is an existing directory or ends with a slash/backslash, treat as directory
                            if os.path.isdir(output_dir) or output_dir.endswith(os.sep) or output_dir.endswith('/'):
                                if not os.path.exists(output_dir):
                                    os.makedirs(output_dir, exist_ok=True)
                                local_mp3 = os.path.join(output_dir, local_mp3)
                            else:
                                # Otherwise treat it as the full file path (e.g. "my_custom_audio.mp3")
                                # Ensure its parent directory exists
                                parent_dir = os.path.dirname(os.path.abspath(output_dir))
                                if parent_dir:
                                    os.makedirs(parent_dir, exist_ok=True)
                                
                                # Make sure it has .mp3 extension
                                if not output_dir.lower().endswith(".mp3"):
                                    local_mp3 = output_dir + ".mp3"
                                else:
                                    local_mp3 = output_dir

                        with open(local_mp3, "wb") as mf:
                            mf.write(download_resp.content)
                        print(f"[+] SUCCESS: Downloaded audio to {os.path.abspath(local_mp3)}")
                    else:
                        print(f"[!] Failed to download MP3. Status: {download_resp.status_code}")
                    return
                elif state == "FAILURE":
                    sys.stdout.write("]\n")
                    print(f"\n[!] Task failed. Error: {status_data.get('result')}")
                    return
                else:
                    sys.stdout.write(".")
                    sys.stdout.flush()
            else:
                pass
        except Exception as e:
            pass
            
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        
    print(f"\n[!] Error: Timeout after {MAX_WAIT} seconds.")

def main():
    parser = argparse.ArgumentParser(description="Convert PDF to Audio via TTS project pipeline")
    parser.add_argument("pdf", help="Path to the input PDF file")
    parser.add_argument("-o", "--output", help="Path, directory, or custom filename to save the final MP3 (defaults to current dir)", default=None)
    parser.add_argument("--skip-services", action="store_true", help="Skip starting services if they are already running")
    
    args = parser.parse_args()

    pdf_path = os.path.abspath(args.pdf)
    
    if not args.skip_services:
        if not start_services():
            print("[!] Could not start required services. Exiting.")
            sys.exit(1)
            
    try:
        process_pdf(pdf_path, args.output)
    except KeyboardInterrupt:
        print("\n[!] Process interrupted by user.")
        sys.exit(1)

if __name__ == "__main__":
    main()
