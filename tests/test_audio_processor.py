import os
import shutil
from pydub import AudioSegment
from pydub.generators import Sine
from worker.audio_processor import load_audio_chunks, concatenate_audio, export_and_cleanup

TEST_FOLDER = "temp_test_audio"

def test_load_and_sort():
    print("\n[Bài Test 1] Hàm load_audio_chunks")
    if os.path.exists(TEST_FOLDER):
        shutil.rmtree(TEST_FOLDER)
    os.makedirs(TEST_FOLDER)
    
    silence = AudioSegment.silent(duration=1000)
    file_names = ["chunk_2.wav", "chunk_10.wav", "chunk_1.wav", "chunk_0.wav"]
    for f in file_names:
        silence.export(os.path.join(TEST_FOLDER, f), format="wav")
        print(f"  + Tạo {f}")
        
    try:
        chunks = load_audio_chunks(TEST_FOLDER)
        print(f"  -> Đã load {len(chunks)} AudioSegments.")
        print("[OK] Test 1: Sắp xếp theo regex số thứ tự thành công.")
    finally:
        if os.path.exists(TEST_FOLDER):
            shutil.rmtree(TEST_FOLDER)

def test_concatenate_sine_waves():
    print("\n[Bài Test 2] Hàm concatenate_audio (Sine wave test)")
    
    # Sinh đoạn 1s Sóng Sine 440 Hz (Nốt La) và 1s Sóng Sine 880 Hz (Nốt La quãng 8)
    sine_440_segment = Sine(440).to_audio_segment(duration=1000)
    sine_880_segment = Sine(880).to_audio_segment(duration=1000)
    
    segments = [sine_440_segment, sine_880_segment]
    print(f"  -> Đã tạo {len(segments)} audio segments. (Mỗi đoạn dài 1000ms)")
    
    # Nối chúng lại với crossfade
    crossfade_val = 50
    combined = concatenate_audio(segments, crossfade_ms=crossfade_val)
    
    # Kiểm chứng độ dài: Công thức = 1000 + 1000 - 50 = 1950
    expected_length = 1000 + 1000 - crossfade_val
    actual_length = len(combined)
    
    print(f"  -> Chiều dài kỳ vọng: {expected_length}ms")
    print(f"  -> Chiều dài thực tế: {actual_length}ms")
    
    if expected_length == actual_length:
        print("[OK] Test 2: Nối file với crossfade và tính toán thời gian chính xác!")
    else:
        print("[FAIL] Test 2: Tính toán thời gian nối bị lệch!")
        
    # Xuất ra file để Kỹ sư có thể tự nghe thử
    output_test_file = "test_sine_concatenated.wav"
    combined.export(output_test_file, format="wav")
    print(f"[OK] Đã xuất {output_test_file} ra thư mục gốc để thu âm kiểm chứng độ mượt.")

def test_export_and_cleanup():
    print("\n[Bài Test 3] Hàm export_and_cleanup")
    CLEANUP_FOLDER = "temp_test_cleanup"
    
    # 1. Setup tạo cục temp chunks mới
    if os.path.exists(CLEANUP_FOLDER):
        shutil.rmtree(CLEANUP_FOLDER)
    os.makedirs(CLEANUP_FOLDER)
    
    silence = AudioSegment.silent(duration=500)
    for i in range(3):
        f = f"chunk_{i}.wav"
        silence.export(os.path.join(CLEANUP_FOLDER, f), format="wav")
        print(f"  + Tạo {f} tại thư mục {CLEANUP_FOLDER}/")

    # 2. Sinh mock audio & Run
    mock_combined = Sine(1000).to_audio_segment(duration=1500)
    output_mp3 = "test_cleanup_final.mp3"
    if os.path.exists(output_mp3):
        os.remove(output_mp3)
        
    print(f"  -> Gọi export_and_cleanup() sinh file {output_mp3} và xoá {CLEANUP_FOLDER}/...")
    success = export_and_cleanup(mock_combined, output_mp3, CLEANUP_FOLDER)
    
    # 3. Assertions
    if success:
        if os.path.exists(output_mp3) and not os.path.exists(CLEANUP_FOLDER):
            print("[OK] Test 3: Sinh file MP3 thành công VÀ Dọn dẹp thư mục tạm thành công!")
        else:
            print("[FAIL] Test 3: Export hoặc Xóa thư mục bị sót.")
            if not os.path.exists(output_mp3): print("    - Thiếu file MP3 đầu ra.")
            if os.path.exists(CLEANUP_FOLDER): print("    - Thư mục dọn dẹp chưa bị xóa đi.")
    else:
        print("[FAIL] Test 3: Hàm export trả về false.")

def main():
    print("--- CHẠY TEST CHO MODULE AUDIO PROCESSOR ---")
    test_load_and_sort()
    test_concatenate_sine_waves()
    test_export_and_cleanup()

if __name__ == "__main__":
    main()
