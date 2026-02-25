"""
Инструмент Maigret — поиск имени пользователя по тысячам сайтов.
Приоритет: папка tools/maigret, затем системный maigret.
"""
import os
import re
import shutil
import subprocess
import sys
from typing import Any

from .base import ToolBase

_ANSI = re.compile(r"\x1b\[[?0-9;]*[a-zA-Z]")
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def _run_maigret(username: str, timeout_sec: int = 180) -> tuple[str, str, int]:
    username = (username or "").strip()
    if not username or " " in username:
        return "", "Укажите одно имя пользователя без пробелов.", -1

    local_dir = os.path.join(_ROOT, "tools", "maigret")
    run_cwd = None
    cmd = None

    if os.path.isdir(os.path.join(local_dir, "maigret")):
        run_cwd = local_dir
        cmd = [sys.executable, "-m", "maigret", username, "--no-color"]
    else:
        mg = shutil.which("maigret")
        if mg:
            cmd = [mg, username, "--no-color"]
        else:
            try:
                import maigret  # noqa: F401
                cmd = [sys.executable, "-m", "maigret", username, "--no-color"]
            except ImportError:
                return "", "Maigret не найден. Установите: pip install maigret или клонируйте в tools/maigret.", -1

    try:
        proc = subprocess.run(
            cmd,
            cwd=run_cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            env={**os.environ, "PYTHONPATH": (run_cwd or "")} if run_cwd else None,
        )
        out = _strip_ansi(proc.stdout or "")
        err = _strip_ansi(proc.stderr or "")
        return out, err, proc.returncode
    except subprocess.TimeoutExpired:
        return "", "Превышено время ожидания ({} сек).".format(timeout_sec), -1
    except FileNotFoundError:
        return "", "Команда не найдена.", -1
    except Exception as e:
        return "", str(e), -1


class ToolMaigret(ToolBase):
    @property
    def tool_id(self) -> str:
        return "maigret"

    @property
    def name(self) -> str:
        return "Maigret"

    @property
    def description(self) -> str:
        return "Поиск имени пользователя по тысячам сайтов (аналог Sherlock, больше баз)."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        username = (params.get("username") or "").strip()
        if not username:
            return {"success": False, "error": "Укажите имя пользователя."}
        if " " in username:
            return {"success": False, "error": "Введите одно имя пользователя без пробелов."}

        timeout = min(max(int(params.get("timeout", 180) or 180), 60), 300)
        out, err, code = _run_maigret(username, timeout_sec=timeout)
        combined = (out + "\n" + err).strip()
        return {
            "success": code == 0,
            "output": combined or "Нет результатов или ошибка.",
        }
