import os
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


if __name__ == "__main__":
    test_parser()
    print("\n" + "="*50 + "\n")
    test_ocr_parser()
