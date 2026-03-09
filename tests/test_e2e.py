import os
import time
import requests

API_BASE = "http://localhost:8000"
POLL_INTERVAL = 3
MAX_WAIT = 300

def main():
    print("--- [STAGE 5 Test] End-to-End PDF to MP3 ---")
    
    # 1. Prepare dummy PDF
    # In earlier tests there was `test_data` directory. Let's see if there's any pdf.
    pdf_path = "test_data/sample.pdf"
    if not os.path.exists(pdf_path):
        os.makedirs("test_data", exist_ok=True)
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.add_font("Arial", "", "C:\\Windows\\Fonts\\arial.ttf", uni=True)
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="Xin chào, đây là bài kiểm tra toàn diện quy trình tạo sách nói.", ln=1)
            pdf.cell(200, 10, txt="Hệ thống sẽ chuyển hóa đoạn văn bản ngắn này thành audio.", ln=2)
            pdf.cell(200, 10, txt="Sau đó, các file chunks sẽ được pydub ghép lại qua crossfade.", ln=3)
            pdf.cell(200, 10, txt="Và cuối cùng xuất ra kết quả là một tệp MP3 duy nhất.", ln=4)
            pdf.output(pdf_path)
            print(f"[0] Đã tạo file PDF mẫu: {pdf_path}")
        except Exception as e:
            print(f"[0] Lỗi tạo file PDF mẫu: {e}. Cần nạp file mẫu thủ công vào test_data/sample.pdf!")
            return

    # 2. Upload PDF
    print(f"\n[1] Đang upload {pdf_path} lên API...")
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            response = requests.post(f"{API_BASE}/upload-pdf/", files=files)
        
        if response.status_code != 200:
            print(f"[LỖI] Upload thất bại: {response.text}")
            return
            
        task_data = response.json()
        task_id = task_data.get("task_id")
        print(f"    -> Nhận được Task ID: {task_id}")
    except Exception as e:
        print(f"[LỖI] Lỗi kết nối API: {e}. Vui lòng kiểm tra Uvicorn!")
        return
    
    # 3. Poll for status
    print("\n[2] Chờ hệ thống Celery xử lý (ext -> nlp -> tts -> merge mp3)...")
    elapsed = 0
    while elapsed < MAX_WAIT:
        try:
            status_resp = requests.get(f"{API_BASE}/task-status/{task_id}")
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                state = status_data.get("status")
                if state == "SUCCESS":
                    result = status_data.get("result", {})
                    print("\n[OK] Task hoàn tất thành công!")
                    mp3_path_internal = result.get("final_mp3_path")
                    print(f"     -> File MP3 đã tạo trên server: {mp3_path_internal}")
                    
                    # 4. Download MP3
                    print("\n[3] Tiến hành tải file MP3 thông qua endpoint GET /download-audio/{task_id}")
                    download_resp = requests.get(f"{API_BASE}/download-audio/{task_id}")
                    if download_resp.status_code == 200:
                        local_mp3 = f"downloaded_{task_id}.mp3"
                        with open(local_mp3, "wb") as mf:
                            mf.write(download_resp.content)
                        print(f"[OK] Tải xuống thành công! Đã lưu tại: {local_mp3}")
                    else:
                        print(f"[LỖI] Không thể tải file MP3. Status: {download_resp.status_code}, Detail: {download_resp.text}")
                    return
                elif state == "FAILURE":
                    print(f"\n[FAIL] Task thất bại. Result: {status_data.get('result')}")
                    return
                else:
                    print(f"    [{elapsed:>3}s] Tình trạng task: {state}...")
            else:
                print(f"    [{elapsed:>3}s] Lỗi fetch status: {status_resp.status_code}")
        except Exception as e:
            print(f"    [{elapsed:>3}s] Lỗi kết nối khi poll: {e}")
            
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        
    print(f"\n[FAIL] Timeout sau {MAX_WAIT} giây.")

if __name__ == "__main__":
    main()
