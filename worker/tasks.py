import os
import json
import gc
import torch
from pydub import AudioSegment
from worker.celery_app import celery_app
from worker.audio_processor import concatenate_audio, export_and_cleanup
from pdf_parser.extractor import extract_text_from_pdf
from worker.nlp_pipeline import process_text_for_tts
from tts_engine.generator import VietnameseTTS

# Directory where processed text and chunk files will be saved.
# Named by task_id for easy lookup in Phase 3.
OUTPUT_DIR = "temp_outputs"
COMPLETED_DIR = "completed_audios"

# Global TTS Engine cache instance. Lazily instantiating for VRAM reuse between task jobs.
_tts_engine = None

def get_tts_engine():
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = VietnameseTTS(use_fp16=True)
    return _tts_engine

@celery_app.task(bind=True, name="process_pdf")
def process_pdf_task(self, file_path: str, prompt_path: str = None):
    """
    Task xử lý PDF qua toàn bộ pipeline:
      1. Trích xuất văn bản  (PyMuPDF + OCR fallback)
      2. Chuẩn hóa tiếng Việt (soe-vinorm)
      3. Phân mảnh chunk      (chunklet-py, clause-level overlap)
      4. Sinh Audio (TTS) với IndexTTS2, VRAM GC, FP16
      5. Lưu kết quả ra disk  ({task_id}.txt  và  {task_id}_chunks.json) cùng các file .wav
    """
    task_id = self.request.id
    print(f"[{task_id}] === BƯỚC 1: Bắt đầu trích xuất PDF: {file_path}", flush=True)

    try:
        # ------------------------------------------------------------------ #
        # Bước 1 — Trích xuất văn bản thô từ PDF
        # ------------------------------------------------------------------ #
        extracted_text = extract_text_from_pdf(file_path)
        char_count = len(extracted_text)
        print(f"[{task_id}] Trích xuất hoàn tất. Ký tự: {char_count}", flush=True)

        # ------------------------------------------------------------------ #
        # Bước 2 & 3 — NLP: Chuẩn hóa tiếng Việt + Phân mảnh chunk
        # ------------------------------------------------------------------ #
        print(f"[{task_id}] === BƯỚC 2–3: Chạy NLP pipeline (Dọn dẹp → Normalize → Chunk)...", flush=True)
        
        chunks = process_text_for_tts(extracted_text)
        chunk_count = len(chunks)

        print(f"[{task_id}] NLP hoàn tất. Số chunks: {chunk_count}", flush=True)

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # ------------------------------------------------------------------ #
        # Bước 4 — TTS Sinh Audio (IndexTTS2)
        # ------------------------------------------------------------------ #
        print(f"[{task_id}] === BƯỚC 4: Bắt đầu sinh âm thanh qua IndexTTS2 Engine...", flush=True)
        tts = get_tts_engine()
        
        # Audio test mồi zero-shot (Cần file dummy mồi dưới 15 giây lưu sẵn)
        if prompt_path and os.path.exists(prompt_path):
            spk_prompt = prompt_path
        else:
            spk_prompt = os.path.join(OUTPUT_DIR, "dummy_spk_prompt.wav")
            if not os.path.exists(spk_prompt):
                with open(spk_prompt, "wb") as f:
                    f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xAC\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
        
        audio_files = []
        for i, chunk_text in enumerate(chunks):
            # Lưu file theo định dạng {task_id}_chunk_{0:04d}.wav để bảo đảm sequence
            chunk_audio_path = os.path.join(OUTPUT_DIR, f"{task_id}_chunk_{i:04d}.wav")
            print(f"[{task_id}] Đang sinh audio cho chunk {i+1}/{chunk_count}...", flush=True)
            
            try:
                # Khởi chạy TTS process. `use_emo_text=True` để LLM tự phân tích emotion.
                tts.synthesize_chunk(
                    text=chunk_text,
                    spk_prompt_path=spk_prompt,
                    output_filename=chunk_audio_path,
                    use_emo_text=True,    # Mặc định LLM đoán mảng
                    emo_alpha=0.6         # Mức độ khuếch đại tự nhiên nhất
                )
            except Exception as e:
                print(f"[{task_id}] Sinh âm thất bại cho chunk {i+1}: {e}", flush=True)
                # Fail gracefully và tiếp tục với các đoạn sau ngắt quãng
                continue
                
            audio_files.append(os.path.abspath(chunk_audio_path))
            print(f"[{task_id}] Chunk {i+1} xong -> {chunk_audio_path}", flush=True)
            
            # --- VRAM Management Constraint ---
            # Bắt buộc gọi GC sau mỗi vòng lặp tránh Python memory leak khi reference audio variable chưa giải phóng
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        # ------------------------------------------------------------------ #
        # Bước 5 — Nối các file audio với pydub và lưu thành MP3
        # ------------------------------------------------------------------ #
        print(f"[{task_id}] === BƯỚC 5: Đang nối {len(audio_files)} files âm thanh...", flush=True)
        final_mp3_path = None
        
        try:
            # 1. Load các file wav thành cấu trúc dữ liệu
            audio_segments = [AudioSegment.from_wav(f) for f in audio_files]
            
            # 2. Xử lý logic ghép nối có crossfade từ module
            combined_audio = concatenate_audio(audio_segments, crossfade_ms=50)
            
            # 3. Định hình thư mục lưu MP3 hoàn chỉnh
            os.makedirs(COMPLETED_DIR, exist_ok=True)
            final_mp3_path = os.path.join(COMPLETED_DIR, f"{task_id}_final.mp3")
            
            # 4. Xuất file MP3 và có thể làm sạch rác (tuy nhiên ta tự xóa file list bên dưới để tránh đụng độ multithread)
            # Hàm export_and_cleanup của module hỗ trợ xóa Temp Dir nhưng OUTPUT_DIR này chứa chung file của task khác
            combined_audio.export(final_mp3_path, format="mp3")
            print(f"[{task_id}] Hậu kỳ thành công! Đã lưu MP3 tại: {final_mp3_path}")
            
            # 5. Dọn dẹp chỉ định các file wav phân mảnh thuộc riêng task id này
            for f in audio_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception as ex:
                        print(f"[{task_id}] Không thể xóa file rác {f}: {ex}")
            print(f"[{task_id}] Đã xóa dọn dẹp {len(audio_files)} .wav file sau lưu hậu kỳ thành công.")
            
        except Exception as e:
            print(f"[{task_id}] Lỗi trong quá trình nối Audio Processing: {e}", flush=True)

        # ------------------------------------------------------------------ #
        # Bước 6 — Lưu kết quả chunk mapping ra disk
        # ------------------------------------------------------------------ #
        chunks_file_path = os.path.join(OUTPUT_DIR, f"{task_id}_chunks.json")
        output_metadata = {
            "chunks": chunks,
            "audio_files": audio_files,
            "final_mp3": final_mp3_path
        }
        
        with open(chunks_file_path, "w", encoding="utf-8") as f:
            json.dump(output_metadata, f, ensure_ascii=False, indent=2)

        abs_chunks_path = os.path.abspath(chunks_file_path)
        print(f"[{task_id}] Đã xử lý tất cả. Metadata -> {abs_chunks_path}", flush=True)

        return {
            "status":           "success",
            "task_id":          task_id,
            "source_pdf":       file_path,
            "chunks_file_path": abs_chunks_path,
            "audio_files":      audio_files,
            "final_mp3_path":   os.path.abspath(final_mp3_path) if final_mp3_path else None,
            "char_count_raw":   char_count,
            "chunk_count":      chunk_count,
        }

    except Exception as e:
        print(f"[{task_id}] LỖI: {e}", flush=True)
        return {
            "status":     "error",
            "task_id":    task_id,
            "source_pdf": file_path,
            "error":      str(e),
        }

