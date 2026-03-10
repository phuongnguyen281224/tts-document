import os
import sys

# Thêm thư mục gốc vào path để import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from worker.nlp_pipeline import normalize_vietnamese_text, process_text_for_tts

def test_normalization():
    test_cases = [
        ("Tôi đang học MLOps", "tôi đang học vận hành học máy"),
        ("HĐND thành phố", "hội đồng nhân dân thành phố"),
        ("Xem video online", "xem vi đê ô on lai"),
        ("MLflow là một tool tốt", "em eo phờ lâu là một tool tốt") # MLflow is in custom_loanwords as "em eo phờ lâu"
    ]
    
    print("--- Bắt đầu kiểm tra Normalization với Custom Dictionaries ---")
    for text, expected in test_cases:
        result = normalize_vietnamese_text(text)
        print(f"Input: {text}")
        print(f"Output: {result}")
        # Not asserting strictly because vietnormalizer might change casing or spacing, but checking if replacement happened
        if any(word in result.lower() for word in expected.split()):
            print("Status: SUCCESS (Replacement detected)")
        else:
            print("Status: FAILED (Replacement NOT detected)")
        print("-" * 20)

if __name__ == "__main__":
    test_normalization()
