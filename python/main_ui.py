import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
from pathlib import Path
import re

# --- THAY ĐỔI 1: IMPORT TkinterDnD ---
from tkinterdnd2 import TkinterDnD
from editor_ui import EditorWindow
from clip_selector import select_clips
from editor_ui import get_video_info, load_json, get_used_videos_path
# --- Quản lý đường dẫn ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANNELS_DIR = PROJECT_ROOT / "Channels"
TOPIC_DIR = PROJECT_ROOT / "Main_clips"


class ChannelCreationDialog(simpledialog.Dialog):
    # (Lớp này không thay đổi, giữ nguyên)
    def __init__(self, parent, title, initial_config):
        self.initial_config = initial_config
        super().__init__(parent, title)

    def body(self, master):
        self.geometry("350x300")
        ttk.Label(master, text="Tên kênh mới:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.channel_name_entry = tk.Entry(master, width=30)
        self.channel_name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.config_vars = {}
        config_keys = ["logo", "transition", "preoverlap", "gap", "blur", "fps"]
        for i, key in enumerate(config_keys):
            label = ttk.Label(master, text=f"{key.capitalize()}:")
            label.grid(row=i + 1, column=0, padx=5, pady=5, sticky="w")
            string_var = tk.StringVar(value=self.initial_config.get(key, ""))
            entry = tk.Entry(master, textvariable=string_var, width=30)
            entry.grid(row=i + 1, column=1, padx=5, pady=5, sticky="ew")
            self.config_vars[key] = string_var
            master.columnconfigure(1, weight=1)
        return self.channel_name_entry

    def validate(self):
        channel_name = self.channel_name_entry.get().strip()
        if not channel_name:
            messagebox.showwarning("Dữ liệu không hợp lệ", "Tên kênh không được để trống.", parent=self)
            return 0
        if not re.match("^[a-zA-Z0-9_-]+$", channel_name):
            messagebox.showwarning("Dữ liệu không hợp lệ",
                                   "Tên kênh chỉ được chứa chữ, số, gạch dưới (_) và gạch ngang (-).", parent=self)
            return 0
        if (CHANNELS_DIR / channel_name).exists():
            messagebox.showwarning("Lỗi", f"Kênh '{channel_name}' đã tồn tại.", parent=self)
            return 0
        return 1

    def apply(self):
        channel_name = self.channel_name_entry.get().strip()
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


# --- THAY ĐỔI 2: Kế thừa từ TkinterDnD.Tk ---
class ChannelSelectorApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("Funny Video Tool - Quản lý Kênh")
        self.geometry("450x550")

        # (Phần còn lại của file không thay đổi)
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
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        channel_frame = ttk.LabelFrame(main_frame, text="1. Chọn/Quản lý Kênh", padding="10")
        channel_frame.pack(fill=tk.X)
        ttk.Label(channel_frame, text="Kênh có sẵn:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.channel_combobox = ttk.Combobox(channel_frame, textvariable=self.selected_channel, state="readonly",
                                             width=25)
        self.channel_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        channel_frame.columnconfigure(1, weight=1)
        self.channel_combobox.bind("<<ComboboxSelected>>", self._on_channel_select)
        self.new_channel_button = ttk.Button(channel_frame, text="Tạo kênh mới", command=self._create_new_channel)
        self.new_channel_button.grid(row=0, column=2, padx=5, pady=5)

        # Chọn topic
        ttk.Label(channel_frame, text="Topic:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.topic_combobox = ttk.Combobox(channel_frame, textvariable=self.selected_topic, state="readonly",
                                             width=25)
        self.topic_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.topic_combobox.bind("<<ComboboxSelected>>", self._on_topic_select)

        ttk.Label(channel_frame, text="Target:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        target_entry = ttk.Entry(channel_frame, textvariable=self.target, state="normal", width=25)
        target_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        channel_frame.columnconfigure(1, weight=1)
        config_frame = ttk.LabelFrame(main_frame, text="2. Cấu hình Kênh", padding="10")
        config_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        config_keys = ["logo", "transition", "preoverlap", "gap", "blur", "fps"]
        for i, key in enumerate(config_keys):
            label = ttk.Label(config_frame, text=f"{key.capitalize()}:")
            label.grid(row=i, column=0, padx=5, pady=5, sticky="w")
            string_var = tk.StringVar()
            entry = ttk.Entry(config_frame, textvariable=string_var, state="readonly", width=25)
            entry.grid(row=i, column=1, padx=5, pady=5, sticky="ew")
            self.config_vars[key] = string_var
            self.config_entries[key] = entry
        config_frame.columnconfigure(1, weight=1)

        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(5, 0))
        self.edit_button = ttk.Button(action_frame, text="Chỉnh sửa", command=self._toggle_edit_mode)
        self.edit_button.pack(side=tk.LEFT, padx=5)
        self.save_button = ttk.Button(action_frame, text="Lưu thay đổi", command=self._save_config, state="disabled")
        self.save_button.pack(side=tk.LEFT, padx=5)

        editor_frame = ttk.Frame(main_frame)
        editor_frame.pack(fill=tk.X, pady=20)
        self.open_editor_button = ttk.Button(
            editor_frame, text="Chọn Clips & Dựng Video →", command=self._open_editor_window
        )
        self.open_editor_button.pack(expand=True, ipady=5)

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
        # Đọc các clip đã dùng
        used_videos = load_json(get_used_videos_path(selected_channel_name))
        selected = select_clips(selected_topic, target_time, used_videos)
        for clip in selected:
            duration = clip["duration"]
            thumb_duration, thumb_path = get_video_info(clip["path"])
            if thumb_duration > 0 and thumb_path:
                editor.imported_clips.append({
                    "path": clip["path"],
                    "duration": duration,
                    "thumb_path": thumb_path,
                    "var": tk.BooleanVar(value=False)
                })

        editor._redraw_media_bin()

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
                self._on_channel_select(None)
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể tạo kênh mới: {e}")

    def _toggle_edit_mode(self, editable=True):
        new_state = "normal" if editable else "readonly"
        for entry in self.config_entries.values():
            entry.config(state=new_state)
        self.save_button.config(state="normal" if editable else "disabled")
        self.edit_button.config(state="disabled" if editable else "normal")

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
            self.channel_combobox['values'] = channels
            self.channel_combobox.current(0)
            self._on_channel_select(None)
        else:
            self.selected_channel.set("Không có kênh nào")
            self.edit_button.config(state="disabled")

    def _populate_topics(self):
        topics = self._get_available_topics()
        if topics:
            self.topic_combobox['values'] = topics
            self.topic_combobox.current(0)
            self._on_channel_select(None)
        else:
            self.selected_channel.set("Không có kênh nào")
            self.edit_button.config(state="disabled")

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
            self.edit_button.config(state="disabled")
            return
        config_data = self._load_channel_config(channel_name)
        if config_data:
            for key, var in self.config_vars.items():
                var.set(config_data.get(key, ""))
            self.edit_button.config(state="normal")
        else:
            messagebox.showerror("Lỗi",
                                 f"Không thể tải cấu hình cho kênh '{channel_name}'. File config.json có thể bị lỗi hoặc không tồn tại.")
            for var in self.config_vars.values(): var.set("")
            self.edit_button.config(state="disabled")

    def _on_topic_select(self, event):
        print(self.selected_topic)

if __name__ == "__main__":
    app = ChannelSelectorApp()
    app.mainloop()