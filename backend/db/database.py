"""
Модуль SQLite: подключение, инициализация схемы, сохранение/чтение истории запусков.
Не зависит от инструментов — только от схемы БД.
"""
import sqlite3
import json
import os
from contextlib import contextmanager
from typing import Any, Generator, Optional

# Путь к БД рядом с проектом
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "osint_panel.db")


def _ensure_data_dir():
    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Создаёт таблицы, если их нет. Вызывать при старте приложения."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_id TEXT NOT NULL,
                params_json TEXT NOT NULL,
                result_json TEXT,
                error_text TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_tool_id ON runs(tool_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS instagram_tried (
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                tried_at TEXT DEFAULT (datetime('now')),
                UNIQUE(username, password)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_instagram_tried_username ON instagram_tried(username)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS instagram_found (
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                found_at TEXT DEFAULT (datetime('now')),
                UNIQUE(username, password)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_instagram_found_username ON instagram_found(username)")


def save_run(tool_id: str, params: dict[str, Any], result: Optional[dict] = None, error: Optional[str] = None) -> int:
    """Сохраняет один запуск инструмента. Возвращает id записи."""
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO runs (tool_id, params_json, result_json, error_text)
            VALUES (?, ?, ?, ?)
            """,
            (tool_id, json.dumps(params, ensure_ascii=False), json.dumps(result, ensure_ascii=False) if result else None, error),
        )
        return cur.lastrowid or 0


def get_last_successful_run(tool_id: str) -> Optional[dict]:
    """Последний успешный запуск инструмента (без ошибки). Нужно для лимита 24ч."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, tool_id, created_at FROM runs WHERE tool_id = ? AND error_text IS NULL ORDER BY created_at DESC LIMIT 1",
            (tool_id,),
        ).fetchone()
        if not row:
            return None
        return {"id": row["id"], "tool_id": row["tool_id"], "created_at": row["created_at"]}


def get_instagram_tried_passwords(username: str) -> set[str]:
    """Пароли, уже пробовавшиеся для этого аккаунта (чтобы не повторять)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT password FROM instagram_tried WHERE username = ?",
            (username.strip().lower(),),
        ).fetchall()
        return {r["password"] for r in rows}


def add_instagram_tried_passwords(username: str, passwords: list[str]) -> None:
    """Сохранить список паролей как уже пробованные для аккаунта."""
    if not passwords:
        return
    uname = username.strip().lower()
    with get_db() as conn:
        for pwd in passwords:
            if not pwd:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO instagram_tried (username, password) VALUES (?, ?)",
                (uname, pwd),
            )


def clear_instagram_tried_passwords(username: str) -> None:
    """Удалить все записи о проверенных паролях для аккаунта (чтобы можно было повторить перебор)."""
    if not username:
        return
    uname = username.strip().lower()
    with get_db() as conn:
        conn.execute("DELETE FROM instagram_tried WHERE username = ?", (uname,))


def get_instagram_tried_count(username: str) -> int:
    """Количество паролей, уже проверявшихся для этого аккаунта."""
    if not username:
        return 0
    uname = username.strip().lower()
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM instagram_tried WHERE username = ?",
            (uname,),
        ).fetchone()
        return row["n"] if row else 0


def save_instagram_found(username: str, password: str) -> None:
    """Сохранить найденный пароль для аккаунта (успешный подбор)."""
    if not username or not password:
        return
    uname = username.strip().lower()
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO instagram_found (username, password) VALUES (?, ?)",
            (uname, password),
        )


def get_instagram_found_list(limit: int = 50) -> list[dict]:
    """Список найденных учёток (username, password, found_at) для отображения в панели."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT username, password, found_at FROM instagram_found ORDER BY found_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"username": r["username"], "password": r["password"], "found_at": r["found_at"]} for r in rows]


def get_run_history(tool_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    """История запусков. Если tool_id задан — только по этому инструменту."""
    with get_db() as conn:
        if tool_id:
            rows = conn.execute(
                "SELECT id, tool_id, params_json, result_json, error_text, created_at FROM runs WHERE tool_id = ? ORDER BY created_at DESC LIMIT ?",
                (tool_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, tool_id, params_json, result_json, error_text, created_at FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "tool_id": r["tool_id"],
                "params": json.loads(r["params_json"]) if r["params_json"] else {},
                "result": json.loads(r["result_json"]) if r["result_json"] else None,
                "error": r["error_text"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
