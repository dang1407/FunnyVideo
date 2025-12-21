import tkinter as tk
import customtkinter as ctk
import platform
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES
import json
import subprocess
import threading
from python.clip_selector import save_used_videos, save_render_history
from DragSortHelper import DDList, ClipItem
from python.consts import *
from python.helper import load_channel_path, get_video_info
from python.render_helper import build_and_render_from_config, generate_ffmpeg_command

try:
    from Tkinter import Tk, IntVar, Label, Entry, Button
    import tkMessageBox as messagebox
    from Tkconstants import *
except ImportError:
    from tkinter import Tk, IntVar, Label, Entry, Button, messagebox
    from tkinter.constants import *

# --- Hằng số và đường dẫn ---


class EditorWindow(ctk.CTkToplevel):
    def __init__(self, parent, channel_name):
        super().__init__(parent)
        self.channel_name = channel_name
        self.title(f"Video Editor - Kênh: {self.channel_name}")
        width = 1200
        height = 700
        # Điều chỉnh vị trí cao hơn một chút để tránh bị tụt xuống dưới
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = max(20, (self.winfo_screenheight() // 2) - (height // 2) - 30)
        self.geometry(f'{width}x{height}+{x}+{y}')
        # Đảm bảo cửa sổ editor luôn ở trên cửa sổ main
        self.attributes('-topmost', True)
        self.after(100, lambda: self.attributes('-topmost', False))

        self.imported_clips = []  # List các dictionary chứa thông tin clip
        self.timeline_clips = []
        self._image_references = []
        self.drag_source_index = None  # Lưu vị trí clip đang được kéo
        # --- Thêm cho phát video ---
        self.current_player = None  # Thread phát video
        self.is_playing = False
        self.current_video_path = None
        self.current_frame_label = None  # Label hiển thị video
        self.current_cap = None
        self.play_button = None  # Nút Play/Pause
        # --------------------------------
        self._create_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_closing(self):
        self._stop_current_video()
        if TEMP_DIR.exists():
            for f in TEMP_DIR.glob("thumb_*.png"):
                try:
                    os.remove(f)
                except:
                    pass
        self.master.deiconify()
        self.destroy()

    def _create_layout(self):
        # We use a simple grid layout or pack.
        # Top: Media Bin. Bottom: (Maybe Controls or Timeline if added later)
        # Original used PanedWindow. We can use CTkScrollableFrame for the main area.

        # Main Container
        main_container = ctk.CTkFrame(self)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Left Panel (Media Bin)
        # In original, media bin was on left?, wait.
        # Original: PanedWindow vertical. top_pane horizontal.
        # media_container in top pane.

        # Let's simplify: A big frame for media sorting.
        # And a control panel on right or top.

        # Control Panel
        control_panel = ctk.CTkFrame(main_container, height=50)
        control_panel.pack(fill="x", side="bottom", padx=5, pady=5)

        ctk.CTkButton(control_panel, text="Import Clips...", command=self._import_clips_from_dialog).pack(side="left",
                                                                                                          padx=10,
                                                                                                          pady=10)
        ctk.CTkButton(control_panel, text="Render Video", command=self._render_video, fg_color="green").pack(
            side="left", padx=10, pady=10)

        self.duration_label = ctk.CTkLabel(control_panel, text="Duration: 0 (s)", font=("Arial", 14, "bold"))
        self.duration_label.pack(side="right", padx=20)

        # Media Bin Area
        media_group = ctk.CTkFrame(main_container)
        media_group.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(media_group, text="Media Imported (Drag & Drop to Reorder)", font=("Arial", 12)).pack(anchor="w",
                                                                                                           padx=10,
                                                                                                           pady=5)

        # Scrollable Frame for Media Items
        self.media_items_frame = ctk.CTkScrollableFrame(media_group, label_text="Clips")
        self.media_items_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Register Drop Target (TkinterDnD) on the list frame
        # Note: TkinterDnD registration usually works on widgets that have a window ID.
        # CTkScrollableFrame -> ._parent_frame or similar.
        # Safe to register on the outer frame.
        self.media_items_frame.drop_target_register(DND_FILES)
        self.media_items_frame.dnd_bind('<<Drop>>', self._handle_drop_import)

    def _raw_media_bin(self):
        # Calculate duration
        total_selected_duration = 0
        number_selected_clips = 0
        for i, clip in enumerate(self.imported_clips):
            if clip["var"].get():
                number_selected_clips += 1
                try:
                    total_selected_duration += float(clip["duration"])
                except:
                    pass
        self.duration_label.configure(text=f"Duration: {total_selected_duration:.2f} (s)")

        # Clear existing
        for widget in self.media_items_frame.winfo_children():
            widget.destroy()

        self._image_references = []

        # Use DDList
        def on_reorder(new_order):
            self.imported_clips = new_order
            # Update display ??? Or just internal list?
            # Original code updated internal list.

        # Create DDList inside the scrollable frame
        # The scrollable frame will handle scrolling if DDList is large.
        # But DDList is absolute positioning. We need to set its size.
        # DDList (Frame) height grows with items. CTkScrollableFrame adjusts scrollbar.

        self.ddlist = DDList(self.media_items_frame, item_width=600, item_height=80,
                             offset_x=10, offset_y=10, gap=10, reorder_callback=on_reorder,
                             fg_color="transparent")  # transparent to blend with scrollable frame
        self.ddlist.pack(fill="x", expand=False)  # Grow with content height

        # Add items
        for clip in self.imported_clips:
            # We must pass 'clip' as value to ClipItem
            # ClipItem expects (master, clip, ...)
            item = ClipItem(self.ddlist, clip, 600, 80, self)
            self.ddlist.add_item(item)

    def render_clip_list(self):
        self._raw_media_bin()
    # --- CÁC HÀM XỬ LÝ SỰ KIỆN ---
    def _import_clips_from_dialog(self):
        initial_dir = PROJECT_ROOT / "Main_clips"
        file_paths = filedialog.askopenfilenames(title="Chọn video clips", initialdir=initial_dir,
                                                 filetypes=[("Video", "*.mp4 *.mov *.avi")])
        # Đảm bảo cửa sổ editor luôn ở trên sau khi đóng dialog
        self.lift()
        self.focus_force()
        if file_paths: self._add_files_to_media_list(file_paths)

    def _handle_drop_import(self, event):
        if event.data:
            # TkinterDnD may return braced strings for spaces
            file_paths = self.tk.splitlist(event.data)
            if file_paths: self._add_files_to_media_list(file_paths)

    def _add_files_to_media_list(self, file_paths):
        newly_added = False
        for path in file_paths:
            normalized_path = os.path.normpath(path)
            if any(c['path'] == normalized_path for c in self.imported_clips): continue

            if os.path.isfile(normalized_path):
                duration, thumb_path = get_video_info(normalized_path)
                if duration > 0 and thumb_path:
                    # In CTk, BooleanVar is ctk.BooleanVar or tk.BooleanVar?
                    # CTkCheckBox uses tk.BooleanVar or ctk.BooleanVar.
                    # Prefer ctk.BooleanVar if available?
                    # ctk doesn't have BooleanVar export? It uses tkinter.Variable.
                    self.imported_clips.append({
                        "path": normalized_path,
                        "duration": duration,
                        "thumb_path": thumb_path,
                        "var": ctk.BooleanVar(value=True) # Default true? Original was false then true?
                    })
                    newly_added = True

        if newly_added: self.render_clip_list()

    # def _on_drag_start(self, event):
    #     """Khi bắt đầu kéo một item."""
    #     # Tìm frame cha (item_frame) của widget đã trigger sự kiện
    #     widget = event.widget
    #     while not hasattr(widget, 'clip_index'):
    #         widget = widget.master
    #     self.drag_source_index = widget.clip_index
    #     return 'move'  # Trả về hành động
    #
    # def _on_drop_reorder(self, event):
    #     """Khi thả một item vào một item khác."""
    #     if self.drag_source_index is None: return
    #
    #     widget = event.widget
    #     while not hasattr(widget, 'clip_index'):
    #         widget = widget.master
    #     drop_target_index = widget.clip_index
    #
    #     # Sắp xếp lại list
    #     dragged_item = self.imported_clips.pop(self.drag_source_index)
    #     self.imported_clips.insert(drop_target_index, dragged_item)
    #
    #     self.drag_source_index = None  # Reset
    #     self._redraw_media_bin()  # Vẽ lại với thứ tự mới

    def _add_selected_to_timeline(self):
        self.timeline_clips.clear()  # Xóa timeline cũ
        for clip in self.imported_clips:
            if clip["var"].get():  # Nếu checkbox được chọn
                self.timeline_clips.append(clip)
    
    def _parse_timecode(self, tc: str) -> float:
        """Chuyển 'HH:MM:SS:FF' (frame cuối cùng) thành giây."""
        try:
            h, m, s, f = map(int, tc.split(":"))
            fps = 25  # default fallback
            return h * 3600 + m * 60 + s + f / fps
        except:
            return 0.0

    def _render_video(self):
        config = load_channel_config(self.channel_name)
        clip_to_render = []
        for clip in self.imported_clips:
            if clip["var"].get():
                clip_to_render.append(clip)
        build_editly_config(self.channel_name, config=config, selected_clips=clip_to_render, output_path=OUT_DIR / self.channel_name)
        # Thêm các clip đã dùng vào used_jsons
        used_videos_path = get_used_videos_path(self.channel_name)
        save_used_videos(clip_to_render, used_videos_path)
        save_render_history(self.imported_clips, load_channel_path(self.channel_name))
    def _detect_gpu(self):
        """Phát hiện loại GPU có sẵn"""
        try:
            # Kiểm tra NVIDIA
            result = subprocess.run(
                ["nvidia-smi"], 
                capture_output=True, 
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                print("Phát hiện NVIDIA GPU")
                return "nvidia"
        except:
            pass
        
        try:
            # Kiểm tra AMD
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if "h264_amf" in result.stdout:
                print("Phát hiện AMD GPU")
                return "amd"
        except:
            pass
        
        try:
            # Kiểm tra Intel QuickSync
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if "h264_qsv" in result.stdout:
                print("Phát hiện Intel GPU")
                return "intel"
        except:
            pass
        
        print("Không phát hiện GPU, sử dụng CPU")
        return "cpu"

    def _get_video_duration(self, video_path):
        """Lấy độ dài video bằng ffprobe (giây)"""
        try:
            result = subprocess.run([
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ], capture_output=True, text=True, check=True)
            
            return float(result.stdout.strip())
        except Exception as e:
            print(f"Lỗi khi lấy duration của {video_path}: {e}")
            return 0

    def _stop_current_video(self):
        self.is_playing = False
        if self.current_cap:
            self.current_cap.release()
            self.current_cap = None

    def _open_in_default_player(self, path):
        open_file_cross_platform(path)

    def toggle_select_clip(self, current_clip_index):
        # Refresh duration label
        total = 0
        for clip in self.imported_clips:
            if clip["var"].get():
                try: total += float(clip["duration"])
                except: pass
        self.duration_label.configure(text=f"Duration: {total:.2f} (s)")

    def change_clip_index_by_offset(self, current_clip_index, offset):
        temp_clips = []
        number_clips = len(self.imported_clips)
        for index, clip in enumerate(self.imported_clips):
            if index < current_clip_index - offset:
                temp_clips.append(clip)
        if(offset > 0):
            temp_clips.append(self.imported_clips[current_clip_index])
            temp_clips.append(self.imported_clips[current_clip_index - offset])
        else:
            temp_clips.append(self.imported_clips[current_clip_index - offset])
            temp_clips.append(self.imported_clips[current_clip_index])

        for index, clip in enumerate(self.imported_clips):
            if index > current_clip_index - offset and index != current_clip_index:
                temp_clips.append(clip)
        self.imported_clips = temp_clips
        self._raw_media_bin()

    def format_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
def probe_duration_sec(video_path):
    """Dùng ffprobe để lấy thời lượng clip (giây)"""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        lines = out.decode().strip().splitlines()
        # Lấy dòng cuối cùng (thường chứa giá trị duration)
        duration_str = lines[-1].strip()
        return float(duration_str)
    except Exception as e:
        print(f"❌ Lỗi khi probe video {video_path}: {e}")
        return 0.0
def tc_to_frames(tc: str, fps: int) -> int:
    """HH:MM:SS:FF -> frames"""
    hh, mm, ss, ff = map(int, tc.split(":"))
    return (hh * 3600 + mm * 60 + ss) * fps + ff

def frames_to_seconds(frames: int, fps: int) -> float:
    return frames / float(fps)

def tc_to_seconds(tc: str, fps: int) -> float:
    return frames_to_seconds(tc_to_frames(tc, fps), fps)


def build_editly_config(channel_name: str, config: dict, selected_clips: list, output_path: str) -> dict:
    import os, json, datetime
    from typing import Optional

    width, height = 1920, 1080
    fps = int(config.get("fps", 30))
    gap_tc = config.get("gap", "00:00:00:00")
    pre_tc = config.get("preoverlap", "00:00:00:00")
    logo_file = config.get("logo", "logo.png")
    trans_file = config.get("transition", "transition.mov")
    blur_conf_str = config.get("blur", 1)
    try:
        blur_conf = float(blur_conf_str)
    except:
        blur_conf = 0.0

    channel_dir = os.path.join(CHANNELS_DIR, channel_name)
    logo_path = os.path.join(channel_dir, logo_file)
    if not os.path.exists(logo_path):
        raise FileNotFoundError(f"Không thấy logo: {logo_path} (yêu cầu logo.png trong thư mục kênh)")

    # Transition
    trans_frames = 0
    trans_duration_s = 0.0
    trans_path = None
    if trans_file:
        trans_path = os.path.join(channel_dir, trans_file)
        if os.path.exists(trans_path):
            trans_duration_s = probe_duration_sec(trans_path)
            trans_frames = int(round(trans_duration_s * fps))
        else:
            raise FileNotFoundError(f"Đã khai báo transition nhưng thiếu file: {trans_path}")

    gap_s = tc_to_seconds(gap_tc, fps) if gap_tc else 0.0
    pre_f = tc_to_frames(pre_tc, fps) if pre_tc else 0
    pre_s = pre_f / fps

    clips_json = []
    audio_tracks = []

    def main_clip_layer(full_path: str, cut_from: float = 0.0, cut_to: Optional[float] = None):
        """
        Tạo layer cho 1 clip:
        Thứ tự layers (từ dưới lên trên):
        1. Video chính (nền)
        2. Logo (luôn hiển thị)
        3. Transition sẽ được append sau (cao nhất)
        """
        v_layer = {
            "type": "video",
            "path": full_path,
            "resizeMode": "contain-blur",
            "width": 1.0
        }
        if blur_conf > 0:
            v_layer["blur"] = blur_conf
        if cut_from and cut_from > 0:
            v_layer["cutFrom"] = cut_from
        if cut_to and cut_to > 0:
            v_layer["cutTo"] = cut_to

        logo_layer = {
            "type": "image-overlay",
            "path": logo_path,
            "position": "center",
            "width": 1.0
        }

        # Thứ tự: video nền trước, logo sau (transition sẽ append sau cùng)
        return {"layers": [v_layer, logo_layer]}

    def black_gap_clip(duration_s: float):
        return {
            "duration": duration_s,
            "layers": [
                {"type": "fill-color", "color": "#000000"},
                {"type": "image-overlay", "path": logo_path, "position": "center", "width": 1.0}
            ]
        }

    if not selected_clips:
        raise RuntimeError("Không chọn được clip nào!")

    # --- MỚI: xử lý dễ hiểu, theo thứ tự timeline ---
    all_duration = 0.0

    # Thêm clip đầu tiên (chưa có transition trước nó)
    first = selected_clips[0]
    first_full = first["path"] if os.path.isabs(first["path"]) else os.path.join(MAIN_CLIPS_DIR, first["path"])
    first_dur = float(first["duration"])
    first_clip_obj = main_clip_layer(first_full, 0.0, first_dur)
    clips_json.append(first_clip_obj)
    all_duration += first_dur

    # Duyệt qua từng transition giữa clip i (A) và clip i+1 (B)
    for i in range(len(selected_clips) - 1):
        A = selected_clips[i]
        B = selected_clips[i + 1]

        # Thông tin clip A (đã tồn tại là clips_json[-1])
        clipA_path = A["path"] if os.path.isabs(A["path"]) else os.path.join(MAIN_CLIPS_DIR, A["path"])
        clipA_dur = float(A["duration"])

        # Thông tin clip B
        clipB_path = B["path"] if os.path.isabs(B["path"]) else os.path.join(MAIN_CLIPS_DIR, B["path"])
        clipB_dur = float(B["duration"])

        # --- 1) Thêm layer transition phần "pre" vào clip A (đè cuối clip A) ---
        if trans_frames > 0:
            trans_pre_start_in_A = clipA_dur - pre_s
            # append layer vào clip A (đã push trước đó)
            clips_json[-1]["layers"].append({
                "type": "video",
                "path": trans_path,
                "start": trans_pre_start_in_A,
                "stop": clipA_dur,
                "cutFrom": 0.0,
                "cutTo": min(pre_s, trans_duration_s),
                "resizeMode": "contain",
                "mixVolume": 1
            })

            # Thêm audio track cho toàn bộ transition (bắt đầu tại thời điểm transition bắt đầu trên timeline)
            audio_tracks.append({
                "path": trans_path,
                "mixVolume": 1,
                "cutFrom": 0.0,
                "cutTo": trans_duration_s,
                "start": all_duration - clipA_dur + trans_pre_start_in_A  # all_duration hiện tại là đã cộng clipA_dur
            })

        # --- 2) Gap đen (nếu có) ---
        if gap_s > 0:
            gap_clip = black_gap_clip(gap_s)
            if trans_frames > 0:
                # transition phần giữa (sau pre_s)
                gap_clip["layers"].append({
                    "type": "video",
                    "path": trans_path,
                    "start": 0.0,  # chạy từ đầu đoạn gap trên transition file (cutted bằng cutFrom)
                    "stop": gap_s,
                    "cutFrom": min(pre_s, trans_duration_s),
                    "cutTo": min(pre_s + gap_s, trans_duration_s),
                    "resizeMode": "contain",
                    "mixVolume": 1
                })
            clips_json.append(gap_clip)
            all_duration += gap_s

        # --- 3) Clip B với phần "post" transition đè lên đầu clip B ---
        clipB_obj = main_clip_layer(clipB_path, 0.0, clipB_dur)
        if trans_frames > 0:
            post_s = max(0.0, trans_duration_s - pre_s - gap_s)
            # phần đầu của clip B bị đè bởi phần còn lại của transition
            clipB_obj["layers"].append({
                "type": "video",
                "path": trans_path,
                "start": 0.0,
                "stop": min(post_s, clipB_dur),
                "cutFrom": min(pre_s + gap_s, trans_duration_s),
                "cutTo": trans_duration_s,
                "resizeMode": "contain",
                "mixVolume": 1
            })
            # lưu ý: audio track đã thêm ở phần A (vì mình chèn 1 audioTracks cho toàn bộ transition),
            # không cần thêm thêm audioTracks ở đây để tránh trùng.

        clips_json.append(clipB_obj)
        all_duration += clipB_dur

    # Nếu chỉ có 1 clip thì all_duration đã cộng ở trên; nếu nhiều clip thì all_duration đã cộng đủ.

    # ============================================================
    # CẤU HÌNH GPU ENCODING - TỐI ƯU TỐC ĐỘ MÀ KHÔNG MẤT CHẤT LƯỢNG
    # ============================================================

    # Tự động detect GPU và chọn encoder phù hợp
    # Ưu tiên: NVIDIA (h264_nvenc) > AMD (h264_amf) > Intel (h264_qsv) > CPU (libx264)

    ffmpeg_params = []

    # Các tùy chọn tối ưu cho GPU encoding
    gpu_configs = {
        # NVIDIA GPU (tốt nhất, hỗ trợ rộng rãi)
        "nvidia": {
            "codec": "h264_nvenc",
            "params": [
                "-preset", "p7",  # preset chất lượng cao nhất (p1-p7, p7 = slow/high quality)
                "-tune", "hq",  # tune cho high quality
                "-rc", "vbr",  # variable bitrate (tốt hơn cbr cho chất lượng)
                "-cq", "19",  # constant quality (18-23, càng thấp càng tốt, 19 = rất tốt)
                "-b:v", "20M",  # bitrate tham khảo cho VBR
                "-maxrate", "25M",  # max bitrate
                "-bufsize", "50M",  # buffer size
                "-profile:v", "high",  # H.264 profile cao
                "-rc-lookahead", "32",  # lookahead frames (tối ưu chất lượng)
                "-spatial_aq", "1",  # spatial adaptive quantization
                "-temporal_aq", "1",  # temporal adaptive quantization
                "-bf", "3",  # B-frames
                "-g", str(fps * 2),  # GOP size (2 giây)
            ]
        },

        # AMD GPU
        "amd": {
            "codec": "h264_amf",
            "params": [
                "-quality", "quality",  # quality mode thay vì speed
                "-rc", "vbr_latency",  # VBR cho chất lượng tốt
                "-qp_i", "18",  # QP cho I-frames
                "-qp_p", "20",  # QP cho P-frames
                "-qp_b", "22",  # QP cho B-frames
                "-b:v", "20M",
                "-maxrate", "25M",
                "-bufsize", "50M",
                "-profile:v", "high",
                "-bf", "3",
                "-g", str(fps * 2),
            ]
        },

        # Intel GPU (Quick Sync)
        "intel": {
            "codec": "h264_qsv",
            "params": [
                "-preset", "veryslow",  # preset chất lượng cao
                "-global_quality", "18",  # quality (15-23, thấp hơn = tốt hơn)
                "-look_ahead", "1",  # enable lookahead
                "-look_ahead_depth", "40",  # lookahead depth
                "-b:v", "20M",
                "-maxrate", "25M",
                "-bufsize", "50M",
                "-profile:v", "high",
                "-bf", "3",
                "-g", str(fps * 2),
            ]
        },

        # CPU fallback (nếu không có GPU hoặc GPU không hỗ trợ)
        "cpu": {
            "codec": "libx264",
            "params": [
                "-preset", "slow",  # slow preset cho chất lượng tốt
                "-crf", "18",  # constant rate factor (15-23, 18 = rất tốt)
                "-profile:v", "high",
                "-level", "4.2",
                "-bf", "3",
                "-g", str(fps * 2),
                "-movflags", "+faststart",  # web optimization
                "-pix_fmt", "yuv420p",  # compatibility
            ]
        }
    }

    # Lấy cấu hình từ config hoặc tự động detect
    gpu_type = config.get("gpu_type", "auto").lower()

    if gpu_type == "auto":
        # Tự động detect (bạn có thể implement hàm detect GPU)
        # Ở đây mặc định thử NVIDIA trước
        gpu_type = "nvidia"
        print(f"🔍 Tự động chọn GPU encoder: {gpu_type}")

    # Chọn cấu hình phù hợp, fallback về CPU nếu không có
    selected_config = gpu_configs.get(gpu_type, gpu_configs["cpu"])

    ffmpeg_params.extend(["-c:v", selected_config["codec"]])
    ffmpeg_params.extend(selected_config["params"])

    # Audio encoding (giữ chất lượng cao)
    ffmpeg_params.extend([
        "-c:a", "aac",
        "-b:a", "320k",  # audio bitrate cao
        "-ar", "48000",  # sample rate
        "-ac", "2",  # stereo
    ])

    # Các tùy chọn chung tối ưu tốc độ
    ffmpeg_params.extend([
        "-threads", "0",  # auto-detect số threads
        "-movflags", "+faststart",  # tối ưu streaming
    ])

    print(f"🎬 GPU Encoding: {selected_config['codec']}")
    print(f"⚡ FFmpeg params: {' '.join(ffmpeg_params)}")

    # Build spec
    output_file_name = f"{channel_name}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.mp4"
    spec = {
        "outPath": os.path.join(output_path, output_file_name),
        "width": width,
        "height": height,
        "fps": fps,
        "keepSourceAudio": True,
        "defaults": {"transition": None},
        "clips": clips_json,
        "audioTracks": audio_tracks,
        "ffmpegOptions": {
            "outputArgs": ffmpeg_params
        }
    }

    # Lưu file JSON
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else output_path, exist_ok=True)
    temp_dir_for_channel = os.path.join(TEMP_DIR, channel_name)
    os.makedirs(temp_dir_for_channel, exist_ok=True)
    config_filename = f"{channel_name}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    config_path = os.path.join(temp_dir_for_channel, config_filename)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã lưu cấu hình editly: {config_path}")

    # Gọi render
    start_render(config_path, selected_clips, channel_name, config)
    return spec

def render_video(config_path, selected_clips, channel_name, channel_config):
    try:
        generate_ffmpeg_command(config_path)
        os.remove(config_path)
        save_used_videos(selected_clips, get_used_videos_path(channel_name))
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi render video bằng editly: {e}")
    except FileNotFoundError:
        print("⚠️ Lệnh 'editly' chưa được cài đặt hoặc không có trong PATH!")

def start_render(config_path, selected_clips, channel_name, channel_config):
    # Tạo luồng riêng để không làm treo UI
    thread = threading.Thread(target=render_video, args=(config_path,selected_clips,channel_name,channel_config,))
    thread.start()
def load_channel_config(channel_name):
    """Đọc config.json trong thư mục kênh"""
    print(f"🔍 Đang tải cấu hình cho kênh: {channel_name}")
    channel_path = load_channel_path(channel_name)

    config_path = os.path.join(channel_path, "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Kênh '{channel_name}' thiếu file config.json.")

    # Đọc config
    config = load_json(config_path)

    # Kiểm tra các file quan trọng (logo + transition)
    logo_path = os.path.join(channel_path, config.get("logo", ""))
    trans_path = os.path.join(channel_path, config.get("transition", ""))

    missing = []
    if not os.path.exists(logo_path):
        missing.append("logo.png")
    if not os.path.exists(trans_path):
        missing.append("transition.mov")

    if missing:
        print(f"⚠️  Thiếu file trong kênh {channel_name}: {', '.join(missing)}")

    # In thông tin cấu hình ra màn hình
    print(f"\n📂 Cấu hình kênh: {channel_name}")
    for k, v in config.items():
        print(f"  {k}: {v}")

    return config
def load_json(file_path, default=None):
    """Đọc JSON an toàn"""
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def get_used_videos_path(channel_name):
    channel_path = load_channel_path(channel_name)
    return os.path.join(channel_path, "used_videos.json")
def load_used_videos(channel_name):
    used_video_path = get_used_videos_path(channel_name)
    if not os.path.exists(used_video_path):
        return []
    try:
        with open(used_video_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Đảm bảo trả về list string
            if isinstance(data, list):
                return data
            return []
    except Exception:
        return []
def open_file_cross_platform(path):
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", path])
        else:  # Linux, Ubuntu, v.v.
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"Lỗi khi mở file: {e}")