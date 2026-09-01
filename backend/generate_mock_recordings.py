import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Paths
BACKEND_DIR = Path("D:/VMS/backend").resolve()
RECORDINGS_DIR = BACKEND_DIR / "recordings"
FFMPEG_PATH = Path("D:/VMS/ffmpeg/ffmpeg.exe").resolve()
TEMPLATE_PATH = BACKEND_DIR / "temp_template.mp4"

print(f"Backend directory: {BACKEND_DIR}")
print(f"Recordings directory: {RECORDINGS_DIR}")
print(f"FFmpeg path: {FFMPEG_PATH}")
print(f"Template path: {TEMPLATE_PATH}")

# 1. Generate 1-hour template if not exists
if not TEMPLATE_PATH.exists():
    print("Generating 1-hour template video (1 fps, 160x120, black screen)...")
    ffmpeg_cmd = [
        str(FFMPEG_PATH),
        "-y", # overwrite if exists
        "-f", "lavfi",
        "-i", "color=c=black:s=160x120:d=3600",
        "-r", "1",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(TEMPLATE_PATH)
    ]
    
    print(f"Running command: {' '.join(ffmpeg_cmd)}")
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg failed with code {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
        exit(1)
    else:
        print("Template file generated successfully!")

# Streams
streams = ["Eagle_192.168.4.242", "Eagle_192.168.4.243", "Eagle_192.168.4.244"]

# Today and yesterday dates
dates_to_generate = [
    datetime.now().date(),
    (datetime.now() - timedelta(days=1)).date()
]

print(f"Target dates: {[d.isoformat() for d in dates_to_generate]}")

# 2. Process each stream
for stream in streams:
    stream_dir = RECORDINGS_DIR / stream
    stream_dir.mkdir(parents=True, exist_ok=True)
    
    # Delete all existing mp4 files
    print(f"Cleaning existing recordings in: {stream_dir}")
    for file in list(stream_dir.glob("*.mp4")):
        try:
            file.unlink()
        except Exception as e:
            print(f"Error deleting {file.name}: {e}")
            
    # Generate 24 files per date
    for d in dates_to_generate:
        for hour in range(24):
            # Filename format: YYYY-MM-DD_HH-MM-SS.mp4
            timestamp_str = f"{d.strftime('%Y-%m-%d')}_{hour:02d}-00-00.mp4"
            dest_path = stream_dir / timestamp_str
            
            try:
                shutil.copy2(TEMPLATE_PATH, dest_path)
                # Set access and modification time to match the timestamp
                dt = datetime(d.year, d.month, d.day, hour, 0, 0)
                os.utime(dest_path, (dt.timestamp(), dt.timestamp()))
            except Exception as e:
                print(f"Error copying to {timestamp_str}: {e}")

# Cleanup template from backend folder
if TEMPLATE_PATH.exists():
    try:
        TEMPLATE_PATH.unlink()
        print("Temporary template cleaned up.")
    except Exception as e:
        print(f"Failed to cleanup template: {e}")

print("Mock recordings generation complete! 24 hours of recordings created per camera.")
