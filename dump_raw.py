import sys
sys.stdout.reconfigure(encoding='utf-8')
from pdf_parser.extractor import extract_text_from_pdf

text = extract_text_from_pdf("file_input/MLOps và MLflow_ Dễ hiểu.pdf")
print(f"Total Raw Length: {len(text)}")
with open("temp_outputs/raw_text.txt", "w", encoding="utf-8") as f:
    f.write(text)
print("Saved to temp_outputs/raw_text.txt")
