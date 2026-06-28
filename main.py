import calendar
import os
import shutil
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

# --- ИМПОРТ НАШИХ СОБСТВЕННЫХ МОДУЛЕЙ ---
from config import BASE_DIR, DB_PATH, LOG_PATH
import database as db
from utils import write_log, normalize_date_input


class MainApp:
    def __init__(self, app_root: tk.Tk) -> None:
        self.root = app_root
        self.root.title("Гастроном Пивники 🍻")

        self.root.bind_class("Entry", "<Control-a>", self.select_all_text)
        self.daily_backup()

        # Запрашиваем конфигурацию из базы данных
        self.cfg_font_size, self.cfg_row_height = db.get_config()
        self.f_norm = ("Arial", self.cfg_font_size)
        self.f_bold = ("Arial", self.cfg_font_size, "bold")
        self.f_content = ("Arial", self.cfg_font_size + 2)
        self.f_big = ("Arial", self.cfg_font_size + 2, "bold")
        self.f_huge = ("Arial", self.cfg_font_size + 6, "bold")
        self.f_strike = ("Arial", self.cfg_font_size + 2, "overstrike")

        self.months_ru = [
            "Январь",
            "Февраль",
            "Март",
            "Апрель",
            "Май",
            "Июнь",
            "Июль",
            "Август",
            "Сентябрь",
            "Октябрь",
            "Ноябрь",
            "Декабрь",
        ]

        self.root.geometry("1150x700")
        self.root.minsize(900, 600)
        try:
            self.root.state("zoomed")
        except tk.TclError:
            self.root.attributes("-zoomed", True)

        self.root.configure(bg="#f4f5f7")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#f4f5f7", borderwidth=0)
        style.configure(
            "TNotebook.Tab", font=self.f_bold, padding=[15, 8], background="#e1e4e8"
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#4CAF50")],
            foreground=[("selected", "white")],
        )
        style.configure(
            "Treeview", font=self.f_norm, rowheight=self.cfg_row_height, borderwidth=0
        )
        style.configure(
            "Treeview.Heading",
            font=self.f_bold,
            background="#d1d5db",
            foreground="#333",
            padding=[0, 5],
        )
        style.map(
            "Treeview",
            background=[("selected", "#0078D7")],
            foreground=[("selected", "white")],
        )
        style.configure("TLabelframe", background="#f4f5f7", borderwidth=2)
        style.configure(
            "TLabelframe.Label",
            font=self.f_bold,
            background="#f4f5f7",
            foreground="#333",
        )

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_codes = tk.Frame(self.notebook, bg="#f4f5f7")
        self.tab_sroki = tk.Frame(self.notebook, bg="#f4f5f7")
        self.tab_todo = tk.Frame(self.notebook, bg="#f4f5f7")
        self.tab_breaks = tk.Frame(self.notebook, bg="#f4f5f7")
        self.tab_cash = tk.Frame(self.notebook, bg="#f4f5f7")
        self.tab_schedule = tk.Frame(self.notebook, bg="#f4f5f7")
        self.tab_history = tk.Frame(self.notebook, bg="#f4f5f7")
        self.tab_settings = tk.Frame(self.notebook, bg="#f4f5f7")

        self.notebook.add(self.tab_codes, text="⚖ Коды")
        self.notebook.add(self.tab_sroki, text="📅 Сроки")
        self.notebook.add(self.tab_todo, text="📋 Список дел")
        self.notebook.add(self.tab_breaks, text="⏳ Перерывы")
        self.notebook.add(self.tab_cash, text="💰 Касса")
        self.notebook.add(self.tab_schedule, text="🗓 График работы")
        self.notebook.add(self.tab_history, text="📜 История")
        self.notebook.add(self.tab_settings, text="⚙ Настройки")

        self.drag_widget: Optional[tk.Widget] = None
        self.drag_y: int = 0
        self.drag_item_id: Optional[int] = None
        self.drag_placeholder: Optional[tk.Frame] = None

        self.cash_vars: Dict[int, tk.StringVar] = {}
        self.cash_labels: Dict[int, tk.Label] = {}

        self.setup_global_context_menu()
        self.setup_codes_tab()
        self.setup_sroki_tab()
        self.setup_todo_tab()
        self.setup_breaks_tab()
        self.setup_cash_tab()
        self.setup_schedule_tab()
        self.setup_history_tab()
        self.setup_settings_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

        self.root.bind("<F1>", lambda e: self.notebook.select(0))
        self.root.bind("<F2>", lambda e: self.notebook.select(1))
        self.root.bind("<F3>", lambda e: self.notebook.select(2))
        self.root.bind("<F4>", lambda e: self.notebook.select(3))
        self.root.bind("<F5>", lambda e: self.notebook.select(4))
        self.root.bind("<F6>", lambda e: self.notebook.select(5))
        self.root.bind("<F7>", lambda e: self.notebook.select(6))
        self.root.bind("<F8>", lambda e: self.notebook.select(7))

        self.root.after(1000, self.check_expired_on_startup)

    def setup_global_context_menu(self) -> None:
        self.context_menu = tk.Menu(self.root, tearoff=0, font=self.f_norm)
        self.context_menu.add_command(label="Копировать", command=self.copy_text)
        self.context_menu.add_command(label="Вставить", command=self.paste_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Выделить всё", command=self.select_all_context
        )
        self.root.bind_class("Entry", "<Button-3>", self.show_context_menu)

    def show_context_menu(self, event: tk.Event) -> None:
        self.focused_widget = event.widget
        if isinstance(event.widget, tk.Entry):
            self.context_menu.tk_popup(
                getattr(event, "x_root", 0), getattr(event, "y_root", 0)
            )

    def copy_text(self) -> None:
        try:
            if hasattr(self, "focused_widget") and isinstance(
                self.focused_widget, tk.Entry
            ):
                self.root.clipboard_clear()
                self.root.clipboard_append(self.focused_widget.selection_get())
        except tk.TclError:
            pass

    def paste_text(self) -> None:
        try:
            if hasattr(self, "focused_widget") and isinstance(
                self.focused_widget, tk.Entry
            ):
                text = self.root.clipboard_get()
                self.focused_widget.insert(tk.INSERT, text)
        except tk.TclError:
            pass

    def select_all_context(self) -> None:
        if hasattr(self, "focused_widget") and isinstance(
            self.focused_widget, tk.Entry
        ):
            self.focused_widget.select_range(0, tk.END)
            self.focused_widget.icursor(tk.END)

    def select_all_text(self, event: tk.Event) -> str:
        if isinstance(event.widget, tk.Entry):
            event.widget.select_range(0, tk.END)
            event.widget.icursor(tk.END)
        return "break"

    def daily_backup(self) -> None:
        if not os.path.exists(DB_PATH):
            return
        backup_dir = os.path.join(BASE_DIR, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        today = datetime.now().strftime("%d_%m_%Y")
        backup_file = os.path.join(backup_dir, f"backup_{today}.db")
        if not os.path.exists(backup_file):
            shutil.copy2(DB_PATH, backup_file)

    def check_expired_on_startup(self) -> None:
        expired_items = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for _, name, _, d_to, _ in db.get_all_sroki_v3():
            try:
                e_date = datetime.strptime(d_to, "%d.%m.%Y")
                if (e_date - today).days <= 0:
                    expired_items.append(f"• {name}")
            except ValueError:
                continue

        if expired_items:
            count = len(expired_items)
            msg = f"Найдено просроченных товаров: {count}\n\n"
            msg += "\n".join(expired_items[:10])
            if count > 10:
                msg += f"\n...и еще {count - 10} шт."
            msg += "\n\nЗайди во вкладку «Сроки»!"
            messagebox.showwarning("⚠️ ЕСТЬ ПРОСРОЧКА!", msg)

    def treeview_sort_column(self, tv: ttk.Treeview, col: str, reverse: bool) -> None:
        columns_data = [(tv.set(k, col), k) for k in tv.get_children("")]
        try:
            columns_data.sort(key=lambda t: int(t[0]), reverse=reverse)
        except ValueError:
            columns_data.sort(reverse=reverse)

        for index, (_, k) in enumerate(columns_data):
            tv.move(k, "", index)
        tv.heading(col, command=lambda: self.treeview_sort_column(tv, col, not reverse))

    def on_tab_change(self, event: tk.Event) -> None:
        tab_index = self.notebook.index(self.notebook.select())
        if tab_index == 0 and hasattr(self, "search_entry"):
            self.search_entry.focus()
        elif tab_index == 1 and hasattr(self, "sr_name"):
            self.sr_name.focus()
        elif tab_index == 2 and hasattr(self, "todo_entry"):
            self.todo_entry.focus()

    # --- Вкладка: To-Do ---
    def setup_todo_tab(self) -> None:
        for widget in self.tab_todo.winfo_children():
            widget.destroy()

        search_frame = tk.Frame(self.tab_todo, bg="#f4f5f7")
        search_frame.pack(side="top", fill="x", padx=10, pady=(10, 0))

        tk.Label(search_frame, text="🔍", bg="#f4f5f7", font=self.f_big).pack(
            side="left"
        )
        self.todo_search_var = tk.StringVar()
        self.todo_search_var.trace_add("write", lambda *a: self.update_todo_list())
        tk.Entry(
            search_frame,
            textvariable=self.todo_search_var,
            font=self.f_norm,
            relief="flat",
            background="#e1e4e8",
            highlightthickness=0,
        ).pack(side="left", fill="x", expand=True, padx=5, ipady=3)

        input_container = tk.Frame(self.tab_todo, bg="#f4f5f7")
        input_container.pack(side="top", fill="x", padx=10, pady=10)

        tk.Label(
            input_container,
            text="Новая задача:",
            font=self.f_bold,
            bg="#f4f5f7",
            fg="#333",
        ).pack(anchor="w")
        tk.Label(
            input_container,
            text="(Перетаскивай задачи мышкой, чтобы менять порядок)",
            font=("Arial", 10),
            bg="#f4f5f7",
            fg="gray",
        ).pack(anchor="w")

        self.todo_entry = tk.Entry(
            input_container, font=self.f_big, relief="flat", highlightthickness=1
        )
        self.todo_entry.pack(fill="x", pady=5)
        self.todo_entry.bind("<Return>", self.save_todo)

        tk.Button(
            input_container,
            text="Добавить",
            font=self.f_bold,
            bg="#4CAF50",
            fg="white",
            relief="raised",
            cursor="hand2",
            command=self.save_todo,
        ).pack(fill="x", pady=5, ipady=5)

        canvas_frame = tk.Frame(self.tab_todo, bg="#f4f5f7")
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.todo_canvas = tk.Canvas(canvas_frame, bg="#f4f5f7", highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.todo_canvas.yview
        )

        self.scrollable_frame = tk.Frame(self.todo_canvas, bg="#f4f5f7")
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.todo_canvas.configure(
                scrollregion=self.todo_canvas.bbox("all")
            ),
        )

        frame_id = self.todo_canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        self.todo_canvas.bind(
            "<Configure>",
            lambda e: self.todo_canvas.itemconfig(frame_id, width=e.width),
        )
        self.todo_canvas.configure(yscrollcommand=scrollbar.set)

        self.todo_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tk.Button(
            self.tab_todo,
            text="🗑 УДАЛИТЬ ВСЕ ЗАДАЧИ",
            font=self.f_big,
            bg="#d32f2f",
            fg="white",
            relief="raised",
            cursor="hand2",
            command=self.clear_all_todos,
        ).pack(pady=5, padx=15)

        self.todo_menu = tk.Menu(self.root, tearoff=0, font=self.f_norm)
        self.todo_menu.add_command(
            label="❌ Удалить", command=self.delete_selected_todo_context
        )
        self.update_todo_list()

    def update_todo_list(self) -> None:
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        search = (
            self.todo_search_var.get().lower()
            if hasattr(self, "todo_search_var")
            else ""
        )
        for db_id, task, is_done, _ in db.get_all_todos():
            if not search or search in task.lower():
                self.create_task_card(self.scrollable_frame, db_id, task, is_done)

        self.root.update_idletasks()
        self.todo_canvas.configure(scrollregion=self.todo_canvas.bbox("all"))

    def create_task_card(
        self, parent: tk.Widget, db_id: int, task: str, is_done: int
    ) -> None:
        bg_color = "white"
        fg_color = "#333" if not is_done else "#999"
        font = self.f_content if not is_done else self.f_strike
        icon = "○" if not is_done else "✓"
        icon_color = "#ccc" if not is_done else "#FFD700"

        card = tk.Frame(parent, bg=bg_color, bd=0)
        setattr(card, "db_id", db_id)
        card.pack(fill="x", pady=1, padx=2)

        tk.Frame(card, bg="#f0f0f0", height=1).pack(side="bottom", fill="x")
        inner = tk.Frame(card, bg=bg_color, padx=10, pady=10)
        inner.pack(fill="both", expand=True)

        lbl_icon = tk.Label(
            inner,
            text=icon,
            font=("Arial", self.cfg_font_size + 4, "bold"),
            bg=bg_color,
            fg=icon_color if is_done else "#ccc",
            cursor="hand2",
            width=3,
        )
        lbl_icon.pack(side="left")

        lbl = tk.Label(
            inner,
            text=task,
            font=font,
            bg=bg_color,
            fg=fg_color,
            wraplength=350,
            justify="left",
            anchor="w",
            cursor="fleur",
        )
        lbl.pack(side="left", fill="x", expand=True, padx=5)

        lbl_icon.bind("<Button-1>", lambda e: self.toggle_todo(db_id, is_done))

        for w in (inner, lbl):
            w.bind(
                "<Button-1>",
                lambda e, widget=card, item_id=db_id: self.on_drag_start(
                    e, widget, item_id
                ),
            )
            w.bind("<B1-Motion>", self.on_drag_motion)
            w.bind("<ButtonRelease-1>", self.on_drag_stop)
            w.bind(
                "<Button-3>",
                lambda e, item_id=db_id: self.show_todo_context(e, item_id),
            )

    def on_drag_start(self, event: Any, widget: tk.Widget, item_id: int) -> None:
        if self.drag_widget:
            return
        self.drag_widget = widget
        self.drag_item_id = item_id
        self.drag_y = getattr(event, "y_root", 0)
        self.drag_placeholder = tk.Frame(
            self.scrollable_frame, bg="#e0e0e0", height=widget.winfo_height()
        )

        for child in widget.winfo_children():
            if isinstance(child, tk.Frame):
                child["bg"] = "#e1f5fe"
                for sub in child.winfo_children():
                    sub["bg"] = "#e1f5fe"
                    

    def on_drag_motion(self, event: Any) -> None:
        if not self.drag_widget or not self.drag_placeholder:
            return
        y = getattr(event, "y_root", 0)
        for w in self.scrollable_frame.winfo_children():
            if w == self.drag_widget or w == self.drag_placeholder:
                continue
            w_y, w_h = w.winfo_rooty(), w.winfo_height()
            if w_y < y < w_y + w_h:
                if y < w_y + w_h / 2:
                    self.drag_placeholder.pack(before=w, fill="x", pady=1, padx=2)
                else:
                    self.drag_placeholder.pack(after=w, fill="x", pady=1, padx=2)
                break

    def on_drag_stop(self, event: tk.Event) -> None:
        if not self.drag_widget or not self.drag_placeholder:
            return
        self.drag_widget.pack(before=self.drag_placeholder, fill="x", pady=1, padx=2)
        self.drag_placeholder.destroy()

        updates = []
        for i, child in enumerate(self.scrollable_frame.pack_slaves()):
            db_id = getattr(child, "db_id", None)
            if db_id is not None:
                updates.append((i, db_id))

        db.update_todo_positions_db(updates)
        self.drag_widget = self.drag_placeholder = self.drag_item_id = None
        self.update_todo_list()

    def show_todo_context(self, event: Any, item_id: int) -> None:
        self.selected_todo_id = item_id
        self.todo_menu.tk_popup(
            getattr(event, "x_root", 0), getattr(event, "y_root", 0)
        )

    def delete_selected_todo_context(self) -> None:
        if hasattr(self, "selected_todo_id") and self.selected_todo_id is not None:
            self.delete_todo(self.selected_todo_id)

    def save_todo(self, event: Optional[tk.Event] = None) -> None:
        task = self.todo_entry.get().strip()
        if not task:
            return
        db.add_todo_db(task, "today")
        write_log(f"Добавлена задача: {task}")
        self.todo_entry.delete(0, "end")
        self.update_todo_list()

    def toggle_todo(self, item_id: int, current_status: int) -> None:
        new_status = 0 if current_status else 1
        db.toggle_todo_db(item_id, new_status)
        write_log(
            f"Изменен статус задачи ID {item_id}: {'Выполнена' if new_status else 'Отменена'}"
        )
        self.update_todo_list()

    def delete_todo(self, item_id: int) -> None:
        db.delete_todo_db(item_id)
        write_log(f"Удалена задача ID {item_id}")
        self.update_todo_list()

    def clear_all_todos(self) -> None:
        if messagebox.askyesno(
            "ВНИМАНИЕ", "Вы уверены, что хотите УДАЛИТЬ ВСЕ задачи?"
        ):
            db.delete_all_todos_db()
            write_log("Очищен весь список задач")
            self.update_todo_list()

    # --- Вкладка: Перерывы ---
    def setup_breaks_tab(self) -> None:
        container = tk.Frame(self.tab_breaks, bg="#f4f5f7")
        container.pack(expand=True, fill="both", padx=20, pady=20)

        self.breaks_data = [
            ("🍲 до 13:00", "13:00"),
            ("🚬 до 16:00", "16:00"),
            ("🍔 до 21:00", "21:00"),
            ("🏡 Домой", "23:00"),
        ]
        self.break_labels: Dict[str, tk.Label] = {}

        for name, time_str in self.breaks_data:
            frame = tk.Frame(container, bg="white", bd=1, relief="raised")
            frame.pack(fill="x", pady=10, ipady=10)
            tk.Label(
                frame, text=f"{name}", font=self.f_big, bg="white", fg="#333"
            ).pack(side="left", padx=20)
            lbl_timer = tk.Label(
                frame, text="--:--:--", font=self.f_huge, bg="white", fg="#2196F3"
            )
            lbl_timer.pack(side="right", padx=20)
            self.break_labels[time_str] = lbl_timer

        self.update_breaks_timer()

    def update_breaks_timer(self) -> None:
        now = datetime.now()
        for name, time_str in self.breaks_data:
            target_time = datetime.strptime(time_str, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            diff = target_time - now
            lbl = self.break_labels[time_str]
            if diff.total_seconds() > 0:
                hours, remainder = divmod(int(diff.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                lbl.config(
                    text=f"через {hours:02}:{minutes:02}:{seconds:02}", fg="#2196F3"
                )
            else:
                lbl.config(
                    text="СМЕНА ОКОНЧЕНА!" if "Домой" in name else "00:00:00",
                    fg="#d32f2f" if "Домой" in name else "#999999",
                )
        self.root.after(1000, self.update_breaks_timer)

    # --- Вкладка: Касса ---
    def setup_cash_tab(self) -> None:
        main_frame = tk.Frame(self.tab_cash, bg="#f4f5f7")
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        grid_frame = tk.Frame(main_frame, bg="#f4f5f7")
        grid_frame.pack(side="left", fill="both", expand=True)

        tk.Label(
            grid_frame, text="Номинал", font=self.f_bold, bg="#f4f5f7", fg="#555"
        ).grid(row=0, column=0, padx=5, pady=5)
        tk.Label(
            grid_frame, text="Кол-во", font=self.f_bold, bg="#f4f5f7", fg="#555"
        ).grid(row=0, column=2, padx=5, pady=5)
        tk.Label(
            grid_frame, text="Сумма", font=self.f_bold, bg="#f4f5f7", fg="#555"
        ).grid(row=0, column=4, padx=5, pady=5)

        self.cash_entries: List[tk.Entry] = []
        denominations = [
            20000,
            10000,
            5000,
            2000,
            1000,
            500,
            200,
            100,
            50,
            20,
            10,
            5,
            1,
        ]

        for i, nominal in enumerate(denominations, start=1):
            tk.Label(
                grid_frame,
                text=f"{nominal} ₸",
                font=self.f_big,
                bg="#f4f5f7",
                anchor="e",
                width=8,
            ).grid(row=i, column=0, padx=5, pady=5)
            tk.Button(
                grid_frame,
                text="−",
                font=self.f_bold,
                width=3,
                bg="#ffcdd2",
                relief="flat",
                cursor="hand2",
                command=lambda n=nominal: self.change_cash_qty(n, -1),
            ).grid(row=i, column=1, padx=5)

            var = tk.StringVar(value="0")
            var.trace_add("write", self.calculate_cash)
            self.cash_vars[nominal] = var

            entry = tk.Entry(
                grid_frame,
                textvariable=var,
                font=self.f_big,
                width=6,
                justify="center",
                relief="flat",
                highlightthickness=1,
            )
            entry.grid(row=i, column=2, padx=5)
            self.cash_entries.append(entry)

            tk.Button(
                grid_frame,
                text="+",
                font=self.f_bold,
                width=3,
                bg="#c8e6c9",
                relief="flat",
                cursor="hand2",
                command=lambda n=nominal: self.change_cash_qty(n, 1),
            ).grid(row=i, column=3, padx=5)

            lbl_sum = tk.Label(
                grid_frame,
                text="0",
                font=self.f_big,
                bg="#f4f5f7",
                width=12,
                anchor="w",
                fg="#333",
            )
            lbl_sum.grid(row=i, column=4, padx=10)
            self.cash_labels[nominal] = lbl_sum

        for i, entry in enumerate(self.cash_entries):
            if i < len(self.cash_entries) - 1:
                entry.bind(
                    "<Return>",
                    lambda e, next_e=self.cash_entries[i + 1]: next_e.focus(),
                )

        total_frame = tk.Frame(main_frame, bg="white", bd=1, relief="raised")
        total_frame.pack(side="right", fill="y", padx=20, pady=20, ipadx=30)

        tk.Label(
            total_frame, text="ИТОГО В КАССЕ:", font=self.f_bold, bg="white", fg="#555"
        ).pack(pady=(30, 5))
        self.lbl_total_cash = tk.Label(
            total_frame,
            text="0 ₸",
            font=("Arial", 30, "bold"),
            bg="white",
            fg="#2196F3",
        )
        self.lbl_total_cash.pack(pady=5)
        tk.Frame(total_frame, height=2, bg="#eee", width=250).pack(pady=20)
        tk.Label(
            total_frame,
            text="Оставить на размен:",
            font=self.f_content,
            bg="white",
            fg="#777",
        ).pack(pady=2)
        tk.Label(
            total_frame, text="10 000 ₸", font=self.f_big, bg="white", fg="#333"
        ).pack(pady=2)
        tk.Frame(total_frame, height=2, bg="#eee", width=250).pack(pady=20)
        tk.Label(
            total_frame, text="Выручка:", font=self.f_bold, bg="white", fg="#333"
        ).pack(pady=(10, 5))
        self.lbl_withdraw = tk.Label(
            total_frame,
            text="-10 000 ₸",
            font=("Arial", 35, "bold"),
            bg="white",
            fg="#d32f2f",
        )
        self.lbl_withdraw.pack(pady=5)

        tk.Button(
            total_frame,
            text="🔄 Сбросить всё",
            font=self.f_bold,
            bg="#e1e4e8",
            relief="flat",
            cursor="hand2",
            command=self.reset_cash,
        ).pack(side="bottom", pady=30, ipady=5, fill="x", padx=20)

    def change_cash_qty(self, nominal: int, delta: int) -> None:
        var = self.cash_vars[nominal]
        try:
            val = int(var.get())
        except ValueError:
            val = 0
        var.set(str(max(0, val + delta)))

    def calculate_cash(self, *args: Any) -> None:
        total = 0
        for nominal, var in self.cash_vars.items():
            text_val = var.get()
            qty = int(text_val) if text_val.isdigit() else 0
            subtotal = nominal * qty
            total += subtotal
            self.cash_labels[nominal].config(text=f"{subtotal:,}".replace(",", " "))

        self.lbl_total_cash.config(text=f"{total:,} ₸".replace(",", " "))
        to_withdraw = total - 10000
        self.lbl_withdraw.config(
            text=f"{to_withdraw:,} ₸".replace(",", " "),
            fg="#4CAF50" if to_withdraw >= 0 else "#d32f2f",
        )

    def reset_cash(self) -> None:
        if messagebox.askyesno("Сброс", "Очистить все поля кассы?"):
            for var in self.cash_vars.values():
                var.set("0")

    # --- Вкладка: Коды ---
    def setup_codes_tab(self) -> None:
        tk.Label(self.tab_codes, text="Поиск:", font=self.f_bold, bg="#f4f5f7").pack(
            pady=5
        )
        search_frame = tk.Frame(self.tab_codes, bg="#f4f5f7")
        search_frame.pack(pady=5, padx=20, fill="x")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.update_list)
        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=self.f_big,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        tk.Button(
            search_frame,
            text="✖ Очистить",
            font=self.f_bold,
            bg="#e1e4e8",
            relief="flat",
            cursor="hand2",
            command=lambda: self.search_var.set(""),
        ).pack(side="right", padx=(10, 0))

        tree_frame = tk.Frame(self.tab_codes)
        tree_frame.pack(pady=5, padx=20, fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("Name", "Code"),
            show="headings",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.heading(
            "Name",
            text="Товар",
            command=lambda: self.treeview_sort_column(self.tree, "Name", False),
        )
        self.tree.heading(
            "Code",
            text="Код PLU",
            command=lambda: self.treeview_sort_column(self.tree, "Code", False),
        )
        self.tree.column("Name", width=800, anchor="w")
        self.tree.column("Code", width=150, anchor="center", stretch=False)

        self.codes_menu = tk.Menu(self.root, tearoff=0, font=self.f_norm)
        self.codes_menu.add_command(label="✏ Изменить", command=self.edit_selected_code)
        self.codes_menu.add_separator()
        self.codes_menu.add_command(
            label="🗑 Удалить", command=self.delete_selected_code
        )
        self.codes_menu.add_command(
            label="📋 Копировать код", command=self.copy_selected_code
        )
        self.tree.bind("<Button-3>", self.show_codes_menu)

        ctrl_frame = tk.Frame(self.tab_codes, bg="#f4f5f7")
        ctrl_frame.pack(pady=5)
        tk.Button(
            ctrl_frame,
            text="✏ Изменить",
            font=self.f_bold,
            bg="#e1e4e8",
            relief="flat",
            cursor="hand2",
            command=self.edit_selected_code,
        ).grid(row=0, column=0, padx=10)
        tk.Button(
            ctrl_frame,
            text="🗑 Удалить",
            font=self.f_bold,
            bg="#ffcccc",
            fg="#a00",
            relief="flat",
            cursor="hand2",
            command=self.delete_selected_code,
        ).grid(row=0, column=1, padx=10)

        add_frame = ttk.LabelFrame(
            self.tab_codes, text="Добавить код (Enter для перехода)"
        )
        add_frame.pack(pady=10, padx=20, fill="x")
        add_frame.columnconfigure(1, weight=1)

        tk.Label(add_frame, text="Название:", bg="#f4f5f7", font=self.f_big).grid(
            row=0, column=0, padx=(10, 5), pady=15, sticky="e"
        )
        self.name_entry = tk.Entry(
            add_frame,
            font=self.f_content,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.name_entry.grid(row=0, column=1, padx=5, pady=15, sticky="ew")

        tk.Label(add_frame, text="Код PLU:", bg="#f4f5f7", font=self.f_big).grid(
            row=0, column=2, padx=(15, 5), pady=15, sticky="e"
        )
        self.code_entry = tk.Entry(
            add_frame,
            font=self.f_content,
            width=15,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.code_entry.grid(row=0, column=3, padx=5, pady=15, sticky="w")

        tk.Button(
            add_frame,
            text="Добавить",
            font=self.f_big,
            bg="#4CAF50",
            fg="white",
            relief="flat",
            cursor="hand2",
            command=self.save_new,
        ).grid(row=0, column=4, padx=15, pady=15)

        self.name_entry.bind("<Return>", lambda e: self.code_entry.focus())
        self.code_entry.bind("<Return>", lambda e: self.save_new())

        self.update_list()
        self.search_entry.focus()

    def show_codes_menu(self, event: Any) -> None:
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.codes_menu.tk_popup(
                getattr(event, "x_root", 0), getattr(event, "y_root", 0)
            )

    def copy_selected_code(self) -> None:
        selected = self.tree.selection()
        if selected:
            code = str(self.tree.item(selected[0], "values")[1])
            self.root.clipboard_clear()
            self.root.clipboard_append(code)

    def update_list(self, *args: Any) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        search = self.search_var.get().lower()
        for db_id, name, code in db.get_all_codes():
            if search in name.lower() or search in code.lower():
                self.tree.insert("", "end", iid=str(db_id), values=(name, code))

    def save_new(self) -> None:
        name = self.name_entry.get().strip()
        code = self.code_entry.get().strip()
        if not name or not code:
            return

        existing_name = db.check_code_exists(code)
        if existing_name:
            messagebox.showerror(
                "Ошибка",
                f"Код {code} уже есть в базе!\nОн записан как: «{existing_name}»",
            )
            return

        db.add_to_db(name, code)
        write_log(f"Добавлен код: {name} -> {code}")
        self.name_entry.delete(0, "end")
        self.code_entry.delete(0, "end")
        self.name_entry.focus()
        self.update_list()

    def delete_selected_code(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выдели строку!")
            return
        item_id = int(selected[0])
        item_name = str(self.tree.item(str(item_id), "values")[0])
        if messagebox.askyesno("Подтверждение", f"Удалить '{item_name}'?"):
            db.delete_code_db(item_id)
            write_log(f"Удален код: {item_name}")
            self.update_list()

    def edit_selected_code(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выдели строку для изменения!")
            return
        item_id = int(selected[0])
        values = self.tree.item(str(item_id), "values")
        original_code = str(values[1])

        edit_win = tk.Toplevel(self.root)
        edit_win.title("Изменить код")
        edit_win.geometry("350x200")
        edit_win.configure(bg="#f4f5f7")

        tk.Label(edit_win, text="Название:", bg="#f4f5f7", font=self.f_bold).pack(
            pady=2
        )
        e_name = tk.Entry(
            edit_win, font=self.f_norm, relief="flat", highlightthickness=1
        )
        e_name.insert(0, str(values[0]))
        e_name.pack()

        tk.Label(edit_win, text="Код PLU:", bg="#f4f5f7", font=self.f_bold).pack(pady=2)
        e_code = tk.Entry(
            edit_win, font=self.f_norm, relief="flat", highlightthickness=1
        )
        e_code.insert(0, original_code)
        e_code.pack()

        def save_changes(event: Optional[tk.Event] = None) -> None:
            new_code = e_code.get().strip()
            existing_name = db.check_code_exists(new_code)
            if existing_name and new_code != original_code:
                messagebox.showerror(
                    "Ошибка",
                    f"Код {new_code} уже занят!\nОн записан как: «{existing_name}»",
                )
                return
            db.update_code_db(item_id, e_name.get().strip(), new_code)
            write_log(
                f"Изменен код ID {item_id}: теперь {e_name.get().strip()} -> {new_code}"
            )
            self.update_list()
            edit_win.destroy()

        edit_win.bind("<Return>", save_changes)
        tk.Button(
            edit_win,
            text="Сохранить",
            command=save_changes,
            bg="#4CAF50",
            fg="white",
            relief="flat",
            font=self.f_bold,
        ).pack(pady=15)

    # --- Вкладка: Сроки ---
    def setup_sroki_tab(self) -> None:
        search_frame = tk.Frame(self.tab_sroki, bg="#f4f5f7")
        search_frame.pack(pady=5, padx=10, fill="x")

        tk.Label(search_frame, text="Поиск:", font=self.f_bold, bg="#f4f5f7").pack(
            side="left"
        )
        self.sr_search_var = tk.StringVar()
        self.sr_search_var.trace_add("write", lambda *a: self.update_sroki_list())

        tk.Entry(
            search_frame,
            textvariable=self.sr_search_var,
            font=self.f_big,
            relief="flat",
            highlightthickness=1,
        ).pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(
            search_frame,
            text="✖ Очистить",
            font=self.f_bold,
            bg="#e1e4e8",
            relief="flat",
            cursor="hand2",
            command=lambda: self.sr_search_var.set(""),
        ).pack(side="right", padx=(10, 0))

        tree_frame = tk.Frame(self.tab_sroki)
        tree_frame.pack(pady=5, padx=10, fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
        cols = ("Name", "From", "To", "Qty", "Days", "Status")
        self.sroki_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.sroki_tree.yview)

        scrollbar.pack(side="right", fill="y")
        self.sroki_tree.pack(side="left", fill="both", expand=True)

        headers = [
            "Товар",
            "Изготовлен",
            "Годен ДО",
            "Кол-во",
            "Осталось дней",
            "Статус",
        ]
        for i, col in enumerate(cols):
            self.sroki_tree.heading(col, text=headers[i])
            if col in ("From", "To"):
                self.sroki_tree.column(col, width=90, anchor="center")
            elif col == "Qty":
                self.sroki_tree.column(col, width=60, anchor="center")
            elif col in ("Days", "Status"):
                self.sroki_tree.column(col, width=120, anchor="center")

        self.sroki_tree.tag_configure("red", background="#ffb3b3")
        self.sroki_tree.tag_configure("orange", background="#ffdca8")
        self.sroki_tree.tag_configure("yellow", background="#ffe6b3")
        self.sroki_tree.tag_configure("green", background="#ccffcc")
        self.sroki_tree.tag_configure(
            "separator", background="#d1d5db", font=self.f_bold, foreground="#333"
        )

        self.sroki_menu = tk.Menu(self.root, tearoff=0, font=self.f_norm)
        self.sroki_menu.add_command(label="✏ Изменить", command=self.edit_selected_srok)
        self.sroki_menu.add_command(
            label="🗑 Удалить", command=self.delete_selected_srok
        )
        self.sroki_menu.add_command(
            label="📋 Копировать название", command=self.copy_selected_srok_name
        )
        self.sroki_tree.bind("<Button-3>", self.show_sroki_menu)

        ctrl_frame = tk.Frame(self.tab_sroki, bg="#f4f5f7")
        ctrl_frame.pack(pady=5)
        tk.Button(
            ctrl_frame,
            text="✏ Изменить",
            font=self.f_bold,
            bg="#e1e4e8",
            relief="flat",
            cursor="hand2",
            command=self.edit_selected_srok,
        ).grid(row=0, column=0, padx=10)
        tk.Button(
            ctrl_frame,
            text="🗑 Удалить",
            font=self.f_bold,
            bg="#ffcccc",
            fg="#a00",
            relief="flat",
            cursor="hand2",
            command=self.delete_selected_srok,
        ).grid(row=0, column=1, padx=10)

        sroki_frame = ttk.LabelFrame(
            self.tab_sroki, text="Добавление (Enter для перехода)"
        )
        sroki_frame.pack(pady=10, padx=10, fill="x")
        sroki_frame.columnconfigure(1, weight=1)

        tk.Label(sroki_frame, text="Название:", font=self.f_big, bg="#f4f5f7").grid(
            row=0, column=0, padx=(10, 5), pady=10, sticky="e"
        )
        self.sr_name = tk.Entry(
            sroki_frame,
            font=self.f_content,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.sr_name.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        tk.Label(
            sroki_frame, text="ОТ (дд.мм.гг):", font=self.f_big, bg="#f4f5f7"
        ).grid(row=0, column=2, padx=(15, 5), pady=10, sticky="e")
        self.sr_date_from = tk.Entry(
            sroki_frame,
            font=self.f_content,
            width=8,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.sr_date_from.grid(row=0, column=3, padx=5, pady=10)

        tk.Label(
            sroki_frame, text="ДО (дд.мм.гг):", font=self.f_big, bg="#f4f5f7"
        ).grid(row=0, column=4, padx=(15, 5), pady=10, sticky="e")
        self.sr_date_to = tk.Entry(
            sroki_frame,
            font=self.f_content,
            width=8,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.sr_date_to.grid(row=0, column=5, padx=5, pady=10)

        tk.Label(sroki_frame, text="Шт:", font=self.f_big, bg="#f4f5f7").grid(
            row=0, column=6, padx=(15, 5), pady=10, sticky="e"
        )
        self.sr_qty = tk.Entry(
            sroki_frame,
            font=self.f_content,
            width=4,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.sr_qty.grid(row=0, column=7, padx=5, pady=10)
        self.sr_qty.insert(0, "0")

        tk.Button(
            sroki_frame,
            text="Добавить",
            bg="#4CAF50",
            fg="white",
            relief="flat",
            cursor="hand2",
            command=self.save_srok,
            font=self.f_big,
        ).grid(row=0, column=8, padx=15, pady=10)

        self.sr_date_from.bind(
            "<KeyRelease>", lambda e: self.format_on_type(e, self.sr_date_from)
        )
        self.sr_date_to.bind(
            "<KeyRelease>", lambda e: self.format_on_type(e, self.sr_date_to)
        )

        self.sr_name.bind("<Return>", lambda e: self.sr_date_from.focus())
        self.sr_date_from.bind("<Return>", lambda e: self.sr_date_to.focus())
        self.sr_date_to.bind("<Return>", lambda e: self.sr_qty.focus())
        self.sr_qty.bind("<Return>", lambda e: self.save_srok())

        self.update_sroki_list()

    def show_sroki_menu(self, event: Any) -> None:
        iid = self.sroki_tree.identify_row(event.y)
        if iid:
            self.sroki_tree.selection_set(iid)
            if "separator" not in self.sroki_tree.item(iid, "tags"):
                self.sroki_menu.tk_popup(
                    getattr(event, "x_root", 0), getattr(event, "y_root", 0)
                )

    def copy_selected_srok_name(self) -> None:
        selected = self.sroki_tree.selection()
        if selected:
            name = str(self.sroki_tree.item(selected[0], "values")[0])
            self.root.clipboard_clear()
            self.root.clipboard_append(name)

    def delete_selected_srok(self) -> None:
        selected = self.sroki_tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выдели строку!")
            return
        if "separator" in self.sroki_tree.item(selected[0], "tags"):
            return
        item_id = int(selected[0])
        item_name = str(self.sroki_tree.item(str(item_id), "values")[0])
        if messagebox.askyesno("Подтверждение", f"Удалить '{item_name}'?"):
            db.delete_srok_db(item_id)
            write_log(f"Удалена партия: {item_name}")
            self.update_sroki_list()

    def edit_selected_srok(self) -> None:
        selected = self.sroki_tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выдели строку для изменения!")
            return
        if "separator" in self.sroki_tree.item(selected[0], "tags"):
            return
        item_id = int(selected[0])
        values = self.sroki_tree.item(str(item_id), "values")

        edit_win = tk.Toplevel(self.root)
        edit_win.title("Изменить партию")
        edit_win.geometry("350x280")
        edit_win.configure(bg="#f4f5f7")

        tk.Label(edit_win, text="Название:", bg="#f4f5f7", font=self.f_bold).pack(
            pady=2
        )
        e_name = tk.Entry(
            edit_win, font=self.f_norm, relief="flat", highlightthickness=1
        )
        e_name.insert(0, str(values[0]))
        e_name.pack()

        tk.Label(
            edit_win, text="ОТ (слитно 6 цифр):", bg="#f4f5f7", font=self.f_bold
        ).pack(pady=2)
        e_from = tk.Entry(
            edit_win, font=self.f_norm, relief="flat", highlightthickness=1
        )
        e_from.insert(0, str(values[1]))
        e_from.pack()
        e_from.bind("<KeyRelease>", lambda e: self.format_on_type(e, e_from))

        tk.Label(
            edit_win, text="ДО (слитно 6 цифр):", bg="#f4f5f7", font=self.f_bold
        ).pack(pady=2)
        e_to = tk.Entry(edit_win, font=self.f_norm, relief="flat", highlightthickness=1)
        e_to.insert(0, str(values[2]))
        e_to.pack()
        e_to.bind("<KeyRelease>", lambda e: self.format_on_type(e, e_to))

        tk.Label(edit_win, text="Кол-во (шт):", bg="#f4f5f7", font=self.f_bold).pack(
            pady=2
        )
        e_qty = tk.Entry(
            edit_win, font=self.f_norm, relief="flat", highlightthickness=1
        )
        e_qty.insert(0, str(values[3]))
        e_qty.pack()

        def save_changes(event: Optional[tk.Event] = None) -> None:
            d_from = normalize_date_input(e_from.get())
            d_to = normalize_date_input(e_to.get())
            qty = e_qty.get() if e_qty.get().isdigit() else "0"
            try:
                datetime.strptime(d_from, "%d.%m.%Y")
                datetime.strptime(d_to, "%d.%m.%Y")
            except ValueError:
                messagebox.showerror(
                    "Ошибка", "Введи корректную дату! (например 150826)"
                )
                return

            db.update_srok_db(item_id, e_name.get(), d_from, d_to, int(qty))
            write_log(f"Изменена партия ID {item_id}: {e_name.get()}, {qty} шт.")
            self.update_sroki_list()
            edit_win.destroy()

        edit_win.bind("<Return>", save_changes)
        tk.Button(
            edit_win,
            text="Сохранить",
            command=save_changes,
            bg="#4CAF50",
            fg="white",
            relief="flat",
            font=self.f_bold,
        ).pack(pady=15)

    def save_srok(self, *args: Any) -> None:
        name = self.sr_name.get()
        d_from = normalize_date_input(self.sr_date_from.get())
        d_to = normalize_date_input(self.sr_date_to.get())
        qty = self.sr_qty.get() if self.sr_qty.get().isdigit() else "0"

        if not name:
            return

        try:
            datetime.strptime(d_from, "%d.%m.%Y")
            datetime.strptime(d_to, "%d.%m.%Y")
        except ValueError:
            messagebox.showerror("Ошибка", "Введи 6 цифр (например 150826)")
            return

        for db_id, existing_name, _, existing_to, _ in db.get_all_sroki_v3():
            if name == existing_name and d_to == existing_to:
                messagebox.showerror(
                    "Ошибка", f"Такой товар с датой '{d_to}' уже есть (ID {db_id})!"
                )
                return

        db.add_srok_v3_db(name, d_from, d_to, int(qty))
        write_log(f"Добавлена партия: {name}, до {d_to}, {qty} шт.")

        self.sr_name.delete(0, "end")
        self.sr_date_from.delete(0, "end")
        self.sr_date_to.delete(0, "end")
        self.sr_qty.delete(0, "end")
        self.sr_name.focus()
        self.update_sroki_list()

    def update_sroki_list(self) -> None:
        for item in self.sroki_tree.get_children():
            self.sroki_tree.delete(item)

        search = self.sr_search_var.get().lower()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        all_items: List[Tuple[int, datetime, int, str, str, str, int]] = []

        for db_id, name, d_from, d_to, qty in db.get_all_sroki_v3():
            try:
                if search and search not in name.lower():
                    continue
                e_date = datetime.strptime(d_to, "%d.%m.%Y")
                days_left = (e_date - today).days
                all_items.append((days_left, e_date, db_id, name, d_from, d_to, qty))
            except ValueError:
                pass

        all_items.sort()
        last_month_year = (-1, -1)

        for days_left, e_date, db_id, name, d_from, d_to, qty in all_items:
            current_month_year = (e_date.month, e_date.year)
            if current_month_year != last_month_year:
                month_name = self.months_ru[e_date.month - 1]
                self.sroki_tree.insert(
                    "",
                    "end",
                    values=(f"--- {month_name} {e_date.year} ---", "", "", "", "", ""),
                    tags=("separator",),
                )
                last_month_year = current_month_year

            if days_left < 0:
                display_days, status, tag = (
                    f"Истек {abs(days_left)} дн. назад",
                    "СНИМИ С ВИТРИНЫ!",
                    "red",
                )
            elif days_left == 0:
                display_days, status, tag = "0 дней", "СРОК ИСТЁК!", "red"
            elif days_left == 1:
                display_days, status, tag = "1 день (Завтра)", "Готовь замену", "orange"
            elif days_left <= 14:
                display_days, status, tag = (
                    f"{days_left} дн",
                    "Срочная продажа",
                    "yellow",
                )
            else:
                display_days, status, tag = f"{days_left} дн", "В норме", "green"

            self.sroki_tree.insert(
                "",
                "end",
                iid=str(db_id),
                values=(name, d_from, d_to, qty, display_days, status),
                tags=(tag,),
            )

    # --- Вкладка: График ---
    def setup_schedule_tab(self) -> None:
        settings_frame = ttk.LabelFrame(self.tab_schedule, text="Настройки графика")
        settings_frame.pack(pady=10, padx=20, fill="x")

        tk.Label(
            settings_frame,
            text="Первый раб. день (дд.мм.гг):",
            font=self.f_bold,
            bg="#f4f5f7",
        ).grid(row=0, column=0, padx=5, pady=10)
        self.cal_start_date = tk.Entry(
            settings_frame,
            font=self.f_norm,
            width=10,
            relief="flat",
            highlightthickness=1,
        )
        self.cal_start_date.grid(row=0, column=1, padx=5, pady=10)
        self.cal_start_date.bind(
            "<KeyRelease>", lambda e: self.format_on_type(e, self.cal_start_date)
        )

        tk.Label(settings_frame, text="Рабочих:", font=self.f_bold, bg="#f4f5f7").grid(
            row=0, column=2, padx=5, pady=10
        )
        self.cal_work = tk.Entry(
            settings_frame,
            font=self.f_norm,
            width=3,
            relief="flat",
            highlightthickness=1,
        )
        self.cal_work.grid(row=0, column=3, padx=5, pady=10)

        tk.Label(settings_frame, text="Выходных:", font=self.f_bold, bg="#f4f5f7").grid(
            row=0, column=4, padx=5, pady=10
        )
        self.cal_rest = tk.Entry(
            settings_frame,
            font=self.f_norm,
            width=3,
            relief="flat",
            highlightthickness=1,
        )
        self.cal_rest.grid(row=0, column=5, padx=5, pady=10)

        tk.Button(
            settings_frame,
            text="💾 Сохранить",
            font=self.f_bold,
            bg="#2196F3",
            fg="white",
            relief="flat",
            cursor="hand2",
            command=self.save_schedule,
        ).grid(row=0, column=6, padx=15, pady=10)

        saved = db.get_schedule_settings()
        if saved:
            self.cal_start_date.insert(0, str(saved[0]))
            self.cal_work.insert(0, str(saved[1]))
            self.cal_rest.insert(0, str(saved[2]))
        else:
            self.cal_start_date.insert(0, datetime.now().strftime("%d.%m.%Y"))
            self.cal_work.insert(0, "2")
            self.cal_rest.insert(0, "2")

        nav_frame = tk.Frame(self.tab_schedule, bg="#f4f5f7")
        nav_frame.pack(pady=5)

        self.current_cal_date = datetime.now()

        tk.Button(
            nav_frame,
            text="◀",
            font=self.f_big,
            relief="flat",
            bg="#e1e4e8",
            cursor="hand2",
            width=3,
            command=self.prev_month,
        ).grid(row=0, column=0, padx=20)
        self.month_lbl = tk.Label(
            nav_frame, text="", font=self.f_huge, bg="#f4f5f7", width=15
        )
        self.month_lbl.grid(row=0, column=1)
        tk.Button(
            nav_frame,
            text="▶",
            font=self.f_big,
            relief="flat",
            bg="#e1e4e8",
            cursor="hand2",
            width=3,
            command=self.next_month,
        ).grid(row=0, column=2, padx=20)

        self.cal_frame = tk.Frame(self.tab_schedule, bg="#f4f5f7")
        self.cal_frame.pack(pady=10)

        for i, day in enumerate(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]):
            color = "#d32f2f" if i >= 5 else "#333333"
            tk.Label(
                self.cal_frame,
                text=day,
                font=self.f_bold,
                fg=color,
                bg="#f4f5f7",
                width=5,
            ).grid(row=0, column=i, pady=5)

        self.day_labels: List[List[tk.Label]] = []
        for row in range(1, 7):
            row_labels = []
            for col in range(7):
                lbl = tk.Label(
                    self.cal_frame,
                    text="",
                    font=self.f_big,
                    width=4,
                    height=2,
                    relief="flat",
                )
                lbl.grid(row=row, column=col, padx=4, pady=4)
                row_labels.append(lbl)
            self.day_labels.append(row_labels)

        self.render_calendar()

    def save_schedule(self) -> None:
        s_date = normalize_date_input(self.cal_start_date.get())
        try:
            datetime.strptime(s_date, "%d.%m.%Y")
            work_d = int(self.cal_work.get())
            rest_d = int(self.cal_rest.get())
            db.save_schedule_settings(s_date, work_d, rest_d)
            write_log("Обновлен график работы")
            self.render_calendar()
        except ValueError:
            messagebox.showerror("Ошибка", "Проверь правильность введенных данных!")

    def prev_month(self) -> None:
        first_day = self.current_cal_date.replace(day=1)
        self.current_cal_date = (first_day - timedelta(days=1)).replace(day=1)
        self.render_calendar()

    def next_month(self) -> None:
        if self.current_cal_date.month == 12:
            self.current_cal_date = self.current_cal_date.replace(
                year=self.current_cal_date.year + 1, month=1, day=1
            )
        else:
            self.current_cal_date = self.current_cal_date.replace(
                month=self.current_cal_date.month + 1, day=1
            )
        self.render_calendar()

    def render_calendar(self) -> None:
        year = self.current_cal_date.year
        month = self.current_cal_date.month
        self.month_lbl.config(text=f"{self.months_ru[month - 1]} {year}")

        cal = calendar.monthcalendar(year, month)
        today = datetime.now().date()

        try:
            start_obj = datetime.strptime(
                normalize_date_input(self.cal_start_date.get()), "%d.%m.%Y"
            ).date()
            work_d = int(self.cal_work.get())
            rest_d = int(self.cal_rest.get())
            cycle_len = work_d + rest_d
        except ValueError:
            start_obj = None
            cycle_len = 0

        for row in range(6):
            for col in range(7):
                lbl = self.day_labels[row][col]
                if row < len(cal) and cal[row][col] != 0:
                    day_num = cal[row][col]
                    cell_date = datetime(year, month, day_num).date()

                    is_work = False
                    if (
                        start_obj
                        and cycle_len > 0
                        and (cell_date - start_obj).days >= 0
                    ):
                        is_work = ((cell_date - start_obj).days % cycle_len) < work_d

                    if is_work:
                        lbl.config(
                            text=str(day_num),
                            bg="#a8e6cf",
                            fg="#004d33",
                            font=self.f_big,
                        )
                    else:
                        lbl.config(
                            text=str(day_num), bg="white", fg="black", font=self.f_norm
                        )

                    if cell_date == today:
                        lbl.config(fg="#d32f2f", font=self.f_huge)
                else:
                    lbl.config(text="", bg="#f4f5f7")

    # --- Вкладка: История ---
    def setup_history_tab(self) -> None:
        ctrl_frame = tk.Frame(self.tab_history, bg="#f4f5f7")
        ctrl_frame.pack(pady=10, padx=20, fill="x")

        tk.Button(
            ctrl_frame,
            text="🔄 Обновить",
            font=self.f_bold,
            bg="#d4edda",
            relief="flat",
            cursor="hand2",
            command=self.load_history,
        ).pack(side="left")
        tk.Button(
            ctrl_frame,
            text="🗑 Очистить лог",
            font=self.f_bold,
            bg="#ffcccc",
            fg="#a00",
            relief="flat",
            cursor="hand2",
            command=self.clear_history,
        ).pack(side="right")

        self.history_text = tk.Text(
            self.tab_history, state="disabled", font=("Consolas", 12), wrap="word"
        )
        self.history_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.load_history()

    def load_history(self) -> None:
        if os.path.exists(LOG_PATH):
            try:
                with open(LOG_PATH, "r", encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                content = "Ошибка чтения лога."
        else:
            content = "Лог файл пуст."

        self.history_text.config(state="normal")
        self.history_text.delete("1.0", tk.END)
        self.history_text.insert("1.0", content)
        self.history_text.see(tk.END)
        self.history_text.config(state="disabled")

    def clear_history(self) -> None:
        if messagebox.askyesno("Подтверждение", "Очистить историю действий?"):
            try:
                with open(LOG_PATH, "w", encoding="utf-8") as f:
                    f.write("")
                self.load_history()
            except OSError as e:
                messagebox.showerror("Ошибка", f"Не удалось очистить лог: {e}")

    # --- Вкладка: Настройки ---
    def setup_settings_tab(self) -> None:
        info_frame = ttk.LabelFrame(self.tab_settings, text="Помощь по программе")
        info_frame.pack(pady=10, padx=20, fill="x")
        tk.Button(
            info_frame,
            text="📖 Открыть инструкцию для смены",
            font=self.f_bold,
            bg="#FFD700",
            fg="#333",
            relief="flat",
            cursor="hand2",
            command=self.show_instructions,
        ).pack(pady=20, padx=20, fill="x")

        set_frame = ttk.LabelFrame(self.tab_settings, text="Внешний вид программы")
        set_frame.pack(pady=10, padx=20, fill="x")

        tk.Label(set_frame, text="Размер текста:", font=self.f_bold, bg="#f4f5f7").grid(
            row=0, column=0, padx=20, pady=15, sticky="e"
        )
        self.var_font = tk.IntVar(value=self.cfg_font_size)
        font_combo = ttk.Combobox(
            set_frame,
            textvariable=self.var_font,
            values=["12", "14", "16", "18", "20", "24", "30"],
            font=self.f_norm,
            width=5,
            state="readonly",
        )
        font_combo.grid(row=0, column=1, padx=10, pady=15, sticky="w")

        tk.Label(
            set_frame, text="Ширина строк в таблице:", font=self.f_bold, bg="#f4f5f7"
        ).grid(row=1, column=0, padx=20, pady=15, sticky="e")
        self.var_row = tk.IntVar(value=self.cfg_row_height)
        row_combo = ttk.Combobox(
            set_frame,
            textvariable=self.var_row,
            values=["40", "50", "60", "70", "90", "120"],
            font=self.f_norm,
            width=5,
            state="readonly",
        )
        row_combo.grid(row=1, column=1, padx=10, pady=15, sticky="w")

        tk.Button(
            set_frame,
            text="Сохранить внешний вид",
            font=self.f_bold,
            bg="#2196F3",
            fg="white",
            relief="flat",
            cursor="hand2",
            command=self.apply_settings,
        ).grid(row=2, column=0, columnspan=3, pady=20)

        backup_frame = ttk.LabelFrame(self.tab_settings, text="Система")
        backup_frame.pack(pady=10, padx=20, fill="x")
        tk.Label(
            backup_frame,
            text="✓ Резервные копии базы (папка backups)\n✓ Файл логов всех операций (gastronom.log)",
            font=self.f_norm,
            bg="#f4f5f7",
            justify="left",
        ).pack(pady=10, padx=10)

    def show_instructions(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Как пользоваться")
        win.geometry("700x450")
        win.configure(bg="#f4f5f7")

        txt = tk.Text(
            win,
            font=self.f_norm,
            wrap="word",
            bg="#f4f5f7",
            relief="flat",
            padx=20,
            pady=20,
        )
        txt.pack(expand=True, fill="both")
        txt.insert(
            "1.0", "🍺 Гастроном Пивники — Помощник смены\n\nИнструкции обновлены."
        )
        txt.config(state="disabled")

    def apply_settings(self) -> None:
        db.save_config(self.var_font.get(), self.var_row.get())
        write_log("Изменены настройки внешнего вида")
        messagebox.showinfo(
            "Готово", "Настройки сохранены!\nЗакройте программу и откройте заново."
        )
        self.root.destroy()

    def format_on_type(self, event: tk.Event, entry_widget: tk.Entry) -> None:
        if getattr(event, "keysym", "") in (
            "BackSpace",
            "Delete",
            "Left",
            "Right",
            "Return",
        ):
            return
        cursor_pos = entry_widget.index(tk.INSERT)
        text = "".join(filter(str.isdigit, entry_widget.get().replace(".", "")))[:6]

        out = text[:2]
        if len(text) > 2:
            out += "." + text[2:4]
        if len(text) > 4:
            out += "." + text[4:6]

        if entry_widget.get() != out:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, out)
            if cursor_pos >= len(entry_widget.get()):
                entry_widget.icursor(tk.END)


if __name__ == "__main__":
    db.init_db()
    root_window = tk.Tk()
    app = MainApp(root_window)
    root_window.mainloop()
