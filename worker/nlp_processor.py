"""
NLP Processor — Vietnamese Text Normalization & Clause-Level Chunking
======================================================================
Giai đoạn 2.5: Xử lý ngôn ngữ tự nhiên tiếng Việt sau khi trích xuất PDF.
"""

import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Số câu tối đa trong một chunk — căn chỉnh cho TTS 10–15 giây / chunk
CHUNK_MAX_SENTENCES: int = 4

# Phần trăm overlap giữa các chunk liền kề (clause-level)
CHUNK_OVERLAP_PERCENT: int = 25

# Regex nhận diện page-marker headers
_PAGE_MARKER_RE = re.compile(
    r'^---\s*Page\s+\d+(?:\s+\[OCR\])?\s*---\s*$',
    flags=re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

def _load_normalizer():
    try:
        from soe_vinorm import SoeNormalizer
        return SoeNormalizer()
    except ImportError as exc:
        raise ImportError("soe-vinorm chưa được cài đặt.") from exc


def _load_chunker():
    try:
        from chunklet import DocumentChunker
        return DocumentChunker()
    except ImportError as exc:
        raise ImportError("chunklet-py chưa được cài đặt.") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_vietnamese_text(text: str) -> str:
    """
    Chuẩn hóa văn bản tiếng Việt cho TTS bằng thư viện soe-vinorm.
    """
    if not text or not text.strip():
        return text

    logger.info("[NLP] Bắt đầu chuẩn hóa văn bản (soe-vinorm)...")

    # Loại bỏ page markers
    text = _PAGE_MARKER_RE.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    try:
        normalizer = _load_normalizer()
        normalized = normalizer.normalize(text)
    except Exception as e:
        logger.warning(f"[NLP] Lỗi khi chuẩn hóa: {e!r}")
        normalized = text

    return normalized


def chunk_normalized_text(text: str) -> List[Dict[str, Any]]:
    """
    Phân mảnh văn bản thành các chunk có clause-level overlap.
    """
    if not text or not text.strip():
        return []

    logger.info(f"[NLP] Bắt đầu phân mảnh (max_sentences={CHUNK_MAX_SENTENCES})...")

    try:
        chunker = _load_chunker()
        # chunklet 2.2.0 API: .chunk_text(text, ...)
        # Trả về list[Box] với các key: content, metadata
        raw_chunks = chunker.chunk_text(
            text, 
            lang='vi', 
            max_sentences=CHUNK_MAX_SENTENCES, 
            overlap_percent=CHUNK_OVERLAP_PERCENT
        )

        if not raw_chunks:
            logger.warning("[NLP] chunklet trả về 0 chunks — dùng fallback.")
            raw_chunks = _fallback_chunk(text)

    except Exception as e:
        logger.error(f"[NLP] Lỗi khi chunking: {e!r} — dùng fallback.")
        raw_chunks = _fallback_chunk(text)

    # Đóng gói kết quả
    result: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(raw_chunks):
        # Xuất phát từ chunklet: chunk là Box với key 'content'
        # Xuất phát từ fallback: chunk là string
        if hasattr(chunk, "content"):
            chunk_text = chunk.content
        elif isinstance(chunk, dict):
            chunk_text = chunk.get("content", str(chunk))
        else:
            chunk_text = str(chunk)

        chunk_text = chunk_text.strip()
        if not chunk_text:
            continue

        result.append({
            "index":      idx,
            "text":       chunk_text,
            "char_count": len(chunk_text),
            "word_count": len(chunk_text.split()),
        })

    return result


def _fallback_chunk(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.?!…])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences: return [text] if text.strip() else []

    chunks: List[str] = []
    step = max(1, CHUNK_MAX_SENTENCES - 1)
    i = 0
    while i < len(sentences):
        group = sentences[i : i + CHUNK_MAX_SENTENCES]
        chunks.append(' '.join(group))
        i += step
    return chunks


def run_nlp_pipeline(raw_text: str) -> Dict[str, Any]:
    normalized = normalize_vietnamese_text(raw_text)
    chunks     = chunk_normalized_text(normalized)
    return {
        "normalized_text": normalized,
        "chunks":          chunks,
        "chunk_count":     len(chunks),
    }
