import sqlite3
from typing import List, Tuple, Optional
from config import DB_PATH


def get_connection():
    """Возвращает подключение к БД."""
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Инициализирует БД и обновляет структуру при необходимости."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Создание таблиц
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS codes (id INTEGER PRIMARY KEY, name TEXT, code TEXT)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS sroki_v3 (id INTEGER PRIMARY KEY, name TEXT, date_from TEXT, date_to TEXT)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY, start_date TEXT, work_d INTEGER, rest_d INTEGER)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, font_size INTEGER, row_height INTEGER)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS todo (id INTEGER PRIMARY KEY, task TEXT, is_done INTEGER DEFAULT 0)"
        )

        # Миграции
        cursor.execute("PRAGMA table_info(sroki_v3)")
        columns = [info[1] for info in cursor.fetchall()]
        if "qty" not in columns:
            cursor.execute("ALTER TABLE sroki_v3 ADD COLUMN qty INTEGER DEFAULT 0")

        cursor.execute("PRAGMA table_info(todo)")
        columns = [info[1] for info in cursor.fetchall()]
        if "day_type" not in columns:
            cursor.execute("ALTER TABLE todo ADD COLUMN day_type TEXT DEFAULT 'today'")
        if "position" not in columns:
            cursor.execute("ALTER TABLE todo ADD COLUMN position INTEGER DEFAULT 0")

        conn.commit()


# --- ФУНКЦИИ КОДОВ (PLU) ---
def get_all_codes() -> List[Tuple[int, str, str]]:
    with get_connection() as conn:
        return (
            conn.cursor()
            .execute("SELECT id, name, code FROM codes ORDER BY name ASC")
            .fetchall()
        )


def check_code_exists(code: str) -> Optional[str]:
    with get_connection() as conn:
        row = (
            conn.cursor()
            .execute("SELECT name FROM codes WHERE code=?", (code,))
            .fetchone()
        )
        return str(row[0]) if row else None


def add_to_db(name: str, code: str) -> None:
    with get_connection() as conn:
        conn.cursor().execute(
            "INSERT INTO codes (name, code) VALUES (?, ?)", (name, code)
        )
        conn.commit()


def delete_code_db(item_id: int) -> None:
    with get_connection() as conn:
        conn.cursor().execute("DELETE FROM codes WHERE id=?", (item_id,))
        conn.commit()


def update_code_db(item_id: int, name: str, code: str) -> None:
    with get_connection() as conn:
        conn.cursor().execute(
            "UPDATE codes SET name=?, code=? WHERE id=?", (name, code, item_id)
        )
        conn.commit()


# --- ФУНКЦИИ СРОКОВ (sroki_v3) ---
def get_all_sroki_v3() -> List[Tuple[int, str, str, str, int]]:
    with get_connection() as conn:
        return (
            conn.cursor()
            .execute("SELECT id, name, date_from, date_to, qty FROM sroki_v3")
            .fetchall()
        )


def add_srok_v3_db(name: str, date_from: str, date_to: str, qty: int) -> None:
    with get_connection() as conn:
        conn.cursor().execute(
            "INSERT INTO sroki_v3 (name, date_from, date_to, qty) VALUES (?, ?, ?, ?)",
            (name, date_from, date_to, qty),
        )
        conn.commit()


def delete_srok_db(item_id: int) -> None:
    with get_connection() as conn:
        conn.cursor().execute("DELETE FROM sroki_v3 WHERE id=?", (item_id,))
        conn.commit()


def update_srok_db(
    item_id: int, name: str, date_from: str, date_to: str, qty: int
) -> None:
    with get_connection() as conn:
        conn.cursor().execute(
            "UPDATE sroki_v3 SET name=?, date_from=?, date_to=?, qty=? WHERE id=?",
            (name, date_from, date_to, qty, item_id),
        )
        conn.commit()


# --- ФУНКЦИИ TODO ---
def get_all_todos() -> List[Tuple[int, str, int, str]]:
    with get_connection() as conn:
        return (
            conn.cursor()
            .execute(
                "SELECT id, task, is_done, day_type FROM todo ORDER BY position ASC, id ASC"
            )
            .fetchall()
        )


def add_todo_db(task: str, day_type: str) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT MAX(position) FROM todo").fetchone()
        max_pos = int(row[0]) if row and row[0] is not None else 0
        cursor.execute(
            "INSERT INTO todo (task, day_type, position) VALUES (?, ?, ?)",
            (task, day_type, max_pos + 1),
        )
        conn.commit()


def update_todo_positions_db(id_position_map: List[Tuple[int, int]]) -> None:
    with get_connection() as conn:
        conn.cursor().executemany(
            "UPDATE todo SET position=? WHERE id=?", id_position_map
        )
        conn.commit()


def toggle_todo_db(item_id: int, is_done: int) -> None:
    with get_connection() as conn:
        conn.cursor().execute(
            "UPDATE todo SET is_done=? WHERE id=?", (is_done, item_id)
        )
        conn.commit()


def delete_todo_db(item_id: int) -> None:
    with get_connection() as conn:
        conn.cursor().execute("DELETE FROM todo WHERE id=?", (item_id,))
        conn.commit()


def delete_all_todos_db() -> None:
    with get_connection() as conn:
        conn.cursor().execute("DELETE FROM todo")
        conn.commit()


# --- ФУНКЦИИ НАСТРОЕК (schedule, config) ---
def get_schedule_settings() -> Optional[Tuple[str, int, int]]:
    with get_connection() as conn:
        return (
            conn.cursor()
            .execute("SELECT start_date, work_d, rest_d FROM schedule LIMIT 1")
            .fetchone()
        )


def save_schedule_settings(start_date: str, work_d: int, rest_d: int) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schedule")
        cursor.execute(
            "INSERT INTO schedule (start_date, work_d, rest_d) VALUES (?, ?, ?)",
            (start_date, work_d, rest_d),
        )
        conn.commit()


def get_config() -> Tuple[int, int]:
    with get_connection() as conn:
        row = (
            conn.cursor()
            .execute("SELECT font_size, row_height FROM config LIMIT 1")
            .fetchone()
        )
        return (int(row[0]), int(row[1])) if row else (20, 70)


def save_config(font_size: int, row_height: int) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config")
        cursor.execute(
            "INSERT INTO config (font_size, row_height) VALUES (?, ?)",
            (font_size, row_height),
        )
        conn.commit()
