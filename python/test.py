from editor_ui import  probe_duration_sec, get_video_info
import cv2
fps = 25
trans_path = "D:\\FunnyVideo\\Channels\\channel1\\Transition.mov"
anime2path = "D:\\FunnyVideo\\Main_clips\\animals\\video11.mp4"
trans_duration_s = probe_duration_sec(trans_path)
trans_frames = int(round(trans_duration_s * fps))
vide_in = get_video_info(anime2path)

def get_fps_opencv(video_path):
    video = cv2.VideoCapture(video_path)
    if not video.isOpened():
        print("Không thể mở video!")
        return None

    fps = video.get(cv2.CAP_PROP_FPS)
    video.release()  # Đóng video sau khi đọc
    return fps

print(get_fps_opencv(trans_path))



