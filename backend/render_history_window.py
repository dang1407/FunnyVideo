import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import os
import customtkinter as ctk
from consts import *
from editor_ui import EditorWindow, get_video_info
from helper import read_all_folder_name, load_history_folder, read_all_file_name, read_json_file_content

class ClipViewerApp(ctk.CTkToplevel):
    def __init__(self, root, channel_name):
        super().__init__(root)
        self.title("Quản Lý Clips Đã Render")
        
        # Center window on screen
        width = 900
        height = 650
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        # Đảm bảo cửa sổ luôn ở trên cửa sổ main
        self.attributes('-topmost', True)
        self.after(100, lambda: self.attributes('-topmost', False))
        
        # Data setup
        date_now = datetime.datetime.now()
        self.year = date_now.year
        self.month = date_now.month
        self.data = []
        self.history_folder_path = load_history_folder(channel_name)
        self.channel_name = channel_name
        self.current_data = []

        self.year_availables = self._read_history_year_in_folder(self.history_folder_path)
        self.month_availables = self._read_history_month_in_year(self.history_folder_path, self.year)
        self.date_availables = self._read_history_file_in_month(self.history_folder_path, self.year, self.month)

        self._create_widgets()
        
        # Load initial data
        if self.year_availables:
            if str(self.year) in self.year_availables:
                self.year_combo.set(str(self.year))
            else:
                self.year_combo.set(self.year_availables[0])
            self.on_year_select(None)
            
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self):
        # Top Config Frame
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(top_frame, text="Năm:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.year_combo = ctk.CTkComboBox(top_frame, values=self.year_availables, command=self._on_year_cb, width=100)
        self.year_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(top_frame, text="Tháng:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.month_combo = ctk.CTkComboBox(top_frame, values=[], command=self._on_month_cb, width=100)
        self.month_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(top_frame, text="Ngày (File):", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.date_combo = ctk.CTkComboBox(top_frame, values=[], command=self._on_date_cb, width=200)
        self.date_combo.pack(side="left", padx=5)
        
        # Treeview (Data Table)
        # Treeview is not available in CTk. We use ttk.Treeview but wrap it or style it.
        tree_frame = ctk.CTkFrame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Style text colors for Treeview to match Dark theme
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2b2b2b", 
                        foreground="white", 
                        fieldbackground="#2b2b2b", 
                        font=("Arial", 12),
                        rowheight=32)
        style.configure("Treeview.Heading",
                        font=("Arial", 13, "bold"),
                        background="#1f1f1f",
                        foreground="white")
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.map('Treeview.Heading',
                  background=[('active', 'white'), ('!active', 'white')],
                  foreground=[('active', '#1f1f1f'), ('!active', '#1f1f1f')])
        
        columns = ("index", "time", "duration", "clips_list")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        self.tree.heading("index", text="STT")
        self.tree.heading("time", text="Giờ Render")
        self.tree.heading("duration", text="Thời Lượng (s)")
        self.tree.heading("clips_list", text="Danh sách clip")
        
        self.tree.column("index", width=50, anchor="center")
        self.tree.column("time", width=150, anchor="center")
        self.tree.column("duration", width=100, anchor="center")
        self.tree.column("clips_list", width=400, anchor="w")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bottom Button Frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        render_btn = ctk.CTkButton(btn_frame, text="Render lại clip đã chọn", 
                                   command=self._open_editor_window, 
                                   font=("Arial", 14, "bold"), height=40)
        render_btn.pack(side="bottom", fill="x") # Or center it?
        
    def _on_year_cb(self, value):
        self.on_year_select(None)
    def _on_month_cb(self, value):
        self.on_month_select(None)
    def _on_date_cb(self, value):
        self.on_date_select(None)

    def _on_close(self):
        # We don't deiconify root here because Editor might be main.
        # But per previous logic:
        if self.master:
            self.master.deiconify()
        self.destroy()

    def on_year_select(self, event):
        try:
            selected_year = self.year_combo.get()
            if selected_year:
                self.year = int(selected_year)
                self.month_availables = self._read_history_month_in_year(self.history_folder_path, self.year)
                self.month_combo.configure(values=self.month_availables)
                if self.month_availables:
                    self.month_combo.set(self.month_availables[0])
                    self.on_month_select(None)
                else:
                    self.month_combo.set("")
                    self.date_combo.set("")
                    self.tree.delete(*self.tree.get_children())
        except Exception as e: print(e)

    def on_month_select(self, event):
        try:
            selected_month = self.month_combo.get()
            if selected_month:
                self.month = int(selected_month)
                self.date_availables = self._read_history_file_in_month(self.history_folder_path, self.year, self.month)
                self.date_combo.configure(values=self.date_availables)
                if self.date_availables:
                    self.date_combo.set(self.date_availables[-1])
                    self.on_date_select(None)
                else:
                    self.date_combo.set("")
                    self.tree.delete(*self.tree.get_children())
        except Exception as e: print(e)

    def on_date_select(self, event):
        self.tree.delete(*self.tree.get_children())
        try:
            val = self.date_combo.get()
            if not val: return
            file_name = val + ".json"
            file_path = os.path.join(self.history_folder_path, str(self.year), str(self.month), file_name)
            self.current_data = read_json_file_content(file_path)

            for index, clip in enumerate(self.current_data):
                clip_data = clip.get("clips", [])
                render_time = clip.get("datetime")
                sum_duration = sum(c.get("duration", 0) for c in clip_data)
                clip_names = [os.path.basename(c.get("path", "")) for c in clip_data]
                
                self.tree.insert("", "end", values=(index + 1, render_time, round(sum_duration, 2), ", ".join(clip_names)))
        except Exception as e:
            print("Error loading date:", e)
            self.current_data = []

    def _open_editor_window(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Chưa chọn video", "Bạn chưa chọn video nào để render lại")
            return

        item = self.tree.item(selected_items[0])
        record = item['values']
        if not record: return
        
        data_index = int(record[0]) - 1
        
        if data_index < len(self.current_data):
            history_item = self.current_data[data_index]
            clips_list = history_item.get("clips", [])
            
            # Open Editor
            editor = EditorWindow(self.master if self.master else self, self.channel_name)
            
            for clip in clips_list:
                thumb_duration, thumb_path = get_video_info(clip.get("path"))
                clip_obj = {
                    "path": clip.get("path"),
                    "duration": clip.get("duration"),
                    "thumb_path": thumb_path,
                    "var": ctk.BooleanVar(value=True) # Use ctk variable
                }
                editor.imported_clips.append(clip_obj)
            
            editor.render_clip_list()
        else:
            messagebox.showerror("Error", "Data sync error")

    def _read_history_year_in_folder(self, history_folder_path):
        result = read_all_folder_name(history_folder_path)
        return result if result is not None else []

    def _read_history_month_in_year(self, history_folder_path, year=None):
        if year is None: year = datetime.datetime.now().year
        folder_path = os.path.join(history_folder_path, str(year))
        result = read_all_folder_name(folder_path)
        return result if result is not None else []

    def _read_history_file_in_month(self, history_folder_path, year, month=None):
        if month is None: month = datetime.datetime.now().month
        folder_path = os.path.join(history_folder_path, str(year), str(month))
        file_names_raw = read_all_file_name(folder_path)
        if file_names_raw is None:
            return []
        return [f.replace(".json", "") for f in file_names_raw]
