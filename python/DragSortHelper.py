from tkinter import *
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
import os

THUMBNAIL_SIZE = (120, 68)

# -----------------------------
# Item class (như cũ)
# -----------------------------
class Item(Frame):
    def __init__(self, master, value, width, height, selection_handler=None, drag_handler=None, drop_handler=None,
                 **kwargs):
        kwargs.setdefault("class_", "Item")
        Frame.__init__(self, master, **kwargs)
        self._x = None
        self._y = None
        self._width = width
        self._height = height
        self._tag = "item%s" % id(self)
        self._value = value
        self._selection_handler = selection_handler
        self._drag_handler = drag_handler
        self._drop_handler = drop_handler

    @property
    def value(self):
        return self._value

    def init(self, container, x, y):
        self._x = x
        self._y = y
        self.place(in_=container, x=x, y=y, width=self._width, height=self._height)
        self.bind_class(self._tag, "<ButtonPress-1>", self._on_selection)
        self.bind_class(self._tag, "<B1-Motion>", self._on_drag)
        self.bind_class(self._tag, "<ButtonRelease-1>", self._on_drop)
        self._add_bindtag(self)
        list_of_widgets = list(self.children.values())
        while len(list_of_widgets) != 0:
            widget = list_of_widgets.pop()
            list_of_widgets.extend(widget.children.values())
            self._add_bindtag(widget)

    def _add_bindtag(self, widget):
        bindtags = widget.bindtags()
        if self._tag not in bindtags:
            widget.bindtags((self._tag,) + bindtags)

    def _on_selection(self, event):
        self.tkraise()
        self._move_lastx = event.x_root
        self._move_lasty = event.y_root
        if self._selection_handler:
            self._selection_handler(self)

    def _on_drag(self, event):
        self.master.update_idletasks()
        self._x += event.x_root - self._move_lastx
        self._y += event.y_root - self._move_lasty
        self._move_lastx = event.x_root
        self._move_lasty = event.y_root
        self.place_configure(x=self._x, y=self._y)
        if self._drag_handler:
            self._drag_handler(self._x, self._y)

    def _on_drop(self, event):
        if self._drop_handler:
            self._drop_handler()

    def set_position(self, x, y):
        self._x = x
        self._y = y
        self.place_configure(x=x, y=y)

    def move(self, dx, dy):
        self._x += dx
        self._y += dy
        self.place_configure(x=self._x, y=self._y)


# -----------------------------
# DDList class (thêm callback)
# -----------------------------
class DDList(Frame):
    def __init__(self, master, item_width, item_height, item_relief=None, item_background=None, item_borderwidth=None,
                 offset_x=0, offset_y=0, gap=0, reorder_callback=None, **kwargs):
        kwargs["width"] = item_width + offset_x * 2
        kwargs["height"] = offset_y * 2
        Frame.__init__(self, master, **kwargs)
        self._item_borderwidth = item_borderwidth
        self._item_relief = item_relief
        self._item_background = item_background
        self._item_width = item_width
        self._item_height = item_height
        self._offset_x = offset_x
        self._offset_y = offset_y
        self._left = offset_x
        self._top = offset_y
        self._right = self._offset_x + self._item_width
        self._bottom = self._offset_y
        self._gap = gap
        self._list_of_items = []
        self._position = {}
        self._index_of_selected_item = None
        self._index_of_empty_container = None
        self._reorder_callback = reorder_callback  # ✅ callback khi reorder

    def add_item(self, item, index=None):
        if index is None:
            index = len(self._list_of_items)
        else:
            for i in range(index, len(self._list_of_items)):
                _item = self._list_of_items[i]
                _item.move(0, self._item_height + self._gap)
                self._position[_item] += 1
        x = self._offset_x
        y = self._offset_y + index * (self._item_height + self._gap)
        self._list_of_items.insert(index, item)
        self._position[item] = index
        item.init(self, x, y)
        self._bottom = self._offset_y + len(self._list_of_items) * (self._item_height + self._gap)
        self.configure(height=self._bottom)
        return item

    def _on_item_selected(self, item):
        self._index_of_selected_item = self._position[item]
        self._index_of_empty_container = self._index_of_selected_item

    def _on_item_dragged(self, x, y):
        quotient, remainder = divmod(y - self._offset_y, self._item_height + self._gap)
        if remainder < self._item_height:
            new_container = max(0, min(quotient, len(self._list_of_items) - 1))
            if new_container != self._index_of_empty_container:
                if new_container > self._index_of_empty_container:
                    for index in range(self._index_of_empty_container + 1, new_container + 1):
                        item = self._list_of_items[index]
                        item.move(0, -(self._item_height + self._gap))
                else:
                    for index in range(self._index_of_empty_container - 1, new_container - 1, -1):
                        item = self._list_of_items[index]
                        item.move(0, self._item_height + self._gap)
                self._index_of_empty_container = new_container

    def _on_item_dropped(self):
        """Xử lý reorder + callback cập nhật list gốc"""
        if self._index_of_selected_item is None:
            return
        item = self._list_of_items.pop(self._index_of_selected_item)
        self._list_of_items.insert(self._index_of_empty_container, item)
        # cập nhật vị trí hiển thị
        for i, it in enumerate(self._list_of_items):
            x = self._offset_x
            y = self._offset_y + i * (self._item_height + self._gap)
            it.set_position(x, y)
            self._position[it] = i
        # gọi callback nếu có
        if self._reorder_callback:
            new_order = [it.value for it in self._list_of_items]
            self._reorder_callback(new_order)
        # reset
        self._index_of_selected_item = None
        self._index_of_empty_container = None


