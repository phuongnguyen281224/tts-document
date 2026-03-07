"""
NLP Pipeline Module (Phase 3)
-----------------------------
Sử dụng thư viện `vietnormalizer` (zero-dependency) để chuẩn hóa văn bản tiếng Việt
đặc biệt tối ưu hóa cho Text-to-Speech (TTS).
"""

import logging
import re
import os

logger = logging.getLogger(__name__)

# Global instances để chia sẻ trạng thái nếu cần
_normalizer = None
_chunker = None

def _get_normalizer():
    """Khởi tạo và trả về instance của VietnameseNormalizer theo mô hình singleton lỏng."""
    global _normalizer
    if _normalizer is None:
        try:
            from vietnormalizer import VietnameseNormalizer
            
            # Khởi tạo đường dẫn tuyệt đối cho các từ điển tùy chỉnh
            base_dir = os.path.dirname(os.path.dirname(__file__))
            acronyms_csv = os.path.join(base_dir, "dictionaries", "custom_acronyms.csv")
            loanwords_csv = os.path.join(base_dir, "dictionaries", "custom_loanwords.csv")
            
            _normalizer = VietnameseNormalizer(
                acronyms_path=acronyms_csv if os.path.exists(acronyms_csv) else None,
                non_vietnamese_words_path=loanwords_csv if os.path.exists(loanwords_csv) else None
            )
            logger.info("Đã khởi tạo VietnameseNormalizer với Custom Dictionaries.")
        except ImportError as e:
            logger.error("Thư viện 'vietnormalizer' chưa được cài đặt. Chạy `pip install vietnormalizer`.")
            raise e
    return _normalizer


def normalize_vietnamese_text(text: str) -> str:
    """
    Chuẩn hóa chuỗi văn bản tiếng Việt chứa số nguyên, số thập phân, ngày tháng,
    tiền tệ (VND, USD) và tỷ lệ phần trăm thành chữ.
    
    Args:
        text: Văn bản thô đầu vào.
    Returns:
        Văn bản đã qua xử lý, có thể phát âm tiếng Việt.
    """
    if not text or not isinstance(text, str):
        return text
        
    # Tiền xử lý: các trường hợp vietnormalizer có thể chưa cover hết
    # 1. Định dạng giờ phút tắt: "2h30m" -> "2 giờ 30 phút"
    text = re.sub(r'(\d+)h(?:(\d+)m|(\d+))?', r'\1 giờ \2\3 phút', text)
    text = text.replace("  ", " ").replace(" phút phút", " phút") # Dọn dẹp spacing
    
    try:
        norm = _get_normalizer()
        # vietnormalizer có hàm normalize để xử lý toàn bộ
        normalized = norm.normalize(text)
        return normalized
    except Exception as e:
        logger.error(f"Lỗi khi chuẩn hóa văn bản bằng vietnormalizer: {e}")
        # Log lỗi nhưng vẫn trả về text gốc/đã làm sạch nếu có lỗi nội bộ
        return text

def _get_chunker():
    """Khởi tạo và trả về instance của DocumentChunker."""
    global _chunker
    if _chunker is None:
        try:
            from chunklet import DocumentChunker
            _chunker = DocumentChunker()
            logger.info("Đã khởi tạo thư viện chunklet DocumentChunker.")
        except ImportError as e:
            logger.error("Thư viện 'chunklet' chưa được cài đặt. Chạy `pip install chunklet`.")
            raise e
    return _chunker

