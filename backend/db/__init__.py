# Модуль БД — один вход для всего проекта
from .database import (
    get_db,
    init_db,
    save_run,
    get_run_history,
    get_last_successful_run,
    get_instagram_tried_passwords,
    add_instagram_tried_passwords,
    clear_instagram_tried_passwords,
    get_instagram_tried_count,
    save_instagram_found,
    get_instagram_found_list,
)

__all__ = [
    "get_db",
    "init_db",
    "save_run",
    "get_run_history",
    "get_last_successful_run",
    "get_instagram_tried_passwords",
    "add_instagram_tried_passwords",
    "clear_instagram_tried_passwords",
    "get_instagram_tried_count",
    "save_instagram_found",
    "get_instagram_found_list",
]
