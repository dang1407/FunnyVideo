import datetime
import random
import subprocess
import json
import os
from tkinter import messagebox

def get_clip_duration(clip_path: str) -> float:
    """
    Dùng ffprobe để lấy thời lượng clip (tính bằng giây).
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=duration",
                "-of", "json", clip_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        info = json.loads(result.stdout)
        duration = float(info["streams"][0]["duration"])
        return duration
    except Exception as e:
        print(f"Lỗi khi đọc thời lượng clip: {clip_path} ({e})")
        return 0.0


def select_clips(topic: str, target_time: float, used_videos: list) -> list:
    """
    Duyệt thư mục Main_clips/<topic> và chọn các clip ngẫu nhiên, bỏ qua các clip đã dùng.
    Tổng thời lượng ≥ target_time (cho phép thêm 3 phút).

    Args:
        topic (str): Tên chủ đề (ví dụ "animal")
        target_time (float): Thời lượng mục tiêu (giây)
        used_videos (list): Danh sách các clip đã dùng

    Returns:
        list[dict]: Danh sách clip được chọn (path + duration)
    """
    base_dir = os.path.join("..", "Main_clips", topic)
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Không tìm thấy thư mục chủ đề: {base_dir}")

    # Lấy tất cả file video trong thư mục
    all_clips = [
        os.path.join(base_dir, f)
        for f in os.listdir(base_dir)
        if f.lower().endswith((".mp4", ".mov", ".mkv"))
    ]
    if used_videos and isinstance(used_videos[0], dict):
        used_video_paths = [v["path"] for v in used_videos if "path" in v]
    else:
        used_video_paths = used_videos or []

    # Loại bỏ clip đã dùng
    available_clips = [clip for clip in all_clips if clip not in used_video_paths]
    if not available_clips:
        messagebox.showerror("Lỗi", "Không còn clip mới để chọn!")

    # Chọn ngẫu nhiên cho đến khi đủ thời lượng
    selected = []
    total_duration = 0.0
    max_duration = target_time + 180  # +3 phút

    while total_duration < target_time and available_clips:
        clip = random.choice(available_clips)
        duration = get_clip_duration(clip)
        if duration <= 0:
            available_clips.remove(clip)
            continue

        selected.append({"path": clip, "duration": duration})
        total_duration += duration
        available_clips.remove(clip)

        if total_duration >= max_duration:
            break

    print(f"Đã chọn {len(selected)} clip, tổng thời lượng ~ {round(total_duration/60, 2)} phút")
    return selected

def save_used_videos(used_videos: list, file_path="used_videos.json"):
    """
    Lưu danh sách clip đã dùng vào file JSON.
    Nếu file đã tồn tại, hàm sẽ đọc danh sách cũ và chỉ thêm clip mới (tránh trùng lặp).
    Hỗ trợ cả 2 dạng:
        - list[str]
        - list[dict] có key "path"
    """
    # Đọc file cũ nếu có
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                existing_videos = json.load(f)
        except json.JSONDecodeError:
            existing_videos = []
    else:
        existing_videos = []

    # Chuẩn hoá về danh sách path string
    def extract_paths(videos):
        if not videos:
            return []
        if isinstance(videos[0], dict):
            return [v["path"] for v in videos if "path" in v]
        return videos

    existing_paths = set(extract_paths(existing_videos))
    new_paths = extract_paths(used_videos)

    # Thêm clip mới chưa có trong danh sách cũ
    updated_paths = list(existing_paths.union(new_paths))

    # Ghi lại file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(updated_paths, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã lưu {len(updated_paths)} clip vào {file_path}")

def save_render_history(used_videos: list, channel_path: str):
    os.makedirs(channel_path, exist_ok=True)  # đảm bảo thư mục tồn tại

    date_now = datetime.datetime.now()
    file_folder = f"history\\{date_now.year}\\{date_now.month}"
    folder_path = os.path.join(channel_path, file_folder)
    os.makedirs(folder_path, exist_ok=True)
    file_name = f"{date_now.year}_{date_now.month}_{date_now.day}.json"
    file_path = os.path.join(folder_path, file_name)

    # Nếu file đã tồn tại, đọc dữ liệu cũ rồi nối thêm
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
    else:
        data = []

    cleaned_clips = []
    for clip in used_videos:
        cleaned = {k: v for k, v in clip.items() if k != "var"}
        # Nếu bạn cần biết clip có selected hay không thì có thể thêm:
        # cleaned["selected"] = clip["var"].get()
        cleaned["var"] = clip["var"].get()
        cleaned_clips.append(cleaned)

    entry = {
        "datetime": date_now.strftime("%Y-%m-%d %H:%M:%S"),
        "clips": cleaned_clips
    }
    data.append(entry)

    # Ghi đè lại file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã lưu lịch sử render: {file_path}")
