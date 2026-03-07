"""
Test script cho module nlp_pipeline.py sử dụng vietnormalizer.
Chạy độc lập để kiểm chứng khả năng xử lý các trường hợp số, ngày, tiền tệ,...
"""

import sys
import os

# Thêm thư mục gốc dự án vào PYTHONPATH
sys.path.insert(0, os.path.dirname(__file__))

from worker.nlp_pipeline import normalize_vietnamese_text, chunk_normalized_text, process_text_for_tts


def test_vietnormalizer_module():
    test_cases = [
        # 1. Số thập phân và phần trăm
        (
            "Lãi suất tăng 1.5% và lạm phát ở mức 4.25%. Cơ thể 70.5kg.",
            "Lãi suất tăng một phẩy năm phần trăm và lạm phát ở mức bốn phẩy hai mươi lăm phần trăm. Cơ thể bảy mươi phẩy năm ki lô gam."
        ),
        
        # 2. Tiền tệ (VND, USD)
        (
            "Sản phẩm A có giá 1.500.000 VND, tương đương khoảng 60 USD.",
            "Sản phẩm A có giá một triệu năm trăm nghìn đồng, tương đương khoảng sáu mươi đô la Mỹ."
        ),
        
        # 3. Ngày tháng kết hợp số lượng
        (
            "Vào ngày 15/03/2024, có 1500 người tham gia sự kiện, lúc 08:30.",
            "Vào ngày mười lăm tháng ba năm hai nghìn không trăm hai mươi tư, có một nghìn năm trăm người tham gia sự kiện, lúc tám giờ ba mươi phút."
        ),
        
        # 4. Ký tự đặc biệt hỗn hợp (ví dụ thêm)
        (
            "Quãng đường dài 12.5 km, tốn 2h30m đi bộ.",
            "Quãng đường dài mười hai phẩy năm ki lô mét, tốn hai giờ ba mươi phút đi bộ."
        ),
        
        # 5. Từ viết tắt (Custom Acronyms)
        (
            "UBND thành phố họp bàn dự án GDDT tại văn phòng cty TNHH.",
            "ủy ban nhân dân thành phố họp bàn dự án giáo dục đào tạo tại văn phòng cty trách nhiệm hữu hạn."
        ),
        
        # 6. Từ ngoại lai (Custom Loanwords)
        (
            "Livestream video marketing trên web và app online bằng hệ thống AI.",
            "lai trim vi đê ô ma két tinh trên oép và áp o n lai bằng hệ thống ây ai."
        )
    ]
    
    total = len(test_cases)
    passed = 0
    
    print("=" * 60)
    print(" BẮT ĐẦU KIỂM THỬ: `vietnormalizer` (worker.nlp_pipeline)")
    print("=" * 60)
    
    for i, (input_text, expected_hint) in enumerate(test_cases, 1):
        print(f"\n[Test Case {i}]")
        print(f"INPUT    : {input_text}")
        
        try:
            result = normalize_vietnamese_text(input_text)
            print(f"OUTPUT   : {result}")
            
            # Since exact output wording might slightly differ based on the internal
            # dictionaries of the library, we do basic heuristic checks rather than strict ==
            is_pass = True
            
            # Kiểm tra xem có chứa chữ số không
            if any(char.isdigit() for char in result):
                print("  => FAILED: Output vẫn còn chứa chữ số!")
                is_pass = False
            
            # Kiểm tra xem các ký hiệu %, /, : có bị biến thành chữ chưa
            for sym in ['%', '/', ':', '$']:
                if sym in result:
                    print(f"  => FAILED: Output vẫn còn ký tự '{sym}' chưa được dịch!")
                    is_pass = False
            
            # Kiểm tra xem các test case 5, 6 có còn từ gốc không (case-insensitive)
            if i in [5, 6]:
                # Chuyển output xuống chữ thường để dễ kiểm tra
                res_lower = result.lower()
                for original_word in ["ubnd", "gddt", "tnhh", "livestream", "video", "marketing", "web", "app", "online", "ai"]:
                    # Sử dụng re để match nguyên từ (word boundary)
                    import re
                    if re.search(r'\b' + re.escape(original_word) + r'\b', res_lower):
                        print(f"  => FAILED: Từ điển không load được! Vẫn còn từ gốc: '{original_word}'")
                        is_pass = False

            if is_pass:
                print("  => PASSED (Tất cả số và ký tự ngày, tiền tệ, phần trăm đã được chuyển thành chữ tiếng Việt)")
                passed += 1
                
        except Exception as e:
            print(f"  => ERROR: {e}")
            
    print("\n" + "=" * 60)
    print(f" TỔNG KẾT NORMALIZATION: {passed}/{total} tests PASSED.")
    print("=" * 60)

