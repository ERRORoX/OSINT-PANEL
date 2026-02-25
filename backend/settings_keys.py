"""
Сохранение и чтение API-ключей в .env в корне проекта.
Один модуль — не зависит от инструментов.
"""
import os
from typing import Any

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(_PROJECT_ROOT, ".env")

# Список ключей: id (имя в .env), подпись для формы, текст помощи, ссылка
KEYS_CONFIG = [
    {
        "id": "TEXTBELT_API_KEY",
        "label": "Textbelt (SMS)",
        "helpText": (
            "Как получить ключ Textbelt для отправки SMS:\n\n"
            "1. Перейдите на сайт textbelt.com (ссылка ниже).\n"
            "2. Нажмите «Create key» или откройте раздел покупки ключа.\n"
            "3. Выберите сумму пополнения (квота — это количество SMS; один текст = одна единица).\n"
            "4. Оплатите. После оплаты вам покажут API-ключ (длинная строка символов).\n"
            "5. Скопируйте ключ и вставьте в поле выше, затем нажмите «Сохранить».\n\n"
            "Без ключа используется бесплатный тест — 1 SMS в день. Своим ключом можно отправлять больше сообщений."
        ),
        "helpUrl": "https://textbelt.com/create-key",
    },
    {
        "id": "TH_SHODAN_KEY",
        "label": "theHarvester: Shodan",
        "helpText": "API-ключ Shodan для theHarvester (поиск хостов, портов). Без ключа модуль shodan недоступен.",
        "helpUrl": "https://account.shodan.io/",
    },
    {
        "id": "TH_VIRUSTOTAL_KEY",
        "label": "theHarvester: VirusTotal",
        "helpText": "API-ключ VirusTotal для theHarvester. Без ключа модуль virustotal недоступен.",
        "helpUrl": "https://www.virustotal.com/gui/my-apikey",
    },
    {
        "id": "TH_HUNTER_KEY",
        "label": "theHarvester: Hunter.io",
        "helpText": "API-ключ Hunter.io для theHarvester (поиск email по домену). Без ключа модуль hunter недоступен.",
        "helpUrl": "https://hunter.io/api-keys",
    },
    {
        "id": "TH_SECURITYTRAILS_KEY",
        "label": "theHarvester: SecurityTrails",
        "helpText": "API-ключ SecurityTrails для theHarvester (поддомены, DNS). Без ключа модуль securityTrails недоступен.",
        "helpUrl": "https://securitytrails.com/corp/api",
    },
    {
        "id": "TH_CENSYS_ID",
        "label": "theHarvester: Censys ID",
        "helpText": "Censys API ID для theHarvester (нужен также Censys Secret). Без ключей модуль censys недоступен.",
        "helpUrl": "https://search.censys.io/account/api",
    },
    {
        "id": "TH_CENSYS_SECRET",
        "label": "theHarvester: Censys Secret",
        "helpText": "Censys API Secret (парный к Censys ID). Сохраняется в .env и подставляется в конфиг theHarvester.",
        "helpUrl": "https://search.censys.io/account/api",
    },
    {
        "id": "H8MAIL_HIBP",
        "label": "h8mail: HaveIBeenPwned",
        "helpText": "API-ключ HaveIBeenPwned для h8mail (поиск email в утечках). Без ключа h8mail использует только публичные источники (Hunter public, Scylla — часто недоступны).",
        "helpUrl": "https://haveibeenpwned.com/API/Key",
    },
]


def load_env_into_os() -> None:
    """Загружает .env в os.environ при старте приложения."""
    for k, v in _read_env().items():
        if v and k not in os.environ:
            os.environ[k] = v


def _read_env() -> dict[str, str]:
    """Читает .env и возвращает словарь KEY=value (без кавычек и пробелов)."""
    out = {}
    if not os.path.isfile(_ENV_PATH):
        return out
    with open(_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _write_env(current: dict[str, str]) -> None:
    """Пишет в .env только ключи из KEYS_CONFIG. current — полный словарь ключ→значение."""
    key_ids = {c["id"] for c in KEYS_CONFIG}
    os.makedirs(os.path.dirname(_ENV_PATH) or ".", exist_ok=True)
    with open(_ENV_PATH, "w", encoding="utf-8") as f:
        f.write("# API keys for OSINT Panel (do not commit secrets)\n")
        for c in KEYS_CONFIG:
            kid = c["id"]
            val = current.get(kid, "")
            f.write(f'{kid}={val}\n')
    for k in key_ids:
        os.environ[k] = current.get(k, "")


def get_keys_for_api() -> dict[str, Any]:
    """Для GET /api/settings/keys: конфиг ключей + замаскированные значения (установлен/нет)."""
    env = _read_env()
    keys = []
    for c in KEYS_CONFIG:
        kid = c["id"]
        val = env.get(kid, "")
        masked = "••••••••" + val[-4:] if len(val) > 4 else ("••••" if val else "")
        keys.append({
            **c,
            "value": masked if val else "",
            "isSet": bool(val),
        })
    return {"keys": keys}


def save_keys_from_api(data: dict[str, str]) -> None:
    """Для POST /api/settings/keys: сохраняет переданные ключи в .env."""
    key_ids = {c["id"] for c in KEYS_CONFIG}
    to_save = {k: (v or "").strip() for k, v in (data or {}).items() if k in key_ids}
    if not to_save:
        return
    current = _read_env()
    current.update(to_save)
    _write_env(current)