# -----------------------------
# ClipItem class
# -----------------------------
class ClipItem(Item):
    def __init__(self, master, clip, width, height, app_ref, **kwargs):
        super().__init__(master, clip, width, height,
                         selection_handler=master._on_item_selected,
                         drag_handler=master._on_item_dragged,
                         drop_handler=master._on_item_dropped,
                         **kwargs)
        self.app_ref = app_ref
        self.clip = clip

        frame = ttk.Frame(self, padding=5)
        frame.pack(fill="both", expand=True)

        # Thumbnail
        try:
            img = Image.open(clip["thumb_path"])
            img = img.resize(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        except Exception:
            img = Image.new("RGB", THUMBNAIL_SIZE, (50, 50, 50))
            draw = ImageDraw.Draw(img)
            draw.text((10, 25), "No Thumb", fill="white")

        photo = ImageTk.PhotoImage(img)
        thumb_label = ttk.Label(frame, image=photo)
        thumb_label.image = photo
        thumb_label.pack(side="left", padx=5)
        self.app_ref._image_references.append(photo)

        # Checkbox
        check = ttk.Checkbutton(frame, variable=clip["var"])
        check.pack(side="left", padx=5)
        check.configure(command=lambda: self.app_ref.toggle_select_clip(self.app_ref.imported_clips.index(clip)))

        # Thông tin
        info_text = f"{os.path.basename(clip['path'])}\n[{self.app_ref.format_time(clip['duration'])}]"
        info_label = ttk.Label(frame, text=info_text, justify="left", font=("Arial", 8))
        info_label.pack(side="left", fill="x", expand=True, padx=5)

        # Nút Play
        play_btn = ttk.Button(frame, text="▶", width=4)
        play_btn.pack(side="right", padx=5)
        play_btn.configure(command=lambda p=clip["path"]: self.app_ref._open_in_default_player(p))


# -----------------------------
# Hàm render clip list (bạn gọi cái này trong app)
# -----------------------------
def render_clip_list(self):
    for child in self.media_items_frame.winfo_children():
        child.destroy()

    def on_reorder(new_order):
        """Callback khi reorder -> cập nhật self.imported_clips"""
        self.imported_clips = new_order

    ddlist = DDList(self.media_items_frame, item_width=600, item_height=80, item_relief="groove",
                    item_borderwidth=1, item_background="#2f2f2f", offset_x=5, offset_y=5, gap=5,
                    reorder_callback=on_reorder)
    ddlist.pack(fill="both", expand=True)

    for clip in self.imported_clips:
        item = ClipItem(ddlist, clip, 600, 80, self)
        ddlist.add_item(item)

    self.ddlist = ddlist
