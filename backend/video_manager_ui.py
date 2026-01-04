"""
Video Manager UI - Quản lý video đã sử dụng
Hiển thị tất cả video trong topic cụ thể từ Main_clips
- Load tất cả video từ topic được truyền vào khi mở kênh
- Hiển thị tên, thumbnail và checkbox "Đã dùng" nếu video có trong used_videos.json
- Tích checkbox: thêm video vào used_videos.json
- Bỏ tích: xóa video khỏi used_videos.json
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, Canvas
from PIL import Image, ImageTk
import json
import os
import subprocess
import platform
from pathlib import Path
from consts import *
from editor_ui import load_json
from helper import get_video_info, load_channel_path, read_json_file_content

class VideoManagerWindow(ctk.CTkToplevel):
    def __init__(self, parent, channel_name, topic):
        super().__init__(parent)
        self.channel_name = channel_name
        self.topic = topic
        self.title(f"Quản lý Video - Kênh: {self.channel_name} - Topic: {self.topic}")
        
        # Kích thước và vị trí
        width = 1400
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
        self.config_file = os.path.join(self.channel_path, "config.json")
        # Load config để lấy thư mục video
        self.video_sources = self._load_video_sources()
        self.used_videos = self._load_used_videos()
        self.all_videos = []  # List of {path, duration, thumb, is_used}
        self._image_references = []
        
        # Performance optimization variables
        self.search_timer = None  # Timer for debouncing search
        self.search_delay = 300  # Delay in milliseconds
        self.current_items = []  # Current rendered items for show/hide optimization
        
        # Lazy loading variables
        self.visible_items = {}  # {index: widget_dict}
        self.item_height = 110  # Height of each item
        self.items_per_page = 20  # Number of items to render at once
        
        # Layout
        self._create_layout()
        
        # Load videos
        self._load_all_videos()
        
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _load_video_sources(self):
        """Load tất cả video từ Main_clips"""
        base_dir = os.path.join(MAIN_CLIPS_DIR, self.topic)
        # Lấy tất cả file video trong thư mục
        all_clips = [
            os.path.join(base_dir, f)
            for f in os.listdir(base_dir)
            if f.lower().endswith((".mp4", ".mov", ".mkv"))
        ]
        return all_clips

    def _load_used_videos(self):
        """Load danh sách video đã sử dụng từ used_videos.json và convert sang absolute paths"""
        used_videos_list = load_json(self.used_videos_file)
        used_videos_set = set()
        
        for rel_path in used_videos_list:
            # Convert relative path to absolute path
            abs_path = os.path.join(self.channel_path, rel_path)
            abs_path = os.path.normpath(abs_path)
            # Normalize to lowercase for case-insensitive comparison on Windows
            abs_path_compare = abs_path.lower() if platform.system() == 'Windows' else abs_path
            used_videos_set.add(abs_path_compare)
            
        return used_videos_set

    def _save_used_videos(self):
        """Lưu danh sách video đã sử dụng vào used_videos.json"""
        try:
            # Convert paths to relative paths (relative to channel folder)
            relative_paths = []
            for abs_path_lower in sorted(self.used_videos):
                try:
                    # Convert back to original case for saving
                    # We stored lowercase for comparison, need to find original path
                    original_path = None
                    for video in self.all_videos:
                        video_path_compare = video['path'].lower() if platform.system() == 'Windows' else video['path']
                        if video_path_compare == abs_path_lower:
                            original_path = video['path']
                            break

                    if original_path:
                        rel_path = os.path.relpath(original_path, self.channel_path)
                    else:
                        rel_path = os.path.relpath(abs_path_lower, self.channel_path)

                    relative_paths.append(rel_path)
                except Exception as e:
                    # If cannot convert to relative, use as is
                    print(f"Cannot convert to relative path: {abs_path_lower}, error: {e}")
                    relative_paths.append(abs_path_lower)

            # Create directory if not exists
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
            text=f"📹 Quản lý Video - {self.channel_name}",
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
            text="✅ Đánh dấu tất cả",
            command=self._mark_all_used,
            width=140,
            fg_color="green"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="❌ Bỏ đánh dấu tất cả",
            command=self._unmark_all_used,
            width=160,
            fg_color="orange"
        ).pack(side="left", padx=5)

        # Filter Frame
        filter_frame = ctk.CTkFrame(main_container)
        filter_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(filter_frame, text="Lọc:", font=("Arial", 12)).pack(side="left", padx=10)

        self.filter_var = ctk.StringVar(value="all")

        ctk.CTkRadioButton(
            filter_frame,
            text="Tất cả",
            variable=self.filter_var,
            value="all",
            command=self._apply_filter
        ).pack(side="left", padx=5)

        ctk.CTkRadioButton(
            filter_frame,
            text="Đã dùng",
            variable=self.filter_var,
            value="used",
            command=self._apply_filter
        ).pack(side="left", padx=5)

        ctk.CTkRadioButton(
            filter_frame,
            text="Chưa dùng",
            variable=self.filter_var,
            value="unused",
            command=self._apply_filter
        ).pack(side="left", padx=5)

        # Search
        search_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        search_frame.pack(side="left", padx=(20, 5))
        
        ctk.CTkLabel(search_frame, text="Tìm kiếm:", font=("Arial", 12)).pack(side="left")
        self.search_entry = ctk.CTkEntry(search_frame, width=250, placeholder_text="Nhập tên file (có thể dùng % và _)")
        self.search_entry.pack(side="left", padx=(5, 0))
        self.search_entry.bind("<KeyRelease>", self._on_search_keyrelease)
        
        # Help tooltip
        help_label = ctk.CTkLabel(
            search_frame,
            text="❓",
            font=("Arial", 10),
            fg_color="gray60",
            corner_radius=8,
            width=20,
            height=20
        )
        help_label.pack(side="left", padx=(3, 0))
        
        # Bind hover events for help
        def show_help(event):
            help_text = (
                "Tìm kiếm thông minh:\n\n"
                "• Tìm kiếm thường: Animal\n"
                "  → tìm tất cả file có chứa 'Animal'\n\n"
                "• Tìm kiếm SQL LIKE:\n"
                "  % = bất kỳ ký tự nào\n"
                "  _ = đúng 1 ký tự\n\n"
                "Ví dụ:\n"
                "• Animal% = bắt đầu với 'Animal'\n"
                "• %test% = có chứa 'test'\n"
                "• a_imals = 'animals', 'agimals', etc."
            )
            # Show tooltip (simple messagebox for now)
            messagebox.showinfo("Hướng dẫn tìm kiếm", help_text)
            
        help_label.bind("<Button-1>", show_help)

        # Video List (Scrollable)
        self.video_list_frame = ctk.CTkScrollableFrame(
            main_container,
            label_text="Danh sách Video"
        )
        self.video_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_all_videos(self):
        """Load tất cả video từ kênh và kiểm tra trạng thái đã dùng"""
        self.all_videos = []

        # Hiển thị progress
        self.stats_label.configure(text="⏳ Đang quét video từ Main_clips...")
        self.update()

        total_sources = len(self.video_sources)
        if total_sources == 0:
            self.stats_label.configure(text="⚠️ Không tìm thấy video nào trong Main_clips")
            messagebox.showwarning("Cảnh báo", "Không tìm thấy video nào trong thư mục Main_clips")
            return

        loaded = 0

        for video_path in self.video_sources:
            # Update progress
            if loaded % 10 == 0:
                self.stats_label.configure(text=f"⏳ Đang tải {loaded}/{total_sources} video...")
                self.update()

            # Get video info (duration and thumbnail)
            duration, thumb_path, width, height = get_video_info(video_path)

            if duration > 0 and thumb_path:
                normalized_path = os.path.normpath(video_path)
                # Normalize to lowercase for case-insensitive comparison on Windows
                normalized_path_compare = normalized_path.lower() if platform.system() == 'Windows' else normalized_path

                # Kiểm tra xem video có trong used_videos.json không
                is_used = normalized_path_compare in self.used_videos

                if loaded < 3:  # Debug first 3 videos
                    print(f"DEBUG: Video path: {normalized_path_compare}")
                    print(f"DEBUG: Is used: {is_used}")

                self.all_videos.append({
                    'path': normalized_path,
                    'duration': duration,
                    'thumb_path': thumb_path,
                    'is_used': is_used,
                    'name': os.path.basename(video_path)
                })

            loaded += 1

        # Sort by name
        self.all_videos.sort(key=lambda x: x['name'].lower())

        # Update stats
        total = len(self.all_videos)
        used = sum(1 for v in self.all_videos if v['is_used'])
        self.stats_label.configure(
            text=f"📊 Tổng: {total} video | ✅ Đã dùng: {used} | ⭕ Chưa dùng: {total - used}"
        )

        # Render list
        self._render_video_list()

    def _render_video_list(self):
        """Hiển thị danh sách video với lazy loading tối ưu"""
        # Show loading indicator
        self.stats_label.configure(text="🔄 Đang lọc video...")
        self.update_idletasks()
        
        # Clear existing efficiently
        for widget in self.video_list_frame.winfo_children():
            widget.destroy()

        self._image_references = []
        self.visible_items = {}

        # Apply filter
        filtered_videos = self._get_filtered_videos()

        if not filtered_videos:
            no_result = ctk.CTkLabel(
                self.video_list_frame,
                text="Không tìm thấy video nào",
                font=("Arial", 14)
            )
            no_result.pack(pady=50)
            # Restore stats
            total = len(self.all_videos)
            used = sum(1 for v in self.all_videos if v['is_used'])
            self.stats_label.configure(
                text=f"📊 Tổng: {total} video | ✅ Đã dùng: {used} | ⭕ Chưa dùng: {total - used}"
            )
            return

        # Hiển thị số lượng
        count_label = ctk.CTkLabel(
            self.video_list_frame,
            text=f"Hiển thị {len(filtered_videos)} video",
            font=("Arial", 12, "bold")
        )
        count_label.pack(pady=5)

        # Render theo batch để tránh lag - giảm batch size cho performance tốt hơn
        batch_size = 30

        # Store current filtered videos for load more
        self.current_filtered_videos = filtered_videos

        for idx, video in enumerate(filtered_videos[:batch_size]):
            self._create_video_item(video, idx)

        # Update stats after initial render
        total = len(self.all_videos)
        used = sum(1 for v in self.all_videos if v['is_used'])
        self.stats_label.configure(
            text=f"📊 Tổng: {total} video | ✅ Đã dùng: {used} | ⭕ Chưa dùng: {total - used} | 🔍 Tìm thấy: {len(filtered_videos)}"
        )

        # Nếu còn nhiều video, hiển thị nút "Load more"
        if len(filtered_videos) > batch_size:
            remaining = len(filtered_videos) - batch_size

            def load_more():
                # Xóa nút load more
                load_more_btn.destroy()

                # Show loading
                loading_label = ctk.CTkLabel(
                    self.video_list_frame,
                    text="⏳ Đang tải thêm video...",
                    font=("Arial", 10)
                )
                loading_label.pack(pady=5)
                self.update_idletasks()

                # Render batch tiếp theo
                start_idx = batch_size
                end_idx = min(start_idx + batch_size, len(filtered_videos))

                for idx in range(start_idx, end_idx):
                    self._create_video_item(filtered_videos[idx], idx)

                # Remove loading label
                loading_label.destroy()

                # Nếu còn nữa, tạo nút load more mới
                if end_idx < len(filtered_videos):
                    remaining_new = len(filtered_videos) - end_idx
                    new_btn = ctk.CTkButton(
                        self.video_list_frame,
                        text=f"⬇️ Tải thêm {remaining_new} video...",
                        command=lambda: self._load_more_videos(filtered_videos, end_idx, new_btn),
                        height=40,
                        font=("Arial", 12)
                    )
                    new_btn.pack(pady=10)

            load_more_btn = ctk.CTkButton(
                self.video_list_frame,
                text=f"⬇️ Tải thêm {remaining} video...",
                command=load_more,
                height=40,
                font=("Arial", 12)
            )
            load_more_btn.pack(pady=10)

    def _load_more_videos(self, filtered_videos, start_idx, button):
        """Load thêm batch video tiếp theo"""
        button.destroy()

        batch_size = 50
        end_idx = min(start_idx + batch_size, len(filtered_videos))

        for idx in range(start_idx, end_idx):
            self._create_video_item(filtered_videos[idx], idx)

        # Nếu còn nữa, tạo nút load more mới
        if end_idx < len(filtered_videos):
            remaining = len(filtered_videos) - end_idx
            new_btn = ctk.CTkButton(
                self.video_list_frame,
                text=f"⬇️ Tải thêm {remaining} video...",
                command=lambda: self._load_more_videos(filtered_videos, end_idx, new_btn),
                height=40,
                font=("Arial", 12)
            )
            new_btn.pack(pady=10)

    def _get_filtered_videos(self):
        """Lọc video theo filter và search"""
        filtered = self.all_videos.copy()

        # Apply status filter
        filter_mode = self.filter_var.get()
        if filter_mode == "used":
            filtered = [v for v in filtered if v['is_used']]
        elif filter_mode == "unused":
            filtered = [v for v in filtered if not v['is_used']]

        # Apply search (hỗ trợ SQL LIKE với % và _)
        search_text = self.search_entry.get().strip()
        if search_text:
            search_lower = search_text.lower()
            
            # Kiểm tra xem có sử dụng SQL LIKE wildcards không
            if '%' in search_text or '_' in search_text:
                # Sử dụng SQL LIKE pattern matching
                import re
                pattern = search_lower
                pattern = re.escape(pattern)  # Escape special regex chars
                pattern = pattern.replace(r'\%', '.*')  # % -> .*
                pattern = pattern.replace(r'\_', '.')   # _ -> .
                pattern = f"^{pattern}$"  # Match whole name với wildcards
                
                try:
                    regex = re.compile(pattern)
                    filtered = [v for v in filtered if regex.search(v['name'].lower())]
                except re.error:
                    # If regex is invalid, fall back to simple contains search
                    search_simple = search_lower.replace('%', '').replace('_', '')
                    filtered = [v for v in filtered if search_simple in v['name'].lower()]
            else:
                # Simple contains search (không có wildcards)
                filtered = [v for v in filtered if search_lower in v['name'].lower()]

        return filtered

    def _create_video_item(self, video, index):
        """Tạo một item video (tối ưu)"""
        # Item container
        item_frame = ctk.CTkFrame(
            self.video_list_frame,
            height=100,
            fg_color=("gray90", "gray20") if index % 2 == 0 else ("gray85", "gray25")
        )
        item_frame.pack(fill="x", padx=5, pady=3)
        item_frame.pack_propagate(False)

        # Thumbnail - Load lazy
        thumb_container = ctk.CTkFrame(item_frame, width=120, height=80)
        thumb_container.pack(side="left", padx=10, pady=10)
        thumb_container.pack_propagate(False)

        # Placeholder trước
        placeholder = ctk.CTkLabel(
            thumb_container,
            text="⏳",
            font=("Arial", 20),
            fg_color="gray60"
        )
        placeholder.place(relx=0.5, rely=0.5, anchor="center")

        # Load thumbnail sau (không block UI) - tăng delay để tránh lag
        def load_thumb():
            try:
                # Check if widget still exists (user might have filtered while loading)
                if not placeholder.winfo_exists():
                    return
                    
                img = Image.open(video['thumb_path'])
                img.thumbnail((120, 80))
                photo = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 80))
                self._image_references.append(photo)

                if placeholder.winfo_exists():
                    placeholder.destroy()
                    thumb_label = ctk.CTkLabel(thumb_container, image=photo, text="")
                    thumb_label.place(relx=0.5, rely=0.5, anchor="center")
            except:
                if placeholder.winfo_exists():
                    placeholder.configure(text="❌", fg_color="gray40")

        # Schedule load thumb sau 50ms để UI render mượt hơn
        self.after(50 + index * 5, load_thumb)  # Stagger loading

        # Info Frame
        info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Video name
        name_label = ctk.CTkLabel(
            info_frame,
            text=video['name'],
            font=("Arial", 12, "bold"),
            anchor="w"
        )
        name_label.pack(fill="x", pady=(0, 5))

        # Details
        details_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        details_frame.pack(fill="x")

        duration_text = f"⏱️ {video['duration']:.1f}s"
        ctk.CTkLabel(
            details_frame,
            text=duration_text,
            font=("Arial", 10)
        ).pack(side="left", padx=(0, 15))

        path_text = f"📁 {video['path']}"
        path_label = ctk.CTkLabel(
            details_frame,
            text=path_text,
            font=("Arial", 9),
            text_color="gray"
        )
        path_label.pack(side="left")

        # Action Frame (Right side)
        action_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        action_frame.pack(side="right", padx=10, pady=10)

        # Play button
        play_btn = ctk.CTkButton(
            action_frame,
            text="▶️ Xem",
            width=80,
            command=lambda: self._play_video(video['path'])
        )
        play_btn.pack(pady=(0, 5))

        # Used checkbox
        used_var = ctk.BooleanVar(value=video['is_used'])

        def on_toggle():
            is_checked = used_var.get()
            self._toggle_used_status(video['path'], is_checked)

        used_check = ctk.CTkCheckBox(
            action_frame,
            text="Đã dùng",
            variable=used_var,
            command=on_toggle,
            font=("Arial", 11, "bold")
        )
        used_check.pack()

        # Update color based on status
        if video['is_used']:
            used_check.configure(fg_color="green", hover_color="darkgreen")

    def _toggle_used_status(self, video_path, is_used):
        """
        Toggle trạng thái đã dùng của video
        - is_used = True: Thêm video vào used_videos.json
        - is_used = False: Xóa video khỏi used_videos.json
        """
        normalized_path = os.path.normpath(video_path)
        # Normalize to lowercase for case-insensitive comparison on Windows
        normalized_path_compare = normalized_path.lower() if platform.system() == 'Windows' else normalized_path

        if is_used:
            # Tích checkbox -> Thêm vào used_videos
            self.used_videos.add(normalized_path_compare)
            print(f"✅ Đã thêm vào used_videos: {os.path.basename(normalized_path)}")
        else:
            # Bỏ tích -> Xóa khỏi used_videos
            self.used_videos.discard(normalized_path_compare)
            print(f"❌ Đã xóa khỏi used_videos: {os.path.basename(normalized_path)}")

        # Lưu vào file used_videos.json
        if self._save_used_videos():
            # Update video in list
            for video in self.all_videos:
                video_path_compare = video['path'].lower() if platform.system() == 'Windows' else video['path']
                if video_path_compare == normalized_path_compare:
                    video['is_used'] = is_used
                    break
            total = len(self.all_videos)
            used_count = sum(1 for v in self.all_videos if v['is_used'])
            self.stats_label.configure(
                text=f"📊 Tổng: {total} video | ✅ Đã dùng: {used_count} | ⭕ Chưa dùng: {total - used_count}"
            )

    def _play_video(self, video_path):
        """Mở video bằng trình phát mặc định"""
        try:
            if platform.system() == 'Windows':
                os.startfile(video_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', video_path])
            else:  # Linux
                subprocess.run(['xdg-open', video_path])
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở video:\n{e}")

    def _on_search_keyrelease(self, event):
        """Handle search input with debouncing"""
        # Cancel previous timer if exists
        if self.search_timer:
            self.after_cancel(self.search_timer)
        
        # Set new timer
        self.search_timer = self.after(self.search_delay, self._debounced_search)
    
    def _debounced_search(self):
        """Execute search after debounce delay"""
        self.search_timer = None
        self._apply_filter()

    def _apply_filter(self):
        """Áp dụng filter và render lại"""
        self._render_video_list()

    def _refresh_videos(self):
        """Refresh danh sách video"""
        self.video_sources = self._load_video_sources()
        self.used_videos = self._load_used_videos()
        self._load_all_videos()

    def _mark_all_used(self):
        """Đánh dấu tất cả video là đã dùng (thêm vào used_videos.json)"""
        confirm = messagebox.askyesno(
            "Xác nhận",
            "Đánh dấu TẤT CẢ video là đã dùng?\n(Chỉ áp dụng cho video đang hiển thị sau filter)"
        )

        if confirm:
            filtered = self._get_filtered_videos()
            for video in filtered:
                normalized_path = os.path.normpath(video['path'])
                normalized_path_compare = normalized_path.lower() if platform.system() == 'Windows' else normalized_path
                self.used_videos.add(normalized_path_compare)
                video['is_used'] = True

            self._save_used_videos()
            self._render_video_list()

            # Update stats
            total = len(self.all_videos)
            used_count = sum(1 for v in self.all_videos if v['is_used'])
            self.stats_label.configure(
                text=f"📊 Tổng: {total} video | ✅ Đã dùng: {used_count} | ⭕ Chưa dùng: {total - used_count}"
            )

            messagebox.showinfo("Thành công", f"Đã đánh dấu {len(filtered)} video là đã dùng")

    def _unmark_all_used(self):
        """Bỏ đánh dấu tất cả video (xóa khỏi used_videos.json)"""
        confirm = messagebox.askyesno(
            "Xác nhận",
            "Bỏ đánh dấu TẤT CẢ video?\n(Chỉ áp dụng cho video đang hiển thị sau filter)"
        )

        if confirm:
            filtered = self._get_filtered_videos()
            for video in filtered:
                normalized_path = os.path.normpath(video['path'])
                normalized_path_compare = normalized_path.lower() if platform.system() == 'Windows' else normalized_path
                self.used_videos.discard(normalized_path_compare)
                video['is_used'] = False

            self._save_used_videos()
            self._render_video_list()

            # Update stats
            total = len(self.all_videos)
            used_count = sum(1 for v in self.all_videos if v['is_used'])
            self.stats_label.configure(
                text=f"📊 Tổng: {total} video | ✅ Đã dùng: {used_count} | ⭕ Chưa dùng: {total - used_count}"
            )

            messagebox.showinfo("Thành công", f"Đã bỏ đánh dấu {len(filtered)} video")

    def _on_closing(self):
        """Đóng cửa sổ"""
        # Cancel search timer if exists
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


def open_video_manager(parent, channel_name, topic):
    """Mở cửa sổ quản lý video"""
    window = VideoManagerWindow(parent, channel_name, topic)
    window.focus()