def chunk_normalized_text(text: str) -> list[dict]:
    """
    Cắt nhỏ văn bản đã chuẩn hóa thành các đoạn (chunks) phù hợp cho TTS (~10-15s).
    Sử dụng chế độ hybrid (kết hợp max_sentences và max_tokens) cùng với
    clause-level overlap để đảm bảo tính liên tục của ngữ cảnh.
    
    Args:
        text: Văn bản đã được chuẩn hóa.
    Returns:
        List các dictionary chứa thông tin chunk.
    """
    if not text or not isinstance(text, str):
        return []
        
    try:
        chunker = _get_chunker()
        
        # Cấu hình Hybrid Chunking cho TTS:
        # 1. max_sentences = 3: Giới hạn theo câu để giữ trọn vẹn ý nghĩa.
        # 2. max_tokens = 80: ~150-250 ký tự, tương đương 10-15 giây audio.
        # 3. overlap_percent = 25: Clause-level overlap (lặp lại 25% nội dung để nối mạch ngữ cảnh).
        # Hàm đếm token đơn giản: đếm số từ cách nhau bằng khoảng trắng.
        def simple_word_counter(t: str) -> int:
            return len(t.split())
            
        raw_chunks = chunker.chunk_text(
            text,
            lang='vi',
            max_sentences=3,
            max_tokens=80,
            overlap_percent=25,
            token_counter=simple_word_counter
        )
        
        result = []
        for idx, chunk in enumerate(raw_chunks):
            # Tuỳ theo version của chunklet, nội dung chunk có thể nằm trong 'content' hoặc 'text'
            if hasattr(chunk, "content"):
                chunk_text = chunk.content
            elif isinstance(chunk, dict):
                chunk_text = chunk.get("content", str(chunk))
            else:
                chunk_text = str(chunk)
                
            chunk_text = chunk_text.strip()
            if chunk_text:
                result.append({
                    "index": idx,
                    "text": chunk_text,
                    "char_count": len(chunk_text),
                    "word_count": len(chunk_text.split())
                })
                
        return result
    except Exception as e:
        logger.error(f"Lỗi khi phân mảnh văn bản bằng chunklet: {e}")
        # Fallback an toàn nếu thuật toán lỗi: trả về toàn bộ text như 1 chunk duy nhất
        return [{
            "index": 0,
            "text": text.strip(),
            "char_count": len(text.strip()),
            "word_count": len(text.strip().split())
        }]

def clean_raw_text(text: str) -> str:
    """
    Tiền xử lý văn bản thô: Dọn dẹp ký tự rác, khoảng trắng thừa,
    và nối lại các từ bị ngắt dòng có dấu gạch ngang (thường gặp khi trích xuất PDF).
    """
    if not text or not isinstance(text, str):
        return ""
        
    # 1. Nối lại các từ bị ngắt dòng do giới hạn lề: "chuyên-\nnghiệp" -> "chuyên nghiệp"
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    
    # 2. Xóa các ký tự zero-width (zero-width space, non-joiner, etc.)
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    
    # 3. Chuyển đổi khoảng trắng (newlines quá nhiều) thành tối đa 2 newlines (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 4. Gom các khoảng trắng ngang thừa (bao gồm tab) thành 1 space duy nhất
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()

def process_text_for_tts(raw_text: str) -> list[str]:
    """
    Hàm tổng (Orchestrator Facade): Thực hiện toàn bộ luồng NLP cho TTS.
    Luồng: Dọn dẹp Regex -> Chuẩn hóa Vietnamese Normalizer -> Phân mảnh Chunklet.
    
    Args:
        raw_text: Văn bản thô mới trích xuất từ PDF hoặc Data Source.
    Returns:
        Danh sách các phân đoạn (string) đã sạch và sẵn sàng đi qua AI Voice.
    """
    logger.info(f"Bắt đầu Orchestrator: text đầu vào dài {len(raw_text)} ký tự.")
    
    # Bước 1: Dọn dẹp văn bản thô
    cleaned = clean_raw_text(raw_text)
    
    # Bước 2: Chuẩn hóa số nguyên, ngày tháng, tiếng nước ngoài -> Chữ Tiếng Việt
    normalized = normalize_vietnamese_text(cleaned)
    logger.info(f"Đã chuẩn hóa thành {len(normalized)} ký tự tiếng Việt.")
    
    # Bước 3: Phân rã văn bản thông minh (Hybrid mode với Clause-level overlap)
    chunks = chunk_normalized_text(normalized)
    
    # Bước 4: Trích xuất List[str]
    final_output = [c["text"] for c in chunks]
    
    logger.info(f"Orchestrator hoàn tất: Tạo ra {len(final_output)} luồng phát âm.")
    return final_output
