"""
Инструмент Subfinder (projectdiscovery) — пассивный поиск поддоменов.
Запуск бинарника из tools/subfinder или из PATH (Go, не Python).
"""
import os
import re
import shutil
import subprocess
from typing import Any

from .base import ToolBase

_ANSI = re.compile(r"\x1b\[[?0-9;]*[a-zA-Z]")
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def _normalize_domain(domain: str) -> str:
    s = (domain or "").strip().lower()
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
            break
    if "/" in s:
        s = s.split("/")[0]
    if s.startswith("www."):
        s = s[4:]
    return s


def _run_subfinder(domain: str, timeout_sec: int = 120) -> tuple[str, str, int]:
    domain = _normalize_domain(domain)
    if not domain or " " in domain or "." not in domain:
        return "", "Укажите корректный домен (например example.com).", -1

    tool_dir = os.path.join(_ROOT, "tools", "subfinder")
    binary = None
    run_cwd = None

    for name in ("subfinder", "subfinder2"):
        path = os.path.join(tool_dir, name)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            binary = path
            run_cwd = tool_dir
            break
    if not binary:
        binary = shutil.which("subfinder")

    if not binary:
        return "", "Subfinder не найден. Соберите из tools/subfinder: go build -o subfinder ./cmd/subfinder или установите бинарник в PATH.", -1

    try:
        proc = subprocess.run(
            [binary, "-d", domain, "-silent"],
            cwd=run_cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
        out = _strip_ansi(proc.stdout or "")
        err = _strip_ansi(proc.stderr or "")
        if not out and err and "silent" in err.lower():
            proc2 = subprocess.run(
                [binary, "-d", domain],
                cwd=run_cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
            )
            out = _strip_ansi(proc2.stdout or "")
            err = _strip_ansi(proc2.stderr or "")
            return out, err, proc2.returncode
        return out, err, proc.returncode
    except subprocess.TimeoutExpired:
        return "", "Превышено время ожидания ({} сек).".format(timeout_sec), -1
    except Exception as e:
        return "", str(e), -1


class ToolSubfinder(ToolBase):
    @property
    def tool_id(self) -> str:
        return "subfinder"

    @property
    def name(self) -> str:
        return "Subfinder"

    @property
    def description(self) -> str:
        return "Пассивный поиск поддоменов (projectdiscovery)."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        domain = _normalize_domain(params.get("domain") or "")
        if not domain:
            return {"success": False, "error": "Укажите домен (например example.com)."}
        if " " in domain or "." not in domain:
            return {"success": False, "error": "Некорректный домен."}

        timeout = max(30, min(300, int(params.get("timeout", 120) or 120)))
        out, err, code = _run_subfinder(domain, timeout_sec=timeout)
        combined = (out + "\n" + err).strip()
        return {
            "success": code == 0,
            "output": combined or "Поддомены не найдены или ошибка запуска.",
        }
