import os
import time
from worker.tasks import process_raw_text_task

POLL_INTERVAL = 2
MAX_WAIT = 180

def main():
    print("--- [STAGE 4 Test] Khởi chạy TTS Hệ Thống Phân Tán ---")
    
    # 1. Đoạn text dài giả lập (~ 5-10 chunks tùy thuật toán)
    long_text = (
        "Xin chào, đây là một bài kiểm tra tổng hợp cho hệ thống chuyển đổi văn bản thành giọng nói. "
        "Chúng ta đang thử nghiệm khả năng xử lý dị bộ của Celery khi kết hợp với mô hình trí tuệ nhân tạo. "
        "Khác với việc thực thi đồng bộ, mô hình kiến trúc phân tán này giúp bảo vệ ứng dụng khỏi bị đơ "
        "hoặc quá tải khi có quá nhiều người truy cập cùng một lúc. Ngoài ra, việc chia nhỏ văn bản "
        "thành các đoạn hội thoại độc lập (chunking) sẽ giúp quá trình suy luận TTS trở nên mượt mà hơn. "
        "Mỗi chunk sẽ được xử lý riêng biệt để tiết kiệm vram đáng kể cho hệ thống gpu bên dưới. "
        "Nếu vòng lặp hoạt động chính xác, chúng ta sẽ thấy hệ thống tự động giải phóng rác và cache "
        "sau mỗi lượt. Cụ thể, các file âm thanh sẽ được đánh số theo tuần tự từ chunk không đến N. "
        "Bạn hãy kiểm tra xem quá trình này có làm đứng máy hay không, và kết quả đầu ra âm thanh "
        "có giữ nguyên được cảm xúc như đã thiết lập qua emo vector hay không nhé. Cảm ơn các bạn."
    )
    
    # 2. Tạo prompt audio giả lập
    prompt_path = "stage4_dummy_prompt.wav"
    with open(prompt_path, "wb") as f:
        f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xAC\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    print(f"[1] Đã tạo file mồi (speaker prompt): {prompt_path}")
    
    # 3. Đẩy Task vào Celery
    print(f"[2] Đẩy đoạn văn bản {len(long_text)} ký tự vào Celery worker...")
    task = process_raw_text_task.delay(long_text, prompt_path)
    print(f"    -> Celery Task ID: {task.id}")
    print(f"    -> Hãy mở terminal phụ chạy Celery worker để THEO DÕI NGAY các bản logs VRAM.\n")
    
    # 4. Polling kết quả
    print("[3] Chờ đợi Celery worker xử lý...")
    elapsed = 0
    while elapsed < MAX_WAIT:
        if task.ready():
            if task.successful():
                result = task.result
                print(f"\n[OK] Task hoàn tất thành công!")
                audio_files = result.get('audio_files', [])
                print(f"     Số lượng file audio (chunks) đã sinh: {len(audio_files)}")
                for f_idx, f_name in enumerate(audio_files):
                    print(f"      - {os.path.basename(f_name)}")
                
                # Cleanup
                if os.path.exists(prompt_path):
                    os.remove(prompt_path)
                return
            else:
                print(f"\n[FAIL] Task thất bại: {task.result}")
                return
        
        print(f"    [{elapsed:>3}s] Tình trạng task: {task.status}...")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        
    print(f"\n[FAIL] Timeout sau {MAX_WAIT} giây.")

if __name__ == "__main__":
    main()
