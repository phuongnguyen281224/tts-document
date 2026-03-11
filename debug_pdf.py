import os
import sys
from pdf_parser.extractor import extract_text_from_pdf

pdf_path = r"file_input\Tóm tắt khóa học AI Prompt Engineering.pdf"

if not os.path.exists(pdf_path):
    print(f"File not found: {pdf_path}")
    sys.exit(1)

try:
    print(f"Testing extraction for: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    print(f"Success! Extracted {len(text)} characters.")
    print("Beginning of text:")
    print(text[:500])
except Exception as e:
    import traceback
    print(f"Error caught: {e}")
    traceback.print_exc()
