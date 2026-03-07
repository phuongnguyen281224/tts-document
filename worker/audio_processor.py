import os
import re
import shutil
from pydub import AudioSegment

def load_audio_chunks(folder_path: str) -> list[AudioSegment]:
    """
    Đọc tất cả các file .wav trong folder_path có tiền tố chunk_,
    sắp xếp đúng theo số nguyên trên tên file và tải thành mảng AudioSegment.
    
    VD: chunk_0.wav, chunk_1.wav, chunk_10.wav
    """
    audio_segments = []
    
    if not os.path.exists(folder_path):
        return audio_segments
        
    # Lấy ra tất cả các file wav hợp lệ
    wav_files = [f for f in os.listdir(folder_path) if f.startswith("chunk_") and f.endswith(".wav")]
    
    # Sắp xếp theo số nguyên
    def extract_chunk_number(filename: str) -> int:
        match = re.search(r'chunk_(\d+)\.wav$', filename)
        if match:
            return int(match.group(1))
        return -1
        
    wav_files.sort(key=extract_chunk_number)
    
    # Load file
    for f in wav_files:
        full_path = os.path.join(folder_path, f)
        segment = AudioSegment.from_file(full_path, format="wav")
        audio_segments.append(segment)
        
    return audio_segments

def concatenate_audio(audio_segments: list[AudioSegment], crossfade_ms: int = 50) -> AudioSegment:
    """
    Nối danh sách các AudioSegment lại thành một đối tượng duy nhất.
    Sử dụng crossfade để làm mượt ranh giới, tránh lỗi click tĩnh điện.
    """
    if not audio_segments:
        return AudioSegment.empty()
        
    # Khởi tạo combined bằng phần tử đầu tiên
    combined = audio_segments[0]
    
    # Lặp qua các phần tử còn lại
    for next_chunk in audio_segments[1:]:
        # Lưu ý: AudioSegment là immutable nên phải gán lại
        combined = combined.append(next_chunk, crossfade=crossfade_ms)
        
    return combined

def export_and_cleanup(combined_audio: AudioSegment, output_mp3_path: str, temp_folder_path: str) -> bool:
    """
    Xuất đối tượng audio đã ghép nối ra MP3, sau đó dọn dẹp thư mục chứa file tạm (chunks).
    Trả về True nếu quy trình hoàn tất thành công.
    """
    if combined_audio is None or len(combined_audio) == 0:
        print("[AudioProcessor] Cảnh báo: File âm thanh trống. Không tải xuất.")
        return False
        
    try:
        # Bước 1: Export MP3
        combined_audio.export(output_mp3_path, format="mp3")
        
        # Bước 2: Dọn dẹp thư mục tệp tạm (chứa chunks)
        if os.path.exists(temp_folder_path):
            shutil.rmtree(temp_folder_path, ignore_errors=True)
            
        return True
    except Exception as e:
        print(f"[AudioProcessor] Lỗi export MP3 và Cleanup: {e}")
        return False

