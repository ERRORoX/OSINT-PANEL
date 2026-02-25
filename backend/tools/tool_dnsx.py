"""
Инструмент dnsx (projectdiscovery) — DNS-запросы: A, AAAA, CNAME и др.
Запуск бинарника из tools/dnsx или из PATH (Go).
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


def _run_dnsx(domain: str, timeout_sec: int = 60) -> tuple[str, str, int]:
    domain = _normalize_domain(domain)
    if not domain or " " in domain or "." not in domain:
        return "", "Укажите корректный домен (например example.com).", -1

    tool_dir = os.path.join(_ROOT, "tools", "dnsx")
    binary = None
    run_cwd = None

    for name in ("dnsx", "dnsx2"):
        path = os.path.join(tool_dir, name)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            binary = path
            run_cwd = tool_dir
            break
    if not binary:
        binary = shutil.which("dnsx")

    if not binary:
        return "", "dnsx не найден. Соберите: cd tools/dnsx && go build -buildvcs=false -o dnsx ./cmd/dnsx или установите в PATH.", -1

    # dnsx принимает список хостов через stdin. -silent, -a -resp для A/AAAA/CNAME с ответом
    try:
        proc = subprocess.run(
            [binary, "-silent", "-a", "-resp", "-aaaa", "-cname"],
            input=domain + "\n",
            cwd=run_cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
        out = _strip_ansi(proc.stdout or "")
        err = _strip_ansi(proc.stderr or "")
        return out, err, proc.returncode
    except subprocess.TimeoutExpired:
        return "", "Превышено время ожидания ({} сек).".format(timeout_sec), -1
    except Exception as e:
        return "", str(e), -1


class ToolDnsx(ToolBase):
    @property
    def tool_id(self) -> str:
        return "dnsx"

    @property
    def name(self) -> str:
        return "dnsx"

    @property
    def description(self) -> str:
        return "DNS-запросы A, AAAA, CNAME по домену (projectdiscovery)."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        domain = _normalize_domain(params.get("domain") or "")
        if not domain:
            return {"success": False, "error": "Укажите домен (например example.com)."}
        if " " in domain or "." not in domain:
            return {"success": False, "error": "Некорректный домен."}

        timeout = max(15, min(120, int(params.get("timeout", 60) or 60)))
        out, err, code = _run_dnsx(domain, timeout_sec=timeout)
        combined = (out + "\n" + err).strip()
        return {
            "success": code == 0 or bool(out),
            "output": combined or "Записей не найдено или ошибка запуска.",
        }
