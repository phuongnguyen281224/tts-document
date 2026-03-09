import requests
import time
import os
import sqlite3

BASE_URL = "http://localhost:8000"
DB_PATH = "tts_jobs.db"

def check_db_record(task_id):
    """
    Connect to SQLite directly to verify the raw record.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT task_id, filename, status, created_at, finished_at FROM audio_jobs WHERE task_id = ?", (task_id,))
        record = cursor.fetchone()
        conn.close()
        
        if record:
            print(f"   [DB] Raw Record -> ID: {record[0]}, File: {record[1]}, Status: {record[2]}, Created: {record[3]}, Finished: {record[4]}")
            return record
        else:
            print("   [DB] Không tìm thấy bản ghi trong SQLite!")
            return None
    except Exception as e:
        print(f"   [DB LỖI] {e}")
        return None

def test_db_flow():
    print("--- Bắt đầu kiểm thử lưu trữ Metadata vào Database ---")
    
    # 1. Tạo file PDF tạm
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n>>\nendobj\n"
    test_pdf_path = "db_test.pdf"
    with open(test_pdf_path, "wb") as f:
        f.write(pdf_content)

    task_id = None
    try:
        # 2. Gửi file lên
        with open(test_pdf_path, "rb") as f:
            files = {"file": ("db_test.pdf", f, "application/pdf")}
            print("\n>> Gửi file PDF giả lên server...")
            upload_res = requests.post(f"{BASE_URL}/upload-pdf/", files=files)
            
            if upload_res.status_code != 200:
                print(f"[LỖI] Upload thất bại. Status: {upload_res.status_code}")
                return

            task_id = upload_res.json().get("task_id")
            print(f"[OK] Nhận task_id: {task_id}")

        # 3. Kiểm tra DB ngay lập tức (Kỳ vọng: PENDING)
        print("\n>> Kiểm tra Database lúc tác vụ vừa tạo (Kỳ vọng: PENDING)...")
        record = check_db_record(task_id)
        if record and record[2] == "PENDING":
             print("[THÀNH CÔNG] Dữ liệu khởi tạo chuẩn xác.")
        else:
             print("[CẢNH BÁO] Sai lệnh khi tạo DB.")

        # 4. Chờ Worker xử lý (có Sleep 10s trong code dummy hiện tại của bạn)
        print("\n>> Đợi Celery Worker hoàn thành task (dự kiến 10s)...")
        for i in range(15):
             time.sleep(1)
             # Poll through Redis check
             status_res = requests.get(f"{BASE_URL}/task-status/{task_id}")
             current_state = status_res.json().get("status")
             if current_state == "SUCCESS":
                  break
             print(f"   Celery Queue Status: {current_state}...")

        # 5. Kiểm tra DB Lần cuối (Kỳ vọng: SUCCESS hoặc FAILURE, finished_at có dữ liệu)
        print("\n>> Kiểm tra lại Database sau khi task xong (Kỳ vọng: SUCCESS/FAILURE)...")
        time.sleep(1) # Give hook a moment to commit
        final_record = check_db_record(task_id)
        
        if final_record and final_record[2] in ["SUCCESS", "FAILURE"] and final_record[4] is not None:
             print(f"\n🎉 [THÀNH CÔNG] Trạng thái cuối ({final_record[2]}) và Thời điểm kết thúc đã được Celery cập nhật vào DB!")
        else:
             print("\n❌ [THẤT BẠI] DB không được Celery cập nhật đúng.")
             
    finally:
        if os.path.exists(test_pdf_path):
             os.remove(test_pdf_path)

if __name__ == "__main__":
    test_db_flow()
