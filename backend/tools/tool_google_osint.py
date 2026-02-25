"""
Объединённый инструмент: проверка email через Holehe и h8mail.
Один ввод email — результаты всех проверок в одной панели.
"""
from typing import Any

from .base import ToolBase


class ToolGoogleOsint(ToolBase):
    @property
    def tool_id(self) -> str:
        return "google-osint"

    @property
    def name(self) -> str:
        return "Google OSINT"

    @property
    def description(self) -> str:
        return "Проверка email: регистрации на сайтах (Holehe) и утечки (h8mail). Один ввод — оба отчёта в одной панели."

    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        email = (params.get("email") or "").strip()
        run_holehe = bool(params.get("run_holehe", True))
        run_h8mail = bool(params.get("run_h8mail", True))

        if not email or "@" not in email:
            return {"success": False, "error": "Укажите email."}
        if not run_holehe and not run_h8mail:
            return {"success": False, "error": "Включите хотя бы один инструмент (Holehe или h8mail)."}

        from .tool_holehe import ToolHolehe
        from .tool_h8mail import ToolH8mail

        results = {}

        if run_holehe:
            r = ToolHolehe().run({"email": email, "only_used": True})
            results["holehe"] = {
                "success": r.get("success", False),
                "output": r.get("output") or r.get("error") or "",
            }
        else:
            results["holehe"] = {"success": False, "output": "(пропущен)"}

        if run_h8mail:
            r = ToolH8mail().run({"email": email, "skip_defaults": False})
            results["h8mail"] = {
                "success": r.get("success", False),
                "output": r.get("output") or r.get("error") or "",
            }
        else:
            results["h8mail"] = {"success": False, "output": "(пропущен)"}

        any_ok = any(results[k].get("success") for k in results)
        return {
            "success": any_ok,
            "results": results,
        }
