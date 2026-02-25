"""
Инструмент Holehe: проверка, на каких сайтах зарегистрирован email.
Использует локальную копию из tools/holehe (если есть), иначе — системный holehe или pip install holehe.
"""
import os
import re
import shutil
import subprocess
import sys
from typing import Any

from .base import ToolBase

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HOLEHE_DIR = os.path.join(_PROJECT_ROOT, "tools", "holehe")

_ANSI_ESCAPE = re.compile(r"\x1b\[[?0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _holehe_from_project() -> bool:
    """Проверяет, что в проекте есть папка tools/holehe с пакетом holehe."""
    if not _HOLEHE_DIR or not os.path.isdir(_HOLEHE_DIR):
        return False
    pkg = os.path.join(_HOLEHE_DIR, "holehe")
    return os.path.isdir(pkg) and os.path.isfile(os.path.join(pkg, "core.py"))


def _run_cmd(args: list[str], timeout_sec: int = 300, env: dict | None = None, cwd: str | None = None) -> tuple[str, str, int]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            env=env if env is not None else os.environ,
            cwd=cwd,
        )
        out = _strip_ansi(proc.stdout or "")
        err = _strip_ansi(proc.stderr or "")
        return out, err, proc.returncode
    except subprocess.TimeoutExpired:
        return "", "Превышено время ожидания ({} сек).".format(timeout_sec), -1
    except FileNotFoundError:
        return "", "Команда не найдена. Установите: pip install holehe или добавьте папку tools/holehe.", -1
    except Exception as e:
        return "", str(e), -1


class ToolHolehe(ToolBase):
    @property
    def tool_id(self) -> str:
        return "holehe"

    @property
    def name(self) -> str:
        return "Holehe"

    @property
    def description(self) -> str:
        return "Проверка регистрации email на 120+ сайтах (Instagram, Twitter, GitHub и др.) без уведомления владельца."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        email = (params.get("email") or "").strip()
        if not email or "@" not in email:
            return {"success": False, "error": "Укажите корректный email."}
        only_used = bool(params.get("only_used", False))

        cmd = []
        run_env = None
        run_cwd = None

        if _holehe_from_project():
            run_env = {**os.environ, "PYTHONPATH": _HOLEHE_DIR}
            run_cwd = _PROJECT_ROOT
            cmd = [sys.executable, "-m", "holehe", email, "--no-color"]
            if only_used:
                cmd.append("--only-used")
        elif shutil.which("holehe"):
            cmd = ["holehe", email, "--no-color"]
            if only_used:
                cmd.append("--only-used")
        else:
            try:
                import holehe  # noqa: F401
                cmd = [sys.executable, "-m", "holehe", email, "--no-color"]
                if only_used:
                    cmd.append("--only-used")
            except ImportError:
                return {"success": False, "error": "Holehe не найден. Добавьте папку tools/holehe или установите: pip install holehe"}

        out, err, code = _run_cmd(cmd, timeout_sec=300, env=run_env, cwd=run_cwd)
        combined = (out + "\n" + err).strip()
        # Убираем строки прогресс-бара (0%|, 1%|, ... 100%|)
        combined = "\n".join(
            line for line in combined.splitlines()
            if not re.match(r"^\s*\d+%\|", line)
        ).strip()
        return {
            "success": code == 0,
            "output": combined or "(пустой вывод)",
            "returncode": code,
        }
