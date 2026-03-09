import requests
import time
import os

BASE_URL = "http://localhost:8000"

def test_task_cancellation():
    print("--- Bắt đầu kiểm thử: Hủy ngang tác vụ (Cancellation) ---")
    
    # Tạo một file PDF tạm hợp lệ để qua được security check
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n>>\nendobj\n"
    test_pdf_path = "cancel_test.pdf"
    with open(test_pdf_path, "wb") as f:
        f.write(pdf_content)

    task_id = None
    try:
        # 1. Gửi file lên để nhận task
        with open(test_pdf_path, "rb") as f:
            files = {"file": ("cancel_test.pdf", f, "application/pdf")}
            print("\n>> Gửi file PDF giả lên server...")
            upload_res = requests.post(f"{BASE_URL}/upload-pdf/", files=files)
            
            if upload_res.status_code != 200:
                print(f"[LỖI] Upload thất bại. Status: {upload_res.status_code}")
                print(upload_res.text)
                return

            task_id = upload_res.json().get("task_id")
            print(f"[OK] Nhận task_id: {task_id}")

        # 2. Đợi 2 giây để worker kịp nhặt task và bắt đầu xử lý
        print("\n>> Đợi 2 giây cho worker chạy...")
        time.sleep(2)
        
        # 3. Yêu cầu hủy task ngay khi nó đang chạy dở
        print("\n>> Gửi lệnh DELETE buộc worker ngắt process...")
        cancel_res = requests.delete(f"{BASE_URL}/tasks/{task_id}")
        
        if cancel_res.status_code == 200:
            print(f"[OK] Lệnh Hủy đã được gửi đi thành công: {cancel_res.json()['message']}")
        else:
            print(f"[LỖI] API báo lỗi khi hủy: {cancel_res.text}")
        
        # 4. Kiểm tra trạng thái task liên tục
        print("\n>> Kiểm tra trạng thái của task_id. Kỳ vọng: 'REVOKED'...")
        for i in range(5):
            time.sleep(1)
            status_res = requests.get(f"{BASE_URL}/task-status/{task_id}")
            if status_res.status_code == 200:
                body = status_res.json()
                print(f"Lần kiểm tra {i+1} - Trạng thái: {body.get('status')} - Thông điệp: {body.get('message', '')}")
                if body.get('status') == "REVOKED":
                    print("\n🎉 [THÀNH CÔNG] Task đã bị thu hồi/tiêu diệt theo đúng thiết kế.")
                    break
            else:
                 print(f"Lỗi truy vấn: {status_res.status_code}")
                 
    except Exception as e:
        print(f"[LỖI CÚ PHÁP] Lỗi trong lúc test: {str(e)}")
    finally:
        if os.path.exists(test_pdf_path):
             os.remove(test_pdf_path)

if __name__ == "__main__":
    test_task_cancellation()
