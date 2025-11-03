import tkinter as tk
from email.policy import default
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import os
import cv2
from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES
import json
import subprocess
from datetime import timedelta
import threading
import datetime
from typing import Optional

from python.clip_selector import save_used_videos

# --- Hằng số và đường dẫn ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMP_DIR = PROJECT_ROOT / "Temp"
THUMBNAIL_SIZE = (160, 90)  # Kích thước thumbnail (rộng, cao)
PIXELS_PER_SECOND = 50  # Giữ lại để vẽ timeline
CHANNELS_DIR = PROJECT_ROOT / "Channels"
MAIN_CLIPS_DIR = os.path.join(PROJECT_ROOT, "Main_clips")
OUT_DIR = PROJECT_ROOT / "Output"
def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_video_info(file_path):
    """Lấy thời lượng và tạo thumbnail cho video."""
    try:
        video = cv2.VideoCapture(file_path)
        if not video.isOpened(): return 0, None

        # Lấy thời lượng
        frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = video.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps if fps > 0 else 0

        # Tạo thumbnail từ khung hình đầu tiên
        ret, frame = video.read()
        thumb_path = None
        if ret:
            # Tạo thư mục Temp nếu chưa có
            TEMP_DIR.mkdir(exist_ok=True)

            # Chuyển đổi màu từ BGR (OpenCV) sang RGB (Pillow)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img.thumbnail(THUMBNAIL_SIZE)

            # Lưu thumbnail
            base_filename = os.path.basename(file_path)
            thumb_filename = f"thumb_{base_filename}.png"
            thumb_path = TEMP_DIR / thumb_filename
            img.save(thumb_path)

        video.release()
        return duration, str(thumb_path)
    except Exception as e:
        print(f"Lỗi khi xử lý video {file_path}: {e}")
        return 0, None


