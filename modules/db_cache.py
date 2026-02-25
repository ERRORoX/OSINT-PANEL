"""
Локальная база данных для кэширования результатов поиска.
Агрегация данных из всех проверок — повторные запросы берутся из кэша.
"""
import os
import sqlite3
import time
from typing import Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "osint_cache.db")


def _ensure_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            search_type TEXT NOT NULL,
            query_normalized TEXT NOT NULL,
            result_text TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (search_type, query_normalized)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_type ON cache(search_type)")
    conn.commit()
    conn.close()


def normalize_query(query: str) -> str:
    """Нормализация запроса для ключа кэша."""
    if not query:
        return ""
    return " ".join(str(query).strip().lower().split())


def save_result(search_type: str, query: str, result_text: str) -> None:
    """Сохранить результат поиска в базу."""
    try:
        _ensure_db()
        key = normalize_query(query)
        if not key:
            return
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO cache (search_type, query_normalized, result_text, created_at) VALUES (?, ?, ?, ?)",
            (search_type, key, result_text or "", time.time()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка сохранения в кэш: {e}")


def get_cached(search_type: str, query: str) -> Optional[str]:
    """Получить результат из кэша. None если не найден."""
    try:
        _ensure_db()
        key = normalize_query(query)
        if not key:
            return None
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT result_text FROM cache WHERE search_type = ? AND query_normalized = ?",
            (search_type, key),
        ).fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except Exception as e:
        print(f"Ошибка чтения из кэша: {e}")
        return None


def get_cache_stats() -> dict:
    """Количество записей в кэше по типам."""
    try:
        _ensure_db()
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT search_type, COUNT(*) FROM cache GROUP BY search_type"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        conn.close()
        return {"by_type": dict(rows), "total": total}
    except Exception:
        return {"by_type": {}, "total": 0}
