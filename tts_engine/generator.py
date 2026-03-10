import os
import logging
import asyncio

logger = logging.getLogger(__name__)

class VietnameseTTS:
    """
    Core engine for Vietnamese Text-To-Speech using Microsoft Edge TTS.
    Provides natural-sounding voices with high expressiveness.
    """
    
    def __init__(self, checkpoint_dir: str = None, config_path: str = None, use_fp16: bool = True):
        """
        Khởi tạo Edge TTS. Không cần load trọng số model vì chạy qua API.
        """
        self.voice = "vi-VN-HoaiMyNeural" # Giọng nữ tiếng Việt xuất sắc
        logger.info(f"Đã cấu hình Edge-TTS với voice: {self.voice}")

    async def _async_synthesize(self, text: str, output_filename: str):
        import edge_tts
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Add a small delay between requests to avoid rate limits
                await asyncio.sleep(0.5) 
                communicate = edge_tts.Communicate(text, self.voice)
                await communicate.save(output_filename)
                return # Success
            except Exception as e:
                logger.warning(f"Lỗi Edge-TTS (Thử lại {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Lỗi Edge-TTS thất bại hoàn toàn sau {max_retries} lần thử: {e}")
                    raise e
                await asyncio.sleep(2) # Wait longer before retrying

    def synthesize_chunk(self, text: str, spk_prompt_path: str, output_filename: str, use_emo_text: bool = True, emo_alpha: float = 0.6, emo_vector: list = None):
        """
        Sinh âm thanh cho một đoạn văn bản sử dụng Edge-TTS.
        Chạy sync wrapper cho luồng async của edge_tts.
        """
        logger.info(f"[Edge-TTS] Sinh âm: '{text[:30]}...' -> {output_filename}")
        
        try:
            # edge-tts yêu cầu chạy trong event loop
            asyncio.run(self._async_synthesize(text, output_filename))
            logger.debug(f"File âm thanh đã được lưu tại: {output_filename}")
            
        except Exception as e:
            logger.error(f"Suy luận TTS thất bại: {e}")
            raise e
