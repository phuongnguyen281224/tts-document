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
_custom_replacements = {} # {word: pronunciation}

def _get_normalizer():
    """Khởi tạo và trả về instance của VietnameseNormalizer theo mô hình singleton lỏng."""
    global _normalizer
    if _normalizer is None:
        try:
            from vietnormalizer import VietnameseNormalizer
            
            # Khởi tạo đường dẫn tuyệt đối cho các từ điển tùy chỉnh
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            acronyms_csv = os.path.join(base_dir, "dictionaries", "custom_acronyms.csv")
            loanwords_csv = os.path.join(base_dir, "dictionaries", "custom_loanwords.csv")
            
            logger.info(f"Đang kiểm tra từ điển: {acronyms_csv} (Exists: {os.path.exists(acronyms_csv)})")
            logger.info(f"Đang kiểm tra từ điển: {loanwords_csv} (Exists: {os.path.exists(loanwords_csv)})")
            
            _normalizer = VietnameseNormalizer(
                acronyms_path=acronyms_csv if os.path.exists(acronyms_csv) else None,
                non_vietnamese_words_path=loanwords_csv if os.path.exists(loanwords_csv) else None
            )
            
            # Manual backup: Load CSV into memory for forced replacement
            import csv
            for path in [acronyms_csv, loanwords_csv]:
                if os.path.exists(path):
                    try:
                        with open(path, mode='r', encoding='utf-8-sig') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                word = row.get('word', '').strip()
                                pron = row.get('vietnamese_pronunciation', '').strip()
                                if word and pron:
                                    _custom_replacements[word] = pron
                    except Exception as e:
                        logger.error(f"Lỗi khi đọc CSV {path}: {e}")
            
            logger.info(f"Đã khởi tạo VietnameseNormalizer. Manual replacements loaded: {len(_custom_replacements)}")
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
        # 1. Manual Replacement (Pre-normalization)
        # Sort keys by length descending to avoid partial matches (e.g., "MLOps" before "ML")
        sorted_keys = sorted(_custom_replacements.keys(), key=len, reverse=True)
        for word in sorted_keys:
            # Case-insensitive replacement with word boundaries to avoid partial matches (e.g. AI in online)
            # Use raw string for pattern to handle \b correctly
            pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
            text = pattern.sub(_custom_replacements[word], text)

        norm = _get_normalizer()
        normalized = norm.normalize(text)
        return normalized
    except Exception as e:
        logger.error(f"Lỗi khi chuẩn hóa văn bản bằng vietnormalizer: {e}")
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
        # 3. overlap_percent = 0: Tắt overlap để tránh bị lặp lại audio ở bản thành phẩm.
        # Hàm đếm token đơn giản: đếm số từ cách nhau bằng khoảng trắng.
        def simple_word_counter(t: str) -> int:
            return len(t.split())
            
        raw_chunks = chunker.chunk_text(
            text,
            lang='vi',
            max_sentences=3,
            max_tokens=80,
            overlap_percent=0,
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
    và xóa bỏ các trích dẫn nguồn (citations) thường gặp khi trích xuất PDF.
    """
    if not text or not isinstance(text, str):
        return ""
        
    # 1. Nối lại các từ bị ngắt dòng do giới hạn lề: "chuyên-\nnghiệp" -> "chuyên nghiệp"
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    
    # 2. Xóa các ký tự zero-width (zero-width space, non-joiner, etc.)
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)

    # 3. Xóa trích dẫn trong ngoặc vuông: [1], [1, 2], [1-5]
    text = re.sub(r'\[\d+(?:[,\-\s]+\d+)*\]', '', text)
    
    # 4. Xóa trích dẫn trong ngoặc đơn: (1), (12) 
    # Thường đứng sau một từ hoặc cuối câu
    text = re.sub(r'\(\d+\)', '', text)

    # 5. Xóa ký tự superscript Unicode (¹, ², ³, ...)
    text = re.sub(r'[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ]', '', text)

    # 6. Xóa số dính liền sau dấu câu: "thành.2" -> "thành.", "triển, 3" -> "triển,"
    # Dùng negative lookbehind (?<!\d) để tránh xóa phần thập phân của số (như 3.14)
    text = re.sub(r'(?<!\d)([.,?!:;])\s*\d+\b', r'\1', text)

    # 7. Xóa số dính liền cuối từ: "nhân loại5" -> "nhân loại"
    # Chỉ áp dụng cho từ có ít nhất 2 chữ cái để tránh xóa các mã/ký hiệu đặc biệt (A1, B2)
    # [A-ZÀ-Ỹ] dùng để bắt các ký tự tiếng Việt có dấu
    text = re.sub(r'\b([A-Za-zÀ-Ỹà-ỹ]{2,})\d+\b', r'\1', text)
    
    # 8. Chuyển đổi khoảng trắng (newlines quá nhiều) thành tối đa 2 newlines (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 9. Gom các khoảng trắng ngang thừa (bao gồm tab) thành 1 space duy nhất
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
    
    # Bước 2: Phân rã văn bản thông minh (Chunking) khi văn bản còn giữ dấu câu và viết hoa
    chunks = chunk_normalized_text(cleaned)
    logger.info(f"Đã phân rã thành {len(chunks)} chunks cơ bản.")
    
    # Bước 3: Chuẩn hóa từng chunk sau khi đã cắt
    final_output = []
    for c in chunks:
        norm_text = normalize_vietnamese_text(c["text"])
        if norm_text:
            final_output.append(norm_text)
    
    logger.info(f"Orchestrator hoàn tất: Tạo ra {len(final_output)} luồng phát âm.")
    return final_output
