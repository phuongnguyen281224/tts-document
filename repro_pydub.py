import os
import sys
from pydub import AudioSegment
from pydub.utils import which

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print(f"Python version: {sys.version}")
print(f"FFmpeg found by pydub: {which('ffmpeg')}")

temp_dir = "temp_outputs"
mp3_files = [f for f in os.listdir(temp_dir) if f.endswith(".mp3")]

if not mp3_files:
    print(f"No MP3 files found in {temp_dir}")
else:
    test_file = os.path.join(temp_dir, mp3_files[0])
    abs_path = os.path.abspath(test_file)
    print(f"Testing with file: {abs_path}")
    print(f"File exists: {os.path.exists(abs_path)}")
    
    try:
        seg = AudioSegment.from_file(abs_path)
        print("Success! Loaded audio segment.")
        print(f"Duration: {len(seg)}ms")
    except Exception as e:
        print(f"Failed to load audio: {e}")
        import traceback
        traceback.print_exc()

print("\nEnvironment PATH:")
for p in os.environ.get('PATH', '').split(os.pathsep):
    if 'ffmpeg' in p.lower():
        print(f"POSSIBLE FFmpeg DIR: {p}")
