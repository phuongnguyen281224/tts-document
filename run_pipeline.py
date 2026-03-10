import subprocess
import time
import requests
import os
import re

def kill_port_8000():
    try:
        output = subprocess.check_output(["netstat", "-ano"], text=True)
        for line in output.splitlines():
            if ":8000" in line and "LISTENING" in line:
                parts = re.split(r'\s+', line.strip())
                if len(parts) >= 5:
                    pid = parts[4]
                    print(f"Killing process {pid} on port 8000...")
                    subprocess.run(["taskkill", "/F", "/PID", pid, "/T"], capture_output=True)
    except Exception as e:
        print(f"Error checking port 8000: {e}")

def kill_others():
    my_pid = os.getpid()
    try:
        output = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq celery.exe", "/FO", "CSV", "/NH"], text=True)
        for line in output.splitlines():
            if not line.strip(): continue
            parts = line.split('","')
            pid = parts[1].strip('"')
            print(f"Killing celery {pid}...")
            subprocess.run(["taskkill", "/F", "/PID", pid, "/T"], capture_output=True)
    except:
        pass

def start_services():
    print("Cleaning up port 8000 and celery...")
    kill_port_8000()
    kill_others()
    time.sleep(2)

    print("Starting FastAPI...")
    with open("fastapi_server.log", "w") as out, open("fastapi_server_error.log", "w") as err:
        subprocess.Popen([r".\venv\Scripts\python.exe", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
                         stdout=out, stderr=err)
    
    print("Starting Celery...")
    with open("celery_worker.log", "w") as out, open("celery_worker_error.log", "w") as err:
        subprocess.Popen([r".\venv\Scripts\celery.exe", "-A", "worker.celery_app", "worker", "--loglevel=info", "--pool=solo"],
                         stdout=out, stderr=err)

    print("Waiting for FastAPI to be ready...")
    for i in range(20):
        try:
            resp = requests.get("http://localhost:8000/docs", timeout=1)
            if resp.status_code == 200:
                print("FastAPI is READY!")
                return True
        except:
            pass
        time.sleep(1)
        print(f"Waiting... {i+1}s")
    
    return False

if __name__ == "__main__":
    if start_services():
        print("Running test script...")
        subprocess.run([r".\venv\Scripts\python.exe", "-u", "tests/test_user_pdf.py"])
    else:
        print("FastAPI failed to start.")