@celery_app.task(bind=True, name="process_raw_text")
def process_raw_text_task(self, text: str, prompt_path: str = None):
    """
    Task xử lý văn bản thô qua NLP -> Sinh Audio, bỏ qua bước trích xuất PDF.
    """
    task_id = self.request.id
    print(f"[{task_id}] === BƯỚC 1: Xử lý Raw Text Task ===", flush=True)

    try:
        char_count = len(text)
        print(f"[{task_id}] Chiều dài VB: {char_count}", flush=True)

        print(f"[{task_id}] === BƯỚC 2–3: Chạy NLP pipeline...", flush=True)
        chunks = process_text_for_tts(text)
        chunk_count = len(chunks)
        print(f"[{task_id}] NLP hoàn tất. Số chunks: {chunk_count}", flush=True)

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        print(f"[{task_id}] === BƯỚC 4: Bắt đầu sinh âm thanh qua IndexTTS2 Engine...", flush=True)
        tts = get_tts_engine()
        
        if prompt_path and os.path.exists(prompt_path):
            spk_prompt = prompt_path
        else:
            spk_prompt = os.path.join(OUTPUT_DIR, "dummy_spk_prompt.wav")
            if not os.path.exists(spk_prompt):
                with open(spk_prompt, "wb") as f:
                    f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xAC\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
        
        audio_files = []
        for i, chunk_text in enumerate(chunks):
            chunk_audio_path = os.path.join(OUTPUT_DIR, f"{task_id}_chunk_{i:04d}.wav")
            print(f"[{task_id}] Đang sinh audio cho chunk {i+1}/{chunk_count}...", flush=True)
            try:
                tts.synthesize_chunk(
                    text=chunk_text,
                    spk_prompt_path=spk_prompt,
                    output_filename=chunk_audio_path,
                    use_emo_text=True,
                    emo_alpha=0.6
                )
            except Exception as e:
                print(f"[{task_id}] Sinh âm thất bại cho chunk {i+1}: {e}", flush=True)
                continue
            audio_files.append(os.path.abspath(chunk_audio_path))
            print(f"[{task_id}] Chunk {i+1} xong -> {chunk_audio_path}", flush=True)
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        # ------------------------------------------------------------------ #
        # Bước 5 — Nối các file audio với pydub và lưu thành MP3
        # ------------------------------------------------------------------ #
        print(f"[{task_id}] === BƯỚC 5: Đang nối {len(audio_files)} files âm thanh...", flush=True)
        final_mp3_path = None
        
        try:
            # 1. Load các file wav thành cấu trúc dữ liệu
            audio_segments = [AudioSegment.from_wav(f) for f in audio_files]
            
            # 2. Xử lý logic ghép nối có crossfade từ module
            combined_audio = concatenate_audio(audio_segments, crossfade_ms=50)
            
            # 3. Định hình thư mục lưu MP3 hoàn chỉnh
            os.makedirs(COMPLETED_DIR, exist_ok=True)
            final_mp3_path = os.path.join(COMPLETED_DIR, f"{task_id}_final.mp3")
            
            # 4. Xuất file MP3
            combined_audio.export(final_mp3_path, format="mp3")
            print(f"[{task_id}] Hậu kỳ thành công! Đã lưu MP3 tại: {final_mp3_path}")
            
            # 5. Dọn dẹp chỉ định các file wav phân mảnh thuộc riêng task id này
            for f in audio_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception as ex:
                        print(f"[{task_id}] Không thể xóa file rác {f}: {ex}")
            print(f"[{task_id}] Đã xóa dọn dẹp {len(audio_files)} .wav file sau lưu hậu kỳ thành công.")
            
        except Exception as e:
            print(f"[{task_id}] Lỗi trong quá trình nối Audio Processing: {e}", flush=True)

        # ------------------------------------------------------------------ #
        # Bước 6 — Lưu kết quả chunk mapping ra disk
        # ------------------------------------------------------------------ #
        chunks_file_path = os.path.join(OUTPUT_DIR, f"{task_id}_chunks.json")
        output_metadata = {
            "chunks": chunks,
            "audio_files": audio_files,
            "final_mp3": final_mp3_path
        }
        with open(chunks_file_path, "w", encoding="utf-8") as f:
            json.dump(output_metadata, f, ensure_ascii=False, indent=2)

        abs_chunks_path = os.path.abspath(chunks_file_path)
        print(f"[{task_id}] Đã xử lý tất cả. Metadata -> {abs_chunks_path}", flush=True)

        return {
            "status":           "success",
            "task_id":          task_id,
            "chunks_file_path": abs_chunks_path,
            "audio_files":      audio_files,
            "final_mp3_path":   os.path.abspath(final_mp3_path) if final_mp3_path else None,
            "char_count_raw":   char_count,
            "chunk_count":      chunk_count,
        }

    except Exception as e:
        print(f"[{task_id}] LỖI: {e}", flush=True)
        return {
            "status":     "error",
            "task_id":    task_id,
            "error":      str(e),
        }
