import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw
import os

THUMBNAIL_SIZE = (120, 68)

# -----------------------------
# Item class
# -----------------------------
class Item(ctk.CTkFrame):
    def __init__(self, master, value, width, height, selection_handler=None, drag_handler=None, drop_handler=None,
                 **kwargs):
        # ctk frame usage
        super().__init__(master, width=width, height=height, **kwargs)
        
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
        self.place(x=x, y=y)
        
        # Binding events on the frame itself
        self.bind("<ButtonPress-1>", self._on_selection)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_drop)
        
        # Recursively bind children so drag works anywhere on item
        self._bind_children(self)

    def _bind_children(self, widget):
        for child in widget.winfo_children():
            # Avoid overwriting existing bindings if buttons etc?
            # ctk buttons have their own events. 
            # We generally want drag on Frame/Label, not Button which has action.
            if not isinstance(child, (ctk.CTkButton, ctk.CTkEntry, ctk.CTkCheckBox, ctk.CTkSwitch)):
                child.bind("<ButtonPress-1>", self._on_selection)
                child.bind("<B1-Motion>", self._on_drag)
                child.bind("<ButtonRelease-1>", self._on_drop)
                self._bind_children(child)

    def _on_selection(self, event):
        self.tkraise()
        self._move_lastx = event.x_root
        self._move_lasty = event.y_root
        if self._selection_handler:
            self._selection_handler(self)

    def _on_drag(self, event):
        # Event coordinates are relative to widget, but x_root/y_root are screen
        # We move based on delta
        dx = event.x_root - self._move_lastx
        dy = event.y_root - self._move_lasty
        self._x += dx
        self._y += dy
        self._move_lastx = event.x_root
        self._move_lasty = event.y_root
        self.place_configure(x=self._x, y=self._y)
        
        if self._drag_handler:
            # We might want to pass x, y relative to container?
            # The logic in DDList needs x,y. _x, _y are correct vars.
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
# DDList class
# -----------------------------
class DDList(ctk.CTkFrame):
    def __init__(self, master, item_width, item_height, item_relief=None, item_background=None, item_borderwidth=None,
                 offset_x=0, offset_y=0, gap=0, reorder_callback=None, **kwargs):
        # Calculate size required? No, we set via place or pack in parent. 
        # But we need to manage internal height for scrolling if parent is scrollable.
        # However, DDList places items absolutely inside itself. 
        # So DDList must be big enough.
        
        # We init with minimal size or specific size?
        # logic: kwargs["width"] = item_width + offset_x * 2
        # CTkFrame kwargs might differ.
        super().__init__(master, **kwargs)
        
        # Set colors if provided
        if item_background:
            self.configure(fg_color=item_background)
            
        self._item_borderwidth = item_borderwidth
        self._item_relief = item_relief # Not fully used in CTkFrame same way
        self._item_width = item_width
        self._item_height = item_height
        self._offset_x = offset_x
        self._offset_y = offset_y
        self._gap = gap
        self._list_of_items = []
        self._position = {}
        self._index_of_selected_item = None
        self._index_of_empty_container = None
        self._reorder_callback = reorder_callback

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
        # Important: set height so parent scrollable frame knows size if packed
        return item

    def _on_item_selected(self, item):
        self._index_of_selected_item = self._position[item]
        self._index_of_empty_container = self._index_of_selected_item

    def _on_item_dragged(self, x, y):
        # Calculate which index we are hovering over
        # y is relative to DDList top
        quotient, remainder = divmod(y - self._offset_y, self._item_height + self._gap)
        # tolerance for overlap? simplified logic from original
        if remainder < self._item_height + self._gap: # check range
            new_container = max(0, min(int(quotient), len(self._list_of_items) - 1))
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
        if self._index_of_selected_item is None:
            return
        item = self._list_of_items.pop(self._index_of_selected_item)
        self._list_of_items.insert(self._index_of_empty_container, item)
        
        for i, it in enumerate(self._list_of_items):
            x = self._offset_x
            y = self._offset_y + i * (self._item_height + 3.4 * self._gap)
            it.set_position(x, y)
            self._position[it] = i

        if self._reorder_callback:
            # We assume item.value contains the clip data
            new_order = [it.value for it in self._list_of_items]
            self._reorder_callback(new_order)

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
                         fg_color=("gray90", "gray20"), # Light/Dark mode colors
                         corner_radius=6,
                         **kwargs)
        self.app_ref = app_ref
        self.clip = clip

        # Layout inside the item
        # Use grid or pack. Pack is easier for left-to-right.
        
        # Thumbnail
        try:
            img = Image.open(clip["thumb_path"])
            img = img.resize(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        except Exception:
            img = Image.new("RGB", THUMBNAIL_SIZE, (50, 50, 50))
            draw = ImageDraw.Draw(img)
            draw.text((10, 25), "No Thumb", fill="white")

        photo = ctk.CTkImage(light_image=img, dark_image=img, size=THUMBNAIL_SIZE)
        # Using CTkImage for high DPI support
        
        thumb_label = ctk.CTkLabel(self, image=photo, text="")
        thumb_label.image = photo # Keep ref? CTkImage usually handles it but good practice.
        thumb_label.pack(side="left", padx=5, pady=5)
        
        # We need to keep ref in app logic if used elsewhere, 
        # but CTkImage helps. Original code stored in self.app_ref._image_references.
        # We can still do that.
        # self.app_ref._image_references.append(photo) 
        # Note: CTkImage object, not ImageTk.PhotoImage.
        
        # Checkbox
        # ctk checkbox uses variable (IntVar or BooleanVar, compatible)
        check = ctk.CTkCheckBox(self, variable=clip["var"], text="", width=24, command=lambda: self.app_ref.toggle_select_clip(self.app_ref.imported_clips.index(clip)))
        check.pack(side="left", padx=5)

        # Info
        info_text = f"{os.path.basename(clip['path'])}\n[{self.app_ref.format_time(clip['duration'])}]"
        info_label = ctk.CTkLabel(self, text=info_text, justify="left", font=("Arial", 12))
        info_label.pack(side="left", fill="x", expand=True, padx=5)
        
        # Buttons
        play_btn = ctk.CTkButton(self, text="▶", width=30)
        play_btn.pack(side="right", padx=5)
        play_btn.configure(command=lambda p=clip["path"]: self.app_ref._open_in_default_player(p))

