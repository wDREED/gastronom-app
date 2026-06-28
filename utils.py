from datetime import datetime
from config import LOG_PATH


def write_log(action: str) -> None:
    """Записывает действие в текстовый лог-файл."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            time_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            f.write(f"[{time_str}] {action}\n")
    except OSError:
        pass


def normalize_date_input(date_str: str) -> str:
    """Приводит ручной ввод даты (например, 150826 или 1.5.26) к стандарту дд.мм.гггг."""
    date_str = date_str.strip()
    if len(date_str) == 6 and date_str.isdigit():
        return f"{date_str[:2]}.{date_str[2:4]}.20{date_str[4:]}"
    if "." in date_str:
        parts = date_str.split(".")
        if len(parts) == 3:
            d, m, y = parts
            if len(d) == 1:
                d = "0" + d
            if len(m) == 1:
                m = "0" + m
            if len(y) == 2:
                y = "20" + y
            return f"{d}.{m}.{y}"
    return date_str
