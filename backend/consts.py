import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMP_DIR = PROJECT_ROOT / "Temp"
THUMBNAIL_SIZE = (160, 90)  # Kích thước thumbnail (rộng, cao)
PIXELS_PER_SECOND = 50  # Giữ lại để vẽ timeline
CHANNELS_DIR = PROJECT_ROOT / "Channels"
MAIN_CLIPS_DIR = os.path.join(PROJECT_ROOT, "Main_clips")
OUT_DIR = PROJECT_ROOT / "Output"
HISTORY_IN_CHANNEL_FOLDER = "history"


CODEC_NAME = 'Apple ProRes 422'