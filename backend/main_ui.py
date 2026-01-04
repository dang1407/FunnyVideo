import customtkinter as ctk
from tkinterdnd2 import TkinterDnD
from tkinter import messagebox
import json
from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk

from editor_ui import EditorWindow, load_json, get_used_videos_path
from clip_selector import select_clips
from render_history_window import ClipViewerApp
from video_manager_ui import open_video_manager
from helper import get_video_info

# --- Quản lý đường dẫn ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANNELS_DIR = PROJECT_ROOT / "Channels"
TOPIC_DIR = PROJECT_ROOT / "Main_clips"

# Thiết lập theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ChannelCreationDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, initial_config):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x500")
        self.initial_config = initial_config
        self.result = None
        
        # Modal setup
        self.transient(parent)
        self.grab_set()
        
        # Center the dialog
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')

        self._create_widgets()
        self.wait_window()

    def _create_widgets(self):
        self.grid_columnconfigure(1, weight=1)
        
        # Tên kênh
        ctk.CTkLabel(self, text="Tên kênh mới:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.channel_name_entry = ctk.CTkEntry(self, width=200)
        self.channel_name_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.config_vars = {}
        config_keys = ["logo", "transition", "preoverlap", "gap", "blur", "fps"]
        
        for i, key in enumerate(config_keys):
            ctk.CTkLabel(self, text=f"{key.capitalize()}:").grid(row=i + 1, column=0, padx=10, pady=10, sticky="w")
            string_var = tk.StringVar(value=str(self.initial_config.get(key, "")))
            entry = ctk.CTkEntry(self, textvariable=string_var, width=200)
            entry.grid(row=i + 1, column=1, padx=10, pady=10, sticky="ew")
            self.config_vars[key] = string_var

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=len(config_keys) + 1, column=0, columnspan=2, pady=20)
        
        ctk.CTkButton(btn_frame, text="Tạo", command=self.apply, width=100).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Hủy", command=self.destroy, fg_color="gray", width=100).pack(side="left", padx=10)

    def apply(self):
        channel_name = self.channel_name_entry.get().strip()
        if not channel_name:
            messagebox.showwarning("Dữ liệu không hợp lệ", "Tên kênh không được để trống.", parent=self)
            return

        if not re.match("^[a-zA-Z0-9_-]+$", channel_name):
            messagebox.showwarning("Dữ liệu không hợp lệ",
                                   "Tên kênh chỉ được chứa chữ, số, gạch dưới (_) và gạch ngang (-).", parent=self)
            return

        if (CHANNELS_DIR / channel_name).exists():
            messagebox.showwarning("Lỗi", f"Kênh '{channel_name}' đã tồn tại.", parent=self)
            return

        config_result = {}
        for key, var in self.config_vars.items():
            value = var.get()
            if key in ['blur', 'fps']:
                try:
                    value = float(value) if '.' in value else int(value)
                except ValueError:
                    pass
            config_result[key] = value
        
        self.result = (channel_name, config_result)
        self.destroy()

# Wrapper class to mix CTk and TkinterDnD
class Tk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)