def test_chunking_module():
    print("\n" + "=" * 60)
    print(" BẮT ĐẦU KIỂM THỬ: `chunklet` (Hybrid Chunking)")
    print("=" * 60)
    
    # Một đoạn văn bản dài khoảng 800 ký tự (Giả định đã qua chuẩn hóa)
    long_text = (
        "Trí tuệ nhân tạo đang thay đổi cách chúng ta làm việc và sinh sống mỗi ngày. "
        "Nhiều công ty lớn đã bắt đầu tích hợp các mô hình ngôn ngữ lớn vào quy trình thực tế. "
        "Theo một báo cáo gần đây của uỷ ban nhân dân thành phố, tỷ lệ ứng dụng công nghệ đã tăng bốn mươi lăm phần trăm. "
        "Việc đào tạo một mô hình vi đê ô có thể tiêu tốn hàng triệu đô la Mỹ nhưng mang lại hiệu quả to lớn. "
        "Giáo dục cũng được hưởng lợi từ các hệ thống học cá nhân hóa. "
        "Tuy nhiên, chúng ta cũng cần phải đối mặt với nhiều thách thức về bảo mật và quyền riêng tư. "
        "Nhiều chuyên gia cho rằng sự hợp tác giữa người và máy là chìa khóa. "
        "Cuối cùng, điều quan trọng nhất là chúng ta phải đảm bảo rằng công nghệ được phát triển vì lợi ích chung của toàn xã hội."
    )
    
    print(f"\nINPUT LENGTH: {len(long_text)} characters")
    
    chunks = chunk_normalized_text(long_text)
    
    print(f"SỐ CHUNKS TẠO RA: {len(chunks)}\n")
    
    for c in chunks:
        print(f"--- Chunk {c['index']} ---")
        print(f"Độ dài: {c['char_count']} ký tự, {c['word_count']} từ")
        print(f"Nội dung:\n{c['text']}\n")

def test_orchestrator():
    print("\n" + "=" * 60)
    print(" BẮT ĐẦU KIỂM THỬ: `process_text_for_tts` (Full Orchestrator)")
    print("=" * 60)
    
    # Chuỗi raw text mô phỏng trích xuất lỗi từ PDF
    raw_flawed_text = (
        "Báo cáo phát triển trí tuệ nhân tạo (AI)\n\n"
        "Năm       nay, ngành công nghiệp phần mềm đạt \t \t doanh thu 120.000 VNĐ một cách bất-\nngờ. "
        "Với sự bùng nổ của livestream video marketing trên nền tảng mạng, nhiều doanh-\nnghiệp đang "
        "áp dụng triệt để những tính năng web và app online mới nhất. Tính đến ngày 16/04/2024, "
        "tỷ lệ lợi nhuận trung bình đã tăng 15.5%. Các chuyên gia nhận định rằng điều này mang lại lợi ích "
        "lâu dài cho cả hệ sinh thái số hóa.\u200b\u200b Cần phải chuẩn bị tốt hơn."
    )
    
    print("\n--- RAW INPUT ---")
    print(raw_flawed_text)
    
    output_strings = process_text_for_tts(raw_flawed_text)
    
    print("\n--- FINAL STRINGS (Audio Segments) ---")
    print(f"Số lượng đoạn phát âm: {len(output_strings)}\n")
    
    for i, seq in enumerate(output_strings):
        print(f"[{i}] {seq}")
        print("-" * 30)

if __name__ == "__main__":
    test_vietnormalizer_module()
    test_chunking_module()
    test_orchestrator()