class EditorWindow(tk.Toplevel):
    def __init__(self, parent, channel_name):
        super().__init__(parent)
        self.channel_name = channel_name
        self.title(f"Video Editor - Kênh: {self.channel_name}")
        self.geometry("1200x700")

        self.imported_clips = []  # List các dictionary chứa thông tin clip
        self.timeline_clips = []
        self.drag_source_index = None  # Lưu vị trí clip đang được kéo

        self._create_menu()
        self._create_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_closing(self):
        # Dọn dẹp file thumbnail tạm
        if TEMP_DIR.exists():
            for f in TEMP_DIR.glob("thumb_*.png"):
                try:
                    os.remove(f)
                except OSError:
                    pass
        self.master.deiconify()
        self.destroy()

    def _create_menu(self):
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Import Clips...", command=self._import_clips_from_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Thoát", command=self._on_closing)
        menu_bar.add_cascade(label="File", menu=file_menu)

    def _create_layout(self):
        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True)
        top_pane = ttk.PanedWindow(main_pane, orient=tk.HORIZONTAL)
        main_pane.add(top_pane, weight=4)

        # --- Cột trái: Media Bin (với thumbnail và scroll) ---
        media_container = ttk.LabelFrame(top_pane, text="Media Imported", padding=5)
        top_pane.add(media_container, weight=1)

        # Thiết lập để kéo thả file vào khu vực này
        media_container.drop_target_register(DND_FILES)
        media_container.dnd_bind('<<Drop>>', self._handle_drop_import)

        # Tạo một canvas có thể cuộn
        self.media_canvas = tk.Canvas(media_container, borderwidth=0)
        scrollbar = ttk.Scrollbar(media_container, orient="vertical", command=self.media_canvas.yview)
        self.media_items_frame = ttk.Frame(self.media_canvas)  # Frame chứa các item

        self.media_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.media_canvas.pack(side="left", fill="both", expand=True)
        self.media_canvas.create_window((0, 0), window=self.media_items_frame, anchor="nw")

        def on_frame_configure(event): self.media_canvas.configure(scrollregion=self.media_canvas.bbox("all"))

        self.media_items_frame.bind("<Configure>", on_frame_configure)

        add_to_timeline_button = ttk.Button(media_container, text="Thêm các clip đã chọn vào Timeline ↓",
                                            command=self._add_selected_to_timeline)
        add_to_timeline_button.pack(side="top", fill="x", pady=5)

    def _redraw_media_bin(self):
        """Vẽ lại toàn bộ danh sách media clip."""
        # Xóa các widget cũ
        for widget in self.media_items_frame.winfo_children():
            widget.destroy()

        # Giữ một tham chiếu đến các đối tượng ảnh để tránh bị xóa
        self._image_references = []

        for i, clip in enumerate(self.imported_clips):
            # Tạo một frame cho mỗi item
            item_frame = ttk.Frame(self.media_items_frame, padding=5, relief="groove", borderwidth=1)
            item_frame.pack(fill="x", padx=5, pady=2)
            item_frame.clip_index = i  # Gán index để nhận biết khi kéo thả

            # Tải và hiển thị thumbnail
            img = Image.open(clip["thumb_path"])
            photo = ImageTk.PhotoImage(img)
            thumb_label = ttk.Label(item_frame, image=photo)
            thumb_label.pack(side="left", padx=5)
            thumb_label.image = photo  # Giữ tham chiếu
            self._image_references.append(photo)

            # Checkbox
            check = ttk.Checkbutton(item_frame, variable=clip["var"])
            check.pack(side="left", padx=5)

            # Tên file và thời lượng
            info_text = f"{os.path.basename(clip['path'])}\n[{format_time(clip['duration'])}]"
            info_label = ttk.Label(item_frame, text=info_text, justify="left")
            info_label.pack(side="left", fill="x", expand=True)

            # --- Kích hoạt Kéo-Thả để Sắp xếp ---
            for widget in [item_frame, thumb_label, info_label, check]:
                widget.dnd_bind('<<DragInitCmd>>', self._on_drag_start)
                widget.dnd_bind('<<Drop>>', self._on_drop_reorder)

    # --- CÁC HÀM XỬ LÝ SỰ KIỆN ---
    def _import_clips_from_dialog(self):
        initial_dir = PROJECT_ROOT / "Main_clips"
        file_paths = filedialog.askopenfilenames(title="Chọn video clips", initialdir=initial_dir,
                                                 filetypes=[("Video", "*.mp4 *.mov *.avi")])
        if file_paths: self._add_files_to_media_list(file_paths)

    def _handle_drop_import(self, event):
        file_paths = self.tk.splitlist(event.data)
        if file_paths: self._add_files_to_media_list(file_paths)

    def _add_files_to_media_list(self, file_paths):
        newly_added = False
        for path in file_paths:
            normalized_path = os.path.normpath(path)
            # Kiểm tra trùng lặp
            if any(c['path'] == normalized_path for c in self.imported_clips): continue

            if os.path.isfile(normalized_path):
                duration, thumb_path = get_video_info(normalized_path)
                if duration > 0 and thumb_path:
                    self.imported_clips.append({
                        "path": normalized_path,
                        "duration": duration,
                        "thumb_path": thumb_path,
                        "var": tk.BooleanVar(value=False)
                    })
                    newly_added = True

        if newly_added: self._redraw_media_bin()

    def _on_drag_start(self, event):
        """Khi bắt đầu kéo một item."""
        # Tìm frame cha (item_frame) của widget đã trigger sự kiện
        widget = event.widget
        while not hasattr(widget, 'clip_index'):
            widget = widget.master
        self.drag_source_index = widget.clip_index
        return 'move'  # Trả về hành động

    def _on_drop_reorder(self, event):
        """Khi thả một item vào một item khác."""
        if self.drag_source_index is None: return

        widget = event.widget
        while not hasattr(widget, 'clip_index'):
            widget = widget.master
        drop_target_index = widget.clip_index

        # Sắp xếp lại list
        dragged_item = self.imported_clips.pop(self.drag_source_index)
        self.imported_clips.insert(drop_target_index, dragged_item)

        self.drag_source_index = None  # Reset
        self._redraw_media_bin()  # Vẽ lại với thứ tự mới

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
        build_editly_config(self.channel_name, config=config, selected_clips=self.timeline_clips, output_path=OUT_DIR / self.channel_name)
        # Thêm các clip đã dùng vào used_jsons
        used_videos_path = get_used_videos_path(self.channel_name)
        save_used_videos(self.timeline_clips, used_videos_path)

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

    def _show_render_progress_with_gpu(self, config_path, output_args, gpu_type):
        """Hiển thị cửa sổ tiến trình render với GPU"""
        """Hiển thị cửa sổ tiến trình render"""
        # Tạo cửa sổ mới
        progress_window = tk.Toplevel(self)
        progress_window.title("Đang render video...")
        progress_window.geometry("600x400")
        progress_window.resizable(False, False)
        
        # Center window
        progress_window.update_idletasks()
        x = (progress_window.winfo_screenwidth() // 2) - (600 // 2)
        y = (progress_window.winfo_screenheight() // 2) - (400 // 2)
        progress_window.geometry(f"600x400+{x}+{y}")
        
        # Thông tin GPU
        info_frame = ttk.Frame(progress_window, padding="10")
        info_frame.pack(fill=tk.X)
        
        ttk.Label(info_frame, text=f"GPU: {gpu_type.upper()}", 
                font=("Arial", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Config: {config_path}", 
                font=("Arial", 8)).pack(anchor=tk.W)
        
        # Progress bar
        progress_frame = ttk.Frame(progress_window, padding="10")
        progress_frame.pack(fill=tk.X)
        
        progress_label = ttk.Label(progress_frame, text="Đang khởi động...", 
                                font=("Arial", 9))
        progress_label.pack(anchor=tk.W, pady=(0, 5))
        
        progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate', length=560)
        progress_bar.pack(fill=tk.X)
        progress_bar.start(10)
        
        # Text widget để hiển thị log
        log_frame = ttk.Frame(progress_window, padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(log_frame, text="Chi tiết:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        
        log_text = tk.Text(log_frame, wrap=tk.WORD, height=15, 
                        font=("Consolas", 8), bg="#1e1e1e", fg="#d4d4d4")
        log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        scrollbar = ttk.Scrollbar(log_text, command=log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        log_text.config(yscrollcommand=scrollbar.set)
        
        # Button cancel
        button_frame = ttk.Frame(progress_window, padding="10")
        button_frame.pack(fill=tk.X)
        
        cancel_button = ttk.Button(button_frame, text="Hủy", 
                                command=lambda: self._cancel_render(progress_window))
        cancel_button.pack(side=tk.RIGHT)
            
        # Chạy render trong thread riêng
        self.render_cancelled = False
        render_thread = threading.Thread(
            target=self._run_render_process_gpu,
            args=(config_path, output_args, progress_label, progress_bar, 
                log_text, progress_window, gpu_type),
            daemon=True
        )
        render_thread.start()

    def _run_render_process_gpu(self, config_path, output_args, progress_label, 
                                progress_bar, log_text, progress_window, gpu_type):
        """Chạy process render với GPU"""
        try:
            import re
            
            # Đọc config để lấy outPath
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            output_path = config['outPath']
            temp_output = output_path.replace('.mp4', '_temp.mp4')
            
            # Bước 1: Render với editly (không nén, fast)
            log_text.insert(tk.END, "=== BƯỚC 1: Render với Editly ===\n")
            log_text.see(tk.END)
            log_text.update()
            
            # Sửa config để output ra file temp
            config['outPath'] = temp_output
            config['fast'] = True  # Fast mode để nhanh
            
            temp_config_path = config_path.replace('.json', '_temp.json')
            with open(temp_config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            process1 = subprocess.Popen(
                ["editly", temp_config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                shell=True
            )
            
            self.render_process = process1
            
            for line in process1.stdout:
                if self.render_cancelled:
                    process1.terminate()
                    return
                
                log_text.insert(tk.END, line)
                log_text.see(tk.END)
                log_text.update()
                
                # Parse progress
                if "clip" in line.lower():
                    match = re.search(r'clip\s+(\d+)/(\d+)', line, re.IGNORECASE)
                    if match:
                        current = int(match.group(1))
                        total = int(match.group(2))
                        percent = (current / total) * 50  # 50% cho bước 1
                        
                        progress_label.config(text=f"Bước 1/2: Rendering clip {current}/{total}")
                        progress_bar.stop()
                        progress_bar.config(mode='determinate', value=percent)
                        progress_label.update()
                        progress_bar.update()
            
            return_code1 = process1.wait()
            if return_code1 != 0:
                raise Exception("Editly render failed")
            
            # Bước 2: Encode lại với GPU
            log_text.insert(tk.END, "\n=== BƯỚC 2: Encode với GPU ===\n")
            log_text.see(tk.END)
            log_text.update()
            
            progress_label.config(text=f"Bước 2/2: Encoding với {gpu_type.upper()}")
            progress_bar.config(value=50)
            progress_label.update()
            progress_bar.update()
            
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", temp_output,
                "-progress", "pipe:1",  # Output progress
                "-y"  # Overwrite
            ] + output_args + [output_path]
            
            log_text.insert(tk.END, f"Command: {' '.join(ffmpeg_cmd)}\n\n")
            log_text.see(tk.END)
            log_text.update()
            
            process2 = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.render_process = process2
            
            # Parse ffmpeg progress
            duration = None
            for line in process2.stdout:
                if self.render_cancelled:
                    process2.terminate()
                    return
                
                log_text.insert(tk.END, line)
                log_text.see(tk.END)
                log_text.update()
                
                # Lấy duration
                if "Duration:" in line:
                    match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})', line)
                    if match:
                        h, m, s = map(int, match.groups())
                        duration = h * 3600 + m * 60 + s
                
                # Lấy progress
                if "time=" in line and duration:
                    match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})', line)
                    if match:
                        h, m, s = map(int, match.groups())
                        current_time = h * 3600 + m * 60 + s
                        percent = 50 + (current_time / duration) * 50  # 50-100%
                        
                        progress_label.config(text=f"Encoding với {gpu_type.upper()}: {percent-50:.1f}%")
                        progress_bar.config(value=percent)
                        progress_label.update()
                        progress_bar.update()
            
            return_code2 = process2.wait()
            
            # Xóa file temp
            # if os.path.exists(temp_output):
            #     os.remove(temp_output)
            # if os.path.exists(temp_config_path):
            #     os.remove(temp_config_path)
            
            if self.render_cancelled:
                progress_label.config(text="Đã hủy render")
                log_text.insert(tk.END, "\n\n=== Đã hủy render ===\n")
                messagebox.showwarning("Đã hủy", "Đã hủy render video")
            elif return_code2 == 0:
                progress_bar.config(value=100)
                progress_label.config(text="Hoàn tất! ✓")
                log_text.insert(tk.END, "\n\n=== Render thành công với GPU! ===\n")
                messagebox.showinfo("Hoàn tất", f"Render video thành công 🎉\nGPU: {gpu_type.upper()}")
                progress_window.destroy()
            else:
                raise Exception("FFmpeg encoding failed")
                
        except Exception as e:
            log_text.insert(tk.END, f"\n\n=== LỖI: {str(e)} ===\n")
            messagebox.showerror("Lỗi", f"Lỗi: {str(e)}")

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
    """
    selected_clips: list các dict từ clip_selector, mỗi item có:
      { "filename": "...", "path": "Full/Hoặc/Relative", "duration": float }
    config: đọc từ config.json của kênh, gồm:
      logo.png, transition.mov (tuỳ chọn), preoverlap, gap, blur, fps

    Logic transition mới:
    - Transition bắt đầu đè vào pre_f frames cuối clip trước
    - Có gap màu đen giữa 2 clips
    - Transition chạy liên tục, không bị gián đoạn
    - Phần sau của transition đè vào đầu clip sau
    """
    width, height = 1920, 1080
    fps = int(config.get("fps", 30))
    gap_tc = config.get("gap", "00:00:00:00")
    pre_tc = config.get("preoverlap", "00:00:00:00")
    logo_file = config.get("logo", "logo.png")
    trans_file = config.get("transition", "transition.mov")
    blur_conf_str = config.get("blur", 1)
    blur_conf = 0
    try:
        blur_conf = float(blur_conf_str)
    except:
        blur_conf = 0
    channel_dir = os.path.join(CHANNELS_DIR, channel_name)
    logo_path = os.path.join(channel_dir, logo_file)
    if not os.path.exists(logo_path):
        raise FileNotFoundError(f"Không thấy logo: {logo_path} (yêu cầu logo.png trong thư mục kênh)")

    # Kiểm tra transition có tồn tại không
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
    pre_s = pre_f / fps  # chuyển pre_f sang giây

    clips_json = []
    audioTracks = []

    def main_clip_layer(full_path: str, cut_from: float = 0.0, cut_to: Optional[float] = None):
        """Layer clip chính + overlay logo.png (full frame 1920x1080 trong suốt)"""
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

        # Logo phủ toàn màn hình (PNG trong suốt 1920x1080)
        logo_layer = {
            "type": "image-overlay",
            "path": logo_path,
            "position": "center",
            "width": 1.0
        }

        return {"layers": [v_layer, logo_layer]}

    def black_gap_clip(duration_s: float):
        """Tạo clip gap màu đen"""
        return {
            "duration": duration_s,
            "layers": [
                {
                    "type": "fill-color",
                    "color": "#000000"
                },
                {
                    "type": "image-overlay",
                    "path": logo_path,
                    "position": "center",
                    "width": 1.0
                }
            ]
        }

    # Kiểm tra nếu không có clip nào được chọn
    if not selected_clips:
        raise RuntimeError("Không chọn được clip nào!")

    # Xử lý từng clip
    for i, item in enumerate(selected_clips):
        full = item["path"]
        if not os.path.isabs(full):
            full = os.path.join(MAIN_CLIPS_DIR, item["path"])
        dur = float(item["duration"])

        is_first = (i == 0)
        is_last = (i == len(selected_clips) - 1)

        if is_first:
            # Clip đầu tiên: chơi bình thường toàn bộ
            clip_obj = main_clip_layer(full, 0.0, dur)

            # Thêm transition overlay vào cuối clip (nếu có clip tiếp theo)
            if trans_frames > 0 and not is_last:
                # Transition bắt đầu từ pre_s giây trước khi clip kết thúc
                trans_start_in_clip = dur - pre_s

                clip_obj["layers"].append({
                    "type": "video",
                    "path": trans_path,
                    "start": trans_start_in_clip,
                    "stop": dur,  # chạy đến hết clip
                    "cutFrom": 0.0,
                    "cutTo": pre_s,
                    "resizeMode": "contain",
                    "mixVolume": 1
                })
                audioTracks.append({
                    "path": trans_path,
                    "mixVolume": 1,
                    "cutFrom": 0.0,
                    "cutTo": trans_duration_s,
                    "start": trans_start_in_clip
                })
            clips_json.append(clip_obj)

            # Thêm gap màu đen (nếu có và không phải clip cuối)
            if gap_s > 0 and trans_frames > 0 and not is_last:
                gap_clip = black_gap_clip(gap_s)

                # Transition tiếp tục chạy trong gap
                gap_clip["layers"].append({
                    "type": "video",
                    "path": trans_path,
                    "start": 0.0,
                    "stop": gap_s,
                    "cutFrom": pre_s,
                    "cutTo": pre_s + gap_s,
                    "resizeMode": "contain",
                    # "mixVolume": 1
                })

                clips_json.append(gap_clip)

        else:
            # Các clip sau: clip chơi bình thường, transition đè vào đầu
            clip_obj = main_clip_layer(full, 0.0, dur)

            # Tính phần transition còn lại sau gap
            trans_remaining_s = trans_duration_s - pre_s - gap_s

            # Transition phần còn lại đè vào đầu clip
            if trans_remaining_s > 0:
                clip_obj["layers"].append({
                    "type": "video",
                    "path": trans_path,
                    "start": 0.0,
                    "stop": min(trans_remaining_s, dur),
                    "cutFrom": pre_s + gap_s,
                    "cutTo": trans_duration_s,
                    "resizeMode": "contain",
                    # "mixVolume": 1
                })
            clips_json.append(clip_obj)

            # Thêm gap cho clip tiếp theo (nếu không phải clip cuối)
            if gap_s > 0 and trans_frames > 0 and not is_last:
                gap_clip = black_gap_clip(gap_s)

                # Transition mới cho cặp clip tiếp theo
                gap_clip["layers"].append({
                    "type": "video",
                    "path": trans_path,
                    "start": 0.0,
                    "stop": gap_s,
                    "cutFrom": pre_s,
                    "cutTo": pre_s + gap_s,
                    "resizeMode": "contain",
                    # "mixVolume": 1
                })

                clips_json.append(gap_clip)

    output_file_name = f"{channel_name}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.mp4"
    spec = {
        "outPath": os.path.join(output_path, output_file_name),
        # "fast": "true",
        "width": width,
        "height": height,
        "fps": fps,
        "keepSourceAudio": True,
        "defaults": {"transition": None},
        "clips": clips_json,
        "audioTracks": audioTracks
    }

    # Lưu file JSON và render video
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    config_filename = f"{channel_name}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    config_path = os.path.join(os.path.dirname(TEMP_DIR/channel_name), config_filename)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã lưu cấu hình editly: {config_path}")

    # Render video bằng editly CLI
    try:
        subprocess.run(["editly", config_path], check=True, shell=True)
        print(f"🎬 Video đã được render: {spec['outPath']}")
        # Xóa file config
        # os.remove(config_path)
    except subprocess.CalledProcessError as e:
        print(f"❌ Lỗi khi render video bằng editly: {e}")
    except FileNotFoundError:
        print("⚠️ Lệnh 'editly' chưa được cài đặt hoặc không có trong PATH!")

    return spec
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
def load_channel_path(channel_name):
    channel_path = os.path.join(CHANNELS_DIR, channel_name)
    if not os.path.exists(channel_path):
        raise FileNotFoundError(f"Kênh '{channel_name}' chưa tồn tại trong Channels/.")
    return channel_path
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
