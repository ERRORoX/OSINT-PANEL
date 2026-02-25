"""
Инструмент theHarvester: сбор email, поддоменов и имён по домену.
API-ключи берутся из настроек панели (вкладка «API ключи») и подставляются в ~/.theHarvester/api-keys.yaml.
"""
import os
import re
import shutil
import subprocess
import sys
from typing import Any

from .base import ToolBase

_ANSI_ESCAPE = re.compile(r"\x1b\[[?0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _normalize_domain(domain: str) -> str:
    """Убирает протокол, www, путь. Оставляет только домен (example.com)."""
    s = (domain or "").strip().lower()
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
            break
    if "/" in s:
        s = s.split("/")[0]
    if "?" in s:
        s = s.split("?")[0]
    if s.startswith("www."):
        s = s[4:]
    return s


def _is_valid_domain(domain: str) -> bool:
    """Проверка: домен не пустой, без пробелов, есть точка, допустимые символы."""
    if not domain or " " in domain:
        return False
    if "." not in domain:
        return False
    import re
    return bool(re.match(r"^[a-z0-9][a-z0-9.-]*\.[a-z0-9.-]+$", domain))


def _write_theharvester_apikeys() -> None:
    """Пишет api-keys.yaml для theHarvester из переменных окружения (ключи из панели «API ключи»)."""
    try:
        import yaml
    except ImportError:
        return
    env = os.environ
    apikeys = {
        "shodan": {"key": (env.get("TH_SHODAN_KEY") or "").strip() or None},
        "virustotal": {"key": (env.get("TH_VIRUSTOTAL_KEY") or "").strip() or None},
        "hunter": {"key": (env.get("TH_HUNTER_KEY") or "").strip() or None},
        "securityTrails": {"key": (env.get("TH_SECURITYTRAILS_KEY") or "").strip() or None},
        "censys": {
            "id": (env.get("TH_CENSYS_ID") or "").strip() or None,
            "secret": (env.get("TH_CENSYS_SECRET") or "").strip() or None,
        },
        "bevigil": {"key": None},
        "bitbucket": {"key": None},
        "brave": {"key": None},
        "bufferoverun": {"key": None},
        "builtwith": {"key": None},
        "criminalip": {"key": None},
        "dehashed": {"key": None},
        "dnsdumpster": {"key": None},
        "fofa": {"key": None, "email": None},
        "fullhunt": {"key": None},
        "github": {"key": None},
        "hackertarget": {"key": None},
        "haveibeenpwned": {"key": None},
        "hunterhow": {"key": None},
        "intelx": {"key": None},
        "leakix": {"key": None},
        "leaklookup": {"key": None},
        "netlas": {"key": None},
        "onyphe": {"key": None},
        "pentestTools": {"key": None},
        "projectDiscovery": {"key": None},
        "rocketreach": {"key": None},
        "securityscorecard": {"key": None},
        "tomba": {"key": None, "secret": None},
        "venacus": {"key": None},
        "whoisxml": {"key": None},
        "windvane": {"key": None},
        "zoomeye": {"key": None},
    }
    for k, v in list(apikeys.items()):
        if isinstance(v, dict):
            apikeys[k] = {kk: (val if val is not None else "") for kk, val in v.items()}
    config_dir = os.path.expanduser("~/.theHarvester")
    os.makedirs(config_dir, exist_ok=True)
    path = os.path.join(config_dir, "api-keys.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump({"apikeys": apikeys}, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _run_cmd(args: list[str], timeout_sec: int = 120) -> tuple[str, str, int]:
    try:
        proc = subprocess.run(
            args,
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
    except FileNotFoundError:
        return "", "Команда не найдена. Установите: pip install theHarvester", -1
    except Exception as e:
        return "", str(e), -1


class ToolTheharvester(ToolBase):
    @property
    def tool_id(self) -> str:
        return "theharvester"

    @property
    def name(self) -> str:
        return "theHarvester"

    @property
    def description(self) -> str:
        return "Сбор email, поддоменов и имён по домену. Источники: Google, Bing, DuckDuckGo, Shodan и др. (для части источников нужны API-ключи)."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        domain = _normalize_domain(params.get("domain") or "")
        if not domain:
            return {"success": False, "error": "Укажите домен (например example.com)."}
        if not _is_valid_domain(domain):
            return {"success": False, "error": "Некорректный домен. Введите только домен: example.com (без http:// и пути)."}
        limit = min(max(int(params.get("limit", 100) or 100), 10), 500)

        # Несколько источников: запуск по очереди и объединение вывода
        sources_raw = params.get("sources")
        if isinstance(sources_raw, list) and sources_raw:
            sources = [str(s).strip().lower() for s in sources_raw if str(s).strip()]
        else:
            sources = [(params.get("source") or "duckduckgo").strip().lower() or "duckduckgo"]
        if not sources:
            sources = ["duckduckgo"]

        _write_theharvester_apikeys()

        cmd_build = None
        for name in ("theHarvester", "theharvester"):
            if shutil.which(name):
                cmd_build = [name]
                break
        if not cmd_build:
            try:
                import theHarvester
                cmd_build = [sys.executable, "-m", "theHarvester"]
            except ImportError:
                try:
                    import theharvester
                    cmd_build = [sys.executable, "-m", "theharvester"]
                except ImportError:
                    return {"success": False, "error": "theHarvester не найден. Установите: pip install theHarvester"}

        parts = []
        any_ok = False
        for src in sources:
            cmd = cmd_build + ["-d", domain, "-b", src, "-l", str(limit)]
            out, err, code = _run_cmd(cmd, timeout_sec=120)
            combined = (out + "\n" + err).strip()
            parts.append("========== Источник: {} ==========\n{}".format(src, combined or "(нет данных)"))
            if code == 0:
                any_ok = True
        full_output = "\n\n".join(parts)
        return {
            "success": any_ok,
            "output": full_output or "(пустой вывод)",
            "returncode": 0 if any_ok else -1,
        }
