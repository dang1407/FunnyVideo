"""
Video Manager UI - Quản lý video đã sử dụng
Hiển thị tất cả video từ used_videos.json
- Load tất cả video đã được đánh dấu là "đã dùng"
- Hiển thị tên, thumbnail và checkbox (mặc định tích)
- Bỏ tích checkbox: đánh dấu để xóa
- Nút "Xóa các video đã tick": xóa các video đã tick khỏi used_videos.json
"""

import customtkinter as ctk
from tkinter import messagebox
from PIL import Image
import json
import os
from consts import *
from editor_ui import load_json
from helper import get_video_info, load_channel_path, open_file_cross_platform


class VideoManagerWindow(ctk.CTkToplevel):
    def __init__(self, parent, channel_name):
        super().__init__(parent)
        self.channel_name = channel_name
        self.title(f"Quản lý Video Đã Dùng - Kênh: {self.channel_name}")
        
        # Kích thước và vị trí
        width = 1200
        height = 800
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = max(20, (self.winfo_screenheight() // 2) - (height // 2) - 30)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        # Luôn ở trên cửa sổ main
        self.attributes('-topmost', True)
        self.after(100, lambda: self.attributes('-topmost', False))
        
        # Dữ liệu
        self.channel_path = load_channel_path(channel_name)
        self.used_videos_file = os.path.join(self.channel_path, "used_videos.json")
        self.all_videos = []  # List of {path, name, duration, thumb_path, var (BooleanVar)}
        self._image_references = []
        
        # Performance optimization
        self.search_timer = None
        self.search_delay = 300
        
        # Layout
        self._create_layout()
        
        # Load videos
        self._load_all_videos()
        
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _save_used_videos(self):
        """Lưu danh sách video còn lại vào used_videos.json"""
        try:
            relative_paths = []
            for video in self.all_videos:
                try:
                    rel_path = os.path.relpath(video['path'], MAIN_CLIPS_DIR)
                    relative_paths.append(rel_path)
                except Exception as e:
                    print(f"Cannot convert to relative path: {video['path']}, error: {e}")
                    relative_paths.append(video['path'])

            os.makedirs(os.path.dirname(self.used_videos_file), exist_ok=True)

            with open(self.used_videos_file, 'w', encoding='utf-8') as f:
                json.dump(relative_paths, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file used_videos.json:\n{e}")
            return False

    def _create_layout(self):
        """Tạo giao diện"""
        # Main container
        main_container = ctk.CTkFrame(self)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Header
        header = ctk.CTkFrame(main_container, height=60)
        header.pack(fill="x", padx=5, pady=5)

        # Title
        title_label = ctk.CTkLabel(
            header,
            text=f"📹 Quản lý Video Đã Dùng - {self.channel_name}",
            font=("Arial", 18, "bold")
        )
        title_label.pack(side="left", padx=20, pady=15)

        # Stats
        self.stats_label = ctk.CTkLabel(
            header,
            text="⏳ Đang tải...",
            font=("Arial", 12)
        )
        self.stats_label.pack(side="left", padx=20)

        # Buttons
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="🔄 Refresh",
            command=self._refresh_videos,
            width=100
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="☑️ Chọn tất cả",
            command=self._select_all,
            width=120,
            fg_color="green"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="☐ Bỏ chọn tất cả",
            command=self._deselect_all,
            width=130,
            fg_color="gray"
        ).pack(side="left", padx=5)

        self.delete_btn = ctk.CTkButton(
            btn_frame,
            text="🗑️ Xóa các video đã tick",
            command=self._delete_checked,
            width=180,
            fg_color="red",
            hover_color="darkred"
        )
        self.delete_btn.pack(side="left", padx=5)

        # Search Frame
        search_frame = ctk.CTkFrame(main_container)
        search_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(search_frame, text="🔍 Tìm kiếm:", font=("Arial", 12)).pack(side="left", padx=10)
        self.search_entry = ctk.CTkEntry(search_frame, width=300, placeholder_text="Nhập tên file...")
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", self._on_search_keyrelease)

        # Video List (Scrollable)
        self.video_list_frame = ctk.CTkScrollableFrame(
            main_container,
            label_text="Danh sách Video Đã Dùng (tick = giữ lại, bỏ tick = xóa)"
        )
        self.video_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_all_videos(self):
        """Load tất cả video từ used_videos.json"""
        self.all_videos = []
        self._image_references = []

        self.stats_label.configure(text="⏳ Đang tải danh sách video đã dùng...")
        self.update()

        # Load danh sách từ file
        try:
            used_videos_list = load_json(self.used_videos_file)
        except:
            used_videos_list = []

        if not used_videos_list:
            self.stats_label.configure(text="⚠️ Chưa có video nào trong danh sách đã dùng")
            return

        total = len(used_videos_list)
        loaded = 0

        for rel_path in used_videos_list:
            abs_path = os.path.join(MAIN_CLIPS_DIR, rel_path)
            abs_path = os.path.normpath(abs_path)

            if loaded % 10 == 0:
                self.stats_label.configure(text=f"⏳ Đang tải {loaded}/{total} video...")
                self.update()

            # Kiểm tra file tồn tại
            abs_path = abs_path.replace("\\", "\\\\")
            check_path = Path(abs_path)
            if not check_path.exists():
                print(f"⚠️ Video không tồn tại: {abs_path}")
                # Vẫn thêm vào list để user có thể xóa
                self.all_videos.append({
                    'path': abs_path,
                    'name': os.path.basename(abs_path),
                    'duration': 0,
                    'thumb_path': None,
                    'var': ctk.BooleanVar(value=False),  # Mặc định tick
                    'exists': False
                })
                loaded += 1
                continue

            # Get video info
            duration, thumb_path, width, height = get_video_info(abs_path)

            self.all_videos.append({
                'path': abs_path,
                'name': os.path.basename(abs_path),
                'duration': duration if duration > 0 else 0,
                'thumb_path': thumb_path,
                'var': ctk.BooleanVar(value=False),  # Mặc định tick (giữ lại)
                'exists': True
            })

            loaded += 1

        # Sort by name
        self.all_videos.sort(key=lambda x: x['name'].lower())

        # Update stats
        self.stats_label.configure(text=f"📊 Tổng: {len(self.all_videos)} video đã dùng")

        # Render list
        self._render_video_list()

    def _render_video_list(self):
        """Hiển thị danh sách video"""
        # Clear existing
        for widget in self.video_list_frame.winfo_children():
            widget.destroy()
        self._image_references = []

        # Apply search filter
        filtered = self._get_filtered_videos()

        if not filtered:
            no_result = ctk.CTkLabel(
                self.video_list_frame,
                text="Không tìm thấy video nào",
                font=("Arial", 14)
            )
            no_result.pack(pady=50)
            return

        # Render với batch
        batch_size = 30
        self.current_filtered = filtered

        for idx, video in enumerate(filtered[:batch_size]):
            self._create_video_item(video, idx)

        # Load more button nếu còn nhiều
        if len(filtered) > batch_size:
            remaining = len(filtered) - batch_size
            load_more_btn = ctk.CTkButton(
                self.video_list_frame,
                text=f"⬇️ Tải thêm {remaining} video...",
                command=lambda: self._load_more(filtered, batch_size, load_more_btn),
                height=40
            )
            load_more_btn.pack(pady=10)

    def _load_more(self, filtered, start_idx, button):
        """Load thêm video"""
        button.destroy()
        batch_size = 50
        end_idx = min(start_idx + batch_size, len(filtered))

        for idx in range(start_idx, end_idx):
            self._create_video_item(filtered[idx], idx)

        if end_idx < len(filtered):
            remaining = len(filtered) - end_idx
            new_btn = ctk.CTkButton(
                self.video_list_frame,
                text=f"⬇️ Tải thêm {remaining} video...",
                command=lambda: self._load_more(filtered, end_idx, new_btn),
                height=40
            )
            new_btn.pack(pady=10)

    def _get_filtered_videos(self):
        """Lọc video theo search"""
        search_text = self.search_entry.get().strip().lower()
        if not search_text:
            return self.all_videos
        return [v for v in self.all_videos if search_text in v['name'].lower()]

    def _create_video_item(self, video, index):
        """Tạo một item video"""
        # Màu nền khác nhau
        bg_color = ("gray90", "gray20") if index % 2 == 0 else ("gray85", "gray25")
        
        # Nếu file không tồn tại, đánh dấu đỏ
        if not video.get('exists', True):
            bg_color = ("red", "darkred")

        item_frame = ctk.CTkFrame(
            self.video_list_frame,
            height=90,
            fg_color=bg_color
        )
        item_frame.pack(fill="x", padx=5, pady=2)
        item_frame.pack_propagate(False)

        # Checkbox (bên trái)
        checkbox = ctk.CTkCheckBox(
            item_frame,
            text="",
            variable=video['var'],
            width=30,
            command=self._update_delete_button
        )
        checkbox.pack(side="left", padx=10)

        # Thumbnail
        thumb_container = ctk.CTkFrame(item_frame, width=100, height=70)
        thumb_container.pack(side="left", padx=5, pady=10)
        thumb_container.pack_propagate(False)

        if video['thumb_path'] and os.path.exists(video['thumb_path']):
            def load_thumb(container=thumb_container, path=video['thumb_path']):
                try:
                    if not container.winfo_exists():
                        return
                    img = Image.open(path)
                    img.thumbnail((100, 70))
                    photo = ctk.CTkImage(light_image=img, dark_image=img, size=(100, 70))
                    self._image_references.append(photo)
                    label = ctk.CTkLabel(container, image=photo, text="")
                    label.place(relx=0.5, rely=0.5, anchor="center")
                except:
                    pass
            self.after(50 + index * 3, load_thumb)
        else:
            ctk.CTkLabel(
                thumb_container,
                text="❌" if not video.get('exists', True) else "🎬",
                font=("Arial", 20)
            ).place(relx=0.5, rely=0.5, anchor="center")

        # Info
        info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Video name
        name_text = video['name']
        if not video.get('exists', True):
            name_text = f"⚠️ {name_text} (FILE KHÔNG TỒN TẠI)"
        
        ctk.CTkLabel(
            info_frame,
            text=name_text,
            font=("Arial", 11, "bold"),
            anchor="w"
        ).pack(fill="x")

        # Duration
        if video['duration'] > 0:
            ctk.CTkLabel(
                info_frame,
                text=f"⏱️ {video['duration']:.1f}s",
                font=("Arial", 9),
                text_color="gray"
            ).pack(anchor="w")

        # Play button (bên phải)
        if video.get('exists', True):
            ctk.CTkButton(
                item_frame,
                text="▶️ Xem",
                width=70,
                command=lambda p=video['path']: open_file_cross_platform(p)
            ).pack(side="right", padx=10)

    def _update_delete_button(self):
        """Cập nhật text nút xóa"""
        checked_count = sum(1 for v in self.all_videos if v['var'].get())
        if checked_count > 0:
            self.delete_btn.configure(
                text=f"🗑️ Xóa {checked_count} video đã tick",
                state="normal"
            )
        else:
            self.delete_btn.configure(
                text="🗑️ Xóa các video đã tick",
                state="disabled"
            )

    def _delete_checked(self):
        """Xóa các video đã tick khỏi used_videos.json"""
        checked = [v for v in self.all_videos if v['var'].get()]
        
        if not checked:
            messagebox.showinfo("Thông báo", "Không có video nào được tick để xóa")
            return

        confirm = messagebox.askyesno(
            "Xác nhận xóa",
            f"Bạn có chắc muốn xóa {len(checked)} video khỏi danh sách đã dùng?\n\n"
            f"(Video sẽ bị xóa khỏi used_videos.json, không xóa file gốc)"
        )

        if not confirm:
            return

        # Giữ lại những video còn tick
        self.all_videos = [v for v in self.all_videos if not v['var'].get()]

        # Lưu file
        if self._save_used_videos():
            self.stats_label.configure(text=f"📊 Tổng: {len(self.all_videos)} video đã dùng")
            self._render_video_list()
            self._update_delete_button()
            messagebox.showinfo("Thành công", f"Đã xóa {len(checked)} video khỏi danh sách")

    def _select_all(self):
        """Chọn tất cả video"""
        for video in self.all_videos:
            video['var'].set(True)
        self._update_delete_button()

    def _deselect_all(self):
        """Bỏ chọn tất cả video"""
        for video in self.all_videos:
            video['var'].set(False)
        self._update_delete_button()

    def _on_search_keyrelease(self, event):
        """Debounce search"""
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(self.search_delay, self._render_video_list)

    def _refresh_videos(self):
        """Refresh danh sách"""
        self._load_all_videos()
        self._update_delete_button()

    def _on_closing(self):
        """Đóng cửa sổ"""
        if self.search_timer:
            self.after_cancel(self.search_timer)

        # Clean up thumbnails
        if TEMP_DIR.exists():
            for f in TEMP_DIR.glob("thumb_*.png"):
                try:
                    os.remove(f)
                except:
                    pass

        self.master.deiconify()
        self.destroy()


def open_video_manager(parent, channel_name):
    """Mở cửa sổ quản lý video đã dùng"""
    window = VideoManagerWindow(parent, channel_name)
    window.focus()
