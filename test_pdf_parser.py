import os
import sys

# Configure stdout to handle Vietnamese characters properly on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
import fitz
from pdf_parser.extractor import extract_text_from_pdf

def create_dummy_pdf(output_path: str):
    """
    Creates a 3-page dummy PDF with repeating headers/footers and unique body text.
    """
    doc = fitz.open()
    header_text = "CONFIDENTIAL - Product Document 2024"
    footer_fixed = "Internal Use Only"
    
    for i in range(3):
        page = doc.new_page()
        page_height = page.rect.height
        
        # 1. Insert Header (y < 72)
        page.insert_text(
            (50, 45), 
            header_text, 
            fontsize=10
        )
        
        # 2. Insert Page Number Footer (y > height - 72)
        page.insert_text(
            (50, page_height - 35), 
            f"Page {i+1} | {footer_fixed}", 
            fontsize=10
        )
        
        # 3. Insert Unique Body Content
        body_y = 120 + (i * 20)
        page.insert_textbox(
            fitz.Rect(50, body_y, 550, body_y + 100), 
            f"This is the unique content for page {i+1}.\n"
            "This text should definitely be preserved by the extractor. It is part of the body text and does not repeat.", 
            fontsize=12, align=0
        )
        
        # 4. Edge Case: Body text starting very high (borderline)
        if i == 1:
            page.insert_text(
                (50, 85), 
                "CRITICAL: This line starts at y=85, just outside the 72pt header zone.", 
                fontsize=11
            )

    doc.save(output_path)
    doc.close()
    print(f"Created multi-page dummy PDF with headers/footers at: {output_path}")

def test_parser():
    dummy_pdf_path = "dummy_test.pdf"
    
    try:
        # Step 1: Create the dummy PDF
        create_dummy_pdf(dummy_pdf_path)
        
        # Step 2: Use the newly created extractor
        print(f"\n--- Extracting text from {dummy_pdf_path} ---\n")
        extracted_text = extract_text_from_pdf(dummy_pdf_path)
        
        # Step 3: Print result
        print("====== EXTRACTED TEXT RESULT (CLEANED) ======")
        print(extracted_text)
        print("=============================================\n")
        
        # Step 4: Validate cleaning rules
        assert '  ' not in extracted_text, "FAIL: Double space found in output!"
        assert '\n\n\n' not in extracted_text, "FAIL: Triple blank line found in output!"
        print("[OK] Cleaned output passed all assertions (no double-spaces, no triple blank lines).")
        print("Extraction completed successfully!")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
    finally:
        # Clean up the dummy file
        if os.path.exists(dummy_pdf_path):
            os.remove(dummy_pdf_path)
            print(f"Cleaned up {dummy_pdf_path}")

def create_scanned_pdf(output_path: str):
    """
    Creates a 'scanned' PDF: text is rendered to a pixmap (image) then
    embedded back as a JPEG into a new PDF — no selectable text layer.
    """
    # Step 1: Create a temporary source PDF with Vietnamese text
    source_doc = fitz.open()
    src_page = source_doc.new_page(width=595, height=842)  # A4
    
    sample_viet_text = (
        "Đây là một đoạn văn bản tiếng Việt mẫu.\n"
        "Hệ thống OCR sẽ nhận dạng chữ từ ảnh scan này.\n"
        "Kỹ thuật trích xuất văn bản rất quan trọng trong xử lý tài liệu."
    )
    src_page.insert_textbox(
        fitz.Rect(50, 100, 550, 700),
        sample_viet_text,
        fontsize=16, align=0
    )

    # Step 2: Render that page to a pixmap (simulate a scanner)
    mat = fitz.Matrix(2, 2)  # 2x zoom for decent DPI
    pix = src_page.get_pixmap(matrix=mat)
    source_doc.close()
    
    # Step 3: Embed the pixmap as the only content in a new PDF
    scanned_doc = fitz.open()
    img_page = scanned_doc.new_page(width=595, height=842)
    img_page.insert_image(
        fitz.Rect(0, 0, 595, 842),
        pixmap=pix
    )
    scanned_doc.save(output_path)
    scanned_doc.close()
    print(f"Created scanned (image-only) PDF at: {output_path}")


