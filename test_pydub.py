import os
import sys
from collections import defaultdict
from pydub import AudioSegment
from worker.audio_processor import concatenate_audio

def main():
    print("Testing concatenate_audio on the 121 files...")
    folder = "temp_outputs"
    uuid_prefix = "94fd174a-864e-4c40-9901-7d48f3fa5f64" # Example UUID from list_dir
    
    audio_files = []
    for i in range(121):
        fpath = os.path.join(folder, f"{uuid_prefix}_chunk_{i:04d}.wav")
        if not os.path.exists(fpath):
            print(f"MISSING FILE: {fpath}")
            continue
        audio_files.append(os.path.abspath(fpath))
    
    print(f"Found {len(audio_files)} wav files.")
    
    try:
        audio_segments = []
        for f in audio_files:
            seg = AudioSegment.from_wav(f)
            audio_segments.append(seg)
        
        valid_segments = [seg for seg in audio_segments if len(seg) > 50]
        print(f"Loaded {len(audio_segments)} segments, {len(valid_segments)} are > 50ms.")
        
        print("Concatenating...")
        combined_audio = concatenate_audio(valid_segments, crossfade_ms=50)
        
        print("Exporting...")
        combined_audio.export("test_final.mp3", format="mp3")
        print("Success!")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"LỖI: {e}")

if __name__ == "__main__":
    main()
