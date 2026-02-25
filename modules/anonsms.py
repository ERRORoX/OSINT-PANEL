"""
Анонимная отправка СМС через Textbelt API.
Совместимо с логикой скрипта из папки ANONSMS (DarkSms).
Используется только в законных целях; ответственность на пользователе.
"""
import re
import requests
from typing import Tuple, Optional

TEXTBELT_URL = "https://textbelt.com/text"
TIMEOUT = 15


def normalize_phone(country_code: str, number: str) -> str:
    """Собирает номер в формате E.164: +код_страны номер."""
    cc = (country_code or "").strip().lstrip("+")
    num = re.sub(r"\D", "", number or "")
    if not cc or not num:
        return ""
    if not cc.isdigit() or len(cc) > 4:
        return ""
    if len(num) < 3 or len(num) > 15:
        return ""
    return "+" + cc + num


def send_anon_sms(phone_e164: str, message: str) -> Tuple[bool, str, Optional[dict]]:
    """
    Отправка одной СМС через Textbelt (как в ANONSMS/DarkSms).
    phone_e164: номер в формате +79001234567
    message: текст сообщения
    Возвращает (success, human_message, raw_response_dict).
    """
    if not phone_e164 or not message or not message.strip():
        return False, "Укажите номер и текст сообщения.", None
    if len(message.strip()) > 1600:
        return False, "Сообщение слишком длинное (Textbelt ограничение).", None
    try:
        r = requests.post(
            TEXTBELT_URL,
            data={
                "phone": phone_e164,
                "message": message.strip(),
                "key": "textbelt",
            },
            timeout=TIMEOUT,
        )
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code == 200 and data.get("success") is True:
            return True, "СМС отправлено успешно.", data
        err = data.get("error") or data.get("message") or r.text or "Неизвестная ошибка"
        return False, str(err)[:300], data
    except requests.RequestException as e:
        return False, "Ошибка сети: {}".format(str(e)[:150]), None
    except Exception as e:
        return False, "Ошибка: {}".format(str(e)[:150]), None


def get_anonsms_path() -> Optional[str]:
    """Путь к папке ANONSMS рядом с проектом (для отображения в UI)."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "ANONSMS")
    if os.path.isdir(path):
        return path
    return None
