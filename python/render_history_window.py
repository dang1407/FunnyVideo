import datetime
import tkinter as tk
from python.consts import *
from python.editor_ui import EditorWindow
from python.helper import read_all_folder_name, load_history_folder, read_all_file_name, read_json_file_content, \
    get_video_info
from tkinter import ttk, messagebox

class ClipViewerApp(tk.Toplevel):
    def __init__(self, root, channel_name):
        super().__init__(root)
        self.root = root
        self.root.title("Quản Lý Clips Đã Render")
        self.root.geometry("800x500")
        date_now = datetime.datetime.now()
        self.year = date_now.year
        self.month = date_now.month
        self.data = []
        self.history_folder_path = load_history_folder(channel_name)
        self.channel_name = channel_name
        # --- 1. Xử lý dữ liệu để lấy danh sách ngày ---
        self.year_availables = self._read_history_year_in_folder(self.history_folder_path)
        self.month_availables = self._read_history_month_in_year(self.history_folder_path, self.year)
        self.date_availables = self._read_history_file_in_month(self.history_folder_path, self.year, self.month)
        self.current_data = []  # Biến này sẽ lưu nội dung json hiện tại
        # --- 2. Tạo giao diện chọn ngày (Top Frame) ---
        top_frame = tk.Frame(self, pady=10)
        top_frame.pack(fill="x")

        # --- 3. Tạo bảng hiển thị clips (Bottom Frame) ---
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Định nghĩa cột
        columns = ("index", "time", "duration", "clips_list")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")

        # Tiêu đề cột
        self.tree.heading("index", text="STT")
        self.tree.heading("time", text="Giờ Render")
        self.tree.heading("duration", text="Thời Lượng (s)")
        self.tree.heading("clips_list", text="Danh sách clip")
        # Kích thước cột
        self.tree.column("index", width=30, anchor="center")
        self.tree.column("time", width=150, anchor="center")
        self.tree.column("duration", width=80, anchor="center")
        self.tree.column("clips_list", width=300, anchor="w")
        # Thanh cuộn (Scrollbar)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tk.Label(top_frame, text="Chọn năm: ", font=("Arial", 11, "bold")).pack(side="left", padx=10)

        self.year_combo = ttk.Combobox(top_frame, values=self.year_availables, state="readonly", font=("Arial", 10))
        self.year_combo.pack(side="left", padx=5)
        self.year_combo.bind("<<ComboboxSelected>>", self.on_year_select)

        if self.year_availables:
            if str(self.year) in self.year_availables:
                self.year_combo.set(self.year)
            else:
                self.year_combo.current(0)

        tk.Label(top_frame, text="Chọn tháng: ", font=("Arial", 11, "bold")).pack(side="left", padx=10)

        self.month_combo = ttk.Combobox(top_frame, values=self.month_availables, state="readonly", font=("Arial", 10))
        self.month_combo.pack(side="left", padx=5)
        self.month_combo.bind("<<ComboboxSelected>>", self.on_month_select)

        if self.month_availables:
            if str(self.month) in self.month_availables:
                self.month_combo.set(self.month)
            else:
                self.month_combo.current(0)  # Chọn ngày đầu tiên mặc định

        tk.Label(top_frame, text="Chọn ngày: ", font=("Arial", 11, "bold")).pack(side="left", padx=10)

        self.date_combo = ttk.Combobox(top_frame, values=self.date_availables, state="readonly", font=("Arial", 10))
        self.date_combo.pack(side="left", padx=5)
        self.date_combo.bind("<<ComboboxSelected>>", self.on_date_select)

        if self.date_availables:
            self.date_combo.current(len(self.date_availables) - 1)
            self.date_combo.event_generate("<<ComboboxSelected>>")

        button_frame = tk.Frame(self, pady=5)
        button_frame.pack(fill="x")
        # Button render
        render_button = tk.Button(button_frame, text="Render lại clip đã chọn",
                                  font=("Arial", 10, "bold"),  # Màu xanh cho dễ nhìn
                                  command=self._open_editor_window)
        render_button.pack(side="top")  # Căn giữa hoặc chỉnh side="left" tùy ý
        # Tải dữ liệu lần đầu (nếu có)
        if self.year_availables:
            self.on_year_select(None)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.root.deiconify()
        self.destroy()
    def on_year_select(self, event):
        """Xử lý khi người dùng chọn ngày"""
        try:
            selected_year = self.year_combo.get()
            print(selected_year)
            if selected_year != "":
                selected_year_int = int(selected_year)
                if selected_year_int != self.year:
                    self.year = selected_year_int
                    self.month_availables = self._read_history_month_in_year(self.history_folder_path, self.year)
                    self.month_combo["values"] = self.month_availables
                    if self.month_availables and len(self.month_availables) > 0:
                        self.month_combo.current(0)  # Reset tháng về đầu
                    self.on_month_select(None)  # Cập nhật lại ngày
        except Exception as e:
            print("lỗi", e)
    def on_month_select(self, event):
        """Xử lý khi người dùng chọn ngày"""
        try:
            selected_month = self.month_combo.get()
            if selected_month != self.month:
                self.month = int(selected_month)
                self.date_availables = self._read_history_file_in_month(self.history_folder_path, self.year, self.month)
                self.date_combo["values"] = self.date_availables
                old_value = self.date_combo.get()
                if old_value not in self.date_availables:
                    self.date_combo.set("")  # clear hiển thị
                else:
                    # nếu còn tồn tại → giữ nguyên hoặc chọn nó lại
                    self.date_combo.set(old_value)
                if self.date_availables and len(self.date_availables) > 0:
                    self.date_combo.current(len(self.date_availables) - 1)  # Reset ngày
                self.on_date_select(None)  # Load data
        except Exception as e:
                print("lỗi", e)
    def on_date_select(self, event):
        """Xử lý khi người dùng chọn ngày"""
        self.tree.delete(*self.tree.get_children())
        try:
            file_name = self.date_combo.get() + ".json"
            file_path = os.path.join(self.history_folder_path, str(self.year), str(self.month), file_name)
            # 1. Đọc và lưu vào self.current_data
            self.current_data = read_json_file_content(file_path)

            # 2. Hiển thị lên Treeview
            # Lưu ý: enumerate trả về (index, item). Code gốc của bạn ghi (clip, index) là bị ngược logic python chuẩn
            for index, clip in enumerate(self.current_data):
                clip_data = clip.get("clips")
                render_time = clip.get("datetime")
                sum_duration = 0
                clip_name_list = []

                if clip_data:
                    for clip_info in clip_data:
                        sum_duration += clip_info.get("duration", 0)
                        clip_name_list.append(os.path.basename(clip_info.get("path", "")))

                # Lưu index vào cột đầu tiên (ẩn hoặc hiện) để lúc click button biết lấy item nào trong mảng
                self.tree.insert("", "end",
                                 values=(index + 1, render_time, round(sum_duration, 2), ", ".join(clip_name_list)))

        except Exception as e:
            print("Lỗi on_date_select:", e)
            self.current_data = []  # Reset nếu lỗi
    def _read_history_year_in_folder(self, history_folder_path):
        file_names = read_all_folder_name(history_folder_path)
        return file_names

    def _read_history_month_in_year(self, history_folder_path, year = None):
        if year == None:
            year = datetime.datetime.now().year
        folder_path = os.path.join(history_folder_path, str(year))
        file_names = read_all_folder_name(folder_path)
        return file_names

    def _read_history_file_in_month(self, history_folder_path, year, month = None):
        if month == None:
            month = datetime.datetime.now().month
        folder_path = os.path.join(history_folder_path, str(year), str(month))
        file_names_raw = read_all_file_name(folder_path)
        file_names = []
        for file_name in file_names_raw:
            file_names.append(file_name.replace(".json", ""))
        return file_names

    def _open_editor_window(self):
        """Hàm mở Editor với dữ liệu từ dòng được chọn"""
        # 1. Lấy dòng đang được chọn trên Treeview
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Chưa chọn video", "Bạn chưa chọn video nào để render lại")
            return

        # 2. Lấy thông tin cột đầu tiên (index)
        item = self.tree.item(selected_items[0])
        record = item['values']
        if not record:
            return

        data_index = int(record[0]) - 1  # Lấy STT

        # 3. Lấy dữ liệu gốc từ self.current_data dựa vào STT
        if data_index < len(self.current_data):
            history_item = self.current_data[data_index]
            clips_list = history_item.get("clips", [])

            # 4. Khởi tạo Editor
            # Lưu ý: EditorWindow thường cần root hoặc toplevel làm master
            # Ở đây ta truyền self.root hoặc tạo Toplevel mới tùy cấu trúc EditorWindow của bạn
            editor = EditorWindow(self.root, self.channel_name)

            # 5. Đổ dữ liệu vào editor
            # Bạn cần mapping đúng format mà EditorWindow yêu cầu
            for clip in clips_list:
                # Tạo BooleanVar cho checkbox
                is_checked = clip.get("var", True)
                thumb_duration, thumb_path = get_video_info(clip.get("path"))
                clip_obj = {
                    "path": clip.get("path"),
                    "duration": clip.get("duration"),
                    "thumb_path": thumb_path,
                    "var": tk.BooleanVar(value=is_checked)
                }
                editor.imported_clips.append(clip_obj)

            # 6. Render lại giao diện clip bên trong Editor
            if hasattr(editor, 'render_clip_list'):
                editor.render_clip_list()
            else:
                print("EditorWindow class chưa có hàm render_clip_list")
        else:
            print("Lỗi: Index không khớp với dữ liệu hiện tại")
