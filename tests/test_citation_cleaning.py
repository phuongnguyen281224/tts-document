import re
import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Mock the environment to test the function without full dependencies if possible
# Or just import it if the environment is ready.
# In this environment, I can import from worker.nlp_pipeline

# Add current dir to path if needed
sys.path.append(os.getcwd())

from worker.nlp_pipeline import clean_raw_text

test_cases = [
    # 1. Punctuation citations
    ("hoàn thành.2", "hoàn thành."),
    ("phát triển, 3", "phát triển,"),
    ("báo cáo? 4", "báo cáo?"),
    ("kết quả:12", "kết quả:"),
    
    # 2. Attached citations
    ("nhân loại5", "nhân loại"),
    ("ứng dụng12", "ứng dụng"),
    ("Việt Nam2024", "Việt Nam"), # Wait, "Việt Nam2024" should probably be "Việt Nam" if it's a citation
    
    # 3. Superscripts
    ("thế kỷ¹", "thế kỷ"),
    ("quy mô²³", "quy mô"),
    ("số liệu⁴⁵⁶", "số liệu"),
    
    # 4. Brackets and Parentheses
    ("nghiên cứu [1]", "nghiên cứu"),
    ("tài liệu [12, 15]", "tài liệu"),
    ("phương pháp [1-4]", "phương pháp"),
    ("dữ liệu (1)", "dữ liệu"),
    
    # 5. Safety: Meaningful numbers (SHOULD BE PRESERVED)
    ("Năm 2024", "Năm 2024"),
    ("Web 2.0", "Web 2.0"),
    ("Có 2 nguyên nhân", "Có 2 nguyên nhân"),
    ("khoảng 50%", "khoảng 50%"),
    ("tỉ lệ 3.14", "tỉ lệ 3.14"),
    ("A1", "A1"), # Length 2 rule: word must have >= 2 letters. Wait, "A1" has 1 letter "A".
    ("B2", "B2"),
    ("HĐND", "HĐND"),
    
    # 6. Spacing
    ("Văn bản  sạch   hơn.", "Văn bản sạch hơn."),
    ("Dòng 1\n\n\nDòng 2", "Dòng 1\n\nDòng 2"),
]

print(f"{'INPUT':<30} | {'EXPECTED':<25} | {'RESULT':<25} | {'STATUS'}")
print("-" * 100)

success_count = 0
for inp, exp in test_cases:
    res = clean_raw_text(inp)
    status = "✅ PASS" if res == exp else "❌ FAIL"
    if res == exp:
        success_count += 1
    print(f"{inp:<30} | {exp:<25} | {res:<25} | {status}")

print("-" * 100)
print(f"Total: {len(test_cases)}, Passed: {success_count}, Failed: {len(test_cases) - success_count}")

if success_count == len(test_cases):
    print("\nAll tests passed successfully!")
else:
    sys.exit(1)
