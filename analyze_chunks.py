import json
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-vie")
with open("temp_outputs/7fd5560d-08ea-4895-bbe6-f9f1e4c02344_chunks.json", encoding="utf-8") as f:
    data = json.load(f)

for i, text in enumerate(data['chunks']):
    tokens = tokenizer(text)["input_ids"]
    print(f"Chunk {i}: {len(text)} chars, {len(tokens)} tokens")
