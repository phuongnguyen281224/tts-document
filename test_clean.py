import sys
import re
sys.stdout.reconfigure(encoding='utf-8')
from worker.nlp_pipeline import process_text_for_tts

with open("temp_outputs/raw_text.txt", encoding="utf-8") as f:
    text = f.read()

# Try to add space after period if followed by a letter (no longer needed)
# text = re.sub(r'\.([a-zA-ZÀ-Ỹà-ỹ])', r'. \1', text)

chunks = process_text_for_tts(text)

print(f"Number of chunks generated: {len(chunks)}")
if len(chunks) > 0:
    for i, c in enumerate(chunks[:5]):
        print(f"Chunk {i} length: {len(c)}")
    print("...")
    for i, c in enumerate(chunks[-5:]):
        print(f"Chunk {len(chunks)-5+i} length: {len(c)}")
        
    print(f"\nMax chunk length: {max(len(c) for c in chunks)}")
    print("\nPreview of chunk 13:")
    print(chunks[-1][:500])
