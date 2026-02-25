"""
Инструмент «Поиск по домену» — использует модуль modules/domain_search.py.
WHOIS, DNS, SSL, crt.sh без внешнего UI (Flet не используется).
"""
import os
import sys
from typing import Any

from .base import ToolBase

# Корень проекта (родитель backend/) для импорта modules
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


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


class ToolDomainSearch(ToolBase):
    @property
    def tool_id(self) -> str:
        return "domain-search"

    @property
    def name(self) -> str:
        return "Поиск по домену"

    @property
    def description(self) -> str:
        return "Информация по домену: WHOIS, DNS, SSL-сертификат, поддомены (crt.sh)."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        domain_raw = (params.get("domain") or "").strip()
        domain = _normalize_domain(domain_raw)
        if not domain:
            return {"success": False, "error": "Укажите домен (например example.com)."}
        if " " in domain:
            return {"success": False, "error": "Некорректный домен."}
        if "." not in domain:
            return {"success": False, "error": "Введите домен с точкой (example.com)."}

        try:
            from modules.domain_search import run_domain_search
            result = run_domain_search(domain)
        except ImportError as e:
            return {"success": False, "error": "Модуль domain_search не найден: " + str(e)[:100]}
        except Exception as e:
            return {"success": False, "error": str(e)[:300]}

        if not result.get("success"):
            return {"success": False, "error": result.get("error", "Ошибка модуля"), "output": result.get("output", "")}
        return {"success": True, "output": result.get("output", "")}
