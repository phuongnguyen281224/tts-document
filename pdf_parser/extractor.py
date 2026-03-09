import os
import re
import fitz
import concurrent.futures
try:
    import pytesseract
    from pdf2image import convert_from_path
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Minimum number of characters expected from a normal text page.
# If PyMuPDF returns fewer than this, OCR is triggered.
OCR_CHAR_THRESHOLD = 20

# Poppler binaries path on Windows (winget install location).
# Set to None on Linux/macOS (relies on PATH).
POPPLER_PATH = r"C:\Users\phuon\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin"

def clean_extracted_text(raw_text: str) -> str:
    """
    Cleans raw extracted (or OCR'd) text using a sequence of regex operations.
    Removes garbage characters and excessive whitespace while preserving
    sentence-level punctuation (.  , ? ! ; :) for downstream chunking.
    
    Args:
        raw_text: The raw string from PyMuPDF or pytesseract.
    Returns:
        A cleaned, normalized string.
    """
    text = raw_text
    
    # Step 1: Remove non-printable control characters, keep Latin + Vietnamese Unicode range
    # Keeps: basic printable ASCII, Latin Extended, Vietnamese precomposed chars, and newlines.
    text = re.sub(r'[^\x20-\x7E\u00C0-\u024F\u1E00-\u1EFF\n]', '', text)
    
    # Step 2: Collapse multiple horizontal whitespace (spaces/tabs) into a single space.
    # \S\n is preserved so newlines are untouched.
    text = re.sub(r'[^\S\n]+', ' ', text)
    
    # Step 3: Strip trailing whitespace from each line.
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    
    # Step 4: Remove lines that contain only punctuation noise or whitespace
    # (e.g., '---------', '...', '   '). Preserve lines with at least one word char.
    text = re.sub(r'^[\s\W]+$', '', text, flags=re.MULTILINE)
    
    # Step 4.5: Smart Un-breaking
    # Join lines that don't end with a punctuation mark, a hyphen, or another newline.
    # We replace single newlines that split a sentence with a space.
    text = re.sub(r'(?<![\.\?\!\,\:\;\-\n])\n(?!\n)', ' ', text)
    
    # Step 5: Collapse 3 or more consecutive blank lines into at most 2.
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def is_page_number(text: str) -> bool:
    """
    Checks if a string looks like a page number (e.g., 'Page 1', '1/10', 'Trang 5', etc.)
    """
    patterns = [
        r'^\d+$',                      # 1
        r'^page\s+\d+$',               # Page 1
        r'^trang\s+\d+$',              # Trang 1
        r'^\d+\s*/\s*\d+$',            # 1/10
        r'^page\s+\d+\s+of\s+\d+$',    # Page 1 of 10
        r'.*\|\s*internal\s*use\s*only.*', # Custom test case for the footer
        r'.*page\s+\d+.*'              # Generic Page X
    ]
    text_lower = text.lower().strip()
    for p in patterns:
        if re.match(p, text_lower):
            return True
    return False


def is_code_or_formula(text: str, threshold: float = 0.15) -> bool:
    """
    Checks if a text block has a high density of special characters,
    indicating it's likely a code snippet or mathematical formula.
    """
    if not text:
        return False
        
    special_chars = set("{}[]\\_^<>=/+*|@#")
    special_count = sum(1 for char in text if char in special_chars)
    
    # Calculate density based on non-whitespace characters to be more accurate
    non_ws_count = len("".join(text.split()))
    
    if non_ws_count == 0:
        return False
        
    return (special_count / non_ws_count) > threshold


