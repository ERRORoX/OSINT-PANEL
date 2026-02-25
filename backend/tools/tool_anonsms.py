"""
Инструмент ANONSMS: отправка SMS через textbelt API.
Бесплатный ключ "textbelt" — лимит 1 SMS в день. Свой ключ (textbelt.com/create-key) — больше квоты.
"""
from .base import ToolBase
import os
import requests
from datetime import datetime, timezone, timedelta
from typing import Any


def _validate_phone(params: dict) -> str | None:
    """Проверка кода страны и номера. Возвращает None или текст ошибки."""
    cc = (params.get("country_code") or "").strip().lstrip("+")
    if not cc.isdigit() or not (1 <= len(cc) <= 4):
        return "Некорректный код страны (1–4 цифры)"
    pn = (params.get("phone_number") or "").strip().replace(" ", "").replace("-", "")
    if not pn.isdigit() or not (3 <= len(pn) <= 15):
        return "Некорректный номер (3–15 цифр)"
    return None


class ToolAnonsms(ToolBase):
    @property
    def tool_id(self) -> str:
        return "anonsms"

    @property
    def name(self) -> str:
        return "Анонимные SMS"

    @property
    def description(self) -> str:
        return "Отправка SMS через Textbelt без раскрытия номера отправителя."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        err = _validate_phone(params)
        if err:
            return {"success": False, "error": err}
        message = (params.get("message") or "").strip()
        if not message:
            return {"success": False, "error": "Укажите текст сообщения."}

        country_code = "+" + (params.get("country_code") or "").strip().lstrip("+")
        phone_number = (params.get("phone_number") or "").strip().replace(" ", "").replace("-", "")
        phone = country_code + phone_number
        # Свой ключ с textbelt.com/create-key даёт больше SMS; иначе бесплатный лимит (1/день)
        api_key = (params.get("api_key") or "").strip() or os.environ.get("TEXTBELT_API_KEY") or "textbelt"

        try:
            resp = requests.post(
                "https://textbelt.com/text",
                json={"phone": phone, "message": message, "key": api_key},
                timeout=15,
            )
            data = resp.json()
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": data.get("error") or resp.text or f"HTTP {resp.status_code}",
                    "raw": data,
                }
            # Реальный лимит: бесплатный ключ — 1 SMS в 24 часа; платный — по квоте
            quota = data.get("quotaRemaining", 0)
            if quota is not None and quota > 0:
                next_sms_at = None  # можно сразу снова
            else:
                next_sms_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            data["nextSmsAt"] = next_sms_at
            return {"success": True, "response": data}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
