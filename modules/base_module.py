"""
Базовый класс для всех OSINT модулей.
Каждый модуль должен наследоваться от этого класса.
"""
import flet as ft
from abc import ABC, abstractmethod
from typing import Optional


class BaseOSINTModule(ABC):
    """Базовый класс для всех OSINT модулей"""
    
    def __init__(self, name: str, description: str = ""):
        """
        Инициализация модуля
        
        Args:
            name: Название модуля
            description: Описание модуля
        """
        self.name = name
        self.description = description
        self.enabled = True
    
    @abstractmethod
    def validate_input(self, input_data: str) -> tuple[bool, Optional[str]]:
        """
        Валидация входных данных
        
        Args:
            input_data: Входные данные для проверки
            
        Returns:
            tuple: (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def search(self, input_data: str) -> ft.Control:
        """
        Основной метод поиска
        
        Args:
            input_data: Входные данные для поиска
            
        Returns:
            ft.Control: Результат поиска в виде Flet компонента
        """
        pass
    
    def create_error_message(self, message: str) -> ft.Text:
        """
        Создание сообщения об ошибке (текст можно выделять и копировать).
        """
        return ft.Text(message, color=ft.Colors.RED, size=16, selectable=True)
    
    def create_title(self, title: str) -> ft.Text:
        """
        Создание заголовка (текст можно выделять и копировать).
        """
        return ft.Text(title, size=20, weight=ft.FontWeight.BOLD, selectable=True)
    
    def create_section_title(self, title: str) -> ft.Text:
        """
        Создание заголовка секции (текст можно выделять и копировать).
        """
        return ft.Text(title, size=16, weight=ft.FontWeight.BOLD, selectable=True)
    
    def selectable_text(self, text: str, size: int = 14, **kwargs) -> ft.Text:
        """
        Текст, который можно выделить и скопировать (любая строка в результатах).
        """
        return ft.Text(text, size=size, selectable=True, **kwargs)
    
    def create_result_container(self, controls: list) -> ft.Column:
        """
        Создание контейнера с результатами
        
        Args:
            controls: Список компонентов
            
        Returns:
            ft.Column: Колонка с результатами
        """
        return ft.Column(controls=controls, spacing=10, scroll=ft.ScrollMode.AUTO)
    
    def create_loading_message(self, message: str = "Выполняется проверка...") -> ft.Row:
        """
        Создание сообщения о загрузке
        
        Args:
            message: Текст сообщения
            
        Returns:
            ft.Row: Компонент с сообщением о загрузке
        """
        return ft.Row(
            controls=[
                ft.ProgressRing(width=20, height=20),
                ft.Text(message, size=14, color=ft.Colors.GREY_400)
            ],
            spacing=10
        )
    
    def create_success_message(self, message: str) -> ft.Text:
        """
        Создание сообщения об успехе
        
        Args:
            message: Текст сообщения
            
        Returns:
            ft.Text: Компонент с сообщением об успехе
        """
        return ft.Text(f"✅ {message}", size=14, color=ft.Colors.GREEN, weight=ft.FontWeight.BOLD)
    
    def create_warning_message(self, message: str) -> ft.Text:
        """
        Создание предупреждающего сообщения
        
        Args:
            message: Текст сообщения
            
        Returns:
            ft.Text: Компонент с предупреждением
        """
        return ft.Text(f"⚠️ {message}", size=14, color=ft.Colors.ORANGE_400, weight=ft.FontWeight.BOLD)
    
    def enable(self):
        """Включить модуль"""
        self.enabled = True
    
    def disable(self):
        """Отключить модуль"""
        self.enabled = False
    
    def is_enabled(self) -> bool:
        """Проверить, включен ли модуль"""
        return self.enabled