def _ocr_page(pdf_path: str, page_num: int) -> str:
    """
    OCR fallback: converts a single PDF page to an image and runs
    pytesseract on it with Vietnamese language support.
    
    Args:
        pdf_path: path to the PDF file.
        page_num: 0-indexed page number.
    Returns:
        OCR-extracted text string, or empty string on failure.
    """
    if not OCR_AVAILABLE:
        print(f"  [OCR] Skipped page {page_num + 1}: pytesseract/pdf2image not installed.")
        return ""
    try:
        # convert_from_path uses 1-indexed pages
        images = convert_from_path(
            pdf_path,
            dpi=200,
            first_page=page_num + 1,
            last_page=page_num + 1,
            poppler_path=POPPLER_PATH
        )
        if not images:
            return ""
        text = pytesseract.image_to_string(images[0], lang='vie')
        return text.strip()
    except pytesseract.TesseractError as e:
        print(f"  [OCR] TesseractError on page {page_num + 1}: {e}")
        return ""
    except Exception as e:
        print(f"  [OCR] Unexpected error on page {page_num + 1}: {e}")
        return ""

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts text from a given PDF path.
    Uses 'page.get_text('blocks')' to parse layout-preserving blocks.
    
    Args:
        pdf_path (str): The absolute or relative path to the PDF file.
        
    Returns:
        str: The concatenated and layout-preserved text.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    extracted_page_texts = [""] * total_pages
    pages_to_ocr = []
    
    # Store blocks by page for the two-pass filtering
    pages_blocks = []
    total_pages = len(doc)
    
    # Pass 1: Collect blocks and find header/footer candidates
    header_footer_candidates = {}
    
    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        blocks = page.get_text("blocks")
        page_height = page.rect.height
        
        # Detect tables to exclude text inside them.
        tables = page.find_tables()
        table_bboxes = []
        if tables.tables:
            for table in tables.tables:
                table_bboxes.append(fitz.Rect(table.bbox))
        
        # We only care about text blocks (block_type == 0). Image blocks (type == 1) are skipped.
        text_blocks = [b for b in blocks if b[6] == 0]
        
        filtered_blocks = []
        for block in text_blocks:
            # Check if this text block overlaps with any table
            block_rect = fitz.Rect(block[:4])
            overlaps_table = False
            for t_bbox in table_bboxes:
                if block_rect.intersects(t_bbox):
                    overlaps_table = True
                    break
            
            if overlaps_table:
                continue

            text_content = block[4].strip()
            if text_content:
                # Check for high-density special characters (code/math blocks)
                if is_code_or_formula(text_content):
                    text_content = "[Nội dung chứa công thức hoặc đoạn mã đã được hệ thống tự động bỏ qua]"
                    
                y0, y1 = block[1], block[3]
                
                # Check if it's in the header or footer zone (72 points = 1 inch)
                is_header = y0 < 72
                is_footer = y1 > (page_height - 72)
                
                if is_header or is_footer:
                    header_footer_candidates[text_content] = header_footer_candidates.get(text_content, 0) + 1
                    
                filtered_blocks.append({
                    "text": text_content,
                    "y0": y0,
                    "y1": y1,
                    "is_header": is_header,
                    "is_footer": is_footer
                })
        
        pages_blocks.append(filtered_blocks)

    # Determine repetitive headers/footers (threshold: >= 2 pages, or 50% of the document)
    threshold = max(2, int(total_pages * 0.5))
    text_to_remove = {
        txt for txt, count in header_footer_candidates.items() 
        if count >= threshold
    }

    # Pass 2: Filter and assemble
    for page_num, pb in enumerate(pages_blocks):
        # Sort blocks vertically, then horizontally
        pb.sort(key=lambda b: (b["y0"], b["text"]))
        
        page_text = []
        for block in pb:
            # Skip if it is a repetitive header/footer OR looks like a page number in the margins
            is_repetitive = block["text"] in text_to_remove
            is_noise = (block["is_header"] or block["is_footer"]) and (is_repetitive or is_page_number(block["text"]))
            
            if is_noise:
                continue
            
            page_text.append(block["text"])
        
        page_body = "\n\n".join(page_text)
        
        # OCR fallback: if the extracted text is suspiciously short, try OCR
        if len(page_body.strip()) < OCR_CHAR_THRESHOLD:
            print(f"  [OCR] Page {page_num + 1}: low text ({len(page_body.strip())} chars), scheduling OCR...")
            pages_to_ocr.append(page_num)
        elif page_text:
            extracted_page_texts[page_num] = f"--- Page {page_num + 1} ---\n\n{page_body}"

    # Perform Concurrent OCR
    if pages_to_ocr:
        max_workers = os.cpu_count() or 4
        print(f"  [OCR] Starting concurrent OCR for {len(pages_to_ocr)} pages using {max_workers} workers...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_page = {executor.submit(_ocr_page, pdf_path, p): p for p in pages_to_ocr}
            for future in concurrent.futures.as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    ocr_text = future.result()
                    if ocr_text:
                        extracted_page_texts[page_num] = f"--- Page {page_num + 1} [OCR] ---\n\n{ocr_text}"
                except Exception as exc:
                    print(f"  [OCR] Page {page_num + 1} generated an exception: {exc}")
            
    doc.close()
    
    # Concatenate all non-empty page contents, separating pages by double newlines
    final_result = "\n\n".join(filter(None, extracted_page_texts))
    
    # Final cleanup pass: remove garbage characters and normalize whitespace
    return clean_extracted_text(final_result)
