import json
import cv2
from PIL import Image
import subprocess
from consts import *

def read_all_folder_name(folder_path):
    try:
        all_entries = os.listdir(folder_path)
        # Filter for only files
        file_names = [entry for entry in all_entries if os.path.isdir(os.path.join(folder_path, entry))]
        return file_names
    except:
        print(f"Không tìm thấy thư mục {folder_path}")
def read_all_file_name(folder_path):
    try:
        all_entries = os.listdir(folder_path)
        # Filter for only files
        file_names = [entry for entry in all_entries if os.path.isfile(os.path.join(folder_path, entry))]
        return file_names
    except:
        print(f"Không tìm thấy thư mục {folder_path}")
def load_channel_path(channel_name):
    channel_path = os.path.join(CHANNELS_DIR, channel_name)
    if not os.path.exists(channel_path):
        raise FileNotFoundError(f"Kênh '{channel_name}' chưa tồn tại trong Channels/.")
    return channel_path
def load_history_folder(channel_name):
    channel_path = os.path.join(CHANNELS_DIR, channel_name)
    if not os.path.exists(channel_path):
        raise FileNotFoundError(f"Kênh '{channel_name}' chưa tồn tại trong Channels/.")
    history_folder_path = os.path.join(channel_path, HISTORY_IN_CHANNEL_FOLDER)
    os.makedirs(history_folder_path, exist_ok=True)
    return history_folder_path
def read_json_file_content(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception:
        return []
def get_video_info(file_path):
    """
    Lấy:
    - duration (giây)
    - thumbnail (đường dẫn)
    - width, height của video
    """
    try:
        video = cv2.VideoCapture(file_path)
        if not video.isOpened():
            return 0, None, 0, 0

        # Lấy kích thước video
        width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Lấy thời lượng
        frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = video.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps if fps > 0 else 0

        # Tạo thumbnail từ frame đầu tiên
        ret, frame = video.read()
        thumb_path = None
        if ret:
            TEMP_DIR.mkdir(exist_ok=True)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail(THUMBNAIL_SIZE)

            base_filename = os.path.basename(file_path)
            thumb_filename = f"thumb_{base_filename}.png"
            thumb_path = TEMP_DIR / thumb_filename
            img.save(thumb_path)

        video.release()
        return duration, str(thumb_path), width, height

    except Exception as e:
        print(f"Lỗi khi xử lý video {file_path}: {e}")
        return 0, None, 0, 0
def get_pixel_aspect_ratio(file_path):
    """
    Trả về pixel aspect ratio (float)
    Mặc định = 1.0 nếu không xác định
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=sample_aspect_ratio",
            "-of", "json",
            file_path
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        data = json.loads(result.stdout)
        sar = data["streams"][0].get("sample_aspect_ratio", "1:1")

        if sar and sar != "0:1":
            num, den = sar.split(":")
            return float(num) / float(den)

    except Exception:
        pass

    return 1.0
