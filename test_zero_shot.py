import os
import logging
from tts_engine.generator import VietnameseTTS

# Bật log level INFO để kiểm tra Output
logging.basicConfig(level=logging.INFO)

def main():
    print("--- Khởi chạy Test Zero-Shot TTS ---")
    
    # 1. Tạo file audio mẫu giả lập (speaker prompt < 15s)
    prompt_path = "dummy_prompt.wav"
    with open(prompt_path, "wb") as f:
        # Ghi dummy RIFF WAVE header để làm giả file âm thanh
        f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xAC\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
        
    print(f"Đã tạo audio mẫu giả lập tại: {prompt_path}")

    # 2. Khởi tạo engine TTS
    print("Đang khởi tạo VietnameseTTS engine...")
    tts = VietnameseTTS(use_fp16=True)
    
    # 3. Gọi tính năng clone giọng hát và test cảm xúc
    text = "Trời ơi, làm ăn kiểu gì thế này? Lại chậm deadline nữa rồi!"
    output_file = "output_zero_shot.wav"
    
    print("\n--- Bắt đầu Clone ---")
    tts.synthesize_chunk(
        text=text,
        spk_prompt_path=prompt_path,
        output_filename=output_file,
        use_emo_text=True,
        emo_alpha=0.6,
        emo_vector=[0, 0, 0, 0, 0, 0, 0.45, 0]
    )
    
    # Xóa file mẫu giả lập sau khi gọi
    os.remove(prompt_path)
    
    # 4. Kiểm chứng đầu ra
    print("\n--- Kết Quả ---")
    if os.path.exists(output_file):
        size = os.path.getsize(output_file)
        print(f"[OK] File '{output_file}' đã được tạo thành công! (Size: {size} bytes)")
    else:
        print(f"[FAILED] Lỗi: Không sinh ra được file '{output_file}'.")

if __name__ == "__main__":
    main()
