"""
Инструмент h8mail: поиск по email в утечках и рекон по почте.
Использует локальную копию из tools/h8mail (если есть), иначе — системный h8mail или pip install h8mail.
"""
import os
import re
import shutil
import subprocess
import sys
from typing import Any

from .base import ToolBase

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_H8MAIL_DIR = os.path.join(_PROJECT_ROOT, "tools", "h8mail")

_ANSI_ESCAPE = re.compile(r"\x1b\[[?0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _h8mail_from_project() -> bool:
    """Проверяет, что в проекте есть папка tools/h8mail с пакетом h8mail."""
    if not _H8MAIL_DIR or not os.path.isdir(_H8MAIL_DIR):
        return False
    pkg = os.path.join(_H8MAIL_DIR, "h8mail")
    return os.path.isdir(pkg) and os.path.isfile(os.path.join(pkg, "__main__.py"))


def _run_cmd(args: list[str], timeout_sec: int = 180, env: dict | None = None, cwd: str | None = None) -> tuple[str, str, int]:
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
        return "", "Команда не найдена. Установите: pip install h8mail или добавьте папку tools/h8mail.", -1
    except Exception as e:
        return "", str(e), -1


class ToolH8mail(ToolBase):
    @property
    def tool_id(self) -> str:
        return "h8mail"

    @property
    def name(self) -> str:
        return "h8mail"

    @property
    def description(self) -> str:
        return "Поиск по email в утечках и рекон: Hunter, Snusbase, HaveIBeenPwned и др. (нужны API-ключи для полного функционала)."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        email = (params.get("email") or "").strip()
        if not email or "@" not in email:
            return {"success": False, "error": "Укажите корректный email."}
        skip_defaults = bool(params.get("skip_defaults", False))

        # API-ключи из .env: Hunter.io (тот же ключ, что для theHarvester) и HaveIBeenPwned для утечек
        api_parts = []
        hunter_key = (os.environ.get("TH_HUNTER_KEY") or os.environ.get("H8MAIL_HUNTER_KEY") or "").strip()
        if hunter_key:
            api_parts.append("hunterio={}".format(hunter_key))
        hibp_key = (os.environ.get("H8MAIL_HIBP") or "").strip()
        if hibp_key:
            api_parts.append("hibp={}".format(hibp_key))
        apikey_arg = ",".join(api_parts) if api_parts else None

        cmd = []
        run_env = None
        run_cwd = None

        if _h8mail_from_project():
            run_env = {**os.environ, "PYTHONPATH": _H8MAIL_DIR}
            run_cwd = _PROJECT_ROOT
            cmd = [sys.executable, "-m", "h8mail", "-t", email]
            if apikey_arg:
                cmd.extend(["--apikey", apikey_arg])
            if skip_defaults:
                cmd.append("--skip-defaults")
        elif shutil.which("h8mail"):
            cmd = ["h8mail", "-t", email]
            if apikey_arg:
                cmd.extend(["--apikey", apikey_arg])
            if skip_defaults:
                cmd.append("--skip-defaults")
        else:
            try:
                import h8mail  # noqa: F401
                cmd = [sys.executable, "-m", "h8mail", "-t", email]
                if apikey_arg:
                    cmd.extend(["--apikey", apikey_arg])
                if skip_defaults:
                    cmd.append("--skip-defaults")
            except ImportError:
                return {"success": False, "error": "h8mail не найден. Добавьте папку tools/h8mail или установите: pip install h8mail"}

        out, err, code = _run_cmd(cmd, timeout_sec=180, env=run_env, cwd=run_cwd)
        combined = (out + "\n" + err).strip()
        return {
            "success": code == 0,
            "output": combined or "(пустой вывод)",
            "returncode": code,
        }
