import re
import sys
sys.stdout.reconfigure(encoding='utf-8')
from vietnormalizer import VietnameseNormalizer
from chunklet import DocumentChunker

norm = VietnameseNormalizer()
text = "Đây là câu thứ nhất. Đây là câu thứ hai? Câu thứ ba ở đây!"
normalized = norm.normalize(text)
print("Original:", text)
print("Normalized:", normalized)

# Try with numbers
text2 = "Bài báo 1.1: Trí tuệ nhân tạo. Phần 2 nói về MLOps."
print("Normalized 2:", norm.normalize(text2))

chunker = DocumentChunker()
chunks = chunker.chunk_text(norm.normalize(text2), lang='vi', max_sentences=1, max_tokens=10)
print("Chunks:", chunks)
