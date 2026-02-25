"""
Базовый контракт для всех инструментов.
Каждый инструмент живёт в своём файле и не зависит от других.
"""
from abc import ABC, abstractmethod
from typing import Any


class ToolBase(ABC):
    """Интерфейс одного OSINT-инструмента."""

    @property
    @abstractmethod
    def tool_id(self) -> str:
        """Уникальный id (латиница, без пробелов), например: anonsms."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Название для отображения в панели."""
        pass

    @property
    def description(self) -> str:
        """Краткое описание (по желанию)."""
        return ""

    @abstractmethod
    def run(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Запуск инструмента. Параметры и результат — словари (JSON-совместимые).
        Не бросать исключения наружу — возвращать {"success": False, "error": "..."}.
        """
        pass