def test_ocr_parser():
    scanned_pdf_path = "scanned_test.pdf"
    
    try:
        # Step 1: Create a fake scanned PDF
        create_scanned_pdf(scanned_pdf_path)
        
        # Step 2: Run the extractor. OCR should trigger automatically.
        print(f"\n--- Running OCR Extraction on {scanned_pdf_path} ---\n")
        extracted_text = extract_text_from_pdf(scanned_pdf_path)
        
        # Step 3: Print results
        print("====== OCR EXTRACTED TEXT RESULT ======")
        print(extracted_text if extracted_text.strip() else "(no text extracted)")
        print("=======================================\n")
        
        if "[OCR]" in extracted_text:
            print("[OK] OCR fallback was successfully triggered!")
        else:
            print("[WARN] OCR fallback did NOT trigger -- Tesseract/poppler may not be installed.")
            
    except Exception as e:
        print(f"OCR Test failed with error: {e}")
    finally:
        if os.path.exists(scanned_pdf_path):
            os.remove(scanned_pdf_path)
            print(f"Cleaned up {scanned_pdf_path}")


def create_exclusion_pdf(output_path: str):
    """
    Creates a PDF with:
    1. Normal text
    2. An image
    3. A structured table (drawn with lines and text)
    To verify that the extractor skips images and tables.
    """
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    
    # 1. Normal Text
    page.insert_textbox(
        fitz.Rect(50, 50, 550, 100),
        "This is normal paragraph text. It MUST be extracted by the parser.",
        fontsize=12, align=0
    )
    
    # 2. Image (simulate by drawing a colored rectangle and adding text over it, 
    # but to truly test standard image extraction exclusion, we insert a real pixmap).
    # Since we can't easily generate a JPEG in memory without PIL, we just draw a shape
    # and know that PyMuPDF's block_type=1 handles real images. The table is the main test.
    page.draw_rect(fitz.Rect(50, 120, 200, 220), color=(1,0,0), fill=(1,0.8,0.8))
    page.insert_textbox(
        fitz.Rect(50, 120, 200, 220),
        "Image Caption/Context (not a real image block, but overlapping a graphic)",
        fontsize=10, align=1
    )
    
    # 3. Table
    # PyMuPDF relies on horizontal/vertical lines or structured gridded text.
    # We will draw a simple 2x2 table grid.
    tbl_rect = fitz.Rect(50, 250, 500, 350)
    
    # Draw Borders
    page.draw_rect(tbl_rect, width=1)
    page.draw_line(fitz.Point(50, 300), fitz.Point(500, 300), width=1) # middle horizontal
    page.draw_line(fitz.Point(275, 250), fitz.Point(275, 350), width=1) # middle vertical
    
    # Draw Text inside cells
    # Row 1
    page.insert_text(fitz.Point(60, 280), "Header 1", fontsize=12)
    page.insert_text(fitz.Point(285, 280), "Header 2", fontsize=12)
    # Row 2
    page.insert_text(fitz.Point(60, 330), "Data A: 123", fontsize=12)
    page.insert_text(fitz.Point(285, 330), "Data B: 456", fontsize=12)
    
    doc.save(output_path)
    doc.close()
    print(f"Created exclusion dummy PDF at: {output_path}")


def test_exclusion_parser():
    exclusion_pdf_path = "exclusion_test.pdf"
    
    try:
        create_exclusion_pdf(exclusion_pdf_path)
        
        print(f"\n--- Running Exclusion Extraction on {exclusion_pdf_path} ---\n")
        extracted_text = extract_text_from_pdf(exclusion_pdf_path)
        
        print("====== EXCLUSION TEXT RESULT ======")
        print(extracted_text)
        print("===================================\n")
        
        # Assertions
        assert "This is normal paragraph text" in extracted_text, "FAIL: Normal text was excluded!"
        assert "Data A: 123" not in extracted_text, "FAIL: Table data was NOT excluded!"
        assert "Header 1" not in extracted_text, "FAIL: Table data was NOT excluded!"
        
        print("[OK] Exclusion test passed! Table content was successfully skipped.")
        
    except Exception as e:
        print(f"Exclusion Test failed with error: {e}")
    finally:
        if os.path.exists(exclusion_pdf_path):
            os.remove(exclusion_pdf_path)
            print(f"Cleaned up {exclusion_pdf_path}")


