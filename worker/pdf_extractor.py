import os
import fitz
import pytesseract
from pdf2image import convert_from_path

def get_text_from_scanned_pdf(file_path: str) -> str:
    """
    Fallback OCR: Use pdf2image to convert PDF to images, then use pytesseract to extract text.
    """
    print("Falling back to OCR using pytesseract...")
    try:
        images = convert_from_path(file_path)
        extracted_text = []
        for index, image in enumerate(images):
            # Try to grab text with Tesseract
            text = pytesseract.image_to_string(image, lang='eng+vie')
            extracted_text.append(f"--- Page {index + 1} (OCR) ---\n" + text)
            
        return "\n\n".join(extracted_text)
    except Exception as e:
        print(f"OCR Failed: {e}")
        return ""

def extract_pdf_text(file_path: str) -> str:
    """
    Extracts text from a PDF saving structural layout using PyMuPDF.
    Implements a Y-coordinate filter to remove repetitive headers and footers.
    Falls back to OCR if the PDF is essentially scanned images.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    doc = fitz.open(file_path)
    total_pages = len(doc)
    
    # Store blocks by page for filtering
    pages_blocks = []
    total_text_length = 0
    
    # Heuristics parameters for header/footer detection
    # Text found in the top 10% or bottom 10% of the page
    HEADER_RATIO = 0.10
    FOOTER_RATIO = 0.90
    
    # Collect blocks from each page
    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        # get_text('blocks') returns a list of tuples: (x0, y0, x1, y1, "text", block_no, block_type)
        blocks = page.get_text("blocks")
        page_height = page.rect.height
        
        filtered_blocks = []
        for block in blocks:
            # block_type 0 = text, 1 = image
            if block[6] == 0:
                text = block[4].strip()
                if text:
                    y0, y1 = block[1], block[3]
                    # We preserve the bounding box and the actual text for filtering
                    filtered_blocks.append({
                        "text": text,
                        "y0": y0,
                        "y1": y1,
                        "is_header": y0 < (page_height * HEADER_RATIO),
                        "is_footer": y1 > (page_height * FOOTER_RATIO)
                    })
                    total_text_length += len(text)
        
        pages_blocks.append(filtered_blocks)

    # Check for empty or near-empty text, implying a scanned document
    # e.g., less than 50 chars per page on average usually means it's an image.
    if total_pages > 0 and (total_text_length / total_pages) < 50:
        doc.close()
        return get_text_from_scanned_pdf(file_path)

    # Filtering headers and footers logic
    # Find text that repeats across multiple pages in header/footer areas
    header_footer_candidates = {}
    for pb in pages_blocks:
        for block in pb:
            if block["is_header"] or block["is_footer"]:
                txt = block["text"]
                header_footer_candidates[txt] = header_footer_candidates.get(txt, 0) + 1

    # Threshold for removal: if the exact text appears in the header/footer of > 50% of the pages
    # or at least 3 times.
    threshold = max(3, int(total_pages * 0.5))
    text_to_remove = {txt for txt, count in header_footer_candidates.items() if count >= threshold}

    final_text_chunks = []
    
    for page_num, pb in enumerate(pages_blocks):
        final_text_chunks.append(f"--- Page {page_num + 1} ---")
        # Sort blocks by Y coordinate (top-down), then X coordinate (left-to-right) roughly
        # PyMuPDF usually does a fair job, but sorting guarantees reading order
        pb.sort(key=lambda b: (b["y0"], b["text"]))
        
        for block in pb:
            # Drop if it is a suspected repetitive header or footer
            if (block["is_header"] or block["is_footer"]) and block["text"] in text_to_remove:
                continue
            final_text_chunks.append(block["text"])
            
    doc.close()
    
    return "\n\n".join(final_text_chunks)

if __name__ == "__main__":
    # Test script snippet if executed directly
    print("pdf_extractor module loaded.")