class ChannelSelectorApp(Tk):
    def __init__(self):
        super().__init__()
        self.title("Funny Video Tool - Quản lý Kênh")
        self.geometry("500x700")
        
        # Căn giữa cửa sổ trên màn hình
        self.update_idletasks()
        width = 500
        height = 700
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        self.selected_channel = tk.StringVar()
        self.selected_topic = tk.StringVar()
        self.target = tk.StringVar()
        self.config_vars = {}
        self.config_entries = {}
        self.initial_config_template = {
            "logo": "logo.png",
            "transition": "transition.mov",
            "preoverlap": "00:00:00:06",
            "gap": "00:00:00:04",
            "blur": 0.25,
            "fps": 30
        }
        
        self._create_widgets()
        self._populate_channels()
        self._populate_topics()

    def _create_widgets(self):
        # Main container with scrolling is not strictly needed as window is large enough, 
        # but usage of Frames is key.
        main_frame = ctk.CTkFrame(self, corner_radius=10)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # 1. Chọn/Quản lý Kênh
        channel_frame = ctk.CTkFrame(main_frame)
        channel_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(channel_frame, text="1. Chọn/Quản lý Kênh", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=3, pady=(10, 5), sticky="w", padx=10)

        ctk.CTkLabel(channel_frame, text="Kênh có sẵn:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        self.channel_combobox = ctk.CTkComboBox(channel_frame, variable=self.selected_channel, width=200, command=self._on_channel_select_cb)
        self.channel_combobox.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        self.new_channel_button = ctk.CTkButton(channel_frame, text="Tạo kênh mới", command=self._create_new_channel, width=100)
        self.new_channel_button.grid(row=1, column=2, padx=10, pady=10)

        # Topic
        ctk.CTkLabel(channel_frame, text="Topic:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.topic_combobox = ctk.CTkComboBox(channel_frame, variable=self.selected_topic, width=200, command=self._on_topic_select_cb)
        self.topic_combobox.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        
        # Target
        ctk.CTkLabel(channel_frame, text="Target:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        target_entry = ctk.CTkEntry(channel_frame, textvariable=self.target, width=200)
        target_entry.grid(row=3, column=1, padx=10, pady=10, sticky="ew")

        channel_frame.columnconfigure(1, weight=1)

        # 2. Cấu hình Kênh
        config_frame = ctk.CTkFrame(main_frame)
        config_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(config_frame, text="2. Cấu hình Kênh", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=(10, 5), sticky="w", padx=10)

        config_keys = ["logo", "transition", "preoverlap", "gap", "blur", "fps"]
        for i, key in enumerate(config_keys):
            ctk.CTkLabel(config_frame, text=f"{key.capitalize()}:").grid(row=i+1, column=0, padx=10, pady=5, sticky="w")
            string_var = tk.StringVar()
            # State in CTkEntry is 'normal' or 'disabled' (readonly is not exactly same, using disabled for now or managing editability)
            entry = ctk.CTkEntry(config_frame, textvariable=string_var, width=200, state="disabled") 
            entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="ew")
            self.config_vars[key] = string_var
            self.config_entries[key] = entry
        
        config_frame.columnconfigure(1, weight=1)

        # Actions
        action_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        action_frame.pack(fill="x", padx=10, pady=(5, 0))
        
        self.edit_button = ctk.CTkButton(action_frame, text="Chỉnh sửa", command=self._toggle_edit_mode)
        self.edit_button.pack(side="left", padx=5)
        
        self.save_button = ctk.CTkButton(action_frame, text="Lưu thay đổi", command=self._save_config, state="disabled")
        self.save_button.pack(side="left", padx=5)

        # Open Editor Buttons - Using Grid for better control
        editor_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        editor_frame.pack(fill="x", padx=10, pady=20)
        # Two columns so we can place buttons side-by-side
        editor_frame.grid_columnconfigure(0, weight=1)
        editor_frame.grid_columnconfigure(1, weight=1)
        
        # Main action spanning full width
        self.open_editor_button = ctk.CTkButton(
            editor_frame, text="Chọn Clips & Dựng Video →", command=self._open_editor_window, height=30, font=("Arial", 14, "bold")
        )
        self.open_editor_button.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)

        # Render old clips and Video Manager on same horizontal row
        self.render_old_clip_button = ctk.CTkButton(
            editor_frame, text="Render clip cũ →", command=self._open_render_history_window, height=30, font=("Arial", 14, "bold")
        )
        self.render_old_clip_button.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=5)

        self.video_manager_button = ctk.CTkButton(
            editor_frame, text="📹 Quản lý Video", command=self._open_video_manager, height=30, font=("Arial", 14, "bold"),
        )
        self.video_manager_button.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=5)

    # Callbacks needed for CTkComboBox (command arg passes value, but bound variable also updates. 
    # original code used bind <<ComboboxSelected>>)
    def _on_channel_select_cb(self, value):
        self._on_channel_select(None)
        
    def _on_topic_select_cb(self, value):
        self._on_topic_select(None)

    def _open_editor_window(self):
        selected_channel_name = self.selected_channel.get()
        if not selected_channel_name or "Không có kênh" in selected_channel_name:
            messagebox.showwarning("Chưa chọn kênh", "Vui lòng chọn một kênh để bắt đầu soạn thảo video.")
            return
        selected_topic = self.selected_topic.get()
        if not selected_topic: 
            messagebox.showwarning("Chưa chọn topic", "Vui lòng chọn một topic để bắt đầu soạn thảo video.")
            return
        
        try:
            target_time = float(self.target.get())
        except ValueError:
            messagebox.showerror("Lỗi", "Giá trị target phải là số!")
            return

        self.withdraw()
        editor = EditorWindow(self, selected_channel_name)
        # Load logic
        used_videos = load_json(get_used_videos_path(selected_channel_name))
        selected = select_clips(selected_topic, target_time, used_videos)
        for clip in selected:
            duration = clip["duration"]
            thumb_duration, thumb_path, width, height = get_video_info(clip["path"])
            if thumb_duration > 0 and thumb_path:
                editor.imported_clips.append({
                    "path": clip["path"],
                    "duration": duration,
                    "thumb_path": thumb_path,
                    "var": tk.BooleanVar(value=True)
                })

        editor.render_clip_list()

    def _open_render_history_window(self):
        selected_channel_name = self.selected_channel.get()
        if not selected_channel_name:
            messagebox.showwarning("Chưa chọn kênh", "Vui lòng chọn một kênh trước.")
            return
        ClipViewerApp(self, selected_channel_name)
    
    def _open_video_manager(self):
        """Mở cửa sổ quản lý video"""
        selected_channel_name = self.selected_channel.get()
        if not selected_channel_name or "Không có kênh" in selected_channel_name:
            messagebox.showwarning("Chưa chọn kênh", "Vui lòng chọn một kênh trước.")
            return
        
        selected_topic = self.selected_topic.get()
        if not selected_topic:
            messagebox.showwarning("Chưa chọn topic", "Vui lòng chọn một topic trước.")
            return
        
        self.withdraw()
        open_video_manager(self, selected_channel_name, selected_topic)

    def _create_new_channel(self):
        dialog = ChannelCreationDialog(self, "Tạo kênh mới", self.initial_config_template)
        if dialog.result:
            channel_name, config_data = dialog.result
            new_channel_path = CHANNELS_DIR / channel_name
            try:
                new_channel_path.mkdir()
                with open(new_channel_path / "config.json", 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=4)
                with open(new_channel_path / "used_videos.json", 'w', encoding='utf-8') as f:
                    json.dump([], f)
                messagebox.showinfo("Thành công", f"Đã tạo kênh '{channel_name}' thành công!")
                self._populate_channels()
                self.selected_channel.set(channel_name)
                # manually update combo box list and selection
                self.channel_combobox.set(channel_name)
                self._on_channel_select(None)
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể tạo kênh mới: {e}")

    def _toggle_edit_mode(self, editable=True):
        new_state = "normal" if editable else "disabled"
        for entry in self.config_entries.values():
            entry.configure(state=new_state)
        self.save_button.configure(state="normal" if editable else "disabled")
        self.edit_button.configure(state="disabled" if editable else "normal")

    def _save_config(self):
        channel_name = self.selected_channel.get()
        if not channel_name or "Không có kênh" in channel_name:
            messagebox.showerror("Lỗi", "Vui lòng chọn một kênh hợp lệ để lưu!")
            return
        config_path = CHANNELS_DIR / channel_name / "config.json"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            for key, var in self.config_vars.items(): config_data[key] = var.get()
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            messagebox.showinfo("Thành công", f"Đã lưu cấu hình cho kênh '{channel_name}' thành công!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Có lỗi xảy ra khi lưu file: {e}")
        finally:
            self._toggle_edit_mode(editable=False)

    def _get_available_channels(self):
        if not CHANNELS_DIR.is_dir(): return []
        return sorted([d.name for d in CHANNELS_DIR.iterdir() if d.is_dir()])
    
    def _get_available_topics(self):
        if not TOPIC_DIR.is_dir(): return []
        return sorted([d.name for d in TOPIC_DIR.iterdir() if d.is_dir()])

    def _populate_channels(self):
        channels = self._get_available_channels()
        if channels:
            self.channel_combobox.configure(values=channels)
            self.channel_combobox.set(channels[0])
            self._on_channel_select(None)
        else:
            self.selected_channel.set("Không có kênh nào")
            self.channel_combobox.configure(values=["Không có kênh nào"])
            self.edit_button.configure(state="disabled")

    def _populate_topics(self):
        topics = self._get_available_topics()
        if topics:
            self.topic_combobox.configure(values=topics)
            self.topic_combobox.set(topics[0])
            self._on_topic_select(None)
        else:
            self.topic_combobox.configure(values=["Không có topic nào"])

    def _load_channel_config(self, channel_name):
        config_path = CHANNELS_DIR / channel_name / "config.json"
        if not config_path.is_file(): return None
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def _on_channel_select(self, event):
        self._toggle_edit_mode(editable=False)
        channel_name = self.selected_channel.get()
        if not channel_name or "Không có kênh" in channel_name:
            self.edit_button.configure(state="disabled")
            return
        config_data = self._load_channel_config(channel_name)
        if config_data:
            for key, var in self.config_vars.items():
                var.set(config_data.get(key, ""))
            self.edit_button.configure(state="normal")
        else:
            # messagebox.showerror could be annoying during recursion or init, but okay here
            # messagebox.showerror("Lỗi", f"Không thể tải cấu hình cho kênh '{channel_name}'.")
            for var in self.config_vars.values(): var.set("")
            self.edit_button.configure(state="disabled")

    def _on_topic_select(self, event):
        pass

if __name__ == "__main__":
    app = ChannelSelectorApp()
    app.mainloop()