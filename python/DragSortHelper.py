try:
    from Tkinter import Frame
except ImportError:
    from tkinter import Frame
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
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

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

        # Python3 compatibility: dict.values() return a view
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

        cursor_x = self._x + event.x
        cursor_y = self._y + event.y

        self._x += event.x_root - self._move_lastx
        self._y += event.y_root - self._move_lasty

        self._move_lastx = event.x_root
        self._move_lasty = event.y_root

        self.place_configure(x=self._x, y=self._y)

        if self._drag_handler:
            self._drag_handler(cursor_x, cursor_y)

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
