"""
Реестр инструментов. Чтобы добавить новый инструмент:
1. Создать файл backend/tools/tool_<id>.py с классом, наследующим ToolBase.
2. Добавить один импорт и одну строку в TOOLS ниже.
Остальной код не трогать.
"""
from typing import Any

from .base import ToolBase

# Импорты модулей инструментов (по одному на инструмент)
from .tool_anonsms import ToolAnonsms
from .tool_instagram_bruter import ToolInstagramBruter
from .tool_grabcam import ToolGrabcam
from .tool_theharvester import ToolTheharvester
from .tool_google_osint import ToolGoogleOsint
from .tool_domain_search import ToolDomainSearch
from .tool_sherlock import ToolSherlock
from .tool_maigret import ToolMaigret
from .tool_subfinder import ToolSubfinder
from .tool_dnsx import ToolDnsx

# Список всех инструментов (Holehe и h8mail объединены в Google OSINT)
TOOLS: list[ToolBase] = [
    ToolAnonsms(),
    ToolInstagramBruter(),
    ToolGrabcam(),
    ToolGoogleOsint(),
    ToolTheharvester(),
    ToolDomainSearch(),
    ToolSherlock(),
    ToolMaigret(),
    ToolSubfinder(),
    ToolDnsx(),
]


def get_all_tools() -> list[dict]:
    """Список инструментов для API: id, name, description."""
    return [
        {"id": t.tool_id, "name": t.name, "description": t.description}
        for t in TOOLS
    ]


def get_tool(tool_id: str) -> ToolBase | None:
    """Найти инструмент по id."""
    for t in TOOLS:
        if t.tool_id == tool_id:
            return t
    return None


def run_tool(tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Запуск инструмента по id. Возвращает результат (включая success/error)."""
    tool = get_tool(tool_id)
    if not tool:
        return {"success": False, "error": f"Unknown tool: {tool_id}"}
    try:
        return tool.run(params)
    except Exception as e:
        return {"success": False, "error": str(e)}
