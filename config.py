import os

# Базовые пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "beer_data.db")
LOG_PATH = os.path.join(BASE_DIR, "gastronom.log")
