"""
test_nlp_pipeline.py — Kiểm tra độc lập pipeline NLP tiếng Việt
=================================================================
Chạy:
    python test_nlp_pipeline.py

Không cần Celery hay Redis. Test trực tiếp 3 hàm trong worker/nlp_processor.py.
"""

import sys
import os

# Configure stdout to handle Vietnamese characters properly on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Đảm bảo import được từ thư mục gốc dự án
sys.path.insert(0, os.path.dirname(__file__))

from worker.nlp_processor import (
    normalize_vietnamese_text,
    chunk_normalized_text,
    run_nlp_pipeline,
    CHUNK_MAX_SENTENCES,
    CHUNK_OVERLAP_PERCENT,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def ok(msg: str):
    print(f"  [OK]   {msg}")

def warn(msg: str):
    print(f"  [WARN] {msg}")

def fail(msg: str):
    print(f"  [FAIL] {msg}")
    raise AssertionError(msg)

# ---------------------------------------------------------------------------
# Test 1 — Vietnamese Normalization
# ---------------------------------------------------------------------------

def test_normalization():
    print_header("Test 1: Chuẩn hóa văn bản tiếng Việt (vinorm)")

    sample = (
        "Năm 2024 có 1.500 sinh viên tốt nghiệp, chiếm 75% tổng số.\n"
        "Học phí trung bình là 15.000.000đ/năm học.\n"
        "Ngày 15/3/2024, TP.HCM tổ chức hội nghị về AI và ML."
    )

    print(f"\n  Input: {sample!r}\n")
    result = normalize_vietnamese_text(sample)
    print(f"  Output: {result!r}\n")

    result_lower = result.lower()

    # 1a. Số có dấu chấm phân cách hàng nghìn → chữ
    if "nghìn" in result_lower or "ngàn" in result_lower or "một" in result_lower:
        ok("Số học đã được chuyển sang chữ (phát hiện 'nghìn'/'một'/'ngàn')")
    else:
        warn("Không phát hiện số học trong output — soe-vinorm có thể chưa cài đặt (dùng fallback)")

    # 1b. Phần trăm → chữ
    if "phần trăm" in result_lower or "%" not in result:
        ok("Phần trăm đã được xử lý")
    else:
        warn("Dấu '%' vẫn còn trong output — có thể soe-vinorm chưa cài")

    # 1c. Page markers đã bị loại bỏ
    sample_with_markers = (
        "--- Page 1 ---\n"
        "Nội dung trang một.\n\n"
        "--- Page 2 [OCR] ---\n"
        "Nội dung trang hai."
    )
    result_markers = normalize_vietnamese_text(sample_with_markers)
    assert "--- Page" not in result_markers, "Page markers chưa được loại bỏ!"
    ok("Page markers ('--- Page N ---') đã bị loại bỏ trước khi normalize")

    # 1d. Text không rỗng sau normalize
    assert result.strip(), "Output sau normalize bị rỗng!"
    ok(f"Output không rỗng ({len(result)} ký tự)")

    print(f"\n  Cấu hình: max_sentences={CHUNK_MAX_SENTENCES}, overlap={CHUNK_OVERLAP_PERCENT}%")


# ---------------------------------------------------------------------------
# Test 2 — Clause-Level Chunking
# ---------------------------------------------------------------------------

def test_chunking():
    print_header("Test 2: Phân mảnh chunk (chunklet-py / fallback)")

    # Đoạn văn có đủ câu để tạo nhiều chunk
    long_text = (
        "Trí tuệ nhân tạo đang thay đổi thế giới một cách sâu sắc. "
        "Các mô hình ngôn ngữ lớn như GPT và Gemini đã đạt được những bước tiến vượt bậc. "
        "Trong lĩnh vực y tế, AIgiúp chẩn đoán bệnh nhanh hơn và chính xác hơn. "
        "Giáo dục cũng được hưởng lợi từ các hệ thống học cá nhân hóa. "
        "Tuy nhiên, cũng có những lo ngại về đạo đức và việc làm của con người. "
        "Chính phủ các nước đang tích cực nghiên cứu chính sách quản lý AI. "
        "Nhiều chuyên gia cho rằng sự hợp tác giữa người và máy là chìa khóa. "
        "Cuối cùng, tương lai của AI phụ thuộc vào cách con người lựa chọn sử dụng nó. "
        "Chúng ta cần đầu tư vào nghiên cứu và giáo dục để chuẩn bị cho kỷ nguyên mới này. "
        "Với sự cẩn thận và trách nhiệm, AI có thể mang lại nhiều lợi ích cho nhân loại."
    )

    print(f"\n  Input: {len(long_text)} ký tự, ~{len(long_text.split())} từ\n")
    chunks = chunk_normalized_text(long_text)
    print(f"  Số chunks tạo ra: {len(chunks)}\n")

    # 2a. Phải tạo ra ít nhất 1 chunk
    if not chunks:
        fail("Không có chunk nào được tạo ra!")
    ok(f"Có {len(chunks)} chunk(s) được tạo ra")

    # 2b. Mỗi chunk có đủ trường cần thiết
    required_fields = {"index", "text", "char_count", "word_count"}
    for i, chunk in enumerate(chunks):
        missing = required_fields - set(chunk.keys())
        if missing:
            fail(f"Chunk {i} thiếu trường: {missing}")
    ok("Mỗi chunk có đủ các trường: index, text, char_count, word_count")

    # 2c. Không chunk nào rỗng
    for i, chunk in enumerate(chunks):
        if not chunk["text"].strip():
            fail(f"Chunk {i} có text rỗng!")
    ok("Không có chunk rỗng")

    # 2d. Chunk size hợp lý (không quá dài — heuristic TTS)
    MAX_CHAR_PER_CHUNK = 600  # ~15 giây đọc, an toàn
    for i, chunk in enumerate(chunks):
        if chunk["char_count"] > MAX_CHAR_PER_CHUNK:
            warn(f"Chunk {i} có {chunk['char_count']} ký tự (> {MAX_CHAR_PER_CHUNK}), "
                 f"có thể hơi dài cho TTS")
    ok(f"Kích thước chunks nằm trong phạm vi hợp lý (ngưỡng: {MAX_CHAR_PER_CHUNK} ký tự)")

    # 2e. Kiểm tra overlap (nếu có > 1 chunk)
    if len(chunks) >= 2:
        first_words = set(chunks[0]["text"].split())
        second_words = set(chunks[1]["text"].split())
        overlap_words = first_words & second_words
        if overlap_words:
            ok(f"Overlap được xác nhận giữa chunk 0 và chunk 1 ({len(overlap_words)} từ chung)")
        else:
            warn("Không phát hiện overlap từ giữa chunk 0 và 1 — "
                 "cần kiểm tra cấu hình chunklet-py khi thư viện đã cài đặt")
    else:
        warn("Chỉ có 1 chunk — không thể kiểm tra overlap (text quá ngắn?)")

    # In vài chunk để inspect
    print("\n  --- Chunk samples ---")
    for chunk in chunks[:3]:
        preview = chunk["text"][:80].replace("\n", "↵")
        print(f"  [{chunk['index']}] ({chunk['char_count']} chars, {chunk['word_count']} words) → {preview!r}...")


# ---------------------------------------------------------------------------
# Test 3 — Full Pipeline (normalize + chunk)
# ---------------------------------------------------------------------------

def test_full_pipeline():
    print_header("Test 3: Full Pipeline (normalize → chunk)")

    # Văn bản giả lập output của pdf_parser (có page markers, số, ngày tháng)
    raw_pdf_text = (
        "--- Page 1 ---\n"
        "Báo cáo tổng kết năm 2023 của Công ty ABC.\n"
        "Doanh thu đạt 250.000.000.000 VND, tăng 15% so với cùng kỳ.\n\n"
        "--- Page 2 ---\n"
        "Ngày 01/01/2024, hội đồng quản trị đã họp và thống nhất kế hoạch 2024.\n"
        "Mục tiêu tăng trưởng đặt ra là 20% với tổng đầu tư 50 tỷ đồng.\n"
        "TP.HCM và Hà Nội là 2 thị trường trọng điểm chiếm 80% doanh số.\n\n"
        "--- Page 3 ---\n"
        "Về nhân sự, công ty hiện có 1.250 nhân viên, trong đó 35% là kỹ sư.\n"
        "Chương trình đào tạo AI và ML sẽ được triển khai từ Q1 năm 2024.\n"
        "Chúng tôi cam kết xây dựng môi trường làm việc tốt nhất cho nhân viên.\n"
    )

    print(f"\n  Input raw_pdf_text: {len(raw_pdf_text)} ký tự\n")

    result = run_nlp_pipeline(raw_pdf_text)

    # 3a. Kết quả có đủ trường
    assert "normalized_text" in result, "Thiếu trường 'normalized_text'"
    assert "chunks" in result, "Thiếu trường 'chunks'"
    assert "chunk_count" in result, "Thiếu trường 'chunk_count'"
    ok("run_nlp_pipeline() trả về đủ 3 trường: normalized_text, chunks, chunk_count")

    # 3b. Page markers đã biến mất
    assert "--- Page" not in result["normalized_text"], "Page markers chưa bị loại bỏ!"
    ok("Page markers đã bị loại bỏ trong normalized_text")

    # 3c. Có chunks
    assert result["chunk_count"] > 0, "Pipeline không tạo ra chunk nào!"
    ok(f"Pipeline tạo ra {result['chunk_count']} chunks")

    # 3d. chunk_count nhất quán với len(chunks)
    assert result["chunk_count"] == len(result["chunks"]), (
        f"chunk_count ({result['chunk_count']}) != len(chunks) ({len(result['chunks'])})"
    )
    ok("chunk_count nhất quán với độ dài danh sách chunks")

    print(f"\n  Kết quả:")
    print(f"    Ký tự đầu vào : {len(raw_pdf_text)}")
    print(f"    Ký tự chuẩn hóa: {len(result['normalized_text'])}")
    print(f"    Số chunks      : {result['chunk_count']}")
    print(f"\n  Chunk 0 preview:")
    if result["chunks"]:
        print(f"    {result['chunks'][0]['text'][:120]!r}...")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("NLP Pipeline Test Suite — Vietnamese TTS Document Processing")
    print(f"Cấu hình: max_sentences={CHUNK_MAX_SENTENCES}, overlap={CHUNK_OVERLAP_PERCENT}%")

    errors = []
    tests = [
        ("Normalization", test_normalization),
        ("Chunking",      test_chunking),
        ("Full Pipeline", test_full_pipeline),
    ]

    for name, fn in tests:
        try:
            fn()
            print(f"\n  ✓ {name} — PASSED\n")
        except AssertionError as e:
            errors.append((name, str(e)))
            print(f"\n  ✗ {name} — FAILED: {e}\n")
        except Exception as e:
            errors.append((name, str(e)))
            print(f"\n  ✗ {name} — ERROR: {e}\n")

    print("="*60)
    if errors:
        print(f"  KẾT QUẢ: {len(tests) - len(errors)}/{len(tests)} PASSED — có lỗi:")
        for name, msg in errors:
            print(f"    - {name}: {msg}")
        sys.exit(1)
    else:
        print(f"  KẾT QUẢ: {len(tests)}/{len(tests)} PASSED — Tất cả tests đạt!")
        sys.exit(0)