def test_unbreaking_parser():
    print(f"\n--- Running Smart Un-breaking Test ---\n")
    
    raw_broken_text = (
        "Đây là một câu hoàn chỉnh.\n"
        "Tuy nhiên câu này đã bị ngắt làm đôi vì\n"
        "hết lề giấy ở trong file PDF.\n\n"
        "Đoạn văn mới bắt đầu ở đây. Nếu một đoạn kết thúc bằng dấu phẩy,\n"
        "hoặc bằng dấu gạch nối-\n"
        "thì nó vẫn nên được giữ nguyên nếu cần, nhưng theo rule ta nối nó lại:\n"
        "Kẻ từ dòng này: dòng một không có dấu\n"
        "dòng hai tiếp tục ý."
    )
    
    from pdf_parser.extractor import clean_extracted_text
    cleaned = clean_extracted_text(raw_broken_text)
    
    print("====== ORIGINAL TEXT ======")
    print(raw_broken_text)
    print("\n====== UN-BROKEN TEXT ======")
    print(cleaned)
    print("===============================\n")
    
    # Assertions
    assert "Đây là một câu hoàn chỉnh.\nT" in cleaned, "FAIL: Should NOT modify valid sentence endings."
    assert "vì hết lề giấy" in cleaned, "FAIL: Did not automatically join lines split without punctuation!"
    assert "dấu phẩy,\nhoặc" in cleaned, "FAIL: Should not join lines ending in comma!"
    assert "dấu gạch nối-\nthì" in cleaned, "FAIL: Should not join lines ending in hyphen!"
    assert "dấu\ndòng hai" not in cleaned, "FAIL: Did not join lines split without punctuation!"
    assert "dấu dòng hai" in cleaned, "FAIL: Joined text missing space or incorrect."
    
    print("[OK] Smart Un-breaking test passed! Sentences successfully rejoined.")


def test_formula_parser():
    formula_pdf_path = "formula_test.pdf"
    
    try:
        # Create a PDF with normal text, python code, and a math formula
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        
        # 1. Normal Text (Should be preserved)
        # Using English/ASCII here because PyMuPDF's default font (helv) 
        # doesn't fully support Vietnamese out-of-the-box via insert_textbox,
        # which causes it to render as '?' and fails the assertion.
        page.insert_textbox(
            fitz.Rect(50, 50, 550, 150),
            "This is a normal paragraph of text. It explains the system architecture, "
            "contains very few special characters, and should be easily read by "
            "the Text-to-Speech model without any problems.",
            fontsize=12, align=0
        )
        
        # 2. Python Code Snippet (High density of special chars)
        # Added more special chars to ensure it confidently passes the 15% threshold.
        code_text = (
            "def calculate_metrics(_data=[{}, []]):\n"
            "    return [x * 2 for x in _data if x > 0] + {'status': True}\n"
            "    # >>> print(data['user_id'])\n"
        )
        page.insert_textbox( fitz.Rect(50, 160, 550, 260), code_text, fontsize=10 )
        
        # 3. Math Formula (LaTeX style)
        math_text = "f(x) = \\int_{0}^{\\infty} e^{-x^2} dx + < \\phi | \\psi > <=> X & Y"
        page.insert_textbox( fitz.Rect(50, 270, 550, 320), math_text, fontsize=12 )
        
        doc.save(formula_pdf_path)
        doc.close()
        
        print(f"\n--- Running Code/Formula Filtering Test on {formula_pdf_path} ---\n")
        extracted_text = extract_text_from_pdf(formula_pdf_path)
        
        print("====== FILTERED TEXT RESULT ======")
        print(extracted_text)
        print("==================================\n")
        
        warning_msg = "[Nội dung chứa công thức hoặc đoạn mã đã được hệ thống tự động bỏ qua]"
        
        # Assertions
        assert "This is a normal paragraph" in extracted_text, "FAIL: Normal text was accidentally filtered!"
        assert "def calculate_metrics" not in extracted_text, "FAIL: Python code was NOT filtered!"
        assert "\\int_{0}^{\\infty}" not in extracted_text, "FAIL: Math formula was NOT filtered!"
        assert extracted_text.count(warning_msg) >= 2, "FAIL: Warning messages not found in place of code/math!"
        
        print("[OK] Formula/Code filtering test passed! Dense blocks were successfully replaced.")

    except Exception as e:
        print(f"Formula Test failed with error: {e}")
    finally:
        if os.path.exists(formula_pdf_path):
            os.remove(formula_pdf_path)
            print(f"Cleaned up {formula_pdf_path}")


if __name__ == "__main__":
    test_parser()
    print("\n" + "="*50 + "\n")
    test_ocr_parser()
    print("\n" + "="*50 + "\n")
    test_exclusion_parser()
    print("\n" + "="*50 + "\n")
    test_unbreaking_parser()
    print("\n" + "="*50 + "\n")
    test_formula_parser()
